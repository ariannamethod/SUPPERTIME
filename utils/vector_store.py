import os
import hashlib
from pinecone import Pinecone, ServerlessSpec
import openai
from tenacity import retry, stop_after_attempt, wait_fixed
import datetime

EMBED_DIM = 1536

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-west-2")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")

pc = None


class PineconeIndexProxy:
    """Proxy object that binds to a Pinecone index when available."""

    def __init__(self):
        self._inner = None

    def bind(self, inner):
        self._inner = inner

    @property
    def ready(self):
        return self._inner is not None

    def __getattr__(self, name):
        if self._inner is None:
            raise ConnectionError("Pinecone index is not initialized")
        return getattr(self._inner, name)

    def __bool__(self):
        return self.ready


index = PineconeIndexProxy()


def init_index():
    """Initialize Pinecone client and index on demand."""
    global pc
    if index.ready:
        return index
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        if PINECONE_INDEX not in [x["name"] for x in pc.list_indexes()]:
            pc.create_index(
                name=PINECONE_INDEX,
                dimension=EMBED_DIM,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=PINECONE_CLOUD,
                    region=PINECONE_REGION
                )
            )
        index.bind(pc.Index(PINECONE_INDEX))
    except Exception as exc:
        raise ConnectionError("Unable to initialize Pinecone index") from exc
    return index

@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def safe_embed(text, openai_api_key):
    return get_embedding(text, openai_api_key)

def get_embedding(text, openai_api_key):
    openai.api_key = openai_api_key
    res = openai.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return res.data[0].embedding

def chunk_text(text, chunk_size=900, overlap=120):
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks

def vectorize_file(fname, openai_api_key):
    """Vectorizes only one file."""
    if not index.ready:
        try:
            init_index()
        except Exception as exc:
            print(f"Failed to connect to Pinecone: {exc}")
            return []
    with open(fname, "r", encoding="utf-8") as f:
        text = f.read()
    chunks = chunk_text(text)
    file_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
    ids = []
    for idx, chunk in enumerate(chunks):
        meta_id = f"{fname}:{idx}"
        emb = safe_embed(chunk, openai_api_key)
        try:
            index.upsert(
                vectors=[(meta_id, emb, {"file": fname, "chunk": idx, "hash": file_hash})]
            )
        except Exception as exc:
            print(f"Failed to upsert vector to Pinecone: {exc}")
            return []
        ids.append(meta_id)
    return ids

def semantic_search_in_file(fname, query, openai_api_key, top_k=5):
    if not index.ready:
        try:
            init_index()
        except Exception as exc:
            print(f"Failed to connect to Pinecone: {exc}")
            return []
    emb = safe_embed(query, openai_api_key)
    file_hash = hashlib.md5(open(fname, encoding='utf-8').read().encode('utf-8')).hexdigest()
    # Search only by id of this file
    # Pinecone can't filter by id, but can by metadata
    try:
        res = index.query(
            vector=emb,
            top_k=top_k,
            include_metadata=True,
            filter={"file": fname, "hash": file_hash},
        )
    except Exception as exc:
        print(f"Failed to query Pinecone: {exc}")
        return []
    matches = res.get("matches", []) if isinstance(res, dict) else getattr(res, "matches", [])
    chunks = []
    for match in matches:
        metadata = match.get("metadata", {})
        chunk_idx = metadata.get("chunk")
        try:
            with open(fname, "r", encoding="utf-8") as f:
                all_chunks = chunk_text(f.read())
                chunk_text_ = all_chunks[chunk_idx] if chunk_idx is not None and chunk_idx < len(all_chunks) else ""
        except Exception:
            chunk_text_ = ""
        if chunk_text_:
            chunks.append(chunk_text_)
    return chunks


def add_memory_entry(text, openai_api_key, metadata=None):
    """Vectorize arbitrary text as a memory entry."""
    if metadata is None:
        metadata = {}
    ts = datetime.datetime.utcnow().isoformat()
    entry_id = metadata.get("id", f"memory-{ts}")
    if not index.ready:
        try:
            init_index()
        except Exception as exc:
            print(f"Failed to connect to Pinecone: {exc}")
            return None
    emb = safe_embed(text, openai_api_key)
    try:
        index.upsert([(entry_id, emb, {**metadata, "ts": ts})])
    except Exception as exc:
        print(f"Failed to upsert memory entry to Pinecone: {exc}")
        return None
    return entry_id


def fetch_entries(ids):
    """Fetch entries by ID from Pinecone."""
    if not ids:
        return {}
    if not index.ready:
        try:
            init_index()
        except Exception as exc:
            print(f"Failed to connect to Pinecone: {exc}")
            return {}
    try:
        return index.fetch(ids)
    except Exception as exc:
        print(f"Failed to fetch from Pinecone: {exc}")
        return {}
