import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import howru


def test_uses_last_non_greeting_message():
    howru.openai_client = None
    history = ["привет", "расскажи о космосе", "как дела"]
    msg = howru._craft_greeting(history)
    assert "космос" in msg.lower()


def test_skips_generic_phrase_echo():
    howru.openai_client = None
    history = ["привет", "как дела", "привет", "обсудим проект"]
    msg = howru._craft_greeting(history)
    # Extract the theme part if present
    if ":" in msg:
        theme = msg.split(":", 1)[1].lower()
        assert "привет" not in theme and "как дела" not in theme
