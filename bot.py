"""Group Hub Bot — entry point.

All-in-one Telegram group + inbox bot:
announce, reply routing, FAQ + AI, polls, schedules, keyword alerts,
payment proof inbox, live countdown, daily message, anonymous feedback,
quiz, weekly top, reminders.

Setup:
  1. cp .env.example .env   (then put your BotFather token in .env)
  2. pip install -r requirements.txt
  3. python bot.py
"""

import logging
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()  # <-- MUST be called so BOT_TOKEN is read from .env

from telegram import BotCommand, Update
from telegram.error import NetworkError
from telegram.ext import Application

import database
from handlers import register_all
from handlers import schedule as schedule_mod

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("hub_bot")


COMMANDS = [
    ("start", "বট চালু / সাহায্য"),
    ("help", "সাহায্য"),
    ("truth18", "18+ Truth game (dice)"),
    ("suggest", "প্রশ্ন suggest করো"),
    ("settruth18", "প্রশ্ন যোগ (অ্যাডমিন)"),
    ("deltruth", "প্রশ্ন মুছুন (অ্যাডমিন)"),
    ("edittruth", "প্রশ্ন এডিট (অ্যাডমিন)"),
    ("truthlist", "প্রশ্নের তালিকা (অ্যাডমিন)"),
    ("gametimer", "game auto-delete timer (অ্যাডমিন)"),
    ("poll", "ভোট শুরু (অ্যাডমিন)"),
    ("endpoll", "ভোট শেষ (অ্যাডমিন)"),
    ("countdown", "লাইভ কাউন্টডাউন (অ্যাডমিন)"),
    ("endcountdown", "কাউন্টডাউন বন্ধ (অ্যাডমিন)"),
    ("cdmsg", "মাইলস্টোন মেসেজ (অ্যাডমিন)"),
    ("cddm", "মাইলস্টোন inbox (অ্যাডমিন)"),
    ("cdlist", "মাইলস্টোন তালিকা (অ্যাডমিন)"),
    ("cdclear", "মাইলস্টোন মুছুন (অ্যাডমিন)"),
    ("announce", "গ্রুপে ঘোষণা (অ্যাডমিন)"),
    ("setgroup", "গ্রুপ bind (অ্যাডমিন)"),
    ("hubstatus", "bind status (অ্যাডমিন)"),
    ("autopin", "ঘোষণা auto-pin (অ্যাডমিন)"),
    ("schedule", "দৈনিক পোস্ট (অ্যাডমিন)"),
    ("cancelschedule", "schedule বাতিল (অ্যাডমিন)"),
    ("setdaily", "প্রতিদিনের মেসেজ (অ্যাডমিন)"),
    ("canceldaily", "daily বাতিল (অ্যাডমিন)"),
    ("setfaq", "auto-reply যোগ (অ্যাডমিন)"),
    ("delfaq", "auto-reply মুছুন (অ্যাডমিন)"),
    ("faqs", "FAQ তালিকা"),
    ("setkeywords", "keyword alert (অ্যাডমিন)"),
    ("feedback", "নাম ছাড়া মতামত"),
    ("quiz", "কুইজ খেলো"),
    ("score", "কুইজ স্কোর"),
    ("top", "সাপ্তাহিক সেরা"),
    ("remind", "মনে করিয়ে দেবে"),
    ("ban", "ইউজার ব্যান (অ্যাডমিন)"),
    ("unban", "আনব্যান (অ্যাডমিন)"),
    ("banned", "ব্যান তালিকা (অ্যাডমিন)"),
]


async def post_init(app):
    """Re-arm saved schedules / daily messages after a restart."""
    try:
        n = schedule_mod.reschedule_all(app)
        if n:
            logger.info("Re-armed %d timed job(s).", n)
    except Exception as e:
        logger.warning("Could not re-arm timed jobs: %s", e)
    try:
        await app.bot.set_my_commands(
            [BotCommand(cmd, desc) for cmd, desc in COMMANDS])
        logger.info("Bot commands registered (%d).", len(COMMANDS))
    except Exception as e:
        logger.warning("Could not set bot commands: %s", e)


def main():
    database.init_db()

    token = (
        os.getenv("BOT_TOKEN", "").strip()
        or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    )
    if not token or token == "your_token_here":
        sys.exit("❌ BOT_TOKEN পাওয়া যায়নি! .env ফাইলে BOT_TOKEN=... বসান।")

    app = Application.builder().token(token).post_init(post_init).build()
    register_all(app)

    logger.info("Group Hub Bot is starting…")
    while True:
        try:
            app.run_polling(allowed_updates=Update.ALL_TYPES)
            break
        except KeyboardInterrupt:
            logger.info("Stopped by user.")
            break
        except NetworkError as e:
            logger.warning("Network problem (%s) — 10 সেকেন্ড পর আবার চেষ্টা…", e)
            time.sleep(10)


if __name__ == "__main__":
    main()
