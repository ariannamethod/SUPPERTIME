# utils/behavior.py

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

DB_PATH = Path("./data/behavior.db")


def _init_db():
    """Создание таблицы событий, если её нет."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                role TEXT,
                message TEXT
            )
        """)


def log_event(role: str, message: str):
    """Логируем любое сообщение (input/response)."""
    _init_db()
    ts = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        conn.execute(
            "INSERT INTO events (ts, role, message) VALUES (?, ?, ?)",
            (ts, role, message),
        )


def fetch_context(timestamp: str, radius: int = 10) -> List[Tuple[str, str, str]]:
    """Возвращает сообщения вокруг указанного timestamp."""
    _init_db()
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        cur = conn.execute("SELECT id FROM events WHERE ts = ?", (timestamp,))
        row = cur.fetchone()
        if not row:
            return []
        rowid = row[0]
        start = max(rowid - radius, 1)
        end = rowid + radius
        cur = conn.execute(
            "SELECT ts, role, message FROM events "
            "WHERE id BETWEEN ? AND ? ORDER BY id",
            (start, end),
        )
        return cur.fetchall()


def extract_citations(message: str) -> List[str]:
    """Вынимает все @timestamps из текста."""
    import re
    return re.findall(r"@([0-9T:\-]+)", message)


def build_context_block(message: str) -> str:
    """Формирует блок контекста из цитат в сообщении."""
    citations = extract_citations(message)
    if not citations:
        return ""

    blocks = []
    for ts in citations:
        ctx = fetch_context(ts)
        if ctx:
            formatted = "\n".join(f"[{t}][{r}] {m}" for t, r, m in ctx)
            blocks.append(formatted)

    if blocks:
        return "=== Context Block ===\n" + "\n---\n".join(blocks) + "\n\n"
    return ""


def inject_behavior(message: str, base_prompt: str) -> str:
    """Вставляет в промпт блоки контекста (если есть)."""
    context_block = build_context_block(message)
    if context_block:
        return base_prompt + "\n\n" + context_block
    return base_prompt