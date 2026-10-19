"""Group polls with live % bars.

/poll <প্রশ্ন> | <অপশন১> | <অপশন২> ...   (admin — গ্রুপ বা bot-এর inbox)
/endpoll                                  (admin — গ্রুপ বা bot-এর inbox) — close + winner
"""

import html
import json

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

import database as db
from utils import command_text, progress_bar, resolve_target_chat


def render_poll(question: str, options, votes: dict, open_: bool) -> str:
    """Pure: build the poll message text with live counts and bars."""
    counts = [0] * len(options)
    for v in votes.values():
        if isinstance(v, int) and 0 <= v < len(options):
            counts[v] += 1
    total = sum(counts)
    lines = [f"📊 <b>{html.escape(question)}</b>", ""]
    for i, opt in enumerate(options):
        pct = (counts[i] / total * 100) if total else 0
        lines.append(f"{i + 1}. {html.escape(opt)} — <b>{counts[i]}</b>")
        lines.append(f"   {progress_bar(pct)}")
    lines.append("")
    lines.append(f"🗳️ মোট ভোট: <b>{total}</b>" + ("  •  ✅ চালু" if open_ else "  •  🔒 বন্ধ"))
    return "\n".join(lines)


def poll_markup(poll_id: int, options) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"{i + 1}. {opt[:28]}",
                                 callback_data=f"pv:{poll_id}:{i}")]
            for i, opt in enumerate(options)]
    return InlineKeyboardMarkup(rows)


async def _send_poll(context, chat_id: int, row) -> None:
    options = json.loads(row["options"])
    votes = json.loads(row["votes"])
    text = render_poll(row["question"], options, votes, bool(row["open"]))
    msg = await context.bot.send_message(
        chat_id, text, parse_mode=ParseMode.HTML,
        reply_markup=poll_markup(row["id"], options) if row["open"] else None)
    db.set_poll_msg(row["id"], msg.message_id)


async def poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id, err = await resolve_target_chat(update, context)
    if not chat_id:
        return await update.effective_message.reply_text(err)
    raw = command_text(update)
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 3:
        return await update.effective_message.reply_text(
            "ব্যবহার: /poll <প্রশ্ন> | <অপশন১> | <অপশন২> ...\n"
            "উদাহরণ: /poll আজ লাইভ কয়টায়? | ৮টায় | ৯টায় | ১০টায়")
    question, options = parts[0], parts[1:]
    if len(options) > 10:
        return await update.effective_message.reply_text("❌ সর্বোচ্চ ১০টা অপশন।")
    # close any previous open poll
    old = db.get_open_poll(chat_id)
    if old:
        db.close_poll(old["id"])
    poll_id = db.create_poll(chat_id, question, options)
    row = db.get_poll(poll_id)
    await _send_poll(context, chat_id, row)
    try:
        await update.effective_message.delete()
    except Exception:
        pass


async def vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try:
        _, poll_id_s, idx_s = q.data.split(":")
        poll_id, idx = int(poll_id_s), int(idx_s)
    except ValueError:
        return await q.answer()
    res = db.vote(poll_id, q.from_user.id, idx)
    if res is None:
        return await q.answer("🔒 Poll বন্ধ।", show_alert=False)
    db.touch_user(q.from_user.id, q.from_user.first_name or "",
                  q.from_user.username or "")
    options, votes = res
    row = db.get_poll(poll_id)
    text = render_poll(row["question"], options, votes, True)
    try:
        await q.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=poll_markup(poll_id, options))
    except Exception:
        pass
    await q.answer("✅ ভোট দেওয়া হয়েছে!")


async def endpoll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id, err = await resolve_target_chat(update, context)
    if not chat_id:
        return await update.effective_message.reply_text(err)
    row = db.get_open_poll(chat_id)
    if not row:
        return await update.effective_message.reply_text("📭 কোনো চালু poll নেই।")
    options = json.loads(row["options"])
    votes = json.loads(row["votes"])
    counts = [0] * len(options)
    for v in votes.values():
        if isinstance(v, int) and 0 <= v < len(options):
            counts[v] += 1
    db.close_poll(row["id"])
    total = sum(counts)
    if total:
        best = max(range(len(options)), key=lambda i: counts[i])
        winner = (f"🏆 <b>বিজয়ী: {html.escape(options[best])}</b> "
                  f"({counts[best]} ভোট)")
    else:
        winner = "📭 কেউ ভোট দেয়নি।"
    text = render_poll(row["question"], options, votes, False) + "\n\n" + winner
    try:
        await context.bot.edit_message_text(
            text, chat_id=row["chat_id"], message_id=row["msg_id"],
            parse_mode=ParseMode.HTML)
    except Exception:
        pass
    await update.effective_message.reply_text(winner, parse_mode=ParseMode.HTML)


def register(app):
    app.add_handler(CommandHandler("poll", poll))
    app.add_handler(CommandHandler("endpoll", endpoll))
    app.add_handler(CallbackQueryHandler(vote_callback, pattern=r"^pv:\d+:\d+$"))
