import importlib
import sys
import types


def load_main(monkeypatch):
    openai_stub = types.ModuleType("openai")

    class DummyOpenAI:
        def __init__(self, *args, **kwargs):
            pass

    openai_stub.OpenAI = DummyOpenAI
    monkeypatch.setitem(sys.modules, "openai", openai_stub)

    pinecone_stub = types.ModuleType("pinecone")

    class DummyPinecone:
        def __init__(self, *args, **kwargs):
            pass

        def list_indexes(self):
            return []

        def create_index(self, *args, **kwargs):
            return None

        def Index(self, *args, **kwargs):
            class DummyIndex:
                def upsert(self, *a, **k):
                    return None

                def query(self, *a, **k):
                    return {"matches": []}

                def fetch(self, *a, **k):
                    return {}

            return DummyIndex()

    pinecone_stub.Pinecone = DummyPinecone
    pinecone_stub.ServerlessSpec = object
    monkeypatch.setitem(sys.modules, "pinecone", pinecone_stub)

    vs_stub = types.ModuleType("utils.vector_store")
    vs_stub.vectorize_file = lambda *a, **k: None
    vs_stub.semantic_search_in_file = lambda *a, **k: []
    vs_stub.add_memory_entry = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "utils.vector_store", vs_stub)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    import main

    importlib.reload(main)
    return main


class DummyResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


def test_send_telegram_message_retries_without_markdown(monkeypatch):
    calls = []

    def fake_post(url, json=None, data=None, files=None):
        calls.append({"url": url, "json": json, "data": data, "files": files})
        if len(calls) == 1:
            return DummyResponse(400, '{"description": "Bad Request: can\'t parse entities: ..."}')
        return DummyResponse(200, "OK")

    main_module = load_main(monkeypatch)
    monkeypatch.setattr(main_module, "TELEGRAM_BOT_TOKEN", "test-token", raising=False)
    monkeypatch.setattr(main_module, "TELEGRAM_API_URL", "https://api.telegram.org/botTEST", raising=False)
    monkeypatch.setattr(main_module.requests, "post", fake_post)

    result = main_module.send_telegram_message(123, "text_with_underscores_")

    assert result is True
    assert len(calls) == 2
    assert calls[0]["json"].get("parse_mode") == "Markdown"
    assert "parse_mode" not in calls[1]["json"]


def test_send_telegram_message_single_call_on_success(monkeypatch):
    calls = []

    def fake_post(url, json=None, data=None, files=None):
        calls.append({"url": url, "json": json, "data": data, "files": files})
        return DummyResponse(200, "OK")

    main_module = load_main(monkeypatch)
    monkeypatch.setattr(main_module, "TELEGRAM_BOT_TOKEN", "test-token", raising=False)
    monkeypatch.setattr(main_module, "TELEGRAM_API_URL", "https://api.telegram.org/botTEST", raising=False)
    monkeypatch.setattr(main_module.requests, "post", fake_post)

    result = main_module.send_telegram_message(321, "regular text")

    assert result is True
    assert len(calls) == 1
    assert calls[0]["json"].get("parse_mode") == "Markdown"
