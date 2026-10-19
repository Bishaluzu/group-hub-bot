"""Shared helpers: admin checks, time parsing, formatting."""

import html
import re
from datetime import datetime, timedelta, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

import database as db

DHAKA = timezone(timedelta(hours=6))  # Asia/Dhaka (no DST)

_HHMM_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
_DELAY_RE = re.compile(r"^(\d+)\s*([smh])$", re.IGNORECASE)
_BUTTON_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_COLOR_MAP = {
    "red": "danger", "danger": "danger",
    "blue": "primary", "primary": "primary",
    "green": "success", "success": "success",
}


def parse_hhmm(s: str):
    """Pure: 'HH:MM' -> (hh, mm) or None."""
    m = _HHMM_RE.match((s or "").strip())
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    return hh, mm


def parse_delay(s: str):
    """Pure: '10s'/'15m'/'2h' -> seconds (int) or None."""
    m = _DELAY_RE.match((s or "").strip())
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    return n * {"s": 1, "m": 60, "h": 3600}[unit]


def current_week() -> str:
    """ISO week key like '2026-W42' for the weekly leaderboard."""
    d = datetime.now(DHAKA).date()
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


async def is_admin_of(bot, chat_id: int, user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


async def admin_in_group(update, context) -> bool:
    """True if issuer is admin/owner of the current group."""
    try:
        m = await update.effective_chat.get_member(update.effective_user.id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


async def require_group_admin(update, context):
    """For group commands. Returns True if issuer is a group admin."""
    if update.effective_chat.type == "private":
        await update.effective_message.reply_text("❌ এই কমান্ড শুধু গ্রুপে কাজ করে।")
        return False
    if not await admin_in_group(update, context):
        await update.effective_message.reply_text("❌ শুধু অ্যাডমিনরা এই কমান্ড ব্যবহার করতে পারেন।")
        return False
    return True


async def require_pm_admin(update, context):
    """For PM admin commands. Returns bound chat_id if issuer admins the bound group."""
    chat_id, _admin_id = db.get_bound()
    if not chat_id:
        await update.effective_message.reply_text(
            "❌ কোনো গ্রুপ bind করা নেই। গ্রুপে গিয়ে /setgroup দিন।")
        return 0
    if not await is_admin_of(context.bot, chat_id, update.effective_user.id):
        await update.effective_message.reply_text("❌ শুধু গ্রুপ অ্যাডমিনরা এই কমান্ড ব্যবহার করতে পারেন।")
        return 0
    return chat_id


async def resolve_target_chat(update, context):
    """Return (chat_id, error_msg) for group-targeting admin commands.

    Works from both the group itself and the bot's PM (inbox):
    - PM: targets the /setgroup-bound group; sender must be admin/owner of it.
    - group: targets this chat; sender must be admin/owner of it.
    On failure returns (0, <Bengali error message>).
    """
    user_id = update.effective_user.id
    if update.effective_chat.type == "private":
        chat_id, _admin_id = db.get_bound()
        if not chat_id:
            return 0, "❌ আগে গ্রুপে গিয়ে /setgroup দিন।"
        if not await is_admin_of(context.bot, chat_id, user_id):
            return 0, "❌ শুধু অ্যাডমিনরা এই কমান্ড ব্যবহার করতে পারেন।"
        return chat_id, None
    if not await admin_in_group(update, context):
        return 0, "❌ শুধু অ্যাডমিনরা এই কমান্ড ব্যবহার করতে পারেন।"
    return update.effective_chat.id, None


def mention_html(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{html.escape(name or "user")}</a>'


def command_text(update) -> str:
    """Raw text after the command, preserving line breaks."""
    msg = update.effective_message
    text = msg.text or msg.caption or ""
    parts = text.split(None, 1)
    return parts[1].strip() if len(parts) > 1 else ""


def extract_buttons(text: str):
    """Parse [label](url) or [label](url|color) -> (clean_text, markup|None)."""
    buttons = []

    def _repl(m):
        label, url = m.group(1).strip(), m.group(2).strip()
        style = None
        if "|" in url:
            url, color = url.rsplit("|", 1)
            url = url.strip()
            style = _COLOR_MAP.get(color.strip().lower())
        kwargs = {"url": url}
        if style:
            kwargs["style"] = style
        buttons.append(InlineKeyboardButton(label, **kwargs))
        return ""

    clean = _BUTTON_RE.sub(_repl, text).strip()
    if not buttons:
        return text, None
    markup = InlineKeyboardMarkup([[b] for b in buttons])
    return clean, markup


def progress_bar(pct: float, width: int = 8) -> str:
    """Pure: 0-100 -> '▓▓▓░░░ 45%' style bar."""
    pct = max(0.0, min(100.0, pct))
    filled = int(round(pct / 100 * width))
    return "▓" * filled + "░" * (width - filled) + f" {pct:.0f}%"


def fmt_hms(total_seconds: int) -> str:
    """Pure: seconds -> '12:34' or '1:02:03'."""
    total_seconds = max(0, int(total_seconds))
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


async def notify_admin(context: ContextTypes.DEFAULT_TYPE, text: str,
                       parse_mode=None, reply_markup=None) -> bool:
    """Send a PM to the bound-group admin. Returns False if no admin / failed."""
    _chat_id, admin_id = db.get_bound()
    if not admin_id:
        return False
    try:
        await context.bot.send_message(
            admin_id, text, parse_mode=parse_mode, reply_markup=reply_markup,
            disable_web_page_preview=True)
        return True
    except Exception:
        return False
