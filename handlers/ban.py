"""PM ban: /ban, /unban, /banned (admin, bot's PM only).

Banned users' PM messages (text/media) are silently ignored — no forward
to admin, no FAQ reply, no AI reply. The ban applies to the bot's inbox
only; it does not ban anyone from the group.

Targeting: reply to a forwarded member message, or /ban <user_id>.
"""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes, filters

import database as db
from utils import command_text, mention_html


def _is_pm_admin(update) -> bool:
    """Only the stored bound-group admin may use these commands."""
    _, admin_id = db.get_bound()
    return bool(admin_id) and update.effective_user.id == admin_id


def _resolve_target(update):
    """(member_id, member_name|None) from reply-to-forwarded or /cmd <id>."""
    msg = update.effective_message
    reply_to = msg.reply_to_message
    if reply_to:
        member_id, member_name = db.lookup_forward(reply_to.message_id)
        if member_id:
            return member_id, member_name
    arg = command_text(update)
    if arg:
        try:
            return int(arg.split()[0]), None
        except (ValueError, IndexError):
            pass
    return None, None


def _deny(update):
    return update.effective_message.reply_text(
        "❌ শুধু অ্যাডমিন (bot-এর PM-এ) এই কমান্ড ব্যবহার করতে পারেন।")


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or not _is_pm_admin(update):
        return await _deny(update)
    _, admin_id = db.get_bound()
    target_id, target_name = _resolve_target(update)
    if not target_id:
        return await update.effective_message.reply_text(
            "ব্যবহার: forward করা মেসেজে reply দিয়ে /ban\n"
            "অথবা: /ban <user_id>")
    if target_id == admin_id:
        return await update.effective_message.reply_text(
            "❌ অ্যাডমিনকে ব্যান করা যাবে না।")
    db.ban_user(target_id, target_name or "")
    await update.effective_message.reply_text(
        f"✅ {mention_html(target_id, target_name or str(target_id))} "
        "ব্যান হয়েছে।",
        parse_mode=ParseMode.HTML)


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or not _is_pm_admin(update):
        return await _deny(update)
    target_id, _ = _resolve_target(update)
    if not target_id:
        return await update.effective_message.reply_text(
            "ব্যবহার: forward করা মেসেজে reply দিয়ে /unban\n"
            "অথবা: /unban <user_id>")
    if db.unban_user(target_id):
        await update.effective_message.reply_text("✅ আনব্যান হয়েছে।")
    else:
        await update.effective_message.reply_text("❌ সে ব্যান তালিকায় নেই।")


async def banned(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or not _is_pm_admin(update):
        return await _deny(update)
    rows = db.list_banned()
    if not rows:
        return await update.effective_message.reply_text("📭 কেউ ব্যান নেই।")
    lines = ["🚫 <b>ব্যান তালিকা:</b>"]
    for uid, name in rows:
        lines.append(
            f"• {mention_html(uid, name or str(uid))} — <code>{uid}</code>")
    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML)


def register(app):
    app.add_handler(CommandHandler("ban", ban,
                                   filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("unban", unban,
                                   filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("banned", banned,
                                   filters=filters.ChatType.PRIVATE))
