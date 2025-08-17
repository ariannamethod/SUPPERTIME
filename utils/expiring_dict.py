import threading
import time
from collections.abc import MutableMapping


class ExpiringDict(MutableMapping):
    """Dictionary with a TTL for each key."""

    def __init__(self, ttl_seconds: int):
        self.ttl = ttl_seconds
        self._store = {}
        self._lock = threading.Lock()

    def _expired(self, key: str) -> bool:
        value, timestamp = self._store[key]
        return time.time() - timestamp > self.ttl

    def __getitem__(self, key):
        with self._lock:
            if key in self._store and not self._expired(key):
                value, _ = self._store[key]
                # refresh access time
                self._store[key] = (value, time.time())
                return value
            self._store.pop(key, None)
            raise KeyError(key)

    def __setitem__(self, key, value):
        with self._lock:
            self._store[key] = (value, time.time())

    def __delitem__(self, key):
        with self._lock:
            del self._store[key]

    def __iter__(self):
        with self._lock:
            keys = list(self._store.keys())
            for key in keys:
                if self._expired(key):
                    del self._store[key]
                else:
                    yield key

    def __len__(self):
        with self._lock:
            self.cleanup()
            return len(self._store)

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def items(self):
        with self._lock:
            for key in list(self._store.keys()):
                if self._expired(key):
                    del self._store[key]
                else:
                    value, _ = self._store[key]
                    yield key, value

    def values(self):
        for _, value in self.items():
            yield value

    def cleanup(self):
        with self._lock:
            now = time.time()
            expired = [k for k, (_, ts) in self._store.items() if now - ts > self.ttl]
            for key in expired:
                del self._store[key]
