"""/remind <10m|2h> <text> in PM -> the bot reminds that user later."""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

import database as db
from utils import command_text, parse_delay


async def _fire(context: ContextTypes.DEFAULT_TYPE):
    user_id, text = context.job.data
    try:
        await context.bot.send_message(
            user_id, f"⏰ <b>মনে করিয়ে দিচ্ছি:</b>\n{text}",
            parse_mode=ParseMode.HTML)
    except Exception:
        pass


async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private" and db.is_banned(update.effective_user.id):
        return
    if update.effective_chat.type != "private":
        return await update.effective_message.reply_text(
            "❌ /remind inbox-এ (bot-এর PM-এ) দিন।")
    if not context.args:
        return await update.effective_message.reply_text(
            "ব্যবহার: /remind <10m|2h> <টেক্সট>\nউদাহরণ: /remind 2h লাইভ শুরু করো")
    secs = parse_delay(context.args[0])
    if not secs or secs < 10 or secs > 7 * 24 * 3600:
        return await update.effective_message.reply_text(
            "❌ সময় ঠিক নয়। উদাহরণ: 10m, 2h (১০ সেকেন্ড – ৭ দিন)")
    parts = command_text(update).split(None, 1)
    text = parts[1] if len(parts) > 1 else ""
    if not text:
        return await update.effective_message.reply_text("❌ কী মনে করাবো লিখুন।")
    if not getattr(context, "job_queue", None):
        return await update.effective_message.reply_text("❌ job system চালু নেই।")
    context.job_queue.run_once(
        _fire, secs,
        data=(update.effective_user.id, text),
        name=f"remind_{update.effective_user.id}_{text[:10]}")
    await update.effective_message.reply_text(
        f"✅ ঠিক আছে, <b>{context.args[0]}</b> পর মনে করিয়ে দেবো।",
        parse_mode=ParseMode.HTML)


def register(app):
    app.add_handler(CommandHandler("remind", remind))
