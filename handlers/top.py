"""Weekly activity leaderboard: counts group text messages per ISO week.

/top — এই সপ্তাহের সবচেয়ে active ১০ জন।
"""

import html

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

import database as db
from utils import current_week


async def count_watcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = msg.from_user
    if user.is_bot:
        return
    db.bump_count(msg.chat_id, current_week(), user.id, user.first_name or "")


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.effective_message.reply_text("❌ /top গ্রুপে দেখুন।")
    week = current_week()
    rows = db.top_week(update.effective_chat.id, week)
    if not rows:
        return await update.effective_message.reply_text("📭 এই সপ্তাহে এখনো কোনো মেসেজ নেই।")
    lines = [f"📊 <b>এই সপ্তাহের Top Active ({week}):</b>"]
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{medal} {html.escape(r['name'])} — <b>{r['count']}</b> মেসেজ")
    await update.effective_message.reply_text("\n".join(lines),
                                              parse_mode=ParseMode.HTML)


def register(app):
    app.add_handler(CommandHandler("top", top))
    # group=1 so it always runs alongside other watchers
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
                       count_watcher),
        group=1)
