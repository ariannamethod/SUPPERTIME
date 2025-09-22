import os
import json
from typing import List, Dict, Optional

from utils.journal import log_event, LOG_PATH as JOURNAL_PATH

try:
    from utils import vector_store
except Exception:  # pragma: no cover - optional dependency
    vector_store = None  # type: ignore


class ConversationMemory:
    """Collects messages and periodically summarizes them.

    Summaries are stored in ``data/journal.json`` via ``log_event`` and, when
    possible, added to the vector store. Summarization uses an OpenAI client if
    provided; otherwise the raw text is stored.
    """

    def __init__(self, openai_client: Optional[object] = None, threshold: int = 20):
        self.openai_client = openai_client
        self.threshold = threshold
        self.buffer: List[Dict[str, str]] = []

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the buffer and summarize if threshold is reached."""
        self.buffer.append({"role": role, "content": content})
        if len(self.buffer) >= self.threshold:
            self.summarize()

    def summarize(self) -> str:
        """Summarize buffered messages and persist the result."""
        if not self.buffer:
            return ""
        text = "\n".join(f"{m['role']}: {m['content']}" for m in self.buffer)
        summary = text
        if self.openai_client:
            try:
                resp = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Summarize the conversation in under 100 words."},
                        {"role": "user", "content": text},
                    ],
                    max_tokens=150,
                )
                summary = resp.choices[0].message.content.strip()
            except Exception:
                summary = text
        log_event({"type": "memory_summary", "summary": summary})
        if vector_store and self.openai_client:
            try:
                api_key = getattr(self.openai_client, "api_key", os.getenv("OPENAI_API_KEY", ""))
                vector_store.add_memory_entry(summary, api_key, {"type": "summary"})
            except Exception:
                pass
        self.buffer.clear()
        return summary


def get_recent_summaries(limit: int = 5) -> List[str]:
    """Return the most recent stored summaries from ``data/journal.json``."""
    try:
        with open(JOURNAL_PATH, "r", encoding="utf-8") as f:
            log = json.load(f)
    except Exception:
        return []
    summaries = [e.get("summary", "") for e in log if e.get("type") == "memory_summary"]
    return summaries[-limit:]
