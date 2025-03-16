#いっぱいコメントあるのは初心者だから許してね

#ライブラリのインポート
import discord
import asyncio
import os
from dotenv import load_dotenv
import datetime #出席記録のためだけにこれインポートするのはなぁという気持ち
import schedule
import time
#import keep_alive #botを落とさないための処理
import requests

load_dotenv()

#keep_alive.keep_alive() #wbeサーバーを起動

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

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.dm_messages = True
client = discord.Client(intents=intents)

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
    
    #定期的にメッセージを送信する
    user = await client.fetch_user(TARGET_USER_ID)
    if user:
        while True:
            try:
                await user.send('定期的なメッセージです。')
                print(f'{user.name} にメッセージを送信しました')
            except Exception as e: 
                print(f"Error: {user.name} にメッセージを送信する際にエラーが発生しました。")
            
            await asyncio.sleep(600)
    
    #出席ロール剥奪処理のスケジューリング
    schedule.every().day.at("00:08").do(lambda: asyncio.create_task(remove_attendance_role(client)))
    asyncio.create_task(scheduler())

#スケジューリング処理
async def scheduler():
    while True:
        schedule.run_pending()
        await asyncio.sleep(60)

#メッセージ受信時の処理
@client.event
async def on_message(message):
    if message.author.bot:
        return

    #テストコマンド
    if message.content == '/test' and message.channel.id == DEBUG_CHANNEL_ID:
        await message.channel.send('テストメッセージです')

    #botの停止コマンド
    if message.content == '/stop' and message.channel.id == DEBUG_CHANNEL_ID:
        await message.channel.send('botを停止します')
        await client.close()
        print('botを停止しました')
        # try:
        #     requests.post('http://127.0.0.1:8080/shutdown')
        # except Exception as e:
        #     print(f"Error: サーバー停止エンドポイントにアクセスできませんでした。")

    # 出席ロール剥奪コマンド
    if message.content == '/remove role' and message.channel.id == DEBUG_CHANNEL_ID:
        #出席ロールの取得
        attendance_role_id = message.guild.get_role(ATTENDANCE_ROLE_ID)
        
        #ロールはく奪関数の呼び出し
        await remove_attendance_role_from_guild(message.guild, attendance_role_id)
        await message.channel.send('出席ロールを剥奪しました。')

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
     
     if attendance_role:
        members = []
        async for member in guild.fetch_members(limit=None):
            members.append(member)
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

#botの起動
if TOKEN is None:
    print("Error: DISCORD_TOKEN を取得出来ませんでした。")
else:
    client.run(TOKEN)