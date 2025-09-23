import os
import datetime
import calendar
import random
import json
import time
import sqlite3
import requests
from openai import OpenAI
from typing import Optional, Dict, Any

# Paths
DATA_PATH = os.getenv("SUPPERTIME_DATA_PATH", "./data")
# Chapters are in the root directory, not in data/
CHAPTERS_DIR = os.getenv("SUPPERTIME_CHAPTERS_DIR", "./chapters")
CACHE_PATH = os.path.join(DATA_PATH, "chapter_cache.json")
ASSISTANT_ID_PATH = os.path.join(DATA_PATH, "assistant_id.txt")
DB_PATH = os.path.join(DATA_PATH, "suppertime_memory.db")

# OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Telegram config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPPERTIME_GROUP_ID = os.getenv("SUPPERTIME_GROUP_ID")
SUPPERTIME_CHAT_ID = os.getenv("SUPPERTIME_CHAT_ID")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else None


# --- SQLite helpers ---
def _init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chapter_rotation (
                date TEXT PRIMARY KEY,
                path TEXT,
                title TEXT,
                content TEXT,
                error INTEGER DEFAULT 0
            )
        """)
        conn.commit()

_init_db()


def save_rotation_to_db(date: str, path: str, title: str, content: str, error: bool = False):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO chapter_rotation (date, path, title, content, error)
            VALUES (?, ?, ?, ?, ?)
        """, (date, path, title, content, int(error)))
        conn.commit()


def load_rotation_from_db(date: str) -> Optional[Dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("""
            SELECT path, title, content, error FROM chapter_rotation WHERE date = ?
        """, (date,))
        row = cur.fetchone()
        if row:
            return {
                "date": date,
                "path": row[0],
                "title": row[1],
                "content": row[2],
                "error": bool(row[3])
            }
    return None


# --- Chapter handling ---
def get_assistant_id() -> Optional[str]:
    if os.path.exists(ASSISTANT_ID_PATH):
        try:
            with open(ASSISTANT_ID_PATH, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return None
    return None


def get_all_chapter_files():
    try:
        return sorted(f for f in os.listdir(CHAPTERS_DIR) if f.startswith("st") and f.endswith(".md"))
    except FileNotFoundError:
        return []


def get_monthly_plan(year: int, month: int):
    chapters = get_all_chapter_files()
    days = calendar.monthrange(year, month)[1]
    if len(chapters) < days:
        raise ValueError("Not enough chapters to cover the month.")
    rnd = random.Random(f"{year}-{month}")
    rnd.shuffle(chapters)
    return chapters[:days]


def get_today_chapter_path():
    today = datetime.date.today()
    try:
        monthly_plan = get_monthly_plan(today.year, today.month)
    except Exception as e:
        return f"[Resonator] {e}"
    idx = today.day - 1
    if idx >= len(monthly_plan):
        return f"[Resonator] No chapter for day {today.day}."
    path = os.path.join(CHAPTERS_DIR, monthly_plan[idx])
    return path if os.path.exists(path) else f"[Resonator] Chapter file not found: {path}"


def load_chapter_content(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"[Resonator] Error loading chapter: {e}"


def extract_chapter_title(content: str) -> str:
    for line in content.splitlines():
        if line.strip().startswith("#"):
            header = line.lstrip("#").strip()
            if "chapter" in header.lower() or "глава" in header.lower():
                return header
            return header
    for line in content.splitlines():
        if line.strip():
            return line.strip()
    return "Untitled"


# --- Cache / rotation ---
def get_today_chapter_info() -> Dict[str, Any]:
    today = datetime.date.today().isoformat()

    cached = load_rotation_from_db(today)
    if cached:
        return cached

    path = get_today_chapter_path()
    if isinstance(path, str) and path.startswith("[Resonator]"):
        info = {"date": today, "path": None, "title": path, "content": "", "error": True}
    else:
        content = load_chapter_content(path)
        if content.startswith("[Resonator]"):
            info = {"date": today, "path": path, "title": content, "content": "", "error": True}
        else:
            title = extract_chapter_title(content)
            info = {"date": today, "path": path, "title": title, "content": content, "error": False}

    save_rotation_to_db(today, info["path"] or "", info["title"], info.get("content", ""), info["error"])
    return info


def load_today_chapter(return_path: bool = False) -> str:
    """Compatibility wrapper that returns today's chapter content or path.

    Historically, other modules imported :func:`load_today_chapter` directly
    from this module. The rotation refactor introduced
    :func:`get_today_chapter_info` without preserving the legacy API, which
    caused import failures in production environments. This helper restores the
    original interface while delegating to the richer chapter metadata loader.

    Args:
        return_path: When ``True``, return the resolved filesystem path instead
            of the chapter contents. Errors are returned as human-readable
            strings regardless of the flag so callers receive context.

    Returns:
        The chapter contents or path for today, or an error string if the
        chapter could not be loaded.
    """

    info = get_today_chapter_info()

    if info.get("error"):
        # Preserve compatibility by returning the descriptive error message.
        return info.get("title") or "[Resonator] Chapter unavailable."

    if return_path:
        return info.get("path") or ""

    return info.get("content", "")


def _notify_chapter_selection(title: str):
    if TELEGRAM_API_URL and (SUPPERTIME_CHAT_ID or SUPPERTIME_GROUP_ID):
        data = {"chat_id": SUPPERTIME_CHAT_ID or SUPPERTIME_GROUP_ID, "text": f"Today's chapter: {title}"}
        try:
            requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=data, timeout=5)
        except Exception as e:
            print(f"[SUPPERTIME][ERROR] Telegram notify failed: {e}")


def daily_chapter_rotation():
    info = get_today_chapter_info()
    if info["error"]:
        print(f"[SUPPERTIME][ERROR] Chapter rotation failed: {info['title']}")
        return {"success": False, "error": info["title"]}
    print(f"[SUPPERTIME] Chapter rotation successful: {info['title']} ({info['path']})")
    _notify_chapter_selection(info["title"])
    return {"success": True, "chapter_title": info["title"], "path": info["path"]}


def run_midnight_rotation_daemon():
    while True:
        now = datetime.datetime.now()
        nxt = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        wait = (nxt - now).total_seconds()
        print(f"[SUPPERTIME] Waiting {wait:.2f}s until next rotation.")
        time.sleep(wait)
        daily_chapter_rotation()
