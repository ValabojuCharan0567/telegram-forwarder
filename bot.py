import os
import aiohttp
import hashlib
import time
import json
import random
import re
import urllib.parse

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from dotenv import load_dotenv

# ---------------- LOAD ENV ---------------- #
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION_STRING")

# ---------------- CONFIG ---------------- #
SOURCE_CHANNELS = [
    "iamprasadtech",
    "extrape",
    "TechFactsDeals",
    "charan0678"
]

TARGET_CHANNEL = "ExtraPeBot"
FOOTER = "\n\n—\n📢 *Follow @TechLabDaily*"

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"

DEDUP_FILE = "seen.json"
PRICE_FILE = "prices.json"

DEDUP_TTL = 24 * 60 * 60
MIN_SCORE = 3

# ---------------- LOAD STATE ---------------- #
SEEN = json.load(open(DEDUP_FILE)) if os.path.exists(DEDUP_FILE) else {}
PRICE_DB = json.load(open(PRICE_FILE)) if os.path.exists(PRICE_FILE) else {}

# ---------------- TELEGRAM CLIENT ---------------- #
client = TelegramClient(
    StringSession(SESSION),
    API_ID,
    API_HASH,
    flood_sleep_threshold=3
)

# ---------------- HELPERS ---------------- #
def score_message(text: str) -> int:
    t = text.lower()
    score = 0
    if any(k in t for k in ["₹", "rs", "%", "http"]):
        score += 3
    if any(k in t for k in ["deal", "offer", "discount", "sale"]):
        score += 2
    if any(k in t for k in ["ai", "tech", "app", "launch", "update"]):
        score += 1
    if len(text.strip()) < 20:
        score -= 3
    return score

def is_duplicate(text: str) -> bool:
    now = time.time()
    h = hashlib.md5(text.encode()).hexdigest()

    for k in list(SEEN.keys()):
        if now - SEEN[k] > DEDUP_TTL:
            del SEEN[k]

    if h in SEEN:
        return True

    SEEN[h] = now
    json.dump(SEEN, open(DEDUP_FILE, "w"))
    return False

def extract_urls(text: str):
    return re.findall(r"https?://\S+", text) if text else []

def remove_urls(text: str) -> str:
    return re.sub(r"https?://\S+", "", text).strip()

def clean_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)

    # Amazon
    if "amazon." in parsed.netloc:
        parts = parsed.path.split("/")
        if "dp" in parts:
            asin = parts[parts.index("dp") + 1]
            return f"https://www.amazon.in/dp/{asin}"

    # Flipkart
    if "flipkart." in parsed.netloc:
        q = urllib.parse.parse_qs(parsed.query)
        if "pid" in q:
            return f"https://www.flipkart.com/p/{q['pid'][0]}"

    return url

def extract_price(text: str):
    m = re.search(r"(₹|rs\.?)\s?([\d,]+)", text.lower())
    return int(m.group(2).replace(",", "")) if m else None

def price_trend(key: str, new_price: int):
    old = PRICE_DB.get(key)
    PRICE_DB[key] = new_price
    json.dump(PRICE_DB, open(PRICE_FILE, "w"))

    if not old:
        return "🆕 First time deal"
    if new_price < old:
        return f"🔻 Price dropped (was ₹{old})"
    if new_price > old:
        return f"🔺 Price increased (was ₹{old})"
    return "➖ Same price as before"

def inject_smart_emojis(text: str) -> str:
    t = text.lower()
    emojis = []
    if any(k in t for k in ["deal", "off", "%", "₹", "discount"]):
        emojis.append("🔥")
    if any(k in t for k in ["tech", "mobile", "laptop"]):
        emojis.append("💻")
    if any(k in t for k in ["bank", "upi", "card"]):
        emojis.append("💳")
    return f"{''.join(emojis[:2])} {text}" if emojis else text

CTAS = [
    "🔖 Save this for later",
    "📌 Useful? Bookmark it",
    "📤 Share with friends",
    "👀 Worth checking",
    "⚡ Don’t miss this"
]

def add_silent_cta(text: str) -> str:
    return text + "\n\n" + random.choice(CTAS)

# ---------------- LOCAL LLM ---------------- #
async def rewrite_with_local_llm(text: str) -> str:
    if not text or len(text.strip()) < 15:
        return text

    prompt = f"""
Rephrase the Telegram message below.

Rules:
- Do NOT change prices, numbers, or coupon codes
- Do NOT include URLs
- Keep it clean and concise
- Telegram-friendly formatting

Message:
{text}
"""

    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OLLAMA_URL, json=payload, timeout=20) as resp:
                data = await resp.json()
                return data.get("response", text).strip()
    except:
        return text

# ---------------- HANDLER ---------------- #
@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def handler(event):
    try:
        msg = event.message
        text = msg.text or msg.message
        if not text:
            return

        # Quality filter
        if score_message(text) < MIN_SCORE:
            return

        # Duplicate filter
        if is_duplicate(text):
            return

        # Extract & clean URLs
        urls = extract_urls(text)
        clean_urls = [clean_url(u) for u in urls]

        # Price logic
        price = extract_price(text)
        key = clean_urls[0] if clean_urls else text[:60]
        price_note = price_trend(key, price) if price else ""

        # AI rewrite
        rewritten = await rewrite_with_local_llm(text)
        rewritten = remove_urls(rewritten)

        if price_note:
            rewritten = f"{price_note}\n\n{rewritten}"

        if clean_urls:
            rewritten += "\n\n🛒 Buy here:\n" + "\n".join(clean_urls)

        final_text = add_silent_cta(
            inject_smart_emojis(rewritten)
        ) + FOOTER

        if msg.media:
            await client.send_file(
                TARGET_CHANNEL,
                msg.media,
                caption=final_text,
                parse_mode="md"
            )
        else:
            await client.send_message(
                TARGET_CHANNEL,
                final_text,
                parse_mode="md"
            )

        print("✅ Posted cleanly (no duplicate links)")

    except Exception as e:
        print("Error:", e)

# ---------------- RUN ---------------- #
print("🚀 Bot running — FINAL CLEAN VERSION")
client.start()
client.run_until_disconnected()
