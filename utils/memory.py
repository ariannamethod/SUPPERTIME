# utils/memory.py

import os
import json
import sqlite3
import time
from typing import List, Dict, Optional

from utils.journal import log_event, LOG_PATH as JOURNAL_PATH

try:
    from utils import vector_store
except Exception:  # optional dependency
    vector_store = None  # type: ignore

# Путь к SQLite памяти
SUPPERTIME_DATA_PATH = os.getenv("SUPPERTIME_DATA_PATH", "./data")
DB_PATH = os.path.join(SUPPERTIME_DATA_PATH, "suppertime_memory.db")


def _init_db():
    os.makedirs(SUPPERTIME_DATA_PATH, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL,
                summary TEXT,
                extra TEXT
            )
        """)
        conn.commit()


_init_db()


def save_summary(summary: str, extra: Optional[Dict] = None) -> None:
    """Сохраняет сводку в SQLite и в JSON-журнал."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO memory_summaries (ts, summary, extra) VALUES (?, ?, ?)",
                (time.time(), summary, json.dumps(extra or {}, ensure_ascii=False))
            )
            conn.commit()
    except Exception as e:
        print(f"[SUPPERTIME][ERROR] Failed to save summary in DB: {e}")

    # Для обратной совместимости пишем и в журнал
    log_event({"type": "memory_summary", "summary": summary})


def get_recent_summaries(limit: int = 5) -> List[str]:
    """Возвращает последние N сводок (SQLite → fallback JSON)."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT summary FROM memory_summaries ORDER BY ts DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            if rows:
                return [r[0] for r in rows]
    except Exception as e:
        print(f"[SUPPERTIME][WARNING] Failed to read from DB: {e}")

    # fallback: читаем JSON-журнал
    if os.path.exists(JOURNAL_PATH):
        try:
            with open(JOURNAL_PATH, "r", encoding="utf-8") as f:
                log = json.load(f)
            if isinstance(log, list):
                summaries = [e.get("summary", "") for e in log if e.get("type") == "memory_summary"]
                return summaries[-limit:]
        except Exception as e:
            print(f"[SUPPERTIME][WARNING] Failed to read journal: {e}")
    return []


def search_summaries(query: str, limit: int = 5) -> List[str]:
    """Поиск по сводкам (SQLite LIKE)."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT summary FROM memory_summaries WHERE summary LIKE ? ORDER BY ts DESC LIMIT ?",
                (f"%{query}%", limit)
            )
            return [r[0] for r in cursor.fetchall()]
    except Exception as e:
        print(f"[SUPPERTIME][WARNING] Search failed: {e}")
        return []


class ConversationMemory:
    """Собирает сообщения и периодически сводит их в summary."""

    def __init__(self, openai_client: Optional[object] = None, threshold: int = 20):
        self.openai_client = openai_client
        self.threshold = threshold
        self.buffer: List[Dict[str, str]] = []
        self.model = os.getenv("SUPPERTIME_MEMORY_MODEL", "gpt-4o")

    def add_message(self, role: str, content: str) -> None:
        self.buffer.append({"role": role, "content": content})
        if len(self.buffer) >= self.threshold:
            self.summarize()

    def summarize(self) -> str:
        if not self.buffer:
            return ""

        text = "\n".join(f"{m['role']}: {m['content']}" for m in self.buffer)
        summary = text if len(text) < 1500 else text[:1500] + "..."

        if self.openai_client:
            try:
                resp = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "Summarize the following conversation in under 100 words, keeping tone and key context.",
                        },
                        {"role": "user", "content": text},
                    ],
                    max_tokens=200,
                )
                summary = resp.choices[0].message.content.strip()
            except Exception as e:
                print(f"[SUPPERTIME][WARNING] Memory summarization failed: {e}")

        # Сохраняем в SQLite и журнал
        save_summary(summary)

        if vector_store and self.openai_client:
            try:
                api_key = getattr(self.openai_client, "api_key", os.getenv("OPENAI_API_KEY", ""))
                vector_store.add_memory_entry(summary, api_key, {"type": "summary"})
            except Exception as e:
                print(f"[SUPPERTIME][WARNING] Failed to push memory to vector store: {e}")

        self.buffer.clear()
        return summary