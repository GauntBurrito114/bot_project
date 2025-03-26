import discord
from discord import app_commands
from discord import ui
import asyncio
import os
from dotenv import load_dotenv
import datetime
import schedule
import re
import io
from collections import defaultdict

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
DEBUG_CHANNEL_ID = int(os.getenv("DEBUG_CHANNEL_ID"))
ATTENDANCE_CONFIRMATION_CHANNEL_ID = int(os.getenv("ATTENDANCE_CONFIRMATION_CHANNEL_ID"))
ATTENDANCE_RECORD_CHANNEL_ID = int(os.getenv("ATTENDANCE_RECORD_CHANNEL_ID"))
ATTENDANCE_ROLE_ID = int(os.getenv("ATTENDANCE_ROLE_ID"))
ATTENDANCE_MESSAGE_ID = int(os.getenv("ATTENDANCE_MESSAGE_ID"))
TARGET_USER_ID = int(os.getenv("TARGET_USER_ID"))
FORTNITE_ROLE_ID = int(os.getenv("FORTNITE_ROLE_ID"))
TOURNAMENT_ROLE_ID = int(os.getenv("TOURNAMENT_ROLE_ID"))
ENJOY_ROLE_ID = int(os.getenv("ENJOY_ROLE_ID"))
CREATOR_ROLE_ID = int(os.getenv("CREATOR_ROLE_ID"))

# 部門ロールのIDと名前の対応
DEPARTMENT_ROLES = {
    "フォートナイト部門": FORTNITE_ROLE_ID,
    "大会部門": TOURNAMENT_ROLE_ID,
    "エンジョイ部門": ENJOY_ROLE_ID,
    "クリエイター部門": CREATOR_ROLE_ID,
}

# メンバーキャッシュ
member_cache = {}
# 参加記録を保存する辞書 (ユーザーID: {累計参加回数: int, 週ごとの参加回数: {週の開始日: int}})
attendance_history = defaultdict(lambda: {"total": 0, "weekly": defaultdict(int)})
# データベースのファイル名
DATABASE_FILE = "attendance_history.db"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
periodic_message_task = None

# botの起動時の処理
@client.event
async def on_ready():
    print(f'{client.user} が起動しました')
    for guild in client.guilds:
        if guild.system_channel:
            try:
                await guild.system_channel.send('Botが起動しました！')
            except discord.Forbidden:
                print(f"Error: サーバー {guild.name} のシステムメッセージチャンネルへの送信権限がありません。")
        else:
            print(f"Error: サーバー {guild.name} にシステムメッセージチャンネルが設定されていません。")

    # 出席確認メッセージにリアクションをつける
    channel = client.get_channel(ATTENDANCE_CONFIRMATION_CHANNEL_ID)
    try:
        message = await channel.fetch_message(ATTENDANCE_MESSAGE_ID)
        await message.add_reaction('✅')
    except discord.NotFound:
        print("Error: 出席確認メッセージが見つかりませんでした。")

    # 定期的なメッセージ送信タスクを開始
    user = await client.fetch_user(TARGET_USER_ID)
    if user:
        global periodic_message_task
        periodic_message_task = asyncio.create_task(send_periodic_message(user))

    # コマンドの登録
    await tree.sync()

    # 出席ロール剥奪処理のスケジューリング
    schedule.every().day.at("00:08").do(lambda: asyncio.create_task(remove_attendance_role(client)))
    asyncio.create_task(scheduler())



# スケジューリング処理
async def scheduler():
    while True:
        schedule.run_pending()
        await asyncio.sleep(60)

# 定期的なメッセージの送信を非同期関数として定義
async def send_periodic_message(user):
    global periodic_message_task
    while True:
        try:
            await user.send('定期的なメッセージです。')
            print(f'{user.name} にメッセージを送信しました')
        except Exception as e:
            print(f"Error: {user.name} にメッセージを送信する際にエラーが発生しました。")
        await asyncio.sleep(600)

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
    if periodic_message_task:
        periodic_message_task.cancel()
    await client.close()
    print('botを停止しました')
    os._exit(0)

@tree.command(name="remove_role", description="出席ロールを剥奪します")
async def remove_role_command(interaction: discord.Interaction):
    if interaction.channel_id != DEBUG_CHANNEL_ID:
        await interaction.response.send_message('このコマンドはこのチャンネルでは実行できません。')
        return
    attendance_role = interaction.guild.get_role(ATTENDANCE_ROLE_ID)
    await remove_attendance_role_from_guild(interaction.guild, attendance_role)
    await interaction.response.send_message('出席ロールを剥奪しました。')

@tree.command(name="members", description="サーバーのメンバーリストを表示します")
async def members_command(interaction: discord.Interaction):
    if interaction.channel_id != DEBUG_CHANNEL_ID:
        await interaction.response.send_message('このコマンドはこのチャンネルでは実行できません。')
        return
    global member_cache
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

# 部門ロールのIDと名前の対応
DEPARTMENT_ROLES = {
    "フォートナイト部門": FORTNITE_ROLE_ID,
    "大会部門": TOURNAMENT_ROLE_ID,
    "エンジョイ部門": ENJOY_ROLE_ID,
    "クリエイター部門": CREATOR_ROLE_ID,
}

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
            async def text_output_callback(interaction):
                await send_attendance_list_as_text_file(interaction, user_names, target_date.strftime(date_format), department)
            text_output_button.callback = text_output_button
            view.add_item(text_output_button)

            await interaction.response.send_message(embed=embed, view=view)
        else:
            embed.description = "指定された部門の出席者はいませんでした。"
            await interaction.response.send_message(embed=embed)
    else:
        embed.description = "出席者はいませんでした。"
        await interaction.response.send_message(embed=embed)

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
    if payload.message_id == ATTENDANCE_MESSAGE_ID and payload.emoji.name == '✅':
        guild = client.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        channel = client.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        if member and not member.bot:
            attendance_record_channel = client.get_channel(ATTENDANCE_RECORD_CHANNEL_ID)
            attendance_role = guild.get_role(ATTENDANCE_ROLE_ID)
            now = datetime.datetime.now()

            if attendance_role in member.roles:
                await message.remove_reaction(payload.emoji, member)
                return

            await attendance_record_channel.send(f'{member.mention} が **{now.strftime("%Y年 %m月 %d日 %H:%M")}** に出席しました。')
            await member.add_roles(attendance_role)

            # 参加記録を更新
            update_attendance_history(member.id, now)


            try:
                await message.remove_reaction(payload.emoji, member)
            except discord.Forbidden:
                print(f"Error: {member.name} のリアクションを削除する権限がありません。")

# 参加記録を更新する関数
def update_attendance_history(user_id, attendance_time):
    global attendance_history
    attendance_history[user_id]["total"] += 1
    week_start = attendance_time - datetime.timedelta(days=attendance_time.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    attendance_history[user_id]["weekly"][week_start] += 1

# ロール剥奪関数の定義
async def remove_attendance_role_from_guild(guild, attendance_role):
    global member_cache
    if guild.id not in member_cache:
        members = []
        async for member in guild.fetch_members(limit=None):
            members.append(member)
        member_cache[guild.id] = members
    else:
        members = member_cache[guild.id]

    if attendance_role:
        for member in members:
            if attendance_role in member.roles:
                try:
                    await member.remove_roles(attendance_role)
                    print(f"{member.name} から出席ロールを剥奪しました。")
                except discord.Forbidden:
                    print(f"Error: {member.name} から出席ロールを剥奪する権限がありません。")

# 毎日0時に出席ロールを剥奪
async def remove_attendance_role(client):
    guild = client.guilds[0]
    attendance_role = guild.get_role(ATTENDANCE_ROLE_ID)

    await remove_attendance_role_from_guild(guild, attendance_role)
    channel = client.get_channel(DEBUG_CHANNEL_ID)
    await channel.send('出席ロールを全員からはく奪しました。')

# サーバーに新しいメンバーが入った時
@client.event
async def on_member_join(member):
    global member_cache
    if member.guild.id in member_cache:
        member_cache[member.guild.id].append(member)

# サーバーからメンバーが脱退したとき
@client.event
async def on_member_remove(member):
    global member_cache
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

# 参加履歴を表示するコマンド
@tree.command(name="attendance_history", description="参加者の累計参加回数を表示します(開発中)")
@app_commands.describe(user="参加履歴を表示するユーザー") # 追加
async def attendance_history_command(interaction: discord.Interaction, user: discord.Member):
    """
    参加者の累計と週ごとの参加回数を表示するコマンド
    """
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


# botの起動
if TOKEN is None:
    print("Error: DISCORD_TOKEN を取得出来ませんでした。")
else:
    client.run(TOKEN)
