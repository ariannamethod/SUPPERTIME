import os
import sqlite3
import time
from typing import Optional, Any

CACHE_DB = os.path.join(os.getenv("SUPPERTIME_DATA_PATH", "./data"), "expiring_cache.db")


class ExpiringCache:
    """SQLite-based cache with TTL per key."""

    def __init__(self, ttl_seconds: int = 3600, db_path: str = CACHE_DB):
        self.ttl = ttl_seconds
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS expiring_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    ts REAL
                )
            """)
            conn.commit()

    def set(self, key: str, value: Any):
        ts = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO expiring_cache (key, value, ts) VALUES (?, ?, ?)",
                (key, str(value), ts)
            )
            conn.commit()

    def get(self, key: str) -> Optional[str]:
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value, ts FROM expiring_cache WHERE key = ?",
                (key,)
            ).fetchone()
        if not row:
            return None
        value, ts = row
        if now - ts > self.ttl:
            self.delete(key)
            return None
        return value

    def delete(self, key: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM expiring_cache WHERE key = ?", (key,))
            conn.commit()

    def cleanup(self):
        """Remove expired entries."""
        cutoff = time.time() - self.ttl
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM expiring_cache WHERE ts < ?", (cutoff,))
            conn.commit()

    def keys(self):
        """Return non-expired keys."""
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT key, ts FROM expiring_cache").fetchall()
        return [k for k, ts in rows if now - ts <= self.ttl]

    def __len__(self):
        return len(self.keys())