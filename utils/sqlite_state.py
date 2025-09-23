import os
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, Optional

_DB_PATH: Optional[str] = None
_DB_LOCK = threading.Lock()


def _ensure_db_initialized() -> None:
    global _DB_PATH
    if _DB_PATH is None:
        default_base = os.getenv("SUPPERTIME_DATA_PATH", "./data")
        default_path = os.path.join(default_base, "suppertime.db")
        init_state_db(default_path)


def _get_connection() -> sqlite3.Connection:
    _ensure_db_initialized()
    assert _DB_PATH is not None
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_state_db(db_path: str) -> None:
    """Initialize the SQLite database used for SUPPERTIME state."""
    global _DB_PATH
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_state (
                user_id TEXT PRIMARY KEY,
                voice_mode INTEGER DEFAULT 0,
                audio_mode INTEGER DEFAULT 0,
                lang TEXT,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS threads (
                user_id TEXT PRIMARY KEY,
                thread_id TEXT,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS openai_cache (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lit_files (
                path TEXT PRIMARY KEY,
                sha256 TEXT,
                size INTEGER,
                mtime REAL,
                indexed_at TEXT,
                last_seen TEXT
            )
            """
        )
        conn.commit()

    _DB_PATH = db_path


def get_user_state(user_id: Any) -> Optional[Dict[str, Any]]:
    user_key = str(user_id)
    with _DB_LOCK:
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT user_id, voice_mode, audio_mode, lang, updated_at FROM user_state WHERE user_id = ?",
                (user_key,),
            ).fetchone()
    if not row:
        return None
    return dict(row)


def set_user_state(
    user_id: Any,
    *,
    voice_mode: Optional[int] = None,
    audio_mode: Optional[int] = None,
    lang: Optional[str] = None,
) -> None:
    user_key = str(user_id)
    current = get_user_state(user_key) or {}
    voice_value = (
        int(bool(voice_mode))
        if voice_mode is not None
        else int(current.get("voice_mode", 0) or 0)
    )
    audio_value = (
        int(bool(audio_mode))
        if audio_mode is not None
        else int(current.get("audio_mode", 0) or 0)
    )
    lang_value = lang if lang is not None else current.get("lang")
    updated_at = datetime.utcnow().isoformat()

    with _DB_LOCK:
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_state (user_id, voice_mode, audio_mode, lang, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    voice_mode=excluded.voice_mode,
                    audio_mode=excluded.audio_mode,
                    lang=excluded.lang,
                    updated_at=excluded.updated_at
                """,
                (user_key, voice_value, audio_value, lang_value, updated_at),
            )
            conn.commit()


def get_thread(user_id: Any) -> Optional[str]:
    user_key = str(user_id)
    with _DB_LOCK:
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT thread_id FROM threads WHERE user_id = ?",
                (user_key,),
            ).fetchone()
    if not row:
        return None
    return row[0]


def set_thread(user_id: Any, thread_id: str) -> None:
    user_key = str(user_id)
    updated_at = datetime.utcnow().isoformat()
    with _DB_LOCK:
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO threads (user_id, thread_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    thread_id=excluded.thread_id,
                    updated_at=excluded.updated_at
                """,
                (user_key, thread_id, updated_at),
            )
            conn.commit()


def get_openai_cache(key: str) -> Optional[str]:
    with _DB_LOCK:
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM openai_cache WHERE key = ?",
                (key,),
            ).fetchone()
    if not row:
        return None
    return row[0]


def set_openai_cache(key: str, value: str) -> None:
    updated_at = datetime.utcnow().isoformat()
    with _DB_LOCK:
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO openai_cache (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=excluded.updated_at
                """,
                (key, value, updated_at),
            )
            conn.commit()


def get_lit_file(path: str) -> Optional[Dict[str, Any]]:
    with _DB_LOCK:
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT path, sha256, size, mtime, indexed_at, last_seen FROM lit_files WHERE path = ?",
                (path,),
            ).fetchone()
    if not row:
        return None
    return dict(row)


def upsert_lit_file(
    path: str,
    sha256: str,
    size: int,
    mtime: float,
    *,
    indexed_at: Optional[str] = None,
    last_seen: Optional[str] = None,
) -> None:
    existing = get_lit_file(path)
    indexed_value = indexed_at if indexed_at is not None else (existing or {}).get("indexed_at")
    last_seen_value = last_seen if last_seen is not None else (existing or {}).get("last_seen")

    with _DB_LOCK:
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO lit_files (path, sha256, size, mtime, indexed_at, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    sha256=excluded.sha256,
                    size=excluded.size,
                    mtime=excluded.mtime,
                    indexed_at=COALESCE(excluded.indexed_at, lit_files.indexed_at),
                    last_seen=COALESCE(excluded.last_seen, lit_files.last_seen)
                """,
                (path, sha256, int(size), float(mtime), indexed_value, last_seen_value),
            )
            conn.commit()
