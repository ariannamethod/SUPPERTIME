import os
import re
import json
import time
import math
import sqlite3
import hashlib
import tempfile
import zipfile
import tarfile
from pathlib import Path
from typing import Dict, Optional, List

from utils.journal import log_event

# Опциональные зависимости
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None
try:
    import docx2txt
except ImportError:
    docx2txt = None
try:
    from striprtf.striprtf import rtf_to_text
except ImportError:
    rtf_to_text = None
try:
    from odf.opendocument import load
    from odf.text import P
except ImportError:
    load = P = None
try:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup
except ImportError:
    ebooklib = epub = BeautifulSoup = None
try:
    import pandas as pd
except ImportError:
    pd = None

# Настройки
BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DB = BASE_DIR / "cache/file_cache.db"
CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
DEFAULT_MAX_TEXT_SIZE = 150_000
DEFAULT_MAX_ARCHIVE_SIZE = 10_000_000  # 10 MB

# SQLite инициализация
def init_cache_db():
    with sqlite3.connect(CACHE_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE,
                hash TEXT,
                summary TEXT,
                relevance REAL,
                timestamp REAL
            )
        """)
        conn.execute("DELETE FROM file_cache WHERE timestamp < ?", (time.time() - 7 * 86400,))
        conn.commit()

init_cache_db()

def save_cache(path: str, file_hash: str, summary: str, relevance: float):
    with sqlite3.connect(CACHE_DB) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO file_cache (path, hash, summary, relevance, timestamp) VALUES (?, ?, ?, ?, ?)",
            (path, file_hash, summary, relevance, time.time())
        )
        conn.commit()

def load_cache(path: str, max_age: float = 43200) -> Optional[Dict]:
    with sqlite3.connect(CACHE_DB) as conn:
        cursor = conn.execute(
            "SELECT hash, summary, relevance FROM file_cache WHERE path = ? AND timestamp > ?",
            (path, time.time() - max_age)
        )
        result = cursor.fetchone()
        if result:
            return {"hash": result[0], "summary": result[1], "relevance": result[2]}
        return None

# relevance — насколько текст "в резонансе" с seed
_SEED_CORPUS = "mars starship chaos resonance xai wulf memory poetry suppertime"
def compute_relevance(text: str) -> float:
    seed_words = set(re.findall(r'\w+', _SEED_CORPUS.lower()))
    text_words = set(re.findall(r'\w+', text.lower()))
    intersection = seed_words & text_words
    return len(intersection) / max(len(text_words), 1) if text_words else 0.0

# ---- extractors ----
def _truncate(text: str, max_len: int = DEFAULT_MAX_TEXT_SIZE) -> str:
    text = text.strip()
    if len(text) > max_len:
        return text[:max_len] + "\n[Truncated]"
    return text

def extract_pdf(path: str) -> str:
    if not PdfReader:
        return "[PDF unsupported: install pypdf]"
    try:
        reader = PdfReader(path)
        text = "".join(page.extract_text() or "" for page in reader.pages)
        return _truncate(text) if text.strip() else "[PDF empty]"
    except Exception as e:
        log_event({"type": "error", "msg": f"PDF error ({path}): {e}"})
        return f"[PDF error: {e}]"

def extract_txt(path: str) -> str:
    encodings = ["utf-8", "latin1", "cp1251"]
    for enc in encodings:
        try:
            with open(path, encoding=enc) as f:
                text = f.read(DEFAULT_MAX_TEXT_SIZE + 1)
            return _truncate(text)
        except UnicodeDecodeError:
            continue
    return "[TXT error: Could not decode]"

def extract_docx(path: str) -> str:
    if not docx2txt:
        return "[DOCX unsupported: install docx2txt]"
    try:
        text = docx2txt.process(path)
        return _truncate(text)
    except Exception as e:
        return f"[DOCX error: {e}]"

def extract_rtf(path: str) -> str:
    if not rtf_to_text:
        return "[RTF unsupported: install striprtf]"
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            text = rtf_to_text(f.read())
        return _truncate(text)
    except Exception as e:
        return f"[RTF error: {e}]"

def extract_odt(path: str) -> str:
    if not load or not P:
        return "[ODT unsupported: install odfpy]"
    try:
        doc = load(path)
        text = "\n".join([p.firstChild.data for p in doc.getElementsByType(P) if p.firstChild])
        return _truncate(text)
    except Exception as e:
        return f"[ODT error: {e}]"

def extract_epub(path: str) -> str:
    if not ebooklib or not BeautifulSoup:
        return "[EPUB unsupported: install ebooklib & beautifulsoup4]"
    try:
        book = epub.read_epub(path)
        chapters = []
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.content, "html.parser")
                chapters.append(soup.get_text())
        return _truncate("\n".join(chapters))
    except Exception as e:
        return f"[EPUB error: {e}]"

def extract_csv(path: str) -> str:
    if not pd:
        return "[CSV unsupported: install pandas]"
    try:
        df = pd.read_csv(path, encoding="utf-8", nrows=100)
        return df.to_string(index=False)
    except Exception as e:
        return f"[CSV error: {e}]"

# ---- main ----
def extract_text_from_file(path: str) -> str:
    ext = os.path.splitext(path)[-1].lower()
    if ext == ".pdf":
        return extract_pdf(path)
    elif ext in [".txt", ".md", ".py", ".js", ".html", ".css", ".json"]:
        return extract_txt(path)
    elif ext in [".docx", ".doc"]:
        return extract_docx(path)
    elif ext == ".rtf":
        return extract_rtf(path)
    elif ext == ".odt":
        return extract_odt(path)
    elif ext == ".epub":
        return extract_epub(path)
    elif ext == ".csv":
        return extract_csv(path)
    else:
        return f"[Unsupported file type: {os.path.basename(path)}]"

def parse_and_cache_file(path: str) -> str:
    try:
        with open(path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()[:8]
        cached = load_cache(path)
        if cached and cached["hash"] == file_hash:
            return f"{cached['summary']}\n(Relevance={cached['relevance']:.2f}, cached)"
        text = extract_text_from_file(path)
        relevance = compute_relevance(text)
        summary = text[:300].replace("\n", " ")
        save_cache(path, file_hash, summary, relevance)
        return f"{text}\n\nSummary: {summary}\nRelevance: {relevance:.2f}"
    except Exception as e:
        return f"[File handling error: {e}]"