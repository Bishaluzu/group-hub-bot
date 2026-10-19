"""Scheduled announce + daily message (Asia/Dhaka time).

/schedule <HH:MM> <text>   — প্রতিদিন ওই সময়ে গ্রুপে পোস্ট (নতুন দিলে আগেরটা বদলে যায়)
/cancelschedule             — বাতিল
/schedinfo                  — বর্তমান schedule দেখুন
/setdaily <HH:MM> <text>   — প্রতিদিনের মেসেজ
/canceldaily, /dailyinfo
Group-এ দিলে ওই গ্রুপে, inbox-এ দিলে bound গ্রুপে (অ্যাডমিন)।
"""

import datetime

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

import database as db
from utils import (DHAKA, admin_in_group, command_text, extract_buttons,
                   parse_hhmm, require_pm_admin)


async def _send_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id, text, prefix = context.job.data
    clean, markup = extract_buttons(text)
    try:
        await context.bot.send_message(
            chat_id, f"{prefix} {clean}", parse_mode=ParseMode.HTML,
            reply_markup=markup, disable_web_page_preview=True)
    except Exception:
        pass


def _arm(context, kind: str, chat_id: int, time_hhmm: str, text: str) -> bool:
    """kind: 'sched' or 'daily'. Replaces any existing job of that kind."""
    parsed = parse_hhmm(time_hhmm)
    if not parsed or not getattr(context, "job_queue", None):
        return False
    hh, mm = parsed
    prefix = "📢" if kind == "sched" else "🌅"
    for job in context.job_queue.jobs():
        if job.name == f"{kind}_{chat_id}":
            job.schedule_removal()
    context.job_queue.run_daily(
        _send_job,
        datetime.time(hh, mm, tzinfo=DHAKA),
        data=(chat_id, text, prefix),
        name=f"{kind}_{chat_id}",
    )
    return True


def _disarm(context, kind: str, chat_id: int) -> None:
    if not getattr(context, "job_queue", None):
        return
    for job in context.job_queue.jobs():
        if job.name == f"{kind}_{chat_id}":
            job.schedule_removal()


def reschedule_all(app) -> int:
    """Re-arm saved schedules + daily messages after a restart."""
    n = 0
    jq = getattr(app, "job_queue", None)
    if not jq:
        return 0

    class _Ctx:
        def __init__(self, job_queue):
            self.job_queue = job_queue

    ctx = _Ctx(jq)
    for chat_id, time_hhmm in db.chats_with_key("sched_time"):
        text = db.get_setting(chat_id, "sched_text", "")
        if text and _arm(ctx, "sched", chat_id, time_hhmm, text):
            n += 1
    for chat_id, time_hhmm in db.chats_with_key("daily_time"):
        text = db.get_setting(chat_id, "daily_text", "")
        if text and _arm(ctx, "daily", chat_id, time_hhmm, text):
            n += 1
    return n


async def _target_chat(update, context):
    """Return target chat_id for schedule/daily, or 0 if not allowed."""
    if update.effective_chat.type == "private":
        return await require_pm_admin(update, context)
    if not await admin_in_group(update, context):
        await update.effective_message.reply_text(
            "❌ শুধু অ্যাডমিনরা এই কমান্ড ব্যবহার করতে পারেন।")
        return 0
    return update.effective_chat.id


async def _set_timed(update, context, kind: str, cmd: str):
    chat_id = await _target_chat(update, context)
    if not chat_id:
        return
    if not context.args or not parse_hhmm(context.args[0]):
        return await update.effective_message.reply_text(
            f"ব্যবহার: /{cmd} <HH:MM> <মেসেজ>\nউদাহরণ: /{cmd} 21:00 আজ রাত ৯টায় লাইভ!")
    time_hhmm = context.args[0]
    parts = command_text(update).split(None, 1)
    text = parts[1] if len(parts) > 1 else ""
    if not text:
        return await update.effective_message.reply_text("❌ মেসেজ লিখুন।")
    db.set_setting(chat_id, f"{kind}_time", time_hhmm)
    db.set_setting(chat_id, f"{kind}_text", text)
    if _arm(context, kind, chat_id, time_hhmm, text):
        label = "ঘোষণা" if kind == "sched" else "ডেইলি মেসেজ"
        await update.effective_message.reply_text(
            f"✅ প্রতিদিন {time_hhmm} (ঢাকা) টায় {label} পাঠানো হবে।")
    else:
        await update.effective_message.reply_text("❌ schedule চালু করা যায়নি।")


async def _cancel_timed(update, context, kind: str):
    chat_id = await _target_chat(update, context)
    if not chat_id:
        return
    db.del_setting(chat_id, f"{kind}_time")
    db.del_setting(chat_id, f"{kind}_text")
    _disarm(context, kind, chat_id)
    await update.effective_message.reply_text("✅ বাতিল হয়েছে।")


async def _info_timed(update, context, kind: str, name: str):
    chat_id = await _target_chat(update, context)
    if not chat_id:
        return
    t = db.get_setting(chat_id, f"{kind}_time", "")
    if not t:
        return await update.effective_message.reply_text(f"📭 কোনো {name} সেট করা নেই।")
    txt = db.get_setting(chat_id, f"{kind}_text", "")
    preview = txt[:80] + "…" if len(txt) > 80 else txt
    await update.effective_message.reply_text(
        f"⏰ <b>{name}:</b> প্রতিদিন {t} (ঢাকা)\n{preview}",
        parse_mode=ParseMode.HTML)


async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _set_timed(update, context, "sched", "schedule")


async def cancelschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _cancel_timed(update, context, "sched")


async def schedinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _info_timed(update, context, "sched", "Scheduled ঘোষণা")


async def setdaily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _set_timed(update, context, "daily", "setdaily")


async def canceldaily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _cancel_timed(update, context, "daily")


async def dailyinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _info_timed(update, context, "daily", "ডেইলি মেসেজ")


def register(app):
    app.add_handler(CommandHandler("schedule", schedule))
    app.add_handler(CommandHandler("cancelschedule", cancelschedule))
    app.add_handler(CommandHandler("schedinfo", schedinfo))
    app.add_handler(CommandHandler("setdaily", setdaily))
    app.add_handler(CommandHandler("canceldaily", canceldaily))
    app.add_handler(CommandHandler("dailyinfo", dailyinfo))
