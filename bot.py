import os
import re
import json
import time
import hashlib
import random
import aiohttp
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

# ---------------- ENV ---------------- #
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OLLAMA_URL = os.getenv("OLLAMA_URL")

TARGET_CHANNEL = "@ExtraPeBot"

SOURCE_CHANNELS = [
    "iamprasadtech",
    "extrape",
    "TechFactsDeals",
    "charan0678"
]

FOOTER = "\n\n—\n📢 *Follow @TechLabDaily*"

DEDUP_FILE = "seen.json"
PRICE_FILE = "prices.json"

SEEN = json.load(open(DEDUP_FILE)) if os.path.exists(DEDUP_FILE) else {}
PRICE_DB = json.load(open(PRICE_FILE)) if os.path.exists(PRICE_FILE) else {}

# ---------------- HELPERS ---------------- #
def score_message(text):
    t = text.lower()
    score = 0
    if any(x in t for x in ["₹", "rs", "%", "http"]): score += 3
    if any(x in t for x in ["deal", "offer", "discount"]): score += 2
    if len(t) < 20: score -= 3
    return score

def is_duplicate(text):
    h = hashlib.md5(text.encode()).hexdigest()
    if h in SEEN: return True
    SEEN[h] = time.time()
    json.dump(SEEN, open(DEDUP_FILE, "w"))
    return False

def extract_urls(text):
    return re.findall(r"https?://\S+", text)

def clean_amazon(url):
    if "amazon." in url and "/dp/" in url:
        asin = url.split("/dp/")[1].split("/")[0]
        return f"https://www.amazon.in/dp/{asin}"
    return url

def extract_price(text):
    m = re.search(r"(₹|rs\.?)\s?([\d,]+)", text.lower())
    return int(m.group(2).replace(",", "")) if m else None

def price_note(key, price):
    old = PRICE_DB.get(key)
    PRICE_DB[key] = price
    json.dump(PRICE_DB, open(PRICE_FILE, "w"))
    if not old: return "🆕 First time deal"
    if price < old: return f"🔻 Price dropped (was ₹{old})"
    return ""

async def rewrite_with_ai(text):
    if not OLLAMA_URL:
        return text
    payload = {
        "model": "mistral",
        "prompt": f"Rewrite clean Telegram deal message without URLs:\n{text}",
        "stream": False
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(OLLAMA_URL, json=payload, timeout=15) as r:
                j = await r.json()
                return j.get("response", text)
    except:
        return text

CTAS = ["📤 Share with friends", "🔖 Save this", "👀 Worth checking"]

# ---------------- HANDLER ---------------- #
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    if chat.username not in SOURCE_CHANNELS:
        return

    text = msg.text or msg.caption
    if not text: return
    if score_message(text) < 3: return
    if is_duplicate(text): return

    urls = [clean_amazon(u) for u in extract_urls(text)]
    price = extract_price(text)
    note = price_note(urls[0] if urls else text[:50], price) if price else ""

    rewritten = await rewrite_with_ai(text)
    rewritten = re.sub(r"https?://\S+", "", rewritten).strip()

    if note:
        rewritten = f"{note}\n\n{rewritten}"

    if urls:
        rewritten += "\n\n🛒 Buy here:\n" + "\n".join(urls)

    final = rewritten + "\n\n" + random.choice(CTAS) + FOOTER

    if msg.photo:
        await context.bot.send_photo(
            chat_id=TARGET_CHANNEL,
            photo=msg.photo[-1].file_id,
            caption=final,
            parse_mode="Markdown"
        )
    else:
        await context.bot.send_message(
            chat_id=TARGET_CHANNEL,
            text=final,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

# ---------------- RUN ---------------- #
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.ALL, on_message))

print("🚀 Bot API version running (Railway-safe)")
app.run_polling()
