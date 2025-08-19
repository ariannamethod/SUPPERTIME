import os
import hashlib
import asyncio
from pinecone import Pinecone, ServerlessSpec
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_fixed
import datetime

EMBED_DIM = 1536

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-west-2")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")

# --- Init Pinecone connection and index ---
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

index = pc.Index(PINECONE_INDEX)

@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
async def safe_embed(text, openai_api_key):
    return await get_embedding(text, openai_api_key)


async def get_embedding(text, openai_api_key):
    client = AsyncOpenAI(api_key=openai_api_key)
    res = await asyncio.wait_for(
        client.embeddings.create(model="text-embedding-ada-002", input=text),
        timeout=30,
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

async def vectorize_file(fname, openai_api_key):
    """Vectorizes only one file."""
    with open(fname, "r", encoding="utf-8") as f:
        text = f.read()
    chunks = chunk_text(text)
    file_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
    ids = []
    for idx, chunk in enumerate(chunks):
        meta_id = f"{fname}:{idx}"
        emb = await safe_embed(chunk, openai_api_key)
        await asyncio.to_thread(
            index.upsert,
            vectors=[(meta_id, emb, {"file": fname, "chunk": idx, "hash": file_hash})],
        )
        ids.append(meta_id)
    return ids

async def semantic_search_in_file(fname, query, openai_api_key, top_k=5):
    emb = await safe_embed(query, openai_api_key)
    file_hash = hashlib.md5(open(fname, encoding="utf-8").read().encode("utf-8")).hexdigest()
    res = await asyncio.to_thread(
        index.query,
        vector=emb,
        top_k=top_k,
        include_metadata=True,
        filter={"file": fname, "hash": file_hash},
    )
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


async def add_memory_entry(text, openai_api_key, metadata=None):
    """Vectorize arbitrary text as a memory entry."""
    if metadata is None:
        metadata = {}
    ts = datetime.datetime.utcnow().isoformat()
    entry_id = metadata.get("id", f"memory-{ts}")
    emb = await safe_embed(text, openai_api_key)
    await asyncio.to_thread(
        index.upsert,
        [(entry_id, emb, {**metadata, "ts": ts})],
    )
    return entry_id


async def fetch_entries(ids):
    """Fetch entries by ID from Pinecone."""
    if not ids:
        return {}
    return await asyncio.to_thread(index.fetch, ids)
