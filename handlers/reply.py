"""PM <-> admin reply routing, FAQ auto-reply, Gemini fallback.

- Any member PM (text/media) -> forwarded to the bound admin with a header.
- Admin replies to a forwarded message -> copied back to the member.
- Admin's fresh plain PM (not a reply) -> posted to the bound group as announcement.
- FAQ keyword match -> instant auto-reply in PM (members only).
- No FAQ match + GEMINI_API_KEY set -> short AI reply (members only).
"""

import logging
import os

import requests
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes, MessageHandler, filters

import database as db
from utils import (admin_reply_back, is_admin_of, mention_html, notify_admin,
                   post_announcement)

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


async def pm_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle every non-command PM. Group=1 so commands run first."""
    msg = update.effective_message
    user = update.effective_user
    chat_id, admin_id = db.get_bound()

    # Admin's own PM: replies route to members; fresh messages -> group announcement.
    # Never forwarded, never FAQ/AI.
    if admin_id and user.id == admin_id:
        if await admin_reply_back(update, context):
            return
        if not chat_id:
            await msg.reply_text("❌ আগে গ্রুপে গিয়ে /setgroup দিন।")
            return
        try:
            await post_announcement(context, chat_id, msg.text or "")
        except Exception as e:
            return await msg.reply_text(
                f"❌ পোস্ট করা যায়নি: {e}\nবট গ্রুপে অ্যাডমিন আছে তো?")
        await msg.reply_text("✅ ঘোষণা গ্রুপে পোস্ট হয়েছে।")
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
