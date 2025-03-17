#いっぱいコメントあるのは初心者だから許してね

#ライブラリのインポート
import discord
from discord import app_commands
import asyncio
import os
from dotenv import load_dotenv
import datetime
import schedule
import re
load_dotenv()

#discord botトークン
TOKEN = os.getenv("DISCORD_TOKEN")
#デバックチャンネルID
DEBUG_CHANNEL_ID = int(os.getenv("debug_channel_id"))
#出席確認チャンネルID
ATTENDANCE_CONFIRMATION_CHANNEL_ID = int(os.getenv("attendance_confirmation_channel_id"))
#出席記録チャンネルID
ATTENDANCE_RECORD_CHANNEL_ID = int(os.getenv("attendance_record_channel_id"))
#出席ロールID
ATTENDANCE_ROLE_ID = int(os.getenv("attendance_role_id"))
#出席確認メッセージID
ATTENDANCE_MESSAGE_ID = int(os.getenv("attendance_message_id"))
#定期的にメッセージを送信するユーザーID
TARGET_USER_ID = int(os.getenv("target_user_id"))
#メンバーキャッシュ
member_cache = {}

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.dm_messages = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
periodic_message_task = None

#botの起動時の処理
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

    #出席確認メッセージにリアクションをつける
    channel = client.get_channel(ATTENDANCE_CONFIRMATION_CHANNEL_ID)
    try:
        message = await channel.fetch_message(ATTENDANCE_MESSAGE_ID)
        await message.add_reaction('✅')
    except discord.NotFound:
        print("Error: 出席確認メッセージが見つかりませんでした。")
    
    #定期的なメッセージ送信タスクを開始
    user = await client.fetch_user(TARGET_USER_ID)
    if user:
            global periodic_message_task
            periodic_message_task = asyncio.create_task(send_periodic_message(user))

    #コマンドの登録
    await tree.sync()
    
    #出席ロール剥奪処理のスケジューリング
    schedule.every().day.at("00:08").do(lambda: asyncio.create_task(remove_attendance_role(client)))
    asyncio.create_task(scheduler())

#スケジューリング処理
async def scheduler():
    while True:
        schedule.run_pending()
        await asyncio.sleep(60)

#定期的なメッセージの送信を非同期関数として定義
async def send_periodic_message(user):
    global periodic_message_task
    while True:
        try:
            await user.send('定期的なメッセージです。')
            print(f'{user.name} にメッセージを送信しました')
        except Exception as e:
            print(f"Error: {user.name} にメッセージを送信する際にエラーが発生しました。")
        await asyncio.sleep(600)

#メッセージ受信時の処理
@client.event
async def on_message(message):
    if message.author.bot:
        return 

#コマンドの定義
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

#コマンドで特定の日時の出席者を表示
@tree.command(name="attendance_list", description="指定された日の出席者リストを表示します")
async def attendance_list_command(interaction: discord.Interaction, date: str):
    if interaction.channel_id != DEBUG_CHANNEL_ID:
        await interaction.response.send_message('このコマンドはこのチャンネルでは実行できません。')
        return
    try:
        # 入力された日付をdatetimeオブジェクトに変換
        target_date = datetime.datetime.strptime(date, "%Y/%m")
        start_date = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = (target_date.replace(month=target_date.month % 12 + 1, day=1) - datetime.timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
    except ValueError:
        await interaction.response.send_message("日付の指定形式が正しくありません。年/月 の形式で入力してください。")
        return

    channel = client.get_channel(ATTENDANCE_RECORD_CHANNEL_ID)
    messages = await get_attendance_messages(channel, start_date, end_date)
    user_ids = extract_user_ids(messages)

    embed = discord.Embed(title=f"**{target_date.strftime('%Y年%m日')}** の出席者リスト", color=0x00ff00)

    if user_ids:
        attendees = "\n".join([f"<@{user_id}>" for user_id in set(user_ids)])
        embed.add_field(name="出席者", value=attendees, inline=False)
    else:
        embed.description = "出席者はいませんでした。"
    await interaction.response.send_message(embed=embed)

#出席管理システム
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
            try:
                await message.remove_reaction(payload.emoji, member)
            except discord.Forbidden:
                print(f"Error: {member.name} のリアクションを削除する権限がありません。")

#ロールはく奪関数の定義
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

#毎日0時に出席ロールを剥奪
async def remove_attendance_role(client):
    guild = client.guilds[0]
    attendance_role = guild.get_role(ATTENDANCE_ROLE_ID)

    await remove_attendance_role_from_guild(guild, attendance_role)
    channel = client.get_channel(DEBUG_CHANNEL_ID)
    await channel.send('出席ロールを全員からはく奪しました。')

#サーバーに新しいメンバーが入った時
@client.event
async def on_member_join(member):
    global member_cache
    if member.guild.id in member_cache:
        member_cache[member.guild.id].append(member)

#サーバーからメンバーが脱退したとき
@client.event
async def on_member_remove(member):
    global member_cache
    if member.guild.id in member_cache:
        member_cache[member.guild.id] = [m for m in member_cache[member.guild.id] if m.id != member.id]

#指定された期間のメッセージを取得する関数
async def get_attendance_messages(channel, start_date, end_date):
    messages = []
    async for message in channel.history(limit=None, after=start_date, before=end_date):
        messages.append(message)
    return messages

#メッセージから出席者のユーザーIDを抽出する関数
def extract_user_ids(messages):
    user_ids = []
    for message in messages:
        match = re.search(r'<@!?(\d+)>', message.content)
        if match:
            user_ids.append(int(match.group(1)))
    return user_ids

#botの起動
if TOKEN is None:
    print("Error: DISCORD_TOKEN を取得出来ませんでした。")
else:
    client.run(TOKEN)