import sys
from pathlib import Path
import types

sys.path.append(str(Path(__file__).resolve().parents[1]))

# Stub vector_store to avoid network calls during import
stub_vs = types.ModuleType("utils.vector_store")
stub_vs.vectorize_file = lambda *a, **k: None
stub_vs.semantic_search_in_file = lambda *a, **k: []
sys.modules["utils.vector_store"] = stub_vs

from fastapi.testclient import TestClient
from webface import server


class DummyChatCompletions:
    def create(self, *args, **kwargs):
        class Msg:
            content = "model says hi"
        class Choice:
            message = Msg()
        class Resp:
            choices = [Choice()]
        return Resp()


class DummyClient:
    chat = type("obj", (), {"completions": DummyChatCompletions()})()


def test_fallback_without_api_key():
    server.openai_client = None
    client = TestClient(server.app)
    resp = client.post("/chat", json={"message": "test message"})
    data = resp.json()
    assert "api" in data["reply"].lower()
    assert "test message" not in data["reply"].lower()


def test_with_openai_client_stub():
    server.openai_client = DummyClient()
    client = TestClient(server.app)
    resp = client.post("/chat", json={"message": "whatever"})
    data = resp.json()
    assert data["reply"] == "model says hi"
