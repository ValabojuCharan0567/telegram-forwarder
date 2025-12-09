import os
from telethon import TelegramClient, events
from dotenv import load_dotenv

load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")

# Read multiple source channels from env as comma-separated IDs
SOURCE_CHANNELS = os.getenv("SOURCE_CHANNELS").split(",")
SOURCE_CHANNELS = [int(ch.strip()) for ch in SOURCE_CHANNELS]

TARGET_CHANNEL = int(os.getenv("TARGET_CHANNEL"))

client = TelegramClient('bot_session', api_id, api_hash).start(bot_token=bot_token)

@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def forward_message(event):
    try:
        await client.send_message(TARGET_CHANNEL, event.message)
        print("Forwarded:", event.message.text)
    except Exception as e:
        print("Error:", e)

print("Bot running on cloud...")
client.run_until_disconnected()
