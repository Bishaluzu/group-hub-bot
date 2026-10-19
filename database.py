"""SQLite persistence for the Group Hub bot.

DB path: /data/hub.db when /data exists (FadeHost persistent disk),
otherwise hub.db next to this file (local / Termux). Never wiped on deploy.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = "/data" if os.path.isdir("/data") else BASE_DIR
DB_PATH = os.path.join(DATA_DIR, "hub.db")

_LOCK = threading.RLock()

DEFAULT_FAQS = [
    ("দাম", "💰 প্রাইস: 30 টাকা = 1 show, 50 টাকা = 2 shows। নিতে চাইলে মেসেজ দাও 👉 @QueenLabiba"),
    ("price", "💰 Price: 30 taka = 1 show, 50 taka = 2 shows. Message 👉 @QueenLabiba"),
    ("লাইভ", "📡 লাইভ দেখতে চ্যানেলে জয়েন করো 👉 https://t.me/freelivestrem"),
    ("live", "📡 Join the channel for live 👉 https://t.me/freelivestrem"),
    ("পেমেন্ট", "💸 bKash/Nagad: 01612927000 (Send Money)। পেমেন্ট করে প্রমাণ পাঠাও"),
    ("payment", "💸 bKash/Nagad: 01612927000 (Send Money). Send proof after payment"),
    ("বিকাশ", "💸 bKash/Nagad: 01612927000 (Send Money)। পেমেন্ট করে প্রমাণ পাঠাও"),
    ("নগদ", "💸 bKash/Nagad: 01612927000 (Send Money)। পেমেন্ট করে প্রমাণ পাঠাও"),
]

DEFAULT_KEYWORDS = ["দাম", "price", "live"]


def _connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(BASE_DIR, exist_ok=True)
    with _LOCK, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                chat_id INTEGER NOT NULL,
                key     TEXT    NOT NULL,
                value   TEXT    NOT NULL DEFAULT '',
                PRIMARY KEY (chat_id, key)
            );
            CREATE TABLE IF NOT EXISTS faqs (
                keyword TEXT PRIMARY KEY,
                reply   TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS keywords (
                chat_id INTEGER NOT NULL,
                word    TEXT    NOT NULL,
                PRIMARY KEY (chat_id, word)
            );
            CREATE TABLE IF NOT EXISTS reply_map (
                fwd_msg_id  INTEGER PRIMARY KEY,
                member_id   INTEGER NOT NULL,
                member_name TEXT    NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS polls (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id  INTEGER NOT NULL,
                msg_id   INTEGER NOT NULL DEFAULT 0,
                question TEXT    NOT NULL,
                options  TEXT    NOT NULL DEFAULT '[]',
                votes    TEXT    NOT NULL DEFAULT '{}',
                open     INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS quiz_scores (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                name    TEXT    NOT NULL DEFAULT '',
                score   INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS msg_count (
                chat_id INTEGER NOT NULL,
                week    TEXT    NOT NULL,
                user_id INTEGER NOT NULL,
                name    TEXT    NOT NULL DEFAULT '',
                count   INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, week, user_id)
            );
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id   INTEGER PRIMARY KEY,
                name      TEXT    NOT NULL DEFAULT '',
                banned_at TEXT    NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS countdown_milestones (
                chat_id INTEGER NOT NULL,
                at_min  INTEGER NOT NULL,
                kind    TEXT    NOT NULL,
                text    TEXT    NOT NULL DEFAULT '',
                PRIMARY KEY (chat_id, at_min, kind)
            );
            CREATE TABLE IF NOT EXISTS known_users (
                user_id  INTEGER PRIMARY KEY,
                name     TEXT    NOT NULL DEFAULT '',
                username TEXT    NOT NULL DEFAULT '',
                seen_at  TEXT    NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS custom_truths (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS hidden_truths (
                idx INTEGER PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS truth_overrides (
                idx  INTEGER PRIMARY KEY,
                text TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS suggestions (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name    TEXT    NOT NULL DEFAULT '',
                text    TEXT    NOT NULL,
                status  TEXT    NOT NULL DEFAULT 'pending',
                chat_id INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        # migration for DBs created before chat_id existed
        try:
            conn.execute("ALTER TABLE suggestions ADD COLUMN chat_id INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass
        for kw, reply in DEFAULT_FAQS:
            conn.execute(
                "INSERT OR IGNORE INTO faqs (keyword, reply) VALUES (?,?)", (kw, reply)
            )


# ------------------------------------------------------------------ settings
def get_setting(chat_id: int, key: str, default: str = "") -> str:
    with _LOCK, _connect() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE chat_id=? AND key=?", (chat_id, key)
        ).fetchone()
        return row["value"] if row else default


def set_setting(chat_id: int, key: str, value) -> None:
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT INTO settings (chat_id, key, value) VALUES (?,?,?) "
            "ON CONFLICT(chat_id, key) DO UPDATE SET value=excluded.value",
            (chat_id, str(key), str(value)),
        )


def del_setting(chat_id: int, key: str) -> None:
    with _LOCK, _connect() as conn:
        conn.execute("DELETE FROM settings WHERE chat_id=? AND key=?", (chat_id, key))


def chats_with_key(key: str):
    """All chat_ids that have a given settings key (for re-arming jobs)."""
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT chat_id, value FROM settings WHERE key=?", (key,)
        ).fetchall()
        return [(r["chat_id"], r["value"]) for r in rows]


# ------------------------------------------------------------- bound group
def get_bound():
    """Return (chat_id, admin_id) of the bound group, (0, 0) if none."""
    chat_id = get_setting(0, "bound_chat_id", "")
    admin_id = get_setting(0, "bound_by", "")
    try:
        return int(chat_id), int(admin_id)
    except ValueError:
        return 0, 0


def set_bound(chat_id: int, admin_id: int) -> None:
    set_setting(0, "bound_chat_id", chat_id)
    set_setting(0, "bound_by", admin_id)


# ---------------------------------------------------------------------- faqs
def save_faq(keyword: str, reply: str) -> None:
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT INTO faqs (keyword, reply) VALUES (?,?) "
            "ON CONFLICT(keyword) DO UPDATE SET reply=excluded.reply",
            (keyword.lower(), reply),
        )


def delete_faq(keyword: str) -> bool:
    with _LOCK, _connect() as conn:
        cur = conn.execute("DELETE FROM faqs WHERE keyword=?", (keyword.lower(),))
        return cur.rowcount > 0


def list_faqs():
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT keyword, reply FROM faqs ORDER BY keyword"
        ).fetchall()
        return [(r["keyword"], r["reply"]) for r in rows]


def find_faq(text: str):
    """Pure-ish lookup: first keyword contained in text (case-insensitive)."""
    low = (text or "").lower()
    for kw, reply in list_faqs():
        if kw and kw in low:
            return reply
    return None


# ------------------------------------------------------------------ keywords
def set_keywords(chat_id: int, words) -> None:
    with _LOCK, _connect() as conn:
        conn.execute("DELETE FROM keywords WHERE chat_id=?", (chat_id,))
        for w in words:
            w = w.strip().lower()
            if w:
                conn.execute(
                    "INSERT OR IGNORE INTO keywords (chat_id, word) VALUES (?,?)",
                    (chat_id, w),
                )


def seed_keywords(chat_id: int) -> None:
    if not list_keywords(chat_id):
        set_keywords(chat_id, DEFAULT_KEYWORDS)


def list_keywords(chat_id: int):
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT word FROM keywords WHERE chat_id=? ORDER BY word", (chat_id,)
        ).fetchall()
        return [r["word"] for r in rows]


def find_keyword(chat_id: int, text: str):
    low = (text or "").lower()
    for w in list_keywords(chat_id):
        if w and w in low:
            return w
    return None


# ----------------------------------------------------------------- reply map
def map_forward(fwd_msg_id: int, member_id: int, member_name: str) -> None:
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO reply_map (fwd_msg_id, member_id, member_name) "
            "VALUES (?,?,?)",
            (fwd_msg_id, member_id, member_name or ""),
        )


def lookup_forward(fwd_msg_id: int):
    with _LOCK, _connect() as conn:
        row = conn.execute(
            "SELECT member_id, member_name FROM reply_map WHERE fwd_msg_id=?",
            (fwd_msg_id,),
        ).fetchone()
        return (row["member_id"], row["member_name"]) if row else (None, None)


# ---------------------------------------------------------------------- polls
def create_poll(chat_id: int, question: str, options) -> int:
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO polls (chat_id, question, options, votes) VALUES (?,?,?,?)",
            (chat_id, question, json.dumps(options, ensure_ascii=False), "{}"),
        )
        return cur.lastrowid


def set_poll_msg(poll_id: int, msg_id: int) -> None:
    with _LOCK, _connect() as conn:
        conn.execute("UPDATE polls SET msg_id=? WHERE id=?", (msg_id, poll_id))


def get_poll(poll_id: int):
    with _LOCK, _connect() as conn:
        return conn.execute("SELECT * FROM polls WHERE id=?", (poll_id,)).fetchone()


def get_open_poll(chat_id: int):
    with _LOCK, _connect() as conn:
        return conn.execute(
            "SELECT * FROM polls WHERE chat_id=? AND open=1 ORDER BY id DESC LIMIT 1",
            (chat_id,),
        ).fetchone()


def vote(poll_id: int, user_id: int, opt_idx: int):
    """Record/replace a vote. Returns (options, votes) after update."""
    with _LOCK, _connect() as conn:
        row = conn.execute(
            "SELECT options, votes, open FROM polls WHERE id=?", (poll_id,)
        ).fetchone()
        if not row or not row["open"]:
            return None
        options = json.loads(row["options"])
        if not (0 <= opt_idx < len(options)):
            return None
        votes = json.loads(row["votes"])
        votes[str(user_id)] = opt_idx
        conn.execute(
            "UPDATE polls SET votes=? WHERE id=?", (json.dumps(votes), poll_id)
        )
        return options, votes


def close_poll(poll_id: int) -> None:
    with _LOCK, _connect() as conn:
        conn.execute("UPDATE polls SET open=0 WHERE id=?", (poll_id,))


# ---------------------------------------------------------------- quiz scores
def add_quiz_score(chat_id: int, user_id: int, name: str, points: int) -> int:
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT INTO quiz_scores (chat_id, user_id, name, score) VALUES (?,?,?,?) "
            "ON CONFLICT(chat_id, user_id) DO UPDATE SET "
            "score=score+excluded.score, name=excluded.name",
            (chat_id, user_id, name or "", points),
        )
        row = conn.execute(
            "SELECT score FROM quiz_scores WHERE chat_id=? AND user_id=?",
            (chat_id, user_id),
        ).fetchone()
        return row["score"]


def top_quiz(chat_id: int, limit: int = 10):
    with _LOCK, _connect() as conn:
        return conn.execute(
            "SELECT name, score FROM quiz_scores WHERE chat_id=? "
            "ORDER BY score DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()


# -------------------------------------------------------------- weekly count
def bump_count(chat_id: int, week: str, user_id: int, name: str) -> None:
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT INTO msg_count (chat_id, week, user_id, name, count) "
            "VALUES (?,?,?,?,1) ON CONFLICT(chat_id, week, user_id) DO UPDATE SET "
            "count=count+1, name=excluded.name",
            (chat_id, week, user_id, name or ""),
        )


def top_week(chat_id: int, week: str, limit: int = 10):
    with _LOCK, _connect() as conn:
        return conn.execute(
            "SELECT name, count FROM msg_count WHERE chat_id=? AND week=? "
            "ORDER BY count DESC LIMIT ?",
            (chat_id, week, limit),
        ).fetchall()


# ------------------------------------------------------------ banned users
def ban_user(user_id: int, name: str = "") -> None:
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO banned_users (user_id, name, banned_at) "
            "VALUES (?,?,?)",
            (user_id, name or "",
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )


def unban_user(user_id: int) -> bool:
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            "DELETE FROM banned_users WHERE user_id=?", (user_id,))
        return cur.rowcount > 0


def is_banned(user_id: int) -> bool:
    with _LOCK, _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM banned_users WHERE user_id=?", (user_id,)
        ).fetchone()
        return row is not None


def list_banned():
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT user_id, name FROM banned_users ORDER BY banned_at"
        ).fetchall()
        return [(r["user_id"], r["name"]) for r in rows]


# ------------------------------------------------------ countdown milestones
def set_milestone(chat_id: int, at_min: int, kind: str, text: str) -> None:
    """kind: 'msg' (group post) or 'dm' (inbox DM)."""
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT INTO countdown_milestones (chat_id, at_min, kind, text) "
            "VALUES (?,?,?,?) "
            "ON CONFLICT(chat_id, at_min, kind) DO UPDATE SET text=excluded.text",
            (chat_id, at_min, kind, text or ""),
        )


def list_milestones(chat_id: int):
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT at_min, kind, text FROM countdown_milestones "
            "WHERE chat_id=? ORDER BY at_min DESC",
            (chat_id,),
        ).fetchall()
        return [(r["at_min"], r["kind"], r["text"]) for r in rows]


def clear_milestones(chat_id: int) -> None:
    with _LOCK, _connect() as conn:
        conn.execute(
            "DELETE FROM countdown_milestones WHERE chat_id=?", (chat_id,))


# ------------------------------------------------------------ known users
def touch_user(user_id: int, name: str = "", username: str = "") -> None:
    """Remember a user for countdown inbox DMs. Cheap upsert."""
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT INTO known_users (user_id, name, username, seen_at) "
            "VALUES (?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "name=excluded.name, username=excluded.username, "
            "seen_at=excluded.seen_at",
            (user_id, name or "", username or "",
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )


def list_known_users():
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT user_id, name FROM known_users ORDER BY seen_at"
        ).fetchall()
        return [(r["user_id"], r["name"]) for r in rows]


# ------------------------------------------------------------ truth game
def add_custom_truth(text: str) -> int:
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO custom_truths (text) VALUES (?)", (text,))
        return cur.lastrowid


def list_custom_truths():
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT id, text FROM custom_truths ORDER BY id").fetchall()
        return [(r["id"], r["text"]) for r in rows]


def get_custom_truth(tid: int):
    with _LOCK, _connect() as conn:
        row = conn.execute(
            "SELECT id, text FROM custom_truths WHERE id=?", (tid,)).fetchone()
        return (row["id"], row["text"]) if row else None


def update_custom_truth(tid: int, text: str) -> bool:
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            "UPDATE custom_truths SET text=? WHERE id=?", (text, tid))
        return cur.rowcount > 0


def delete_custom_truth(tid: int) -> bool:
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            "DELETE FROM custom_truths WHERE id=?", (tid,))
        return cur.rowcount > 0


def hide_builtin_truth(idx: int) -> None:
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO hidden_truths (idx) VALUES (?)", (idx,))


def list_hidden_truths() -> set:
    with _LOCK, _connect() as conn:
        rows = conn.execute("SELECT idx FROM hidden_truths").fetchall()
        return {r["idx"] for r in rows}


def set_truth_override(idx: int, text: str) -> None:
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT INTO truth_overrides (idx, text) VALUES (?,?) "
            "ON CONFLICT(idx) DO UPDATE SET text=excluded.text",
            (idx, text))


def get_truth_overrides() -> dict:
    with _LOCK, _connect() as conn:
        rows = conn.execute("SELECT idx, text FROM truth_overrides").fetchall()
        return {r["idx"]: r["text"] for r in rows}


# ------------------------------------------------------------ suggestions
def add_suggestion(user_id: int, name: str, text: str, chat_id: int = 0) -> int:
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO suggestions (user_id, name, text, chat_id) VALUES (?,?,?,?)",
            (user_id, name or "", text, chat_id or 0))
        return cur.lastrowid


def get_suggestion(sid: int):
    with _LOCK, _connect() as conn:
        row = conn.execute(
            "SELECT id, user_id, name, text, status, chat_id FROM suggestions WHERE id=?",
            (sid,)).fetchone()
        return dict(row) if row else None


def set_suggestion_status(sid: int, status: str) -> bool:
    """Set status only if still pending (double-tap safe)."""
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            "UPDATE suggestions SET status=? WHERE id=? AND status='pending'",
            (status, sid))
        return cur.rowcount > 0
