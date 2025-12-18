import os
import re
import time
import json
import hashlib
import random
import aiohttp
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from telegram.helpers import escape_markdown

# ---------- ENV ----------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing")

TARGET_CHANNEL = "@ExtraPeBot"

SOURCE_CHANNELS = {
    "iamprasadtech",
    "extrape",
    "TechFactsDeals",
    "charan0678"
}

FOOTER = "\n\n—\n📢 *Follow @TechLabDaily*"
CTAS = ["📤 Share with friends", "👀 Worth checking", "🔖 Save this deal"]

SEEN_FILE = "seen.json"

# ---------- STATE ----------
def load_seen():
    try:
        with open(SEEN_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

SEEN = load_seen()

# ---------- HELPERS ----------
def is_duplicate(text: str) -> bool:
    h = hashlib.md5(text.encode()).hexdigest()
    if h in SEEN:
        return True
    SEEN[h] = int(time.time())
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(SEEN, f)
    except:
        pass
    return False

def extract_urls(text):
    return re.findall(r"https?://\S+", text)

def clean_amazon(url):
    if "amazon." in url and "/dp/" in url:
        asin = url.split("/dp/")[1].split("/")[0]
        return f"https://www.amazon.in/dp/{asin}"
    return url

async def rewrite_with_groq(text: str) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama3-8b-8192",
        "messages": [
            {
                "role": "system",
                "content": "Rewrite Telegram deal posts cleanly with emojis. Do not include links."
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "temperature": 0.6
    }

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload
            ) as r:
                if r.status != 200:
                    return text
                data = await r.json()
                return data["choices"][0]["message"]["content"].strip()
    except:
        return text  # SAFE FALLBACK

# ---------- HANDLER ----------
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    if not chat.username or chat.username not in SOURCE_CHANNELS:
        return

    text = msg.text or msg.caption
    if not text:
        return

    if is_duplicate(text):
        return

    urls = [clean_amazon(u) for u in extract_urls(text)]
    rewritten = await rewrite_with_groq(text)
    rewritten = re.sub(r"https?://\S+", "", rewritten).strip()

    rewritten = escape_markdown(rewritten, version=2)

    if urls:
        rewritten += "\n\n🛒 *Buy here:*\n" + "\n".join(urls)

    final = rewritten + "\n\n" + random.choice(CTAS) + FOOTER

    if msg.photo:
        await context.bot.send_photo(
            chat_id=TARGET_CHANNEL,
            photo=msg.photo[-1].file_id,
            caption=final,
            parse_mode="MarkdownV2"
        )
    else:
        await context.bot.send_message(
            chat_id=TARGET_CHANNEL,
            text=final,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True
        )

# ---------- RUN ----------
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.ALL, on_message))

print("🚀 Bot running with Groq AI (Cloud-only, Stable)")
app.run_polling()
