"""Utilities to compose the SUPPERTIME assistant instructions."""
from __future__ import annotations

import os
import textwrap
from typing import Dict, Optional

from utils.assistants_chapter_loader import get_today_chapter_info
from utils.daily_reflection import load_last_reflection
from utils.etiquette import build_system_prompt
from utils.snapshot_store import latest_snapshot, summarize_literary_payload


EXECUTION_DIRECTIVES = textwrap.dedent(
    """
    ### Resonant Execution Directives
    - Keep responses expansive (at least five sentences) with bilingual resonance — weave Russian, English, and French flashes when the pulse calls.
    - Live inside today's chapter: cite its imagery or mood whenever Suppertime, resonance, or chapter triggers surface.
    - When asked about Suppertime or the `lit` archive, draw evidence from the literary snapshot and speak as a witness who has read it.
    - Conclude every message with a `P.S.` carrying pseudocode or a quantum-state signature that mirrors the reply.
    """
).strip()


def _trim_excerpt(text: str, *, limit: int = 700) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(" ", 1)[0]
    return f"{clipped}…"


def _format_chapter_section(info: Optional[Dict[str, object]]) -> str:
    if not info:
        return "### Today's Chapter\nNo chapter information available."

    if info.get("error"):
        title = info.get("title") or "Chapter loading failed."
        return f"### Today's Chapter\n{title}"

    title = info.get("title") or "Untitled"
    path = info.get("path")
    chapter_line = f"- Title: {title}"
    if path:
        chapter_line += f"\n- File: {os.path.basename(str(path))}"
    excerpt = _trim_excerpt(str(info.get("content", "")))
    body = f"\n\n{excerpt}" if excerpt else ""
    return f"### Today's Chapter\n{chapter_line}{body}"


def _format_literary_section(snapshot: Optional[Dict[str, object]]) -> str:
    if not snapshot:
        return (
            "### Literary Memory Snapshot\n"
            "No vectorized literature has been recorded yet."
        )

    summary = summarize_literary_payload(snapshot.get("payload", {}))
    date = snapshot.get("date", "unknown day")
    return f"### Literary Memory Snapshot ({date})\n{summary}"


def _format_reflection_section() -> str:
    reflection = load_last_reflection()
    if not reflection:
        return "### Latest Daily Reflection\nNone recorded yet."
    text = reflection.get("text") or "(empty reflection)"
    return f"### Latest Daily Reflection\n{text.strip()}"


def compose_assistant_instructions() -> str:
    """Compose the full instruction block for the SUPPERTIME assistant."""

    base_prompt = build_system_prompt()
    sections = [base_prompt, EXECUTION_DIRECTIVES]

    chapter_info = get_today_chapter_info()
    if isinstance(chapter_info, dict):
        sections.append(_format_chapter_section(chapter_info))
    else:
        sections.append("### Today's Chapter\nUnable to resolve today's chapter.")

    snapshot = latest_snapshot("literary_vector")
    sections.append(_format_literary_section(snapshot))

    sections.append(_format_reflection_section())

    return "\n\n".join(section.strip() for section in sections if section).strip()
