"""18+ Truth Game: dice roll -> question -> reply -> Q+A card.

- /truth18 (anyone, group/PM): animated dice, then a random 18+ question.
- /settruth18, /deltruth, /edittruth, /truthlist, /gametimer (admin).
- Suggest a question via the [➕ ...] button (or /suggest): admin
  approves / edits / rejects in PM.
- Permanent reply keyboard button "🎲 18+ প্রশ্ন" in group + PM.
"""

import asyncio
import html
import logging
import os
import random
import re

from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      KeyboardButton, ReplyKeyboardMarkup, Update)
from telegram.constants import ParseMode
from telegram.ext import (ApplicationHandlerStop, CallbackQueryHandler,
                          CommandHandler, ContextTypes, MessageHandler,
                          filters)

import database as db
from utils import (admin_in_group, command_text, mention_html,
                   require_pm_admin)

logger = logging.getLogger("hub.truth")

# Dice promo video shipped with the bot (assets/dice_promo.mp4).
_ASSETS_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "assets"))
_PROMO_VIDEO_PATH = os.path.join(_ASSETS_DIR, "dice_promo.mp4")


async def _send_promo_video(context, chat_id: int):
    """Send the dice promo video after the dice animation.

    First send uploads from assets/dice_promo.mp4 and caches the
    file_id in bot_data; later rounds reuse the cached file_id.
    Returns the sent message or None on failure.
    """
    bot_data = getattr(context, "bot_data", None) or {}
    file_id = bot_data.get("dice_promo_file_id")
    vmsg = None
    try:
        if file_id:
            vmsg = await context.bot.send_video(chat_id, video=file_id)
        elif os.path.isfile(_PROMO_VIDEO_PATH):
            with open(_PROMO_VIDEO_PATH, "rb") as f:
                vmsg = await context.bot.send_video(chat_id, video=f)
            try:
                context.bot_data["dice_promo_file_id"] = vmsg.video.file_id
            except Exception:
                pass
    except Exception:
        vmsg = None
    return vmsg

BUILT_IN_TRUTHS = [
    "🔞 সবচেয়ে naughty স্বপ্ন কী দেখেছো?",
    "🔞 কখনো কাউকে kiss করার সময় ধরা খেয়েছো?",
    "🔞 তোমার শরীরের কোন অংশটা সবচেয়ে attractive মনে হয়?",
    "🔞 কখনো মাঝরাতে কাউকে miss করে উল্টাপাল্টা মেসেজ দিয়েছো?",
    "🔞 প্রথম crush-কে নিয়ে কখনো কল্পনায় হারিয়ে গেছো?",
    "🔞 কখনো কারো ফোনে গোপন ছবি দেখে ফেলেছো?",
    "🔞 বিছানায় সবচেয়ে awkward মুহূর্ত কোনটা ছিল?",
    "🔞 কখনো public place-এ দুষ্টুমি করেছো?",
    "🔞 তোমার secret fantasy কী? 😏",
    "🔞 কখনো কাউকে দেখে ভেতরে ভেতরে পাগল হয়েছো?",
    "🔞 সবচেয়ে hot ড্রেস কোনটা পরেছো?",
    "🔞 কখনো মিথ্যা বলে কারো সাথে দেখা করতে গেছো?",
    "🔞 রাতে ঘুমানোর আগে কী ভাবো? 😏",
    "🔞 কখনো কারো দিকে তাকিয়ে ধরা খেয়েছো?",
    "🔞 কখনো বাথরুমে আয়নার সামনে পোজ দিয়েছো? 🪞",
    "🔞 কোন মেয়েকে দেখে প্রথমবার বুক ধড়ফড় করেছিল?",
    "🔞 কখনো কোন মেয়ের ছবি সেভ করে রেখেছো?",
    "🔞 মেয়েদের কোন ড্রেসে সবচেয়ে hot লাগে?",
    "🔞 কখনো কোন মেয়েকে impress করতে মিথ্যা বলেছো?",
    "🔞 রাতে কোন মেয়ের কথা ভেবে ঘুমাতে দেরি হয়েছে?",
    "🔞 কখনো crush-এর নাম ফোনে অন্য নামে সেভ করেছো?",
    "🔞 কোন মেয়ের হাসি সবচেয়ে সুন্দর লাগে?",
    "🔞 কখনো মেয়ের মেসেজের reply-এর জন্য বারবার ফোন চেক করেছো?",
    "🔞 প্রথম কোন মেয়েকে ভালো লেগেছিল?",
    "🔞 কখনো কোন মেয়ের পেছনে লুকিয়ে ফলো করেছো?",
    "🔞 মেয়েদের কোন পারফিউমের গন্ধ পাগল করে?",
    "🔞 কখনো স্বপ্নে কোন মেয়েকে দেখে হেসে ঘুম ভেঙেছে?",
    "🔞 কোন মেয়েকে দেখে মনে হয়েছে \"ওকে বিয়ে করবো\"?",
    "🔞 কখনো মেয়ের সামনে স্মার্ট সাজার চেষ্টায় বোকা হয়েছো?",
    "🔞 মেয়েদের লম্বা চুল না ছোট চুল — কোনটা বেশি টানে?",
    "🔞 কখনো কোন মেয়ের জন্য বন্ধুর সাথে ঝগড়া করেছো?",
    "🔞 শাড়ি না ওয়েস্টার্ন — মেয়েদের কোন লুকে দুর্বল?",
    "🔞 কখনো মেয়েকে মেসেজ লিখে ডিলিট করেছো?",
    "🔞 কোন মেয়ের চোখ সবচেয়ে সুন্দর?",
    "🔞 কখনো crush-এর বাড়ির সামনে দিয়ে অকারণে হেঁটে গেছো?",
    "🔞 কখনো কোন মেয়েকে ভুলে \"জান\" বলে ফেলেছো? 😂",
    "🔞 প্রথম প্রপোজ কাকে করেছিলে, কী হয়েছিল?",
    "🔞 কখনো মেয়ের রিপ্লাই না পেয়ে সারারাত জেগে ছিলে?",
    "🔞 কোন নায়িকাকে দেখে crush খেয়েছো?",
    "🔞 মেয়েদের হাসির শব্দে কখনো মন গলেছে?",
    "🔞 কখনো কোন মেয়ের জন্য পড়াশোনা/কাজ ভুলে গেছো?",
    "🔞 লিপস্টিকের কোন শেড মেয়েদের উপর সবচেয়ে hot লাগে? 💋",
    "🔞 কখনো মেয়েকে দেখে বন্ধুদের সামনে লজ্জা পেয়েছো?",
    "🔞 কোন মেয়ের সাথে বৃষ্টিতে ভিজতে চাও? 🌧️",
    "🔞 কখনো মেয়ের ছবিতে লাইক দিয়ে সাথে সাথে আনলাইক করেছো? 😂",
    "🔞 মেয়েদের কোন অভ্যাসটা সবচেয়ে cute লাগে?",
    "🔞 কখনো crush-কে স্বপ্নে বিয়ে করেছো? 💍",
    "🔞 কোন মেয়ের গলার স্বর শুনে প্রেমে পড়েছো?",
    "🔞 সত্যি বলো — এখন কার কথা ভাবছো? 😏",
]

HEADER = "⚠️ <b>যা বলবি সত্যি করে বলবি, পাম মারবি না!</b> ⚠️"
GAME_KEY = "🎲 18+ প্রশ্ন"
GAME_KEY_RE = r"^🎲 18\+ প্রশ্ন$"

# round_id -> {"question": str, "owner": int, "chat_id": int}
ROUNDS = {}
# (chat_id, user_id) -> {"kind": "answer", "question": str, "prompt_msg_id": int}
#                     or {"kind": "suggest", "prompt_msg_id": int}
# Last tap wins.
PENDING = {}
# (admin_pm_chat_id, admin_id) -> {"sid": int, "prompt_msg_id": int}
PENDING_ADMIN_EDIT = {}
_round_counter = 0


def truth_keyboard():
    """Persistent reply keyboard with the game button."""
    return ReplyKeyboardMarkup([[KeyboardButton(GAME_KEY)]],
                               resize_keyboard=True)


def _clean(q: str) -> str:
    """Strip a leading 🔞 so the header prefix never doubles up."""
    q = (q or "").strip()
    if q.startswith("🔞"):
        q = q[1:].strip()
    return q


def get_pool():
    """Built-in (minus hidden) + custom questions."""
    hidden = db.list_hidden_truths()
    pool = [t for i, t in enumerate(BUILT_IN_TRUTHS) if i not in hidden]
    pool.extend(t for _id, t in db.list_custom_truths())
    return pool


def _gametimer_seconds(chat_id: int) -> int:
    v = (db.get_setting(chat_id, "gametimer", "") or "").strip()
    return int(v) if v.isdigit() and int(v) > 0 else 0


async def _delete_job(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data
    try:
        await context.bot.delete_message(d["chat_id"], d["msg_id"])
    except Exception:
        pass


def _schedule_delete(context, chat_id: int, msg_id: int):
    secs = _gametimer_seconds(chat_id)
    if secs and getattr(context, "job_queue", None):
        try:
            context.job_queue.run_once(
                _delete_job, secs,
                data={"chat_id": chat_id, "msg_id": msg_id},
                name=f"truthdel_{chat_id}_{msg_id}")
        except Exception:
            pass


def _cb_new(owner_id: int, rid: int) -> str:
    return f"truth:new:{owner_id}:{rid}"


def _cb_reply(owner_id: int, rid: int) -> str:
    return f"truth:reply:{owner_id}:{rid}"


def _next_round(question: str, owner_id: int, chat_id: int) -> int:
    global _round_counter
    _round_counter += 1
    ROUNDS[_round_counter] = {"question": question, "owner": owner_id,
                              "chat_id": chat_id}
    return _round_counter


async def _admin_chat(update, context) -> int:
    """Target chat_id if issuer is admin (group or PM). 0 = denied."""
    if update.effective_chat.type == "private":
        return await require_pm_admin(update, context)
    if not await admin_in_group(update, context):
        await update.effective_message.reply_text(
            "❌ শুধু অ্যাডমিনরা এই কমান্ড ব্যবহার করতে পারেন।")
        return 0
    return update.effective_chat.id


async def _new_round(context, chat_id: int, user_id: int):
    """Dice animation -> question message with Reply / new-question buttons."""
    pool = get_pool()
    if not pool:
        await context.bot.send_message(chat_id, "❌ প্রশ্নের তালিকা খালি।")
        return
    try:
        dice_msg = await context.bot.send_dice(
            chat_id, emoji="🎲", reply_markup=truth_keyboard())
    except Exception:
        dice_msg = None
    _schedule_delete(context, chat_id,
                     dice_msg.message_id if dice_msg else 0)
    # Promo video right after the dice (arrives while it animates).
    vmsg = await _send_promo_video(context, chat_id)
    _schedule_delete(context, chat_id,
                     vmsg.message_id if vmsg else 0)
    await asyncio.sleep(4)
    try:
        value = dice_msg.dice.value
    except Exception:
        value = random.randint(1, 6)
    question = pool[value % len(pool)]
    rid = _next_round(question, user_id, chat_id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Reply",
                              callback_data=_cb_reply(user_id, rid)),
         InlineKeyboardButton("🎲 নতুন প্রশ্ন",
                              callback_data=_cb_new(user_id, rid))],
        [InlineKeyboardButton("➕ চাইলে নিজে একটা প্রশ্ন অ্যাড করো",
                              callback_data=f"truth:addq:{user_id}")],
    ])
    qmsg = await context.bot.send_message(
        chat_id, f"{HEADER}\n🔞 {_clean(question)}",
        parse_mode=ParseMode.HTML, reply_markup=kb)
    _schedule_delete(context, chat_id, qmsg.message_id)


# ------------------------------------------------------------------ commands
async def truth18(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private" and db.is_banned(
            update.effective_user.id):
        return
    user = update.effective_user
    db.touch_user(user.id, user.full_name, user.username or "")
    await _new_round(context, update.effective_chat.id, user.id)


async def keyboard_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permanent keyboard button -> same as /truth18. Stop propagation so
    the PM router doesn't forward the button text to the admin."""
    if update.effective_chat.type == "private" and db.is_banned(
            update.effective_user.id):
        raise ApplicationHandlerStop()
    user = update.effective_user
    db.touch_user(user.id, user.full_name, user.username or "")
    await _new_round(context, update.effective_chat.id, user.id)
    raise ApplicationHandlerStop()


async def settruth18(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_chat(update, context):
        return
    text = command_text(update)
    if not text:
        return await update.effective_message.reply_text(
            "ব্যবহার: /settruth18 <প্রশ্ন>")
    tid = db.add_custom_truth(text)
    await update.effective_message.reply_text(
        f"✅ প্রশ্ন যোগ হয়েছে। (id: {tid})")


async def deltruth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_chat(update, context):
        return
    arg = command_text(update).strip()
    m = re.fullmatch(r"b(\d+)", arg, re.IGNORECASE)
    if m:
        idx = int(m.group(1)) - 1
        if not (0 <= idx < len(BUILT_IN_TRUTHS)):
            return await update.effective_message.reply_text(
                f"❌ b1–b{len(BUILT_IN_TRUTHS)} এর মধ্যে দিন।")
        if idx in db.list_hidden_truths():
            return await update.effective_message.reply_text(
                f"ℹ️ b{idx + 1} ইতিমধ্যে লুকানো আছে।")
        db.hide_builtin_truth(idx)
        return await update.effective_message.reply_text(
            f"✅ b{idx + 1} লুকানো হয়েছে।")
    if arg.isdigit():
        if db.delete_custom_truth(int(arg)):
            return await update.effective_message.reply_text(
                f"✅ {arg} নম্বর প্রশ্ন মুছে ফেলা হয়েছে।")
        return await update.effective_message.reply_text("❌ পাওয়া যায়নি।")
    await update.effective_message.reply_text(
        "ব্যবহার: /deltruth <id>  বা  /deltruth b<নম্বর>\n"
        "উদাহরণ: /deltruth 3  |  /deltruth b3")


async def edittruth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_chat(update, context):
        return
    raw = command_text(update)
    parts = raw.split(None, 1)
    if len(parts) < 2 or not parts[0].isdigit():
        return await update.effective_message.reply_text(
            "ব্যবহার: /edittruth <id> <নতুন প্রশ্ন>")
    if db.update_custom_truth(int(parts[0]), parts[1].strip()):
        await update.effective_message.reply_text("✅ প্রশ্ন এডিট হয়েছে।")
    else:
        await update.effective_message.reply_text("❌ পাওয়া যায়নি।")


async def truthlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_chat(update, context):
        return
    hidden = db.list_hidden_truths()
    lines = ["📝 <b>Truth প্রশ্ন (18+):</b>", "", "<b>Built-in:</b>"]
    for i, t in enumerate(BUILT_IN_TRUTHS):
        mark = " 🚫<i>লুকানো</i>" if i in hidden else ""
        lines.append(f"b{i + 1}. {html.escape(_clean(t))}{mark}")
    customs = db.list_custom_truths()
    lines.append("")
    lines.append("<b>Custom:</b>")
    if customs:
        for tid, t in customs:
            lines.append(f"{tid}. {html.escape(_clean(t))}")
    else:
        lines.append("(নেই)")
    text = "\n".join(lines)
    if len(text) > 3800:
        text = text[:3800] + "\n…"
    await update.effective_message.reply_text(text,
                                              parse_mode=ParseMode.HTML)


async def gametimer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = await _admin_chat(update, context)
    if not chat_id:
        return
    arg = command_text(update).strip().lower()
    if not arg:
        secs = _gametimer_seconds(chat_id)
        return await update.effective_message.reply_text(
            f"⏱️ বর্তমান: {'off' if not secs else f'{secs} সেকেন্ড'}\n"
            "ব্যবহার: /gametimer <সেকেন্ড|off>")
    if arg == "off":
        db.set_setting(chat_id, "gametimer", "")
        return await update.effective_message.reply_text(
            "✅ game auto-delete বন্ধ।")
    if arg.isdigit() and int(arg) > 0:
        db.set_setting(chat_id, "gametimer", arg)
        return await update.effective_message.reply_text(
            f"✅ {arg} সেকেন্ড পর game message auto-delete হবে।")
    await update.effective_message.reply_text(
        "ব্যবহার: /gametimer <সেকেন্ড|off>")


# ------------------------------------------------------------------ suggest
async def _notify_admin_suggestion(context, user, text: str, sid: int):
    """Send the suggestion to the admin's PM with Approve/Edit/Reject."""
    _chat_id, admin_id = db.get_bound()
    if not admin_id:
        return
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve",
                             callback_data=f"truthsug:ok:{sid}"),
        InlineKeyboardButton("✏️ এডিট",
                             callback_data=f"truthsug:edit:{sid}"),
        InlineKeyboardButton("❌ Reject",
                             callback_data=f"truthsug:no:{sid}"),
    ]])
    uname = f" (@{user.username})" if user.username else ""
    try:
        await context.bot.send_message(
            admin_id,
            f"💡 <b>নতুন প্রশ্ন suggestion</b>\n"
            f"👤 {mention_html(user.id, user.full_name)}{uname}\n"
            f"🔞 {html.escape(text)}",
            parse_mode=ParseMode.HTML, reply_markup=kb)
    except Exception:
        pass


async def _submit_suggestion(context, user, text: str):
    """Store a suggestion and route it to the admin. Shared by the
    [➕ ...] button flow and /suggest."""
    sid = db.add_suggestion(user.id, user.full_name, text)
    await _notify_admin_suggestion(context, user, text, sid)
    return sid


async def suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alternate path: /suggest <text> (anyone, group/PM, not banned)."""
    if update.effective_chat.type == "private" and db.is_banned(
            update.effective_user.id):
        return
    text = command_text(update)
    if not text:
        return await update.effective_message.reply_text(
            "ব্যবহার: /suggest <তোমার প্রশ্ন>")
    user = update.effective_user
    db.touch_user(user.id, user.full_name, user.username or "")
    await _submit_suggestion(context, user, text)
    await update.effective_message.reply_text(
        "✅ তোমার প্রশ্ন পাঠানো হয়েছে, অ্যাডমিন approve করলে যোগ হবে।")


async def sug_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    m = re.fullmatch(r"truthsug:(ok|edit|no):(\d+)", q.data or "")
    if not m:
        return
    action, sid = m.group(1), int(m.group(2))
    _chat_id, admin_id = db.get_bound()
    if not admin_id or q.from_user.id != admin_id:
        return await q.answer("❌ শুধু অ্যাডমিন।", show_alert=True)
    sug = db.get_suggestion(sid)
    if not sug or sug["status"] != "pending":
        return await q.answer("ইতিমধ্যে সিদ্ধান্ত নেওয়া হয়েছে।")
    text, uid = sug["text"], sug["user_id"]
    try:
        if action == "ok":
            if not db.set_suggestion_status(sid, "approved"):
                return await q.answer("ইতিমধ্যে সিদ্ধান্ত নেওয়া হয়েছে।")
            db.add_custom_truth(text)
            await q.edit_message_text(f"✅ যোগ হয়েছে: {text}")
            try:
                await context.bot.send_message(
                    uid, "✅ তোমার প্রশ্ন যোগ হয়েছে! 🎉")
            except Exception:
                pass
        elif action == "no":
            if not db.set_suggestion_status(sid, "rejected"):
                return await q.answer("ইতিমধ্যে সিদ্ধান্ত নেওয়া হয়েছে।")
            await q.edit_message_text(f"❌ বাতিল: {text}")
            try:
                await context.bot.send_message(
                    uid, "❌ তোমার প্রশ্ন approve হয়নি।")
            except Exception:
                pass
        else:  # edit — admin sends the corrected text next in PM
            key = (q.message.chat.id, q.from_user.id)
            if key in PENDING_ADMIN_EDIT:
                return await q.answer("✍️ ইতিমধ্যে সংশোধিত প্রশ্নের অপেক্ষায়…")
            try:
                prompt = await q.message.reply_text(
                    "✍️ সংশোধিত প্রশ্ন লিখে পাঠাও")
            except Exception:
                return
            PENDING_ADMIN_EDIT[key] = {"sid": sid,
                                       "prompt_msg_id": prompt.message_id}
            return await q.answer()
    except Exception:
        pass
    await q.answer()


async def admin_edit_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel a pending admin edit when the admin types a command instead.

    Runs before command handlers (group=-1); never stops propagation."""
    user = update.effective_user
    _c, admin_id = db.get_bound()
    if (update.effective_chat.type == "private" and admin_id
            and user.id == admin_id):
        PENDING_ADMIN_EDIT.pop((update.effective_chat.id, user.id), None)


# ------------------------------------------------------------------ game flow
async def truth_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data or ""
    m = re.fullmatch(r"truth:(new|reply):(\d+):(\d+)", data)
    m_add = re.fullmatch(r"truth:addq:(\d+)", data)
    if not m and not m_add:
        return
    tapper = q.from_user
    chat = q.message.chat
    try:
        await q.answer()
    except Exception:
        pass
    if m_add:
        # suggest-a-question button: anyone (owner irrelevant)
        if chat.type == "private" and db.is_banned(tapper.id):
            return
        PENDING[(chat.id, tapper.id)] = {"kind": "suggest"}
        try:
            prompt = await q.message.reply_text(
                "✍️ তোমার প্রশ্ন লিখে পাঠাও…")
        except Exception:
            return
        PENDING[(chat.id, tapper.id)]["prompt_msg_id"] = prompt.message_id
        _schedule_delete(context, chat.id, prompt.message_id)
        return
    kind, owner_id, rid = m.group(1), int(m.group(2)), int(m.group(3))
    if kind == "reply":
        if chat.type == "private" and db.is_banned(tapper.id):
            return
        rnd = ROUNDS.get(rid)
        question = (rnd or {}).get("question", "")
        if not question:
            return
        try:
            prompt = await q.message.reply_text(
                "✍️ তোমার উত্তর লিখে পাঠাও…")
        except Exception:
            return
        PENDING[(chat.id, tapper.id)] = {
            "kind": "answer", "question": question,
            "prompt_msg_id": prompt.message_id}
        _schedule_delete(context, chat.id, prompt.message_id)
        return
    # new question
    rnd = ROUNDS.get(rid)
    if tapper.id == owner_id and rnd:
        try:
            await context.bot.delete_message(chat.id,
                                             q.message.message_id)
        except Exception:
            pass
    await _new_round(context, chat.id, tapper.id)


async def _drop_msgs(context, chat_id: int, msg, prompt_msg_id: int):
    try:
        await context.bot.delete_message(chat_id, prompt_msg_id)
    except Exception:
        pass
    try:
        await msg.delete()
    except Exception:
        pass


async def answer_watcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Consume pending answer / suggestion / admin-edit text: the user's next
    plain-text non-command message.

    Registered at group=-1 so it runs before the PM router / FAQ watchers.
    """
    msg = update.effective_message
    text = (msg.text or "").strip()
    if not text or text.startswith("/"):
        return
    chat = update.effective_chat
    user = update.effective_user
    key = (chat.id, user.id)

    # 1) admin editing a suggested question (PM only)
    _c, admin_id = db.get_bound()
    if chat.type == "private" and admin_id and user.id == admin_id:
        edit = PENDING_ADMIN_EDIT.pop(key, None)
        if edit:
            sug = db.get_suggestion(edit["sid"])
            if not sug or sug["status"] != "pending":
                raise ApplicationHandlerStop()
            await _drop_msgs(context, chat.id, msg, edit["prompt_msg_id"])
            db.add_custom_truth(text)
            db.set_suggestion_status(edit["sid"], "approved")
            try:
                await context.bot.send_message(
                    chat.id, f"✅ যোগ হয়েছে: {text}")
            except Exception:
                pass
            try:
                await context.bot.send_message(
                    sug["user_id"], "✅ তোমার প্রশ্ন যোগ হয়েছে! 🎉")
            except Exception:
                pass
            raise ApplicationHandlerStop()

    # 2) member pending action (answer or suggest) — last tap wins
    entry = PENDING.pop(key, None)
    if not entry:
        return
    if chat.type == "private" and db.is_banned(user.id):
        raise ApplicationHandlerStop()
    await _drop_msgs(context, chat.id, msg, entry.get("prompt_msg_id", 0))

    if entry.get("kind") == "suggest":
        db.touch_user(user.id, user.full_name, user.username or "")
        await _submit_suggestion(context, user, text)
        try:
            await context.bot.send_message(
                chat.id,
                "✅ তোমার প্রশ্ন পাঠানো হয়েছে, অ্যাডমিন approve করলে যোগ হবে।")
        except Exception:
            pass
        raise ApplicationHandlerStop()

    # kind == "answer": post the Q+A card
    mention = mention_html(user.id, user.full_name)
    rid = _next_round(entry["question"], user.id, chat.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 নতুন প্রশ্ন",
                              callback_data=_cb_new(user.id, rid))],
        [InlineKeyboardButton("➕ চাইলে নিজে একটা প্রশ্ন অ্যাড করো",
                              callback_data=f"truth:addq:{user.id}")],
    ])
    card = (f"❓ <b>প্রশ্ন:</b> {html.escape(_clean(entry['question']))}\n"
            f"👤 <b>{mention} এর উত্তর:</b> {html.escape(text)}")
    try:
        sent = await context.bot.send_message(
            chat.id, card, parse_mode=ParseMode.HTML, reply_markup=kb)
    except Exception:
        return
    db.touch_user(user.id, user.full_name, user.username or "")
    _schedule_delete(context, chat.id, sent.message_id)
    raise ApplicationHandlerStop()


def register(app):
    app.add_handler(CommandHandler("truth18", truth18))
    app.add_handler(CommandHandler("settruth18", settruth18))
    app.add_handler(CommandHandler("deltruth", deltruth))
    app.add_handler(CommandHandler("edittruth", edittruth))
    app.add_handler(CommandHandler("truthlist", truthlist))
    app.add_handler(CommandHandler("gametimer", gametimer))
    app.add_handler(CommandHandler("suggest", suggest))
    # keyboard button: group 0 so it runs before the PM router (group 1);
    # the handler itself stops propagation.
    app.add_handler(MessageHandler(filters.Regex(GAME_KEY_RE), keyboard_play))
    # pending-answer watcher: runs before everything else.
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex(GAME_KEY_RE),
        answer_watcher), group=-1)
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.COMMAND, admin_edit_guard),
        group=-1)
    app.add_handler(CallbackQueryHandler(
        truth_callback, pattern=r"^truth:(new|reply|addq)"))
    app.add_handler(CallbackQueryHandler(
        sug_callback, pattern=r"^truthsug:(ok|edit|no):\d+$"))
