"""End-to-end ingestion helper: SQLite ingestion + semantic chunk creation."""
from __future__ import annotations

import json

from .chunker import build_chunks
from .config import SEMANTIC_CHUNKS_DIR as CHUNKS_DIR
from .ingest import ingest_to_sqlite
from .vector_store import build_chroma_collection


def main() -> None:
    print("Starting ingestion to SQLite...")
    ingest_to_sqlite()
    print("Building semantic chunks...")
    build_chunks()

    chunks = []
    for path in sorted(CHUNKS_DIR.glob("*_chunks.json")):
        chunks.extend(json.loads(path.read_text(encoding="utf-8")))

    if not chunks:
        print("No semantic chunks found to upload.")
        return

    print(f"Uploading {len(chunks)} chunks to Chroma...")
    # Using local sentence-transformers embeddings for now: the Gemini
    # embedding API key is hitting quota (429). Switch backend back to
    # "gemini" once that's resolved.
    build_chroma_collection("university_semantic_chunks", chunks, backend="local")


if __name__ == "__main__":
    main()
