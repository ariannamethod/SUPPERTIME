import random
import types
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from utils import howru


def test_format_history_truncates_long_entries():
    history = [
        {"role": "user", "text": "привет"},
        {"role": "assistant", "text": "a" * 400},
    ]
    formatted = howru._format_history(history)
    assert "user: привет" in formatted
    assert "assistant:" in formatted
    # Ensure the long assistant text is truncated with ellipsis
    assert formatted.splitlines()[-1].endswith("...")


def test_generate_checkin_without_client_uses_fallback_seeded():
    howru.openai_client = None
    random.seed(1)
    message = howru._generate_checkin(["context"])
    expected = (
        "Привет, врезался луч резонанса. Как держится твоя траектория? "
        "Если что-то гремит — дай знать."
    )
    assert message == expected


def test_generate_checkin_with_client_includes_context():
    class StubClient:
        def __init__(self):
            self.calls = []
            self.chat = types.SimpleNamespace(completions=self)

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return types.SimpleNamespace(
                choices=[
                    types.SimpleNamespace(
                        message=types.SimpleNamespace(content="crafted check-in")
                    )
                ]
            )

    stub = StubClient()
    howru.openai_client = stub
    history = [{"role": "user", "text": "расскажи о космосе"}]
    message = howru._generate_checkin(history)
    assert message == "crafted check-in"
    prompt = stub.calls[0]["messages"][1]["content"]
    assert "расскажи о космосе" in prompt
