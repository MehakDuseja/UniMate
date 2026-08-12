"""Ensure SQLite + Chroma are ready so chat never fails on empty stores."""

from __future__ import annotations

import json
import logging

from src.config import CHROMA_DIR, INGEST_DB, SEMANTIC_CHUNKS_DIR
from src.chunker import build_chunks
from src.ingest import ingest_to_sqlite
from src.vector_store import build_chroma_collection

logger = logging.getLogger(__name__)
COLLECTION_NAME = "university_semantic_chunks"


def _chroma_ready() -> bool:
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        names = [c.name for c in client.list_collections()]
        return COLLECTION_NAME in names
    except Exception:
        return False


def _sqlite_ready() -> bool:
    try:
        import sqlite3

        if not INGEST_DB.exists():
            return False
        conn = sqlite3.connect(str(INGEST_DB))
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM university_data"
            ).fetchone()
            return bool(row and row[0] > 0)
        finally:
            conn.close()
    except Exception:
        return False


def ensure_retrieval_stores(*, force: bool = False) -> dict[str, bool]:
    """Idempotent bootstrap used by the web app on startup."""
    sqlite_ok = _sqlite_ready()
    chroma_ok = _chroma_ready()
    if force or not sqlite_ok:
        logger.info("Building SQLite ingest store…")
        ingest_to_sqlite()
        sqlite_ok = _sqlite_ready()
    if force or not chroma_ok:
        logger.info("Building semantic chunks + Chroma collection…")
        build_chunks()
        chunks = []
        for path in sorted(SEMANTIC_CHUNKS_DIR.glob("*_chunks.json")):
            chunks.extend(json.loads(path.read_text(encoding="utf-8")))
        if chunks:
            build_chroma_collection(COLLECTION_NAME, chunks, backend="local")
        chroma_ok = _chroma_ready()
    return {"sqlite": sqlite_ok, "chroma": chroma_ok}
