import ast
import base64
import os
import pickle
import sqlite3
import threading
import time
from collections.abc import MutableMapping
from typing import Optional, Any

CACHE_DB = os.path.join(os.getenv("SUPPERTIME_DATA_PATH", "./data"), "expiring_cache.db")


SERIALIZATION_PREFIX = "b64:"


def _serialize(value: Any) -> str:
    """Serialize Python objects into a safe base64-encoded string."""
    payload = pickle.dumps(value)
    encoded = base64.b64encode(payload).decode("ascii")
    return f"{SERIALIZATION_PREFIX}{encoded}"


def _deserialize(value: Any) -> tuple[Any, bool]:
    """Deserialize stored values and report whether they came from legacy format."""
    if isinstance(value, str) and value.startswith(SERIALIZATION_PREFIX):
        data = value[len(SERIALIZATION_PREFIX) :]
        try:
            payload = base64.b64decode(data.encode("ascii"))
            return pickle.loads(payload), False
        except Exception:
            # If decoding fails, fall back to the stored string as legacy data
            return value, True
    if isinstance(value, str):
        try:
            return ast.literal_eval(value), True
        except (ValueError, SyntaxError):
            return value, True
    return value, True


class ExpiringCache(MutableMapping):
    """SQLite-based cache with TTL per key."""

    def __init__(
        self,
        ttl_seconds: int = 3600,
        db_path: str = CACHE_DB,
        namespace: Optional[str] = None,
    ):
        self.ttl = ttl_seconds
        self.db_path = db_path
        self.namespace = namespace or self.__class__.__name__
        self._prefix = f"{self.namespace}::"
        self._lock = threading.Lock()  # P1 FIX: Thread safety
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

    def _scoped_key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def _strip_prefix(self, stored_key: str) -> Optional[str]:
        if not stored_key.startswith(self._prefix):
            return None
        return stored_key[len(self._prefix) :]

    def set(self, key: str, value: Any):
        with self._lock:  # P1 FIX: Thread-safe write
            ts = time.time()
            encoded_value = _serialize(value)
            scoped_key = self._scoped_key(str(key))
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO expiring_cache (key, value, ts) VALUES (?, ?, ?)",
                    (scoped_key, encoded_value, ts)
                )
                conn.commit()

    def _get_with_timestamp(self, key: str) -> Optional[tuple[Any, float, bool]]:
        with self._lock:  # P1 FIX: Thread-safe read
            now = time.time()
            scoped_key = self._scoped_key(str(key))
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT value, ts FROM expiring_cache WHERE key = ?",
                    (scoped_key,)
                ).fetchone()
            if not row:
                return None
            value, ts = row
            if now - ts > self.ttl:
                self.delete(key)
                return None
            decoded, legacy = _deserialize(value)
            return decoded, ts, legacy

    def get(self, key: str, default: Any = None) -> Any:
        result = self._get_with_timestamp(key)
        if result is None:
            return default
        value, _, legacy = result
        if legacy:
            self.set(key, value)
        return value

    def delete(self, key: str):
        scoped_key = self._scoped_key(str(key))
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM expiring_cache WHERE key = ?", (scoped_key,))
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
            rows = conn.execute(
                "SELECT key, ts FROM expiring_cache WHERE key LIKE ?",
                (f"{self._prefix}%",),
            ).fetchall()
        result = []
        for stored_key, ts in rows:
            if now - ts > self.ttl:
                continue
            user_key = self._strip_prefix(stored_key)
            if user_key is not None:
                result.append(user_key)
        return result

    def __len__(self):
        return len(self.keys())

    # MutableMapping interface
    def __getitem__(self, key: str) -> Any:
        result = self._get_with_timestamp(key)
        if result is None:
            raise KeyError(key)
        value, _, legacy = result
        if legacy:
            self.set(key, value)
        return value

    def __setitem__(self, key: str, value: Any):
        self.set(key, value)

    def __delitem__(self, key: str):
        if self._get_with_timestamp(key) is None:
            raise KeyError(key)
        self.delete(key)

    def __iter__(self):
        return iter(self.keys())

    def __contains__(self, key: object) -> bool:
        try:
            lookup_key = str(key)
        except Exception:
            return False
        return self._get_with_timestamp(lookup_key) is not None


class ExpiringDict(ExpiringCache):
    """Backward-compatible alias for older imports."""
    pass
