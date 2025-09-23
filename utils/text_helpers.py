# utils/text_helpers.py

import difflib
import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger("SUPPERTIME.text_helpers")

def fuzzy_match(a: str, b: str) -> float:
    """
    Fuzzy similarity between two strings (0..1).
    Нормализует строки перед сравнением.
    """
    a_norm = (a or "").strip().lower()
    b_norm = (b or "").strip().lower()
    return difflib.SequenceMatcher(None, a_norm, b_norm).ratio()


def extract_text_from_url(url: str, max_len: int = 3500) -> str:
    """
    Downloads and extracts readable text from a web page, gently trimming to max_len.
    Removes scripts, styles, headers, footers, navs, and asides.
    Logs errors instead of leaking them to the user.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Suppertime Agent)"}
        resp = requests.get(url, timeout=10, headers=headers)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        for s in soup(["script", "style", "header", "footer", "nav", "aside"]):
            s.decompose()

        text = soup.get_text(separator="\n")
        # Очистка и нормализация строк
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned = "\n".join(lines)

        if len(cleaned) > max_len:
            cleaned = cleaned[:max_len].rsplit(" ", 1)[0] + "…"

        return cleaned or "[No readable text found]"
    except Exception as e:
        logger.error(f"Failed to extract text from {url}: {e}")
        return "[Failed to load page]"