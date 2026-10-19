"""Smart pinned countdown: /countdown <minutes> | <title>.

- Posts a pinned timer in the group; adaptive display
  (ঘণ্টা -> মিনিট -> সেকেন্ড), edited every minute, every second
  in the last 60 seconds.
- Milestones: /cdmsg <min> | <text> posts to the group when the
  remaining time drops to <min> minutes; /cddm <min> | <text> DMs
  <text> to every known user instead. /cdmsg 0 / /cddm 0 fire at end.
- /cdlist lists milestones, /cdclear clears them,
  /endcountdown stops the active countdown.
- Inbox DMs only reach users who pressed /start on the bot
  (Telegram limit) and skips banned users + the admin.
"""

import time

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

import database as db
from utils import (command_text, extract_buttons, fmt_time_left,
                   resolve_target_chat)

MAX_MINUTES = 180
JOB_PREFIX = "countdown_"


# ------------------------------------------------------------- pure helpers
def parse_countdown_args(raw: str):
    """Pure: '120 | title' -> (120, 'title'); '45' -> (45, '')."""
    minutes_s, _, title = raw.partition("|")
    minutes_s = minutes_s.strip()
    if not minutes_s.isdigit():
        return None, None
    return int(minutes_s), title.strip()


def render_timer(title: str, remaining: int) -> str:
    """Pure: full timer message text (big timer first, so the pinned bar shows it)."""
    line = f"⏳ <b>{fmt_time_left(remaining)}</b> ⏳"
    return f"{line}\n{title}" if title else line


def due_milestones(prev_remaining: int, remaining: int, milestones):
    """Pure: milestones whose threshold was crossed between two ticks.

    milestones: iterable of (at_min, kind, text). Each fires exactly
    once, when remaining drops from above at_min*60 to at/under it.
    at_min=0 fires at the end.
    """
    due = []
    for at_min, kind, text in milestones:
        threshold = at_min * 60
        if prev_remaining > threshold >= remaining:
            due.append((at_min, kind, text))
    return due


# ------------------------------------------------------------------ firing
async def _fire_milestone(context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                          kind: str, text: str):
    clean, markup = extract_buttons(text or "")
    body = clean if clean else (text or "")
    if kind == "dm":
        _, admin_id = db.get_bound()
        for uid, _name in db.list_known_users():
            if uid == admin_id or db.is_banned(uid):
                continue
            try:
                await context.bot.send_message(
                    uid, body, parse_mode=ParseMode.HTML,
                    reply_markup=markup)
            except Exception:
                pass  # user blocked the bot or never pressed /start
        return
    try:
        await context.bot.send_message(
            chat_id, body, parse_mode=ParseMode.HTML,
            reply_markup=markup)
    except Exception:
        pass


async def _tick(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    remaining = int(data["end"] - time.time())
    chat_id, msg_id = data["chat_id"], data["msg_id"]
    prev = data.get("prev", remaining + 1)
    milestones = db.list_milestones(chat_id)
    if remaining <= 0:
        title = data.get("title", "")
        end_text = (f"🔴 <b>LIVE START!</b> 🎥\n{title}" if title
                    else "🔴 <b>LIVE START!</b> 🎥")
        try:
            await context.bot.edit_message_text(
                end_text, chat_id=chat_id, message_id=msg_id,
                parse_mode=ParseMode.HTML, reply_markup=data.get("markup"))
        except Exception:
            pass
        for _at, kind, text in due_milestones(prev, remaining, milestones):
            await _fire_milestone(context, chat_id, kind, text)
        context.job.schedule_removal()
        return
    for _at, kind, text in due_milestones(prev, remaining, milestones):
        await _fire_milestone(context, chat_id, kind, text)
    data["prev"] = remaining
    display = render_timer(data.get("title", ""), remaining)
    if display != data.get("last"):
        data["last"] = display
        try:
            await context.bot.edit_message_text(
                display, chat_id=chat_id, message_id=msg_id,
                parse_mode=ParseMode.HTML, reply_markup=data.get("markup"))
        except Exception:
            pass


async def _stop_countdown(context: ContextTypes.DEFAULT_TYPE,
                          chat_id: int) -> bool:
    """Remove the countdown job and unpin its timer. True if one was running."""
    stopped = False
    if getattr(context, "job_queue", None):
        for job in context.job_queue.jobs():
            if job.name == f"{JOB_PREFIX}{chat_id}":
                job.schedule_removal()
                stopped = True
    old_msg = db.get_setting(chat_id, "countdown_msg", "")
    if old_msg:
        try:
            await context.bot.unpin_chat_message(chat_id, int(old_msg))
        except Exception:
            pass
        db.del_setting(chat_id, "countdown_msg")
    return stopped


# ---------------------------------------------------------------- commands
async def countdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id, err = await resolve_target_chat(update, context)
    if not chat_id:
        return await update.effective_message.reply_text(err)
    minutes, title = parse_countdown_args(command_text(update))
    if minutes is None:
        return await update.effective_message.reply_text(
            "ব্যবহার: /countdown <মিনিট> | <শিরোনাম>\n"
            "উদাহরণ: /countdown 120 | 🔴 আজকের LIVE!")
    if not (1 <= minutes <= MAX_MINUTES):
        return await update.effective_message.reply_text(
            f"❌ 1–{MAX_MINUTES} মিনিটের মধ্যে দিন।")
    if not getattr(context, "job_queue", None):
        return await update.effective_message.reply_text("❌ job system চালু নেই।")
    await _stop_countdown(context, chat_id)
    clean_title, markup = extract_buttons(title) if title else ("", None)
    display = render_timer(clean_title, minutes * 60)
    msg = await context.bot.send_message(
        chat_id, display, parse_mode=ParseMode.HTML, reply_markup=markup)
    try:
        await context.bot.pin_chat_message(chat_id, msg.message_id,
                                           disable_notification=True)
    except Exception:
        pass
    db.set_setting(chat_id, "countdown_msg", msg.message_id)
    context.job_queue.run_repeating(
        _tick, interval=1, first=1,
        data={"chat_id": chat_id, "msg_id": msg.message_id,
              "end": time.time() + minutes * 60,
              "title": clean_title, "markup": markup,
              "last": display, "prev": minutes * 60 + 1},
        name=f"{JOB_PREFIX}{chat_id}",
    )
    try:
        await update.effective_message.delete()
    except Exception:
        pass


async def endcountdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id, err = await resolve_target_chat(update, context)
    if not chat_id:
        return await update.effective_message.reply_text(err)
    if await _stop_countdown(context, chat_id):
        await update.effective_message.reply_text("⏹️ কাউন্টডাউন বন্ধ হয়েছে।")
    else:
        await update.effective_message.reply_text("📭 কোনো চালু কাউন্টডাউন নেই।")


async def _set_milestone(update: Update, context: ContextTypes.DEFAULT_TYPE,
                         kind: str):
    chat_id, err = await resolve_target_chat(update, context)
    if not chat_id:
        return await update.effective_message.reply_text(err)
    raw = command_text(update)
    at_s, _, text = raw.partition("|")
    at_s = at_s.strip()
    if not at_s.isdigit() or not text.strip():
        name = "/cdmsg" if kind == "msg" else "/cddm"
        return await update.effective_message.reply_text(
            f"ব্যবহার: {name} <মিনিট> | <মেসেজ>\n"
            f"উদাহরণ: {name} 30 | ⏳ ৩০ মিনিট বাকি!")
    db.set_milestone(chat_id, int(at_s), kind, text.strip())
    where = "গ্রুপে পোস্ট" if kind == "msg" else "সবার inbox-এ পাঠানো"
    await update.effective_message.reply_text(
        f"✅ মাইলস্টোন সেট: {at_s} মিনিট বাকিতে {where} হবে।")


async def cdmsg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _set_milestone(update, context, "msg")


async def cddm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _set_milestone(update, context, "dm")


async def cdlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id, err = await resolve_target_chat(update, context)
    if not chat_id:
        return await update.effective_message.reply_text(err)
    rows = db.list_milestones(chat_id)
    if not rows:
        return await update.effective_message.reply_text("📭 কোনো মাইলস্টোন সেট নেই।")
    lines = ["⏱️ <b>মাইলস্টোন:</b>"]
    for at_min, kind, text in rows:
        where = "👥 গ্রুপ" if kind == "msg" else "📩 inbox"
        preview = (text[:40] + "…") if len(text) > 40 else text
        lines.append(f"• {at_min} মিনিট বাকি → {where}: {preview}")
    await update.effective_message.reply_text("\n".join(lines),
                                              parse_mode=ParseMode.HTML)


async def cdclear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id, err = await resolve_target_chat(update, context)
    if not chat_id:
        return await update.effective_message.reply_text(err)
    db.clear_milestones(chat_id)
    await update.effective_message.reply_text("🗑️ সব মাইলস্টোন মুছে ফেলা হয়েছে।")


def register(app):
    app.add_handler(CommandHandler("countdown", countdown))
    app.add_handler(CommandHandler("cdmsg", cdmsg))
    app.add_handler(CommandHandler("cddm", cddm))
    app.add_handler(CommandHandler("cdlist", cdlist))
    app.add_handler(CommandHandler("cdclear", cdclear))
    app.add_handler(CommandHandler("endcountdown", endcountdown))
