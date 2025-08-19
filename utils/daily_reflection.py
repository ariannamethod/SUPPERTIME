import os
import json
import datetime
import threading
import time
import asyncio
from utils.vector_store import add_memory_entry
from utils.journal import log_event

DATA_PATH = os.getenv("SUPPERTIME_DATA_PATH", "./data")
JOURNAL_FILE = os.path.join(DATA_PATH, "journal.json")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")


def record_daily_reflection(text):
    ts = datetime.datetime.utcnow().isoformat()
    metadata = {"type": "daily_reflection", "ts": ts}
    vector_id = None
    try:
        vector_id = asyncio.run(add_memory_entry(text, OPENAI_KEY, metadata))
    except Exception as e:
        print(f"[SUPPERTIME][ERROR] Vector log failed: {e}")
    entry = {**metadata, "text": text, "vector_id": vector_id}
    log_event(entry)
    return entry


def load_last_reflection():
    try:
        with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)
        reflections = [e for e in entries if e.get("type") == "daily_reflection"]
        if reflections:
            return sorted(reflections, key=lambda x: x.get("ts", ""))[-1]
    except Exception:
        return None


def schedule_daily_reflection(get_chapter_title, get_chat_summary):
    def _loop():
        while True:
            now = datetime.datetime.utcnow()
            next_midnight = (now + datetime.timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
            time.sleep(max(60, (next_midnight - now).total_seconds()))
            chapter = get_chapter_title() or "Unknown"
            summary = get_chat_summary()
            text = f"{datetime.date.today().isoformat()} :: {chapter} :: {summary}"
            record_daily_reflection(text)
    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    return thread
