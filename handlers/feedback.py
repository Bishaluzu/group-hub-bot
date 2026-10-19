"""/feedback <text> in PM -> posted to the bound group anonymously."""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

import database as db
from utils import command_text


async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return await update.effective_message.reply_text(
            "❌ /feedback inbox-এ (bot-এর PM-এ) দিন।")
    text = command_text(update)
    if not text:
        return await update.effective_message.reply_text(
            "ব্যবহার: /feedback <তোমার মতামত>\nনাম ছাড়া গ্রুপে পোস্ট হবে।")
    chat_id, _admin = db.get_bound()
    if not chat_id:
        return await update.effective_message.reply_text("❌ কোনো গ্রুপ bind করা নেই।")
    try:
        await context.bot.send_message(
            chat_id,
            f"📮 <b>Anonymous feedback:</b>\n{text}",
            parse_mode=ParseMode.HTML)
    except Exception as e:
        return await update.effective_message.reply_text(f"❌ পোস্ট করা যায়নি: {e}")
    await update.effective_message.reply_text("✅ তোমার মতামত নাম ছাড়া পোস্ট হয়েছে।")


def register(app):
    app.add_handler(CommandHandler("feedback", feedback))
