import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from utils.sqlite_state import get_lit_file, init_state_db, upsert_lit_file


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class LitMonitor:
    """Watch the ./lit directory and README.md for changes."""

    def __init__(self, root_dir: Path, db_path: str, on_change: Callable[[], None]):
        self.root_dir = Path(root_dir)
        self.db_path = db_path
        self.on_change = on_change
        self.lit_dir = self.root_dir / "lit"
        self.readme_path = self.root_dir / "README.md"
        if db_path:
            init_state_db(db_path)

    def _target_paths(self) -> Iterable[Path]:
        if self.lit_dir.exists():
            for pattern in ("**/*.txt", "**/*.md", "**/*.py"):
                yield from self.lit_dir.glob(pattern)
        if self.readme_path.exists():
            yield self.readme_path

    def _normalize_path(self, path: Path) -> str:
        try:
            relative = path.relative_to(self.root_dir)
        except ValueError:
            return path.resolve().as_posix()
        return relative.as_posix()

    def snapshot(self) -> bool:
        """Capture the current state and persist changes to SQLite."""
        changed = False
        timestamp = datetime.utcnow().isoformat()

        for file_path in self._target_paths():
            if not file_path.is_file():
                continue
            try:
                stat = file_path.stat()
            except FileNotFoundError:
                continue

            key = self._normalize_path(file_path)
            sha_value = _sha256_of_file(file_path)
            size_value = stat.st_size
            mtime_value = stat.st_mtime

            existing = get_lit_file(key)
            if (
                not existing
                or existing.get("sha256") != sha_value
                or int(existing.get("size") or 0) != size_value
                or float(existing.get("mtime") or 0.0) != mtime_value
            ):
                changed = True

            upsert_lit_file(
                key,
                sha_value,
                size_value,
                mtime_value,
                last_seen=timestamp,
            )

        return changed

    def run_loop(self, interval_sec: int = 2) -> None:
        """Continuously monitor files for changes."""
        while True:
            try:
                if self.snapshot():
                    try:
                        self.on_change()
                    except Exception as exc:
                        print(f"[SUPPERTIME][WARNING] LitMonitor callback failed: {exc}")
            except Exception as exc:
                print(f"[SUPPERTIME][WARNING] LitMonitor encountered an error: {exc}")
            time.sleep(max(1, interval_sec))
