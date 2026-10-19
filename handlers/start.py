"""/start and /help."""

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

HELP_PM = """👋 <b>Group Hub Bot</b>

<b>অ্যাডমিন (inbox):</b>
/announce &lt;টেক্সট&gt; — গ্রুপে ঘোষণা
/autopin on|off — ঘোষণা auto-pin
/schedule &lt;HH:MM&gt; &lt;টেক্সট&gt; — প্রতিদিন নির্দিষ্ট সময়ে পোস্ট
/cancelschedule — schedule বাতিল
/setdaily &lt;HH:MM&gt; &lt;টেক্সট&gt; — প্রতিদিনের মেসেজ
/setfaq &lt;শব্দ&gt; | &lt;উত্তর&gt; — auto-reply যোগ
/delfaq &lt;শব্দ&gt; — মুছুন
/faqs — তালিকা
/setkeywords w1,w2 — keyword alert
/feedback &lt;টেক্সট&gt; — গ্রুপে নাম ছাড়া পোস্ট
/remind &lt;10m|2h&gt; &lt;টেক্সট&gt; — পরে মনে করিয়ে দেবে

কেউ inbox-এ মেসেজ দিলে আপনার কাছে forward হবে — reply দিলেই member-এর কাছে যাবে। ছবি/document পাঠালে Approve/Reject বাটন পাবেন।"""

HELP_GROUP = """👋 <b>Group Hub Bot</b> — গ্রুপে /setgroup দিয়ে bind করুন।

<b>অ্যাডমিন:</b> /poll, /endpoll, /quiz, /countdown, /announce
<b>সবাই:</b> /score, /top, /faqs"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram.constants import ParseMode
    if update.effective_chat.type == "private":
        await update.effective_message.reply_text(HELP_PM, parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text(
            "👋 Group Hub Bot চালু! গ্রুপ bind করতে অ্যাডমিন /setgroup দিন।")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram.constants import ParseMode
    if update.effective_chat.type == "private":
        await update.effective_message.reply_text(HELP_PM, parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text(HELP_GROUP, parse_mode=ParseMode.HTML)


def register(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
