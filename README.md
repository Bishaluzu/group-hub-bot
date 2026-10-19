# Group Hub Bot 🍒

All-in-one Telegram **group + inbox** bot (Python, `python-telegram-bot`).

## Features
| # | Feature | Command |
|---|---------|---------|
| 1 | Bind group | `/setgroup` (in group, admin) |
| 2 | Announce to group from PM | just type a message in the bot's PM (or `/announce <text>`) — photo/video also works |
| 3 | Auto-pin announcements | `/autopin on\|off` |
| 4 | Reply routing (member PM → admin → back) | automatic |
| 5 | FAQ auto-reply (PM + group) | `/setfaq kw \| reply`, `/delfaq`, `/faqs` |
| 6 | AI fallback (Gemini, optional) | automatic in PM |
| 7 | Polls with live % bars | `/poll q \| o1 \| o2`, `/endpoll` — গ্রুপ বা bot-এর inbox দুটোতেই চলে |
| 8 | Scheduled announce (daily, Dhaka time) | `/schedule HH:MM <text>`, `/cancelschedule` — গ্রুপ বা inbox |
| 9 | Keyword alerts to admin | `/setkeywords w1,w2` |
| 10 | Payment proof inbox (Approve/Reject) | send photo in PM |
| 11 | Live countdown | `/countdown <minutes>` — গ্রুপ বা bot-এর inbox দুটোতেই চলে |
| 12 | Daily message | `/setdaily HH:MM <text>` — গ্রুপ বা inbox |
| 13 | Anonymous feedback | `/feedback <text>` (PM) |
| 14 | Quiz game (+10) | `/quiz`, `/score` |
| 15 | Weekly top members | `/top` |
| 16 | Reminder | `/remind 10m\|2h <text>` (PM) |
| 17 | PM ban (bot inbox only, not the group) | `/ban`, `/unban`, `/banned` (admin, PM — reply to a forwarded message or `/ban <user_id>`) |

Admin checks are **native Telegram** (group admin/owner) — no `ADMIN_IDS` needed.

## Deploy — FadeHost (free, 24/7)
1. Push this folder to a GitHub repo.
2. FadeHost → Apps and bots → **Host a bot or app** → **Telegram bot** → **Your own repository**.
3. Fill: Name, **Telegram bot token** (BotFather), GitHub repo URL `https://github.com/<you>/<repo>`, Plan **Free**.
4. (Optional) token also works as `BOT_TOKEN` env var; Gemini key as `GEMINI_API_KEY`.
5. Deploy → open Telegram → `/start` the bot.

## Deploy — Termux / local
```bash
pip install -r requirements.txt
cp .env.example .env   # then put your BotFather token in .env
python bot.py
```

## First run
1. Add the bot to your group as **admin** (needs: post, delete, pin messages).
2. In the group send `/setgroup` (as admin).
3. In the bot's PM send `/hubstatus` to verify the binding.
4. Try typing a plain message in the bot's PM — it will be posted to the group
   (`/announce Hello group!` also works).

## Data
SQLite at `/data/hub.db` on FadeHost (survives deploys), `./hub.db` locally.
