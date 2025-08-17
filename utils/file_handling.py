import os
import tempfile
from pypdf import PdfReader
import re

MAX_TEXT_SIZE = 150_000  # Увеличим максимальный размер текста для обработки

def extract_text_from_pdf(path):
    """Extract text from PDF files."""
    try:
        reader = PdfReader(path)
        parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                parts.append(page_text)
        text = "\n\n".join(parts).strip()
        if text:
            # Clean up text - remove excessive newlines and spaces
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r' {2,}', ' ', text)
            return text[:MAX_TEXT_SIZE] + ('\n[Trimmed: only the first part is shown.]' if len(text) > MAX_TEXT_SIZE else '')
        return '[PDF is empty or unreadable—sometimes, silence is all that is left.]'
    except Exception as e:
        return f"[PDF reading error ({os.path.basename(path)}): {e}. Perhaps a simple .txt would resonate better.]"

def extract_text_from_txt(path):
    """Extract text from plain text files."""
    try:
        # Try several encodings
        encodings = ['utf-8', 'latin-1', 'cp1251', 'windows-1252']
        text = None
        
        for encoding in encodings:
            try:
                with open(path, encoding=encoding) as f:
                    text = f.read()
                break
            except UnicodeDecodeError:
                continue
        
        if text is None:
            return "[TXT reading error: Could not determine file encoding.]"
            
        # Clean up text
        text = re.sub(r'\r\n', '\n', text)  # Normalize line endings
        text = re.sub(r'\n{3,}', '\n\n', text)  # Reduce excessive newlines
        
        return text[:MAX_TEXT_SIZE] + ('\n[Trimmed: only the first part is shown.]' if len(text) > MAX_TEXT_SIZE else '')
    except Exception as e:
        return f"[TXT reading error ({os.path.basename(path)}): {e}. This file may not be suitable for Suppertime resonance.]"

def extract_text_from_docx(path):
    """Extract text from DOCX files."""
    try:
        import docx2txt
        text = docx2txt.process(path)
        text = text.strip()
        if text:
            # Clean up text
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r' {2,}', ' ', text)
            return text[:MAX_TEXT_SIZE] + ('\n[Trimmed: only the first part is shown.]' if len(text) > MAX_TEXT_SIZE else '')
        return '[DOCX is empty or unreadable—sometimes, emptiness is the message.]'
    except Exception as e:
        return f"[DOCX reading error ({os.path.basename(path)}): {e}. Try converting to .txt for better resonance.]"

def extract_text_from_rtf(path):
    """Extract text from RTF files."""
    try:
        from striprtf.striprtf import rtf_to_text
        with open(path, encoding="utf-8", errors="ignore") as f:
            text = rtf_to_text(f.read())
        text = text.strip()
        if text:
            # Clean up text
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r' {2,}', ' ', text)
            return text[:MAX_TEXT_SIZE] + ('\n[Trimmed: only the first part is shown.]' if len(text) > MAX_TEXT_SIZE else '')
        return '[RTF is empty or unreadable.]'
    except Exception as e:
        return f"[RTF reading error ({os.path.basename(path)}): {e}. Try converting to .txt for better resonance.]"

def extract_text_from_odt(path):
    """Extract text from ODT files."""
    try:
        from odf.opendocument import load
        from odf.text import P
        doc = load(path)
        text = "\n".join([p.firstChild.data for p in doc.getElementsByType(P) if p.firstChild])
        text = text.strip()
        if text:
            # Clean up text
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r' {2,}', ' ', text)
            return text[:MAX_TEXT_SIZE] + ('\n[Trimmed: only the first part is shown.]' if len(text) > MAX_TEXT_SIZE else '')
        return '[ODT is empty or unreadable.]'
    except Exception as e:
        return f"[ODT reading error ({os.path.basename(path)}): {e}. Try converting to .txt for better resonance.]"

def extract_text_from_epub(path):
    """Extract text from EPUB files."""
    try:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup
        
        def chapter_to_text(chapter):
            soup = BeautifulSoup(chapter.content, 'html.parser')
            text = soup.get_text()
            return text
        
        book = epub.read_epub(path)
        chapters = []
        
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                chapters.append(chapter_to_text(item))
                
        text = "\n\n".join(chapters)
        text = text.strip()
        if text:
            # Clean up text
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r' {2,}', ' ', text)
            return text[:MAX_TEXT_SIZE] + ('\n[Trimmed: only the first part is shown.]' if len(text) > MAX_TEXT_SIZE else '')
        return '[EPUB is empty or unreadable.]'
    except Exception as e:
        return f"[EPUB reading error ({os.path.basename(path)}): {e}. Try converting to .txt for better resonance.]"

def extract_text_from_csv(path):
    """Extract text from CSV files."""
    try:
        import csv
        
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            rows = list(reader)

            # Format as a table
            parts = []
            for row in rows[:100]:  # Limit to first 100 rows
                parts.append(" | ".join(row))

            if len(rows) > 100:
                parts.append("[Trimmed: only showing first 100 rows]")

            return "\n".join(parts)
    except Exception as e:
        return f"[CSV reading error ({os.path.basename(path)}): {e}. Try converting to .txt for better resonance.]"

def extract_text_from_file(path):
    """Extract text from various file types."""
    ext = os.path.splitext(path)[-1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(path)
    elif ext in [".txt", ".md", ".py", ".js", ".html", ".css", ".json"]:
        return extract_text_from_txt(path)
    elif ext in [".docx", ".doc"]:
        return extract_text_from_docx(path)
    elif ext == ".rtf":
        return extract_text_from_rtf(path)
    elif ext == ".odt":
        return extract_text_from_odt(path)
    elif ext == ".epub":
        return extract_text_from_epub(path)
    elif ext == ".csv":
        return extract_text_from_csv(path)
    else:
        return f"[Unsupported file type: {os.path.basename(path)}. SUPPERTIME invites only what can be read and reflected upon.]"

def get_file_metadata(path):
    """Get metadata about a file."""
    try:
        stat = os.stat(path)
        size_kb = stat.st_size / 1024
        
        return {
            "filename": os.path.basename(path),
            "extension": os.path.splitext(path)[1].lower(),
            "size_kb": round(size_kb, 2),
            "last_modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception:
        return {
            "filename": os.path.basename(path),
            "extension": os.path.splitext(path)[1].lower(),
            "error": "Could not retrieve file metadata"
        }
