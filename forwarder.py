import os
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION_STRING")

# Channels to read FROM
SOURCE_CHANNELS = [
    "iamprasadtech",
    "extrape",
    "TechFactsDeals",
    "charan0678"
]

# Destination bot/channel
TARGET_CHANNEL = "ExtraPeBot"

# Create client with zero-delay settings
client = TelegramClient(
    StringSession(SESSION),
    API_ID,
    API_HASH,
    connection_retries=0,        # no waiting for reconnection
    retry_delay=0,               # no retry delay
    flood_sleep_threshold=0      # disable automatic waiting for flood limits
)

@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def forward_message(event):
    try:
        # ZERO DELAY FORWARDING
        await client.send_message(TARGET_CHANNEL, event.message)

        print("Forwarded instantly:", event.message.text)
    except Exception as e:
        print("Error forwarding:", e)

print("USERBOT RUNNING (ZERO DELAY MODE)…")
client.start()
print("Forwarding active…")
client.run_until_disconnected()
