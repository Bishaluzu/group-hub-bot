"""Payment proof inbox: member sends photo/document in PM ->
forwarded to the admin with Approve / Reject buttons.

Admin's own PM media: reply to a forwarded message -> routes to that member;
fresh media -> posted to the bound group as announcement."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (CallbackQueryHandler, ContextTypes, MessageHandler,
                          filters)

import database as db
from utils import (admin_reply_back, is_admin_of, mention_html,
                   post_announcement_media)


async def proof_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """PM photo/document from a member -> admin with approve/reject."""
    msg = update.effective_message
    user = update.effective_user
    # Banned users are silently ignored.
    if db.is_banned(user.id):
        return
    chat_id, admin_id = db.get_bound()
    if not chat_id or not admin_id:
        return
    if user.id == admin_id:
        # reply to a forwarded member message -> route to that member
        if await admin_reply_back(update, context):
            return
        # fresh media from admin -> post to group as announcement
        try:
            if msg.photo:
                await post_announcement_media(
                    context, chat_id, caption=msg.caption or "",
                    photo=msg.photo[-1].file_id)
            elif msg.document:
                await post_announcement_media(
                    context, chat_id, caption=msg.caption or "",
                    document=msg.document.file_id)
            else:
                return
        except Exception as e:
            return await msg.reply_text(
                f"❌ পোস্ট করা যায়নি: {e}\nবট গ্রুপে অ্যাডমিন আছে তো?")
        await msg.reply_text("✅ ঘোষণা গ্রুপে পোস্ট হয়েছে।")
        return
    name = user.first_name or "user"
    uname = f"@{user.username}" if user.username else "no username"
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"proof:1:{user.id}",
                             style="success"),
        InlineKeyboardButton("❌ Reject", callback_data=f"proof:0:{user.id}",
                             style="danger"),
    ]])
    try:
        header = await context.bot.send_message(
            admin_id,
            f"🧾 <b>পেমেন্ট প্রমাণ</b>\n👤 {mention_html(user.id, name)} ({uname})\n"
            f"🆔 <code>{user.id}</code>",
            parse_mode=ParseMode.HTML, reply_markup=markup)
        fwd = await context.bot.forward_message(
            chat_id=admin_id, from_chat_id=msg.chat_id,
            message_id=msg.message_id)
        db.map_forward(fwd.message_id, user.id, name)
        db.map_forward(header.message_id, user.id, name)
        await msg.reply_text("✅ প্রমাণ পাঠানো হয়েছে, অ্যাডমিন চেক করবে।")
    except Exception:
        pass


async def proof_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try:
        _, decision, member_s = q.data.split(":")
        member_id = int(member_s)
    except ValueError:
        return await q.answer()
    chat_id, _admin = db.get_bound()
    if not chat_id or not await is_admin_of(context.bot, chat_id, q.from_user.id):
        return await q.answer("❌ শুধু অ্যাডমিন।", show_alert=True)
    ok = decision == "1"
    try:
        if ok:
            await context.bot.send_message(
                member_id, "✅ <b>তোমার পেমেন্ট approve হয়েছে!</b> ধন্যবাদ 🍒",
                parse_mode=ParseMode.HTML)
            await q.edit_message_text("✅ <b>Approved</b>", parse_mode=ParseMode.HTML)
        else:
            await context.bot.send_message(
                member_id, "❌ <b>পেমেন্ট reject হয়েছে।</b> সঠিক প্রমাণ আবার পাঠাও।",
                parse_mode=ParseMode.HTML)
            await q.edit_message_text("❌ <b>Rejected</b>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await q.answer(f"⚠️ {e}", show_alert=True)
        return
    await q.answer("✅ done")


def register(app):
    app.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & (filters.PHOTO | filters.Document.ALL)
                       & ~filters.COMMAND, proof_inbox),
        group=1)
    app.add_handler(CallbackQueryHandler(proof_callback, pattern=r"^proof:[01]:\d+$"))
