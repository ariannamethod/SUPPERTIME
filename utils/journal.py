import os
import json
from datetime import datetime
from utils.logger import logger

LOG_PATH = "data/journal.json"
WILDERNESS_PATH = "data/wilderness.md"

def log_event(event):
    """
    Append an event with a timestamp to the journal log (journal.json).
    """
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        if not os.path.isfile(LOG_PATH):
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                f.write("[]")
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            log = json.load(f)
            if not isinstance(log, list):
                log = []
        log.append({"ts": datetime.now().isoformat(), **event})
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Failed to write journal event: %s", e)

def wilderness_log(fragment):
    """
    Append a fragment to the wilderness log (wilderness.md).
    """
    try:
        os.makedirs(os.path.dirname(WILDERNESS_PATH), exist_ok=True)
        with open(WILDERNESS_PATH, "a", encoding="utf-8") as f:
            f.write(fragment.strip() + "\n\n")
    except Exception as e:
        logger.warning("Failed to write wilderness fragment: %s", e)
