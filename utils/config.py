import os
import glob
import json
import hashlib
import threading

from utils.whatdotheythinkiam import reflect_on_readme

from utils.vector_store import vectorize_file, semantic_search_in_file

SUPPERTIME_DATA_PATH = os.getenv("SUPPERTIME_DATA_PATH", "./data")
LIT_DIR = os.path.join(SUPPERTIME_DATA_PATH, "lit")
if not os.path.isdir(LIT_DIR):
    fallback = "./lit"
    if os.path.isdir(fallback):
        LIT_DIR = fallback

SNAPSHOT_PATH = os.path.join(SUPPERTIME_DATA_PATH, "vectorized_snapshot.json")


def _load_snapshot():
    try:
        with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_snapshot(snapshot):
    os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)


def _file_hash(path):
    try:
        hash_md5 = hashlib.md5()
        with open(path, "r", encoding="utf-8") as f:
            for chunk in iter(lambda: f.read(8192), ""):
                hash_md5.update(chunk.encode("utf-8"))
        return hash_md5.hexdigest()
    except Exception:
        return ""


def vectorize_lit_files():
    """Vectorize new or updated literary files."""
    lit_files = (
        glob.glob(os.path.join(LIT_DIR, "*.txt"))
        + glob.glob(os.path.join(LIT_DIR, "*.md"))
    )
    if not lit_files:
        return "No literary files found in the lit directory."

    snapshot = _load_snapshot()
    changed = []
    for path in lit_files:
        h = _file_hash(path)
        if not h:
            continue
        if snapshot.get(path) != h:
            try:
                vectorize_file(path, os.getenv("OPENAI_API_KEY"))
                snapshot[path] = h
                changed.append(path)
            except Exception as e:
                print(f"[SUPPERTIME][ERROR] Failed to vectorize {path}: {e}")
    if changed:
        _save_snapshot(snapshot)
        return f"Indexed {len(changed)} files."
    return "No new literary files to index."


def get_vectorized_files():
    """Return list of vectorized literary files."""
    snapshot = _load_snapshot()
    return list(snapshot.keys())


def search_lit_files(query):
    """Search vectorized literary files for a query."""
    lit_files = get_vectorized_files()
    if not lit_files:
        return "No literary files have been indexed yet."

    results = []
    for file_path in lit_files:
        try:
            chunks = semantic_search_in_file(
                file_path, query, os.getenv("OPENAI_API_KEY"), top_k=2
            )
            if chunks:
                file_name = os.path.basename(file_path)
                results.append(
                    f"From {file_name}:\n\n" + "\n\n---\n\n".join(chunks)
                )
        except Exception as e:
            print(f"[SUPPERTIME][ERROR] Failed to search in {file_path}: {e}")

    if results:
        return "\n\n==========\n\n".join(results)
    return "No relevant information found in the literary files."


def _search_logs(query):
    """Search in journal and other data files for the query."""
    query_lower = query.lower()
    hits = []
    data_files = [
        "journal.json",
        "wilderness.md",
        "suppertime_resonance.md",
        "who_is_real_me.md",
    ]
    for name in data_files:
        path = os.path.join(SUPPERTIME_DATA_PATH, name)
        if not os.path.isfile(path):
            continue
        try:
            if name.endswith(".json"):
                with open(path, "r", encoding="utf-8") as f:
                    entries = json.load(f)
                if isinstance(entries, list):
                    for entry in entries:
                        text = json.dumps(entry, ensure_ascii=False)
                        if query_lower in text.lower():
                            ts = entry.get("ts", "?")
                            snippet = text[:200]
                            hits.append(f"[{name} @ {ts}] {snippet}")
            else:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                idx = text.lower().find(query_lower)
                if idx != -1:
                    snippet = text[max(0, idx - 50): idx + 150]
                    hits.append(f"[{name}] ...{snippet}...")
        except Exception as e:
            print(f"[SUPPERTIME][ERROR] Failed to search in {name}: {e}")
    return hits


def search_memory(query):
    """Search both vectorized literary files and local logs."""
    lit_res = search_lit_files(query)
    log_res = _search_logs(query)

    pieces = []
    if lit_res and not lit_res.startswith("No "):
        pieces.append(lit_res)
    if log_res:
        pieces.append("\n\n".join(log_res))
    if pieces:
        return "\n\n==========\n\n".join(pieces)
    return "No relevant information found in the memory."


def explore_lit_directory():
    """Return information about literary files and their status."""
    lit_files = (
        glob.glob(os.path.join(LIT_DIR, "*.txt"))
        + glob.glob(os.path.join(LIT_DIR, "*.md"))
    )
    if not lit_files:
        return "No literary files found in the lit directory."

    snapshot = _load_snapshot()
    report = [f"Found {len(lit_files)} literary files:"]
    for path in lit_files:
        file_name = os.path.basename(path)
        status = "Indexed" if path in snapshot else "Not indexed"
        try:
            size_kb = os.path.getsize(path) / 1024
            with open(path, "r", encoding="utf-8") as f:
                preview = "".join(f.readlines()[:3]).strip()
                if len(preview) > 100:
                    preview = preview[:100] + "..."
            report.append(
                f"\n**{file_name}** ({size_kb:.1f} KB) - {status}\n"
                f"Preview: {preview}"
            )
        except Exception:
            report.append(f"\n**{file_name}** - {status} (Error reading file)")
    return "\n".join(report)


# Thread control events
_lit_check_event = threading.Event()
_lit_check_thread = None

_identity_reflection_event = threading.Event()
_identity_reflection_thread = None


def schedule_lit_check(interval_hours=72):
    """Periodically check the lit folder for new files."""

    def _loop():
        while True:
            if _lit_check_event.is_set():
                break
            vectorize_lit_files()
            if _lit_check_event.wait(interval_hours * 3600):
                break

    global _lit_check_thread
    _lit_check_thread = threading.Thread(target=_loop, daemon=True)
    _lit_check_thread.start()
    return _lit_check_thread


def stop_lit_check():
    """Stop the lit folder checking loop."""

    _lit_check_event.set()
    if _lit_check_thread:
        _lit_check_thread.join()


def schedule_identity_reflection(interval_days=7):
    """Run README reflection on startup and weekly."""

    def _loop():
        # initial run
        reflect_on_readme(force=True)
        while True:
            if _identity_reflection_event.is_set():
                break
            if _identity_reflection_event.wait(interval_days * 24 * 3600):
                break
            try:
                reflect_on_readme()
            except Exception as e:
                print(f"[SUPPERTIME][ERROR] Identity reflection failed: {e}")

    global _identity_reflection_thread
    _identity_reflection_thread = threading.Thread(target=_loop, daemon=True)
    _identity_reflection_thread.start()
    return _identity_reflection_thread


def stop_identity_reflection():
    """Stop the identity reflection loop."""

    _identity_reflection_event.set()
    if _identity_reflection_thread:
        _identity_reflection_thread.join()
