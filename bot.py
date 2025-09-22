import discord
from discord import app_commands
from discord.ext import tasks, commands
import asyncio
import os
from dotenv import load_dotenv
import datetime
import re
import io
from collections import defaultdict
import web_server
import logging
import keep_alive
from flask import Flask
import schedule

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
DEBUG_CHANNEL_ID = int(os.getenv("debug_channel_id"))
ATTENDANCE_CONFIRMATION_CHANNEL_ID = int(os.getenv("attendance_confirmation_channel_id"))
ATTENDANCE_RECORD_CHANNEL_ID = int(os.getenv("attendance_record_channel_id"))
ATTENDANCE_ROLE_ID = int(os.getenv("attendance_role_id"))
ATTENDANCE_MESSAGE_ID = int(os.getenv("attendance_message_id"))
FORTNITE_ROLE_ID = int(os.getenv("FORTNITE_ROLE_ID"))
TOURNAMENT_ROLE_ID = int(os.getenv("TOURNAMENT_ROLE_ID"))
ENJOY_ROLE_ID = int(os.getenv("ENJOY_ROLE_ID"))
CREATOR_ROLE_ID = int(os.getenv("CREATOR_ROLE_ID"))
guild_id = int(os.getenv("guild_id"))

# 部門ロールのIDと名前の対応
DEPARTMENT_ROLES = {
    "フォートナイト部門": FORTNITE_ROLE_ID,
    "大会部門": TOURNAMENT_ROLE_ID,
    "エンジョイ部門": ENJOY_ROLE_ID,
    "クリエイター部門": CREATOR_ROLE_ID,
}

# メンバーキャッシュ
member_cache = {}

# 出席履歴のキャッシュ
attendance_history = defaultdict(lambda: {"total": 0, "weekly": defaultdict(int)})
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
app = Flask(__name__)

# ログの設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# botの起動時の処理
@client.event
async def on_ready():
    logging.info(f'{client.user} が起動しました')

    web_server.start_web_server()
    if os.getenv("RENDER_EXTERNAL_URL"):
        asyncio.create_task(keep_alive.start_keep_alive())
    else:
        logging.warning("RENDER_EXTERNAL_URL が設定されていないため keep_alive をスキップします。")

    channel = client.get_channel(ATTENDANCE_CONFIRMATION_CHANNEL_ID)
    if not hasattr(client, "reaction_added"):
        try:
            message = await channel.fetch_message(ATTENDANCE_MESSAGE_ID)
            await message.add_reaction('✅')
            client.reaction_added = True
        except discord.NotFound:
            logging.info("出席確認メッセージが見つかりませんでした。")
    for reaction in message.reactions:
            if reaction.emoji == '✅':
                async for user in reaction.users():
                    member = message.guild.get_member(user.id)
                    await handle_attendance_reaction(message.guild, member, message, reaction.emoji)
    try:
        synced = await tree.sync()
        logging.info(f"Synced {len(synced)} command(s).")
    except Exception as e:
        logging.error(f"コマンドの同期中にエラーが発生しました: {e}")

    schedule.every().day.at("00:00").do(lambda: asyncio.create_task(call_remove_attendance_roles(client)))
    asyncio.create_task(midnight_task_loop())

async def midnight_task_loop():
    tz_jst = datetime.timezone(datetime.timedelta(hours=9))
    while True:
        now = datetime.datetime.now(tz_jst)
        # 翌日のJST 0:00
        next_midnight = (now + datetime.timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        wait_seconds = (next_midnight - now).total_seconds()
        logging.info(f"次回ロール剥奪まで待機: {wait_seconds} 秒")
        await asyncio.sleep(wait_seconds)

        try:
            await call_remove_attendance_roles()
        except Exception as e:
            logging.error(f"ロールのはく奪中にエラーが発生しました: {e}")

# メッセージ受信時の処理
@client.event
async def on_message(message):
    if message.author.bot:
        return

# コマンドの定義
@tree.command(name="test", description="テストコマンドです")
async def test_command(interaction: discord.Interaction):
    await interaction.response.send_message("テストメッセージです")

@tree.command(name="stop", description="botを停止します")
async def stop_command(interaction: discord.Interaction):
    if interaction.channel_id != DEBUG_CHANNEL_ID:
        await interaction.response.send_message('このコマンドはこのチャンネルでは実行できません。')
        return
    await interaction.response.send_message("botを停止します")
    await client.close()
    logging.info('botを停止しました')
    os._exit(0)

@tree.command(name="members", description="サーバーのメンバーリストを表示します")
async def members_command(interaction: discord.Interaction):
    if interaction.channel_id != DEBUG_CHANNEL_ID:
        await interaction.response.send_message('このコマンドはこのチャンネルでは実行できません。')
        return
    guild = interaction.guild
    if guild.id not in member_cache:
        members = []
        async for member in guild.fetch_members(limit=None):
            members.append(member)
        member_cache[guild.id] = members
    else:
        members = member_cache[guild.id]

    member_list = "\n".join([member.name for member in members])
    await interaction.response.send_message(f"サーバーのメンバーリスト:\n{member_list}")

# 出席者リストを表示するコマンド
@tree.command(name="attendance_list", description="指定された日の出席者リストを表示します")
async def attendance_list_command(
    interaction: discord.Interaction,
    date: str,
    department: str = None,
):
    try:
        # 入力された日付をdatetimeオブジェクトに変換
        target_date = datetime.datetime.strptime(date, "%Y/%m/%d")
        start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        date_format = "%Y年%m月%d日"
    except ValueError:
        try:
            target_date = datetime.datetime.strptime(date, "%Y/%m")
            start_date = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = (target_date.replace(month=target_date.month % 12 + 1, day=1) - datetime.timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
            date_format = "%Y年%m月"
        except ValueError:
            await interaction.response.send_message("日付の形式が正しくありません。YYYY/MM/DD またはYYYY/MM の形式で入力してください。")
            return

    channel = client.get_channel(ATTENDANCE_RECORD_CHANNEL_ID)
    messages = await get_attendance_messages(channel, start_date, end_date)
    user_ids = extract_user_ids(messages)

    title = f"**{target_date.strftime(date_format)}** の出席者リスト"
    if department:
        title += f" ({department})"
    embed = discord.Embed(title=title, color=0x00ff00)

    if user_ids:
        user_names = []
        filtered_user_ids = []
        for user_id in set(user_ids):
            user = interaction.guild.get_member(user_id)
            if user:
                if department:
                    department_role_id = DEPARTMENT_ROLES[department]
                    department_role = interaction.guild.get_role(department_role_id)
                    if department_role and department_role in user.roles:
                        user_names.append(user.display_name)
                        filtered_user_ids.append(user_id)
                else:
                    user_names.append(user.display_name)
                    filtered_user_ids.append(user_id)
            else:
                user_names.append(f"ユーザーID: {user_id}")

        if filtered_user_ids:
            attendees = "\n".join([f"<@{user_id}>" for user_id in set(filtered_user_ids)])
            embed.add_field(name="出席者", value=attendees, inline=False)

            view = discord.ui.View()
            text_output_button = discord.ui.Button(label="テキストで出力", style=discord.ButtonStyle.primary)

            #修正：callbackをButtonに直接代入するのではなく、関数を定義してbuttonに明示的に登録
            async def text_output_callback(interaction_inner):
                await send_attendance_list_as_text_file(interaction_inner, user_names, target_date.strftime(date_format), department)

            text_output_button.callback = text_output_callback  #関数を登録

            view.add_item(text_output_button)

            await interaction.response.send_message(embed=embed, view=view)
        else:
            embed.description = "指定された部門の出席者はいませんでした。"
            await interaction.response.send_message(embed=embed)
    else:
        embed.description = "出席者はいませんでした。"
        await interaction.response.send_message(embed=embed)

@tree.command(name="remove_role",description="出席ロールをサーバー全員から剥奪します")
async def remove_role_command(interaction: discord.Interaction):
    if interaction.channel_id != DEBUG_CHANNEL_ID:
        await interaction.response.send_message('このコマンドはこのチャンネルでは実行できません。', ephemeral=True)
        return

    await interaction.response.send_message("出席ロールの剥奪を開始します…")
    try:
        await call_remove_attendance_roles()
        await interaction.followup.send("出席ロールの剥奪が完了しました。")
    except Exception as e:
        logging.error(f"/remove_role 実行中に例外発生: {e}")
        await interaction.followup.send("エラーが発生しました。ログを確認してください。")

# 選択肢の定義
@attendance_list_command.autocomplete("department")
async def department_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=name, value=name)
        for name in DEPARTMENT_ROLES
        if current.lower() in name.lower()
    ]

# 出席管理システム
@client.event
async def on_raw_reaction_add(payload):
    if payload.message_id == ATTENDANCE_MESSAGE_ID:
        guild = client.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        channel = client.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        await handle_attendance_reaction(guild, member, message, payload.emoji.name)

# 参加記録を更新する関数
def update_attendance_history(user_id, attendance_time):
    attendance_history[user_id]["total"] += 1
    week_start = attendance_time - datetime.timedelta(days=attendance_time.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    attendance_history[user_id]["weekly"][week_start] += 1

# サーバーに新しいメンバーが入った時
@client.event
async def on_member_join(member):
    if member.guild.id in member_cache:
        member_cache[member.guild.id].append(member)

# サーバーからメンバーが脱退したとき
@client.event
async def on_member_remove(member):
    if member.guild.id in member_cache:
        member_cache[member.guild.id] = [m for m in member_cache[member.guild.id] if m.id != member.id]

# 指定された期間のメッセージを取得する関数
async def get_attendance_messages(channel, start_date, end_date):
    messages = []
    async for message in channel.history(limit=None, after=start_date, before=end_date):
        messages.append(message)
    return messages

# メッセージから出席者のユーザーIDを抽出する関数
def extract_user_ids(messages):
    user_ids = []
    for message in messages:
        match = re.search(r'<@!?(\d+)>', message.content)
        if match:
            user_ids.append(int(match.group(1)))
    return user_ids

# 出席者リストをテキストファイルとして送信する関数
async def send_attendance_list_as_text_file(interaction, user_names, date_str, department=None):
    """出席者リストをテキストファイルとして送信する関数"""
    if not user_names:
        await interaction.response.send_message("出席者はいませんでした。")
        return

    text_content = "\n".join(user_names)
    filename = f"attendance_list_{date_str.replace('/', '-')}"
    if department:
        filename += f"_{department}"
    filename += ".txt"
    text_file = io.StringIO(text_content)

    await interaction.response.send_message(
        file=discord.File(text_file, filename=filename)
    )

# ロールはく奪関数
async def call_remove_attendance_roles():
    guild = client.get_guild(guild_id)
    if guild is None:
        logging.error(f"Guild {guild_id} が見つかりません")
        return

    role = guild.get_role(ATTENDANCE_ROLE_ID)
    if role is None:
        logging.error(f"Role {ATTENDANCE_ROLE_ID} が見つかりません")
        return

    removed_count = 0
    for member in guild.members:
        if role in member.roles and not member.bot:
            try:
                await member.remove_roles(role)
                removed_count += 1
                await asyncio.sleep(5)  # 5秒間隔で処理
            except Exception as e:
                logging.error(f"{member} からロール剥奪中にエラー: {e}")
    logging.info(f"出席ロールを剥奪しました。対象メンバー数: {removed_count}")

# 参加履歴を表示するコマンド
@tree.command(name="attendance_history", description="参加者の累計参加回数を表示します(開発中)")
@app_commands.describe(user="参加履歴を表示するユーザー") # 追加
async def attendance_history_command(interaction: discord.Interaction, user: discord.Member):
    
    channel = client.get_channel(ATTENDANCE_RECORD_CHANNEL_ID)
    # エラーの原因となる可能性のある datetime.datetime.min を、より具体的な過去の日付に置き換える
    start_date = datetime.datetime(2020, 1, 1)  # 例: 2020年1月1日
    end_date = datetime.datetime.now()
    messages = await get_attendance_messages(channel, start_date, end_date)
    user_ids = extract_user_ids(messages)

    # ユーザーIDごとの出席回数をカウント
    user_attendance_count = defaultdict(int)
    for user_id in user_ids:
        user_attendance_count[user_id] += 1

    target_user_id = user.id
    total_count = user_attendance_count.get(target_user_id, 0)

    embed = discord.Embed(title=f"{user.display_name} の参加記録", color=0x00ff00)
    embed.add_field(name="累計参加回数", value=str(total_count), inline=False)

    await interaction.response.send_message(embed=embed)

# 出席確認メッセージのリアクション処理
async def handle_attendance_reaction(guild, member, message, emoji):
    if emoji != '✅':
        return
    if member is None or member.bot:
        return

    attendance_record_channel = guild.get_channel(ATTENDANCE_RECORD_CHANNEL_ID)
    attendance_role = guild.get_role(ATTENDANCE_ROLE_ID)
    now = datetime.datetime.now()

    if attendance_role in member.roles:
        return

    await attendance_record_channel.send(
        f'{member.mention} が **{now.strftime("%Y年 %m月 %d日 %H:%M")}** に出席しました。'
    )
    await member.add_roles(attendance_role)

    try:
        await message.remove_reaction(emoji, member)
    except discord.Forbidden:
        logging.error(f"Error: {member.name} のリアクションを削除する権限がありません。")

# botの起動
if TOKEN is None:
    logging.error("Error: DISCORD_TOKEN を取得出来ませんでした。")
else:
    client.run(TOKEN)