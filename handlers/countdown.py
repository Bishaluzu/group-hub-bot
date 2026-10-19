"""Live countdown: /countdown <minutes> (admin, group).

Posts a countdown message, edits every 5 seconds, every 1 second during
the last 30 seconds, ends with '🔴 LIVE START!'.
"""

import time

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from utils import admin_in_group, fmt_hms

MAX_MINUTES = 180


async def _tick(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    remaining = int(data["end"] - time.time())
    chat_id, msg_id = data["chat_id"], data["msg_id"]
    if remaining <= 0:
        try:
            await context.bot.edit_message_text(
                "🔴 <b>LIVE START!</b> 🎥\nসবাই জয়েন করো!",
                chat_id=chat_id, message_id=msg_id, parse_mode=ParseMode.HTML)
        except Exception:
            pass
        context.job.schedule_removal()
        return
    display = f"⏳ <b>লাইভ শুরু হতে বাকি:</b> <code>{fmt_hms(remaining)}</code>"
    # throttle: every 5s normally, every 1s in the last 30s
    if remaining <= 30 or remaining % 5 == 0:
        if display != data.get("last"):
            data["last"] = display
            try:
                await context.bot.edit_message_text(
                    display, chat_id=chat_id, message_id=msg_id,
                    parse_mode=ParseMode.HTML)
            except Exception:
                pass


async def countdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.effective_message.reply_text("❌ /countdown গ্রুপে দিন।")
    if not await admin_in_group(update, context):
        return await update.effective_message.reply_text(
            "❌ শুধু অ্যাডমিনরা countdown চালাতে পারেন।")
    if not context.args or not context.args[0].isdigit():
        return await update.effective_message.reply_text(
            "ব্যবহার: /countdown <মিনিট>\nউদাহরণ: /countdown 30")
    minutes = int(context.args[0])
    if not (1 <= minutes <= MAX_MINUTES):
        return await update.effective_message.reply_text(
            f"❌ 1–{MAX_MINUTES} মিনিটের মধ্যে দিন।")
    if not getattr(context, "job_queue", None):
        return await update.effective_message.reply_text("❌ job system চালু নেই।")
    # remove any existing countdown in this chat
    for job in context.job_queue.jobs():
        if job.name == f"countdown_{update.effective_chat.id}":
            job.schedule_removal()
    msg = await update.effective_message.reply_text(
        f"⏳ <b>লাইভ শুরু হতে বাকি:</b> <code>{fmt_hms(minutes * 60)}</code>",
        parse_mode=ParseMode.HTML)
    context.job_queue.run_repeating(
        _tick, interval=1, first=1,
        data={"chat_id": update.effective_chat.id, "msg_id": msg.message_id,
              "end": time.time() + minutes * 60, "last": ""},
        name=f"countdown_{update.effective_chat.id}",
    )
    try:
        await update.effective_message.delete()
    except Exception:
        pass


def register(app):
    app.add_handler(CommandHandler("countdown", countdown))
