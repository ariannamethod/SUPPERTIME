import importlib
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))


def test_snapshot_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPPERTIME_DATA_PATH", str(tmp_path))

    snapshot_store = importlib.import_module("utils.snapshot_store")
    importlib.reload(snapshot_store)

    snapshot_store.upsert_snapshot(
        "literary_vector",
        {str(Path("lit") / "chapter.md"): "hash123"},
        snapshot_date="2025-09-22",
        metadata={"file_count": 1},
    )

    latest = snapshot_store.latest_snapshot("literary_vector")
    assert latest["date"] == "2025-09-22"
    assert latest["payload"] == {str(Path("lit") / "chapter.md"): "hash123"}
    assert latest["metadata"]["file_count"] == 1

    summary = snapshot_store.summarize_literary_payload(latest["payload"])
    assert "chapter.md" in summary


def test_compose_prompt_uses_latest_context(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPPERTIME_DATA_PATH", str(tmp_path))

    prompt_builder = importlib.import_module("utils.prompt_builder")
    prompt_builder = importlib.reload(prompt_builder)

    monkeypatch.setattr(prompt_builder, "build_system_prompt", lambda *a, **k: "BASE")
    monkeypatch.setattr(
        prompt_builder,
        "get_today_chapter_info",
        lambda: {"title": "SHIFT", "path": "chapters/st01.md", "content": "The field hums."},
    )
    monkeypatch.setattr(
        prompt_builder,
        "latest_snapshot",
        lambda *_: {"date": "2025-09-22", "payload": {"lit/file.md": "abc"}, "metadata": {}},
    )
    monkeypatch.setattr(
        prompt_builder,
        "load_last_reflection",
        lambda: {"text": "Resonance recorded."},
    )

    instructions = prompt_builder.compose_assistant_instructions()

    assert "BASE" in instructions
    assert "Resonant Execution Directives" in instructions
    assert "file.md" in instructions
    assert "Resonance recorded" in instructions
    assert "P.S." in instructions
