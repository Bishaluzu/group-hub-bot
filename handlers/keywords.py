"""Keyword alerts: notify the admin when a member writes watched words.

/setkeywords w1,w2,w3   (admin: group or PM) — replace the list
/keywords               — show current list
Default on /setgroup: দাম, price, live
"""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

import database as db
from utils import admin_in_group, command_text, mention_html, require_pm_admin


async def _admin_chat(update, context) -> int:
    if update.effective_chat.type == "private":
        return await require_pm_admin(update, context)
    if not await admin_in_group(update, context):
        await update.effective_message.reply_text(
            "❌ শুধু অ্যাডমিনরা এই কমান্ড ব্যবহার করতে পারেন।")
        return 0
    return update.effective_chat.id


async def setkeywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = await _admin_chat(update, context)
    if not chat_id:
        return
    raw = command_text(update)
    words = [w.strip() for w in raw.replace("，", ",").split(",") if w.strip()]
    if not words:
        return await update.effective_message.reply_text(
            "ব্যবহার: /setkeywords দাম,price,live")
    db.set_keywords(chat_id, words)
    await update.effective_message.reply_text(
        "✅ Keywords: " + ", ".join(f"<b>{w}</b>" for w in words),
        parse_mode=ParseMode.HTML)


async def keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = await _admin_chat(update, context)
    if not chat_id:
        return
    words = db.list_keywords(chat_id)
    if not words:
        return await update.effective_message.reply_text("📭 কোনো keyword সেট নেই।")
    await update.effective_message.reply_text(
        "🔔 Keywords: " + ", ".join(f"<b>{w}</b>" for w in words),
        parse_mode=ParseMode.HTML)


async def keyword_watcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.from_user.is_bot:
        return
    chat_id = msg.chat_id
    text = msg.text or msg.caption or ""
    if not text:
        return
    word = db.find_keyword(chat_id, text)
    if not word:
        return
    # don't alert on admins' own messages
    try:
        m = await msg.chat.get_member(msg.from_user.id)
        from telegram.constants import ChatMemberStatus
        if m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return
    except Exception:
        pass
    user = msg.from_user
    name = user.first_name or "user"
    preview = text[:200]
    _bchat, admin_id = db.get_bound()
    if not admin_id:
        return
    try:
        await context.bot.send_message(
            admin_id,
            f"🔔 <b>Keyword alert:</b> <code>{word}</code>\n"
            f"👤 {mention_html(user.id, name)}\n💬 {preview}",
            parse_mode=ParseMode.HTML)
    except Exception:
        pass


def register(app):
    app.add_handler(CommandHandler("setkeywords", setkeywords))
    app.add_handler(CommandHandler("keywords", keywords))
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
                       keyword_watcher),
        group=2)
