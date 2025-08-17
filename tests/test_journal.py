import sys
import json
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import journal


def test_log_event_appends(monkeypatch, tmp_path):
    monkeypatch.setattr(journal, "LOG_PATH", str(tmp_path / "journal.json"))
    journal.log_event({"type": "a"})
    journal.log_event({"type": "b"})
    with open(journal.LOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data[0]["type"] == "a"
    assert data[1]["type"] == "b"


def test_wilderness_log_appends(monkeypatch, tmp_path):
    monkeypatch.setattr(journal, "WILDERNESS_PATH", str(tmp_path / "wild.md"))
    journal.wilderness_log("first")
    journal.wilderness_log("second")
    with open(journal.WILDERNESS_PATH, "r", encoding="utf-8") as f:
        text = f.read()
    assert text == "first\n\nsecond\n\n"
