"""Persistent snapshot storage for SUPPERTIME using SQLite."""
from __future__ import annotations

import datetime as _dt
import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Iterable, Optional

SUPPERTIME_DATA_PATH = os.getenv("SUPPERTIME_DATA_PATH", "./data")
DB_PATH = os.path.join(SUPPERTIME_DATA_PATH, "suppertime.db")


def _ensure_directory() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


@contextmanager
def _connect() -> Iterable[sqlite3.Connection]:
    _ensure_directory()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_type TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                payload TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(snapshot_type, snapshot_date)
            )
            """
        )
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_snapshot(
    snapshot_type: str,
    payload: Dict[str, Any],
    *,
    snapshot_date: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Persist a daily snapshot of a given type."""

    current_time = _dt.datetime.now(_dt.timezone.utc)
    if snapshot_date is None:
        snapshot_date = current_time.date().isoformat()

    record = json.dumps(payload, ensure_ascii=False)
    meta = json.dumps(metadata or {}, ensure_ascii=False)
    created_at = current_time.isoformat()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO snapshots (snapshot_type, snapshot_date, payload, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_type, snapshot_date) DO UPDATE SET
                payload=excluded.payload,
                metadata=excluded.metadata,
                created_at=excluded.created_at
            """,
            (snapshot_type, snapshot_date, record, meta, created_at),
        )
    return snapshot_date


def get_recent_snapshots(snapshot_type: str, limit: int = 5) -> list[Dict[str, Any]]:
    """Return the most recent snapshots of a given type."""

    if limit <= 0:
        return []

    with _connect() as conn:
        cursor = conn.execute(
            """
            SELECT snapshot_date, payload, metadata, created_at
            FROM snapshots
            WHERE snapshot_type = ?
            ORDER BY snapshot_date DESC, id DESC
            LIMIT ?
            """,
            (snapshot_type, limit),
        )
        rows = cursor.fetchall()

    snapshots: list[Dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except Exception:
            payload = {}
        try:
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        except Exception:
            metadata = {}
        snapshots.append(
            {
                "date": row["snapshot_date"],
                "payload": payload,
                "metadata": metadata,
                "created_at": row["created_at"],
            }
        )
    return snapshots


def latest_snapshot(snapshot_type: str) -> Optional[Dict[str, Any]]:
    """Return the most recent snapshot for the provided type."""

    snapshots = get_recent_snapshots(snapshot_type, limit=1)
    return snapshots[0] if snapshots else None


def summarize_literary_payload(payload: Dict[str, Any], *, max_items: int = 6) -> str:
    """Create a short human-readable summary of a literary snapshot payload."""

    if not isinstance(payload, dict):
        return "No literary memory snapshot captured."

    items = []
    for path, file_hash in list(payload.items())[:max_items]:
        name = os.path.basename(path)
        items.append(f"- {name} [{str(file_hash)[:10] if file_hash else 'no-hash'}]")

    if not items:
        return "No literary memory snapshot captured."

    remaining = max(0, len(payload) - max_items)
    if remaining:
        items.append(f"…and {remaining} more entries in the lit archive.")

    return "\n".join(items)
