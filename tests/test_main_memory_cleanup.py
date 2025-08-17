import sys
import types
import importlib
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))


def test_log_history_cleanup(monkeypatch):
    openai_stub = types.ModuleType("openai")

    class DummyOpenAI:
        def __init__(self, *args, **kwargs):
            pass

    openai_stub.OpenAI = DummyOpenAI
    monkeypatch.setitem(sys.modules, "openai", openai_stub)

    pinecone_stub = types.ModuleType("pinecone")

    class DummyPinecone:
        def __init__(self, *a, **k):
            pass

        def list_indexes(self):
            return []

        def create_index(self, *a, **k):
            pass

        def Index(self, name):
            class I:
                def upsert(self, *a, **k):
                    pass

                def query(self, *a, **k):
                    return {"matches": []}

                def fetch(self, ids):
                    return {}

            return I()

    pinecone_stub.Pinecone = DummyPinecone
    pinecone_stub.ServerlessSpec = object
    monkeypatch.setitem(sys.modules, "pinecone", pinecone_stub)

    vs_stub = types.ModuleType("utils.vector_store")
    vs_stub.vectorize_file = lambda *a, **k: None
    vs_stub.semantic_search_in_file = lambda *a, **k: []
    vs_stub.add_memory_entry = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "utils.vector_store", vs_stub)

    monkeypatch.setenv("OPENAI_API_KEY", "x")
    import main
    importlib.reload(main)

    for i in range(25):
        main.log_history("user", f"msg{i}")

    history = main.CHAT_HISTORY["user"]
    assert len(history) == 20
    assert history[0] == "msg5"
