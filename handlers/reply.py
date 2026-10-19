"""PM <-> admin reply routing, FAQ auto-reply, Gemini fallback.

- Any member PM (text/media) -> forwarded to the bound admin with a header.
- Admin replies to a forwarded message -> copied back to the member.
- FAQ keyword match -> instant auto-reply in PM.
- No FAQ match + GEMINI_API_KEY set -> short AI reply.
"""

import logging
import os

import requests
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes, MessageHandler, filters

import database as db
from utils import is_admin_of, mention_html, notify_admin

logger = logging.getLogger("hub.reply")

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()

SYSTEM = (
    "You are a friendly assistant for a Telegram paid-show group. "
    "Reply in the SAME language the user writes in (Bengali or English). "
    "Keep every reply short: 1 to 3 lines max. Warm and casual. "
    "Never mention you are an AI model."
)


def ask_gemini(prompt: str) -> str | None:
    """Return AI reply, or None if key missing / error (feature silently off)."""
    if not GEMINI_KEY:
        return None
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_MODEL}:generateContent")
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "generationConfig": {"maxOutputTokens": 250, "temperature": 0.8},
    }
    try:
        r = requests.post(url, params={"key": GEMINI_KEY}, json=body, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.warning("gemini error: %s", e)
        return None


async def _forward_to_admin(update, context, member):
    """Forward a member's PM to the admin and record the mapping."""
    chat_id, admin_id = db.get_bound()
    if not chat_id:
        return
    name = member.first_name or "user"
    uname = f"@{member.username}" if member.username else "no username"
    try:
        header = await context.bot.send_message(
            admin_id,
            f"💬 <b>{mention_html(member.id, name)}</b> ({uname})\n"
            f"🆔 <code>{member.id}</code> — reply দিলে member-এর কাছে যাবে।",
            parse_mode="HTML")
        fwd = await context.bot.forward_message(
            chat_id=admin_id,
            from_chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id)
        db.map_forward(fwd.message_id, member.id, name)
        # also map the header so replying to it works
        db.map_forward(header.message_id, member.id, name)
    except Exception as e:
        logger.warning("forward to admin failed: %s", e)


async def _admin_reply_back(update, context):
    """Admin replied to a forwarded message -> copy it to the member."""
    reply_to = update.effective_message.reply_to_message
    if not reply_to:
        return False
    member_id, member_name = db.lookup_forward(reply_to.message_id)
    if not member_id:
        return False
    try:
        await context.bot.copy_message(
            chat_id=member_id,
            from_chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id,
            caption=(update.effective_message.caption or None))
        await update.effective_message.reply_text(f"✅ {member_name}-এর কাছে পাঠানো হয়েছে।")
    except Exception as e:
        await update.effective_message.reply_text(f"❌ পাঠানো যায়নি: {e}")
    return True


async def pm_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle every non-command PM. Group=1 so commands run first."""
    msg = update.effective_message
    user = update.effective_user
    chat_id, admin_id = db.get_bound()

    # Admin's own PM: only route replies, nothing else.
    if admin_id and user.id == admin_id:
        await _admin_reply_back(update, context)
        return

    text = msg.text or msg.caption or ""

    # 1) FAQ auto-reply (text only)
    if text:
        faq = db.find_faq(text)
        if faq:
            try:
                await context.bot.send_chat_action(msg.chat_id, ChatAction.TYPING)
            except Exception:
                pass
            await msg.reply_text(faq)

    # 2) Gemini fallback for plain text (silently off without key)
    if text and not db.find_faq(text):
        ai = ask_gemini(text)
        if ai:
            await msg.reply_text(ai)
        else:
            await msg.reply_text("✅ মেসেজ পেয়েছি, অ্যাডমিন শীঘ্রই রিপ্লাই দেবে।")

    # 3) Always forward to admin so nothing is missed
    if chat_id:
        await _forward_to_admin(update, context, user)


def register(app):
    # text only here; photos/documents are handled by proof.py
    app.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
                       pm_router),
        group=1)
