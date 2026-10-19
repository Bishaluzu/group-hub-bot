"""Bengali quiz game: /quiz -> 4 buttons, +10 for correct. /score leaderboard."""

import html
import random

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

import database as db

# (question, [opt0..opt3], correct_index)
QUESTIONS = [
    ("বাংলাদেশের জাতীয় ফল কোনটি?", ["আম", "কাঁঠাল", "লিচু", "পেয়ারা"], 1),
    ("বাংলাদেশের রাজধানী কোনটি?", ["চট্টগ্রাম", "ঢাকা", "খুলনা", "রাজশাহী"], 1),
    ("সূর্য কোন দিকে ওঠে?", ["পশ্চিম", "উত্তর", "পূর্ব", "দক্ষিণ"], 2),
    ("এক সপ্তাহে কয় দিন?", ["৫", "৬", "৭", "৮"], 2),
    ("বাংলাদেশের জাতীয় মাছ কোনটি?", ["রুই", "ইলিশ", "কাতলা", "পাবদা"], 1),
    ("পানির রাসায়নিক সংকেত কী?", ["CO2", "H2O", "O2", "NaCl"], 1),
    ("বাংলা নববর্ষ কোন মাসে?", ["চৈত্র", "বৈশাখ", "জ্যৈষ্ঠ", "আষাঢ়"], 1),
    ("ক্রিকেটে এক ওভারে কয় বল?", ["৫", "৬", "৮", "১০"], 1),
    ("বাংলাদেশের মুদ্রার নাম কী?", ["রুপি", "টাকা", "ডলার", "দিনার"], 1),
    ("সবচেয়ে বড় গ্রহ কোনটি?", ["পৃথিবী", "মঙ্গল", "বৃহস্পতি", "শনি"], 2),
    ("কম্পিউটারের জনক কে?", ["নিউটন", "চার্লস ব্যাবেজ", "আইনস্টাইন", "এডিসন"], 1),
    ("বাংলাদেশ কবে স্বাধীন হয়?", ["১৯৪৭", "১৯৫২", "১৯৭১", "১৯৭২"], 2),
]

POINTS = 10
# (chat_id, msg_id) -> {"correct": int, "done": set(user_id)}
ACTIVE = {}


async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.effective_message.reply_text("❌ /quiz গ্রুপে খেলুন।")
    q_text, opts, correct = random.choice(QUESTIONS)
    order = list(range(4))
    random.shuffle(order)
    shown = [opts[i] for i in order]
    correct_shown = order.index(correct)
    rows = [[InlineKeyboardButton(f"{chr(65 + i)}. {o[:28]}",
                                 callback_data=f"qz:{correct_shown}:{i}")]
            for i, o in enumerate(shown)]
    msg = await update.effective_message.reply_text(
        f"🧠 <b>Quiz:</b> {html.escape(q_text)}\n\nসঠিক উত্তরে <b>+{POINTS}</b> পয়েন্ট!",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(rows))
    ACTIVE[(update.effective_chat.id, msg.message_id)] = {
        "correct": correct_shown, "done": set()}


async def quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try:
        _, correct_s, picked_s = q.data.split(":")
        correct, picked = int(correct_s), int(picked_s)
    except ValueError:
        return await q.answer()
    key = (q.message.chat_id, q.message.message_id)
    state = ACTIVE.get(key)
    uid = q.from_user.id
    db.touch_user(uid, q.from_user.first_name or "",
                  q.from_user.username or "")
    if state and uid in state["done"]:
        return await q.answer("তুমি আগেই উত্তর দিয়েছো!", show_alert=False)
    name = q.from_user.first_name or "user"
    if picked == correct:
        total = db.add_quiz_score(q.message.chat_id, uid, name, POINTS)
        if state:
            state["done"].add(uid)
        await q.answer(f"✅ সঠিক! +{POINTS} (মোট: {total})", show_alert=True)
    else:
        if state:
            state["done"].add(uid)
        await q.answer("❌ ভুল উত্তর!", show_alert=False)


async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.effective_message.reply_text("❌ /score গ্রুপে দেখুন।")
    rows = db.top_quiz(update.effective_chat.id)
    if not rows:
        return await update.effective_message.reply_text(
            "📭 এখনো কেউ পয়েন্ট পায়নি। /quiz খেলুন!")
    lines = ["🏆 <b>Quiz Leaderboard:</b>"]
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{medal} {html.escape(r['name'])} — <b>{r['score']}</b>")
    await update.effective_message.reply_text("\n".join(lines),
                                              parse_mode=ParseMode.HTML)


def register(app):
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CallbackQueryHandler(quiz_callback, pattern=r"^qz:\d:\d$"))
