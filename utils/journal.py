import os
import json
from datetime import datetime

SUPPERTIME_DATA_PATH = os.getenv("SUPPERTIME_DATA_PATH", "./data")

LOG_PATH = os.path.join(SUPPERTIME_DATA_PATH, "journal.json")
WILDERNESS_PATH = os.path.join(SUPPERTIME_DATA_PATH, "wilderness.md")


def log_event(event: dict) -> None:
    """
    Append an event with a timestamp to the journal log (journal.json).
    Each event is a dict; timestamp is auto-inserted.
    """
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

        # ensure journal exists
        if not os.path.isfile(LOG_PATH):
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                f.write("[]")

        try:
            with open(LOG_PATH, "r", encoding="utf-8") as f:
                log = json.load(f)
            if not isinstance(log, list):
                print("[SUPPERTIME][WARNING] Journal corrupted, resetting to empty list")
                log = []
        except Exception as e:
            print(f"[SUPPERTIME][ERROR] Failed to read journal: {e}, resetting")
            log = []

        log.append({"ts": datetime.now().isoformat(), **event})

        with open(LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"[SUPPERTIME][ERROR] Failed to log event: {e}")


def wilderness_log(fragment: str) -> None:
    """
    Append a fragment to the wilderness log (wilderness.md).
    """
    try:
        os.makedirs(os.path.dirname(WILDERNESS_PATH), exist_ok=True)
        with open(WILDERNESS_PATH, "a", encoding="utf-8") as f:
            f.write(fragment.strip() + "\n\n")
    except Exception as e:
        print(f"[SUPPERTIME][ERROR] Failed to write wilderness log: {e}")