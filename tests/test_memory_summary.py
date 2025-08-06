import sys
import types
import json
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

# Stub vector_store to avoid network calls
stub_vs = types.ModuleType("utils.vector_store")
stub_vs.add_memory_entry = lambda *a, **k: None
sys.modules["utils.vector_store"] = stub_vs

from utils import journal  # noqa: E402


def test_memory_writes_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(journal, "LOG_PATH", str(tmp_path / "journal.json"))
    import importlib
    import utils.memory as memory
    importlib.reload(memory)
    from utils.memory import ConversationMemory, get_recent_summaries

    mem = ConversationMemory(openai_client=None, threshold=2)
    mem.add_message("user", "hello")
    mem.add_message("assistant", "hi")
    summaries = get_recent_summaries()
    assert summaries and "hello" in summaries[-1]
    # ensure journal file was created
    with open(journal.LOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data[-1]["type"] == "memory_summary"
