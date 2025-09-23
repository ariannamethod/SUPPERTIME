# utils/vector_store.py

import os
import sys
import json
import time
import hashlib
import logging
import datetime
from typing import List, Dict, Any, Optional

from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

# Pinecone v3
from pinecone import Pinecone, ServerlessSpec

# OpenAI embeddings (совместимо с новыми SDK)
try:
    # openai>=1.0.0
    from openai import OpenAI
    _OPENAI_CLIENT_STYLE = "v1"
except Exception:
    # старый клиент
    import openai as _openai_legacy
    _OPENAI_CLIENT_STYLE = "legacy"

# -------------------- Logging (Railway: stdout/stderr) --------------------

logger = logging.getLogger("SUPPERTIME.vector_store")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# -------------------- Config --------------------

# По умолчанию используем text-embedding-3-small (1536 dims), можно переопределить env’ом
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
_EMBED_DIM_MAP = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    # на всякий случай старые алиасы
    "text-embedding-ada-002": 1536,
}
EMBED_DIM = int(os.getenv("EMBED_DIM", _EMBED_DIM_MAP.get(EMBED_MODEL, 1536)))

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-west-2")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")

if not PINECONE_INDEX:
    logger.warning("PINECONE_INDEX is not set. Vector store will not initialize until it is provided.")

# -------------------- Pinecone lazy proxy --------------------

class PineconeIndexProxy:
    """Lazy proxy; безопасен до init_index()."""

    def __init__(self):
        self._inner = None

    def bind(self, inner):
        self._inner = inner

    @property
    def ready(self) -> bool:
        return self._inner is not None

    def __getattr__(self, name):
        if self._inner is None:
            raise ConnectionError("Pinecone index is not initialized")
        return getattr(self._inner, name)

    def __bool__(self):
        return self.ready


pc = None
index = PineconeIndexProxy()

# -------------------- OpenAI embeddings helper --------------------

def _get_openai_client(openai_api_key: Optional[str]):
    if not openai_api_key:
        raise ValueError("OpenAI API key is required for embeddings")
    if _OPENAI_CLIENT_STYLE == "v1":
        return OpenAI(api_key=openai_api_key)
    else:
        _openai_legacy.api_key = openai_api_key
        return _openai_legacy

@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(1.0),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _embed_once(text: str, openai_api_key: str) -> List[float]:
    text = text or ""
    if not text.strip():
        return [0.0] * EMBED_DIM

    client = _get_openai_client(openai_api_key)

    if _OPENAI_CLIENT_STYLE == "v1":
        # openai>=1.0.0
        res = client.embeddings.create(model=EMBED_MODEL, input=text)
        return res.data[0].embedding
    else:
        # legacy
        res = client.Embedding.create(model=EMBED_MODEL, input=text)
        return res["data"][0]["embedding"]

def safe_embed(text: str, openai_api_key: str) -> List[float]:
    try:
        return _embed_once(text, openai_api_key)
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        # не валим пайплайн — возвращаем нулевой вектор
        return [0.0] * EMBED_DIM

# -------------------- Pinecone init --------------------

def init_index():
    """Инициализировать Pinecone и индекс. Идемпотентно."""
    global pc
    if index.ready:
        return index

    if not PINECONE_API_KEY or not PINECONE_INDEX:
        raise ConnectionError("Pinecone credentials not set (PINECONE_API_KEY/PINECONE_INDEX)")

    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        existing = [x.name for x in pc.list_indexes()]
        if PINECONE_INDEX not in existing:
            logger.info(f"Creating Pinecone index '{PINECONE_INDEX}' (dim={EMBED_DIM})...")
            pc.create_index(
                name=PINECONE_INDEX,
                dimension=EMBED_DIM,
                metric="cosine",
                spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
            )
            # индексу нужно время подняться
            for _ in range(30):
                if PINECONE_INDEX in [x.name for x in pc.list_indexes()]:
                    break
                time.sleep(1.0)
        index.bind(pc.Index(PINECONE_INDEX))
        logger.info(f"Pinecone index '{PINECONE_INDEX}' is ready.")
    except Exception as exc:
        logger.error(f"Unable to initialize Pinecone index: {exc}")
        raise ConnectionError("Unable to initialize Pinecone index") from exc

    return index

# -------------------- Text chunking --------------------

def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> List[str]:
    """Простой чанкёр с overlap. Никаких урезаний смысла — только деление."""
    chunks: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start += max(1, chunk_size - overlap)
    return chunks

# -------------------- Vectorization --------------------

def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _read_utf8(fname: str) -> str:
    with open(fname, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def vectorize_file(fname: str, openai_api_key: str) -> List[str]:
    """Завекторизовать один файл. Возвращает список meta_id."""
    if not index.ready:
        try:
            init_index()
        except Exception as exc:
            logger.error(f"Failed to connect to Pinecone: {exc}")
            return []

    try:
        text = _read_utf8(fname)
    except Exception as e:
        logger.error(f"Failed to read file '{fname}': {e}")
        return []

    chunks = chunk_text(text)
    file_hash = _sha256_bytes(text.encode("utf-8"))
    ids: List[str] = []

    for idx, chunk in enumerate(chunks):
        meta_id = f"{fname}:{idx}"
        emb = safe_embed(chunk, openai_api_key)
        try:
            index.upsert(
                vectors=[(meta_id, emb, {"file": fname, "chunk": idx, "hash": file_hash})]
            )
            ids.append(meta_id)
        except Exception as exc:
            logger.error(f"Failed to upsert vector to Pinecone for '{meta_id}': {exc}")
            # продолжаем остальные чанки вместо немедленного выхода
            continue

    logger.info(f"Vectorized '{fname}': {len(ids)} chunks upserted.")
    return ids

# -------------------- Semantic search --------------------

def semantic_search_in_file(
    fname: str,
    query: str,
    openai_api_key: str,
    top_k: int = 5,
    return_scores: bool = False,
) -> List[str]:
    """Семантический поиск по одному файлу, фильтр метаданными (file, hash)."""
    if not index.ready:
        try:
            init_index()
        except Exception as exc:
            logger.error(f"Failed to connect to Pinecone: {exc}")
            return []

    emb = safe_embed(query, openai_api_key)

    try:
        text = _read_utf8(fname)
        file_hash = _sha256_bytes(text.encode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to read file for search '{fname}': {e}")
        return []

    try:
        res = index.query(
            vector=emb,
            top_k=top_k,
            include_metadata=True,
            filter={"file": fname, "hash": file_hash},
        )
    except Exception as exc:
        logger.error(f"Failed to query Pinecone: {exc}")
        return []

    matches = getattr(res, "matches", None)
    if matches is None and isinstance(res, dict):
        matches = res.get("matches", [])
    if not matches:
        return []

    # Реконструируем исходные чанки (важно использовать тот же chunker)
    try:
        all_chunks = chunk_text(text)
    except Exception as e:
        logger.error(f"Failed to re-chunk text for '{fname}': {e}")
        return []

    out: List[str] = []
    for m in matches:
        md = getattr(m, "metadata", None) or m.get("metadata", {})
        chunk_idx = md.get("chunk")
        if isinstance(chunk_idx, int) and 0 <= chunk_idx < len(all_chunks):
            if return_scores:
                score = getattr(m, "score", None) or m.get("score")
                out.append(json.dumps({"chunk_idx": chunk_idx, "score": score, "text": all_chunks[chunk_idx]}))
            else:
                out.append(all_chunks[chunk_idx])

    return out

# -------------------- Arbitrary memory entries --------------------

def add_memory_entry(
    text: str,
    openai_api_key: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Векторизовать произвольный текст как запись памяти."""
    if metadata is None:
        metadata = {}

    ts = datetime.datetime.utcnow().isoformat()
    entry_id = metadata.get("id", f"memory-{ts}")

    if not index.ready:
        try:
            init_index()
        except Exception as exc:
            logger.error(f"Failed to connect to Pinecone: {exc}")
            return None

    emb = safe_embed(text, openai_api_key)
    try:
        index.upsert([(entry_id, emb, {**metadata, "ts": ts})])
        logger.info(f"Memory entry upserted: {entry_id}")
        return entry_id
    except Exception as exc:
        logger.error(f"Failed to upsert memory entry '{entry_id}': {exc}")
        return None

# -------------------- Fetch --------------------

def fetch_entries(ids: List[str]) -> Dict[str, Any]:
    """Получить записи по id из Pinecone."""
    if not ids:
        return {}

    if not index.ready:
        try:
            init_index()
        except Exception as exc:
            logger.error(f"Failed to connect to Pinecone: {exc}")
            return {}

    try:
        res = index.fetch(ids)
        return res if isinstance(res, dict) else getattr(res, "vectors", {})
    except Exception as exc:
        logger.error(f"Failed to fetch from Pinecone: {exc}")
        return {}