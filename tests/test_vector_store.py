import sys
import types
import importlib
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def vector_store(monkeypatch):
    sys.modules.pop("utils.vector_store", None)
    monkeypatch.setenv("PINECONE_API_KEY", "test")
    monkeypatch.setenv("PINECONE_INDEX", "test-index")

    pinecone_stub = types.ModuleType("pinecone")

    class DummyIndex:
        def __init__(self):
            self.upserts = []

        def upsert(self, vectors):
            self.upserts.extend(vectors)

        def query(self, vector, top_k, include_metadata, filter):
            return {"matches": [{"metadata": {"chunk": 0}}, {"metadata": {"chunk": 1}}]}

        def fetch(self, ids):
            return {}

    class DummyPinecone:
        def __init__(self, api_key=None):
            self.index = DummyIndex()

        def list_indexes(self):
            return []

        def create_index(self, *args, **kwargs):
            pass

        def Index(self, name):
            return self.index

    pinecone_stub.Pinecone = DummyPinecone

    class DummyServerlessSpec:
        def __init__(self, *a, **k):
            pass

    pinecone_stub.ServerlessSpec = DummyServerlessSpec
    monkeypatch.setitem(sys.modules, "pinecone", pinecone_stub)

    openai_stub = types.ModuleType("openai")
    openai_stub.embeddings = types.SimpleNamespace(
        create=lambda *a, **k: types.SimpleNamespace(data=[types.SimpleNamespace(embedding=[0.0])])
    )
    monkeypatch.setitem(sys.modules, "openai", openai_stub)

    import utils.vector_store as vs
    importlib.reload(vs)
    return vs


def test_chunk_text(vector_store):
    chunks = vector_store.chunk_text("abcdefghij", chunk_size=5, overlap=2)
    assert chunks[0] == "abcde"
    assert chunks[1] == "defgh"
    assert chunks[2] == "ghij"
    assert chunks[3] == "j"


def test_vectorize_and_search(monkeypatch, tmp_path, vector_store):
    monkeypatch.setattr(
        vector_store,
        "chunk_text",
        lambda text, chunk_size=900, overlap=120: ["alpha", "beta"],
    )

    calls = []

    def fake_safe_embed(text, api_key):
        calls.append(text)
        return [0.1]

    monkeypatch.setattr(vector_store, "safe_embed", fake_safe_embed)
    index = vector_store.index

    file_path = tmp_path / "sample.txt"
    file_path.write_text("alpha beta", encoding="utf-8")

    ids = vector_store.vectorize_file(str(file_path), "key")
    assert ids == [f"{file_path}:{i}" for i in range(2)]
    assert len(index.upserts) == 2

    chunks = vector_store.semantic_search_in_file(str(file_path), "query", "key", top_k=2)
    assert chunks == ["alpha", "beta"]
    assert calls == ["alpha", "beta", "query"]
