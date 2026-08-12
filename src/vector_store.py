"""Vector store helper for semantic chunk persistence.

Uses Google Gemini (`google.genai`) to produce embeddings and persists
them into a Chroma collection when available. If Chroma is not usable the
helper saves embeddings to a local JSON file next to the chunks.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, List, Optional
import time
import random

from .config import (
    CHROMA_DIR,
    SEMANTIC_CHUNKS_DIR as CHUNKS_DIR,
    EMBEDDING_API_KEY,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    OPENAI_API_KEY,
)

try:  # Optional runtime deps
    import chromadb
except Exception:  # pragma: no cover - allow running without chromadb
    chromadb = None

try:
    import google.genai as genai
except Exception:  # pragma: no cover - allow running without Gemini client
    genai = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - allow running without sentence-transformers
    SentenceTransformer = None

CHROMA_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

LOCAL_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
_local_model: Any = None


def save_chunks_to_json(chunks: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(chunks, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(chunks)} semantic chunks to {out_path}")


def _extract_vector_from_embedding_obj(obj: Any) -> Optional[List[float]]:
    """Extract numeric embedding vector from various response shapes."""
    if obj is None:
        return None
    # pydantic model -> dict-like
    try:
        if hasattr(obj, "dict"):
            d = obj.dict()
        elif hasattr(obj, "__dict__"):
            d = dict(obj.__dict__)
        else:
            d = obj
        # common field names
        for key in ("values", "embedding", "vector", "embeddings", "data"):
            if isinstance(d, dict) and key in d:
                val = d[key]
                if isinstance(val, list) and all(isinstance(x, (int, float)) for x in val):
                    return [float(x) for x in val]
        # sometimes the object itself is a list
        if isinstance(obj, (list, tuple)) and all(isinstance(x, (int, float)) for x in obj):
            return [float(x) for x in obj]
    except Exception:
        pass
    return None


def _batch(iterable: Iterable, n: int):
    """Yield successive n-sized chunks from iterable."""
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= n:
            yield batch
            batch = []
    if batch:
        yield batch


def get_openai_embeddings(
    texts: list[str],
    model: str = EMBEDDING_MODEL,
    api_key: Optional[str] = None,
    batch_size: int = 64,
) -> list[list[float]]:
    """Return embeddings using the OpenAI embeddings API."""
    key = (api_key or OPENAI_API_KEY or EMBEDDING_API_KEY or "").strip()
    if not key:
        raise RuntimeError("No OpenAI API key found. Set OPENAI_API_KEY in the environment.")
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("openai is not installed. Install openai to produce embeddings.") from exc

    client = OpenAI(api_key=key)
    vectors: list[list[float]] = []
    for batch_texts in _batch(texts, batch_size):
        resp = client.embeddings.create(model=model, input=batch_texts)
        ordered = sorted(resp.data, key=lambda row: row.index)
        vectors.extend([list(row.embedding) for row in ordered])
    return vectors


def get_gemini_embeddings(
    texts: list[str],
    model: str = EMBEDDING_MODEL,
    api_key: Optional[str] = EMBEDDING_API_KEY,
    batch_size: int = 32,
    max_retries: int = 5,
    backoff_factor: float = 1.0,
) -> list[list[float]]:
    """Return embeddings for a list of texts using Google Gemini (`google.genai`).

    This function is resilient against a few different response shapes.
    """
    if genai is None:
        raise RuntimeError("google.genai is not installed. Install google-genai to produce embeddings.")
    if not api_key:
        raise RuntimeError("No embedding API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY in the environment.")

    client = genai.Client(api_key=api_key)
    vectors: list[list[float]] = []

    for batch_texts in _batch(texts, batch_size):
        attempt = 0
        last_exc: Optional[Exception] = None
        while attempt <= max_retries:
            try:
                resp = client.models.embed_content(model=model, contents=batch_texts)
                emb_objs = getattr(resp, "embeddings", None)
                if emb_objs is None:
                    try:
                        resp_dict = resp.dict() if hasattr(resp, "dict") else dict(resp)
                        emb_objs = resp_dict.get("embeddings")
                    except Exception:
                        emb_objs = None

                if emb_objs is None:
                    raise RuntimeError("Gemini returned no embeddings for the request")

                for e in emb_objs:
                    vec = _extract_vector_from_embedding_obj(e)
                    if vec is None:
                        try:
                            d = e.dict() if hasattr(e, "dict") else dict(e)
                            for v in d.values():
                                if isinstance(v, list) and all(isinstance(x, (int, float)) for x in v):
                                    vec = [float(x) for x in v]
                                    break
                        except Exception:
                            pass
                    if vec is None:
                        raise RuntimeError("Unable to extract embedding vector from Gemini response object")
                    vectors.append(vec)
                break
            except Exception as e:
                last_exc = e
                attempt += 1
                if attempt > max_retries:
                    print(f"Embedding batch failed after {max_retries} retries: {e}")
                    break
                sleep_for = backoff_factor * (2 ** (attempt - 1)) + random.random() * 0.1
                print(f"Embedding batch error (attempt {attempt}/{max_retries}), retrying in {sleep_for:.1f}s: {e}")
                time.sleep(sleep_for)

        if last_exc is not None and attempt > max_retries:
            print("Partial embeddings produced; some batches failed.")
            return vectors

    return vectors


def get_embeddings(
    texts: list[str],
    model: str = EMBEDDING_MODEL,
    api_key: Optional[str] = EMBEDDING_API_KEY,
    batch_size: int = 32,
) -> list[list[float]]:
    """Route to Gemini or OpenAI embeddings based on configured provider."""
    if EMBEDDING_PROVIDER == "openai":
        return get_openai_embeddings(texts, model=model, api_key=api_key, batch_size=max(batch_size, 64))
    return get_gemini_embeddings(texts, model=model, api_key=api_key, batch_size=batch_size)


def get_local_embeddings(texts: list[str], model_name: str = LOCAL_EMBEDDING_MODEL) -> list[list[float]]:
    """Embed texts locally with sentence-transformers. No API key or quota
    needed; used as a fallback when the Gemini embedding API is rate-limited."""
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers is not installed.")
    global _local_model
    if _local_model is None:
        _local_model = SentenceTransformer(model_name)
    vectors = _local_model.encode(texts, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def build_chroma_collection(
    collection_name: str,
    chunks: list[dict[str, Any]],
    embed_batch: int = 128,
    backend: str = "gemini",
) -> None:
    """Compute embeddings for chunks and persist into Chroma (when available).

    Saves a fallback JSON containing embeddings next to the chunks if Chroma
    cannot be used in the current runtime. `backend` selects "gemini" (API,
    subject to quota) or "local" (sentence-transformers, no quota/network).
    """
    ids = [c["chunk_id"] for c in chunks]
    docs = [c["text"] for c in chunks]
    metadatas = [c.get("metadata", {}) for c in chunks]

    if backend == "local":
        print(f"Producing embeddings for {len(docs)} chunks using local model '{LOCAL_EMBEDDING_MODEL}'...")
        vectors = get_local_embeddings(docs)
    else:
        label = "OpenAI" if EMBEDDING_PROVIDER == "openai" else "Gemini"
        print(f"Producing embeddings for {len(docs)} chunks using {label} model '{EMBEDDING_MODEL}'...")
        vectors = get_embeddings(docs, model=EMBEDDING_MODEL, api_key=EMBEDDING_API_KEY, batch_size=embed_batch)

    if len(vectors) != len(ids):
        # get_gemini_embeddings returns whatever succeeded so far if a batch
        # failed partway through the run - upserting the full ids/docs/
        # metadatas against a shorter vectors list would either error out or
        # silently misalign, assigning the wrong embedding to the wrong
        # chunk id. Keep only the successfully-embedded prefix and say so.
        print(
            f"Warning: got {len(vectors)} embeddings for {len(ids)} chunks (some batches likely failed) - "
            f"only persisting the {len(vectors)} that succeeded."
        )
        ids = ids[: len(vectors)]
        docs = docs[: len(vectors)]
        metadatas = metadatas[: len(vectors)]

    if chromadb is None:
        # fallback: save embeddings to file for manual import
        out_path = CHUNKS_DIR / "_chunks_with_embeddings.json"
        payload = [
            {"id": _id, "text": text, "metadata": md, "embedding": vec}
            for _id, text, md, vec in zip(ids, docs, metadatas, vectors)
        ]
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Chromadb not available; saved {len(payload)} embeddings to {out_path}")
        return

    # create chroma client and upsert vectors (chromadb >= 1.0 API)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    # Drop and recreate rather than upsert-into-existing: upsert only
    # overwrites matching IDs, so chunk IDs from a previous run that no
    # longer exist (e.g. a garbled entry that got filtered out upstream)
    # would otherwise linger in the collection forever.
    if collection_name in [col.name for col in client.list_collections()]:
        client.delete_collection(name=collection_name)
    collection = client.create_collection(name=collection_name)

    collection.upsert(ids=ids, documents=docs, metadatas=metadatas, embeddings=vectors)
    print(f"Persisted {len(chunks)} chunks into Chroma collection '{collection_name}'")
