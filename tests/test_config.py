import sys
import types
import importlib
import json
import hashlib
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))


def test_file_hash(monkeypatch, tmp_path):
    stub_vs = types.ModuleType("utils.vector_store")
    stub_vs.vectorize_file = lambda *a, **k: None
    stub_vs.semantic_search_in_file = lambda *a, **k: []
    monkeypatch.setitem(sys.modules, "utils.vector_store", stub_vs)
    import utils.config as config
    importlib.reload(config)

    file_path = tmp_path / "x.txt"
    file_path.write_text("hello", encoding="utf-8")
    expected = hashlib.md5(b"hello").hexdigest()
    assert config._file_hash(str(file_path)) == expected
    assert config._file_hash(str(tmp_path / "missing.txt")) == ""


def test_vectorize_lit_files_workflow(monkeypatch, tmp_path):
    calls = []
    stub_vs = types.ModuleType("utils.vector_store")

    def fake_vectorize_file(path, api_key):
        calls.append(path)

    stub_vs.vectorize_file = fake_vectorize_file
    stub_vs.semantic_search_in_file = lambda *a, **k: []
    monkeypatch.setitem(sys.modules, "utils.vector_store", stub_vs)
    import utils.config as config
    importlib.reload(config)

    lit_dir = tmp_path / "lit"
    lit_dir.mkdir()
    file_path = lit_dir / "file.txt"
    file_path.write_text("content", encoding="utf-8")

    monkeypatch.setattr(config, "LIT_DIR", str(lit_dir))
    monkeypatch.setattr(config, "SNAPSHOT_PATH", str(tmp_path / "snapshot.json"))

    result = config.vectorize_lit_files()
    assert result == "Indexed 1 files."
    assert calls == [str(file_path)]

    result2 = config.vectorize_lit_files()
    assert result2 == "No new literary files to index."

    with open(config.SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
    assert snapshot[str(file_path)] == config._file_hash(str(file_path))
