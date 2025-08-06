import random
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


def test_uses_earlier_message_when_last_is_greeting():
    howru.openai_client = None
    random.seed(0)
    history = ["привет", "давай обсудим проект", "hi"]
    msg = howru._craft_greeting(history)
    assert "проект" in msg.lower()


def test_uses_prepared_topic_if_no_history_theme():
    howru.openai_client = None
    random.seed(0)
    history = ["привет", "hi", "ok"]
    msg = howru._craft_greeting(history)
    assert "favorite books" in msg.lower()


def test_fallback_message_when_no_topic_available():
    howru.openai_client = None
    backup = howru.DEFAULT_TOPICS
    howru.DEFAULT_TOPICS = []
    random.seed(0)
    history = ["привет", "hi"]
    msg = howru._craft_greeting(history)
    assert msg in {
        "Привет! Как проходит твой день?",
        "Hey there! How's your day going?",
    }
    howru.DEFAULT_TOPICS = backup
