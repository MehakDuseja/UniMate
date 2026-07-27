"""Retrieval interface over the existing Chroma collection + SQLite table
built by src/ingest_and_vectorize.py. Applies metadata pre-filters (province,
degree level) before semantic search, per the project's retrieval strategy."""
from __future__ import annotations

import sqlite3
from typing import Any, Optional

import chromadb

from src.config import CHROMA_DIR, INGEST_DB
from src.vector_store import get_local_embeddings

COLLECTION_NAME = "university_semantic_chunks"


def _get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(COLLECTION_NAME)


def _build_where_filter(profile: dict[str, Any]) -> Optional[dict[str, Any]]:
    clauses: list[dict[str, Any]] = []
    if profile.get("preferred_province"):
        clauses.append({"province": profile["preferred_province"]})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _build_query_text(profile: dict[str, Any]) -> str:
    parts: list[str] = []
    if profile.get("field_of_study"):
        parts.append(f"{profile['field_of_study']} program")
    if profile.get("degree_level"):
        parts.append(f"{profile['degree_level']} degree eligibility")
    if profile.get("budget_pkr_per_semester"):
        parts.append(f"budget around {profile['budget_pkr_per_semester']} PKR per semester")
    if profile.get("preferred_cities"):
        parts.append(f"located in {', '.join(profile['preferred_cities'])}")
    elif profile.get("preferred_province"):
        parts.append(f"located in {profile['preferred_province']}")
    if profile.get("scholarship_required"):
        parts.append("scholarships and financial assistance available")
    if profile.get("academic_percentage"):
        parts.append(f"academic percentage {profile['academic_percentage']}")
    if profile.get("hostel_required"):
        parts.append("hostel accommodation available")
    return ". ".join(parts) or "university admission eligibility and programs"


def retrieve_universities(profile: dict[str, Any], top_k: int = 10) -> list[dict[str, Any]]:
    """Semantic search over admission/program/scholarship chunks, pre-filtered
    by province when the student has stated a preference."""
    collection = _get_collection()
    query_text = _build_query_text(profile)
    query_vector = get_local_embeddings([query_text])[0]
    where = _build_where_filter(profile)

    result = collection.query(query_embeddings=[query_vector], n_results=top_k, where=where)

    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    dists = result.get("distances", [[]])[0]
    return [
        {"text": doc, "metadata": meta, "distance": dist}
        for doc, meta, dist in zip(docs, metas, dists)
    ]


def get_structured_record(university_id: str) -> Optional[dict[str, Any]]:
    """Look up the structured SQLite row (fees, eligibility %, courses JSON) for
    one university, to ground the ranker/presenter in verified fields."""
    conn = sqlite3.connect(INGEST_DB)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM university_data WHERE university_id = ?", (university_id,)
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def list_all_universities() -> list[dict[str, Any]]:
    conn = sqlite3.connect(INGEST_DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM university_data").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
