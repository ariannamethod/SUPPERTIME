# utils/daily_reflection.py

import os
import json
import datetime
import threading
import time
import sqlite3
from typing import Optional, List, Dict

from utils.vector_store import add_memory_entry
from utils.journal import log_event

DATA_PATH = os.getenv("SUPPERTIME_DATA_PATH", "./data")
JOURNAL_FILE = os.path.join(DATA_PATH, "journal.json")
DB_PATH = os.path.join(DATA_PATH, "suppertime_memory.db")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")


def _init_db():
    os.makedirs(DATA_PATH, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                text TEXT,
                chapter TEXT,
                vector_id TEXT
            )
        """)
        conn.commit()


_init_db()


def record_daily_reflection(text: str, chapter: str = "Unknown") -> Dict:
    """Записывает ежедневное отражение в SQLite, JSON-журнал и вектор-стор."""
    ts = datetime.datetime.utcnow().isoformat()
    metadata = {"type": "daily_reflection", "ts": ts, "chapter": chapter}
    vector_id: Optional[str] = None

    try:
        vector_id = add_memory_entry(text, OPENAI_KEY, metadata)
    except Exception as e:
        print(f"[SUPPERTIME][ERROR] Vector log failed: {e}")

    entry = {**metadata, "text": text, "vector_id": vector_id}

    # SQLite запись
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO daily_reflections (ts, text, chapter, vector_id) VALUES (?, ?, ?, ?)",
                (ts, text, chapter, vector_id),
            )
            conn.commit()
    except Exception as e:
        print(f"[SUPPERTIME][ERROR] Failed to save reflection in DB: {e}")

    # JSON-журнал для обратной совместимости
    log_event(entry)

    return entry


def load_last_reflection() -> Optional[Dict]:
    """Возвращает последнюю запись reflection (SQLite → fallback JSON)."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT ts, text, chapter, vector_id FROM daily_reflections ORDER BY ts DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if row:
                return {"ts": row[0], "text": row[1], "chapter": row[2], "vector_id": row[3]}
    except Exception as e:
        print(f"[SUPPERTIME][WARNING] Failed to load from DB: {e}")

    # fallback
    try:
        with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)
        reflections = [e for e in entries if e.get("type") == "daily_reflection"]
        if reflections:
            return sorted(reflections, key=lambda x: x.get("ts", ""))[-1]
    except Exception:
        return None


def get_recent_reflections(limit: int = 5) -> List[Dict]:
    """Возвращает последние N reflection-записей."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT ts, text, chapter, vector_id FROM daily_reflections ORDER BY ts DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                {"ts": r[0], "text": r[1], "chapter": r[2], "vector_id": r[3]} for r in rows
            ]
    except Exception as e:
        print(f"[SUPPERTIME][WARNING] Failed to get reflections: {e}")
        return []


def search_reflections(query: str, limit: int = 5) -> List[Dict]:
    """Поиск по содержимому reflection-записей."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT ts, text, chapter, vector_id FROM daily_reflections WHERE text LIKE ? ORDER BY ts DESC LIMIT ?",
                (f"%{query}%", limit),
            )
            return [
                {"ts": r[0], "text": r[1], "chapter": r[2], "vector_id": r[3]} for r in cursor.fetchall()
            ]
    except Exception as e:
        print(f"[SUPPERTIME][WARNING] Search failed: {e}")
        return []


def schedule_daily_reflection(get_chapter_title, get_chat_summary):
    """Планировщик: каждый день в 00:05 пишет новую запись reflection."""

    def _loop():
        while True:
            now = datetime.datetime.utcnow()
            next_midnight = (now + datetime.timedelta(days=1)).replace(
                hour=0, minute=5, second=0, microsecond=0
            )
            time.sleep(max(60, (next_midnight - now).total_seconds()))

            chapter = get_chapter_title() or "Unknown"
            summary = get_chat_summary() or ""
            text = f"{datetime.date.today().isoformat()} :: {chapter} :: {summary}"

            record_daily_reflection(text, chapter=chapter)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    return thread