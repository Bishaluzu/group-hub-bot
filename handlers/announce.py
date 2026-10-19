"""Group binding + announcements from the admin's PM.

/setgroup            (in group, admin) — bind this group
/announce <text>     (admin PM) — post to the bound group
plain message        (admin PM) — also posted to the bound group, no command needed
/autopin on|off      (admin: group or PM) — auto-pin announcements
/hubstatus           (admin PM) — show binding status
"""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

import database as db
from utils import (admin_in_group, command_text, post_announcement,
                   require_pm_admin)
from .truth import truth_keyboard


async def setgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.effective_message.reply_text(
            "❌ /setgroup গ্রুপের ভেতরে দিতে হবে।")
    if not await admin_in_group(update, context):
        return await update.effective_message.reply_text(
            "❌ শুধু অ্যাডমিনরা এই কমান্ড ব্যবহার করতে পারেন।")
    chat_id = update.effective_chat.id
    db.set_bound(chat_id, update.effective_user.id)
    db.seed_keywords(chat_id)
    try:
        title = update.effective_chat.title or chat_id
        await update.effective_message.reply_text(
            f"✅ <b>{title}</b> bind হয়েছে!\n"
            "এখন inbox-এ শুধু লিখলেই (বা /announce &lt;টেক্সট&gt;) এখানে পোস্ট হবে।",
            parse_mode=ParseMode.HTML, reply_markup=truth_keyboard())
    except Exception:
        pass


async def _do_announce(context, chat_id: int, text: str):
    return await post_announcement(context, chat_id, text)


async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin sends /announce <text> in PM -> posted to bound group."""
    if update.effective_chat.type != "private":
        # also allow in group: announce to the same group
        if not await admin_in_group(update, context):
            return await update.effective_message.reply_text(
                "❌ শুধু অ্যাডমিনরা এই কমান্ড ব্যবহার করতে পারেন।")
        text = command_text(update)
        if not text:
            return await update.effective_message.reply_text(
                "ব্যবহার: /announce <টেক্সট>")
        await _do_announce(context, update.effective_chat.id, text)
        return await update.effective_message.reply_text("✅ ঘোষণা পোস্ট হয়েছে।")

    chat_id = await require_pm_admin(update, context)
    if not chat_id:
        return
    text = command_text(update)
    if not text:
        return await update.effective_message.reply_text(
            "ব্যবহার: /announce <টেক্সট>\nউদাহরণ: /announce আজ রাত ৯টায় লাইভ! [🎯 Join](https://t.me/x|red)")
    try:
        await _do_announce(context, chat_id, text)
    except Exception as e:
        return await update.effective_message.reply_text(
            f"❌ পোস্ট করা যায়নি: {e}\nবট গ্রুপে অ্যাডমিন আছে তো?")
    await update.effective_message.reply_text("✅ ঘোষণা গ্রুপে পোস্ট হয়েছে।")


async def autopin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        chat_id = await require_pm_admin(update, context)
        if not chat_id:
            return
    else:
        if not await admin_in_group(update, context):
            return await update.effective_message.reply_text(
                "❌ শুধু অ্যাডমিনরা এই কমান্ড ব্যবহার করতে পারেন।")
        chat_id = update.effective_chat.id
    if not context.args or context.args[0].lower() not in ("on", "off"):
        cur = db.get_setting(chat_id, "autopin", "0") == "1"
        return await update.effective_message.reply_text(
            f"বর্তমান: {'on' if cur else 'off'}\nব্যবহার: /autopin <on|off>")
    on = context.args[0].lower() == "on"
    db.set_setting(chat_id, "autopin", "1" if on else "0")
    await update.effective_message.reply_text(
        f"✅ Auto-pin {'on' if on else 'off'}।")


async def hubstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    chat_id, admin_id = db.get_bound()
    if not chat_id:
        return await update.effective_message.reply_text("📭 কোনো গ্রুপ bind করা নেই।")
    try:
        chat = await context.bot.get_chat(chat_id)
        title = chat.title or chat_id
    except Exception:
        title = chat_id
    await update.effective_message.reply_text(
        f"🔗 Bound group: <b>{title}</b>\n🆔 <code>{chat_id}</code>",
        parse_mode=ParseMode.HTML)


def register(app):
    app.add_handler(CommandHandler("setgroup", setgroup))
    app.add_handler(CommandHandler("announce", announce))
    app.add_handler(CommandHandler("autopin", autopin))
    app.add_handler(CommandHandler("hubstatus", hubstatus))
