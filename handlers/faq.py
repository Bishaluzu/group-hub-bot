"""FAQ auto-replies: /setfaq, /delfaq, /faqs + group watcher.

/setfaq <keyword> | <reply>   (admin: group or PM)
/delfaq <keyword>             (admin: group or PM)
/faqs                         (anyone)
Group text messages auto-reply on keyword match.
"""

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

import database as db
from utils import admin_in_group, command_text, require_pm_admin


async def _admin_here(update, context) -> int:
    """Return the target chat_id if issuer is admin (group or PM). 0 = denied."""
    if update.effective_chat.type == "private":
        return await require_pm_admin(update, context)
    if not await admin_in_group(update, context):
        await update.effective_message.reply_text(
            "❌ শুধু অ্যাডমিনরা এই কমান্ড ব্যবহার করতে পারেন।")
        return 0
    return update.effective_chat.id


async def setfaq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = await _admin_here(update, context)
    if not chat_id:
        return
    raw = command_text(update)
    if "|" not in raw:
        return await update.effective_message.reply_text(
            "ব্যবহার: /setfaq <শব্দ> | <উত্তর>\nউদাহরণ: /setfaq দাম | 💰 30 টাকা = 1 show")
    kw, reply = [p.strip() for p in raw.split("|", 1)]
    if not kw or not reply:
        return await update.effective_message.reply_text("❌ শব্দ ও উত্তর দুটোই দিন।")
    db.save_faq(kw, reply)
    await update.effective_message.reply_text(f"✅ FAQ যোগ হয়েছে: <b>{kw}</b>",
                                              parse_mode=ParseMode.HTML)


async def delfaq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = await _admin_here(update, context)
    if not chat_id:
        return
    kw = command_text(update).strip().lower()
    if not kw:
        return await update.effective_message.reply_text("ব্যবহার: /delfaq <শব্দ>")
    if db.delete_faq(kw):
        await update.effective_message.reply_text(f"✅ <b>{kw}</b> মুছে ফেলা হয়েছে।",
                                                  parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text("❌ এমন FAQ নেই।")


async def faqs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = db.list_faqs()
    if not rows:
        return await update.effective_message.reply_text("📭 কোনো FAQ নেই।")
    lines = ["❓ <b>FAQs:</b>"]
    for kw, reply in rows:
        preview = reply[:60] + "…" if len(reply) > 60 else reply
        lines.append(f"• <b>{kw}</b> → {preview}")
    await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def faq_watcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Group text -> FAQ auto-reply."""
    msg = update.effective_message
    if msg.from_user.is_bot:
        return
    text = msg.text or msg.caption or ""
    if not text:
        return
    reply = db.find_faq(text)
    if reply:
        try:
            await context.bot.send_chat_action(msg.chat_id, ChatAction.TYPING)
        except Exception:
            pass
        await msg.reply_text(reply)


def register(app):
    app.add_handler(CommandHandler("setfaq", setfaq))
    app.add_handler(CommandHandler("delfaq", delfaq))
    app.add_handler(CommandHandler("faqs", faqs))
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
                       faq_watcher),
        group=2)
