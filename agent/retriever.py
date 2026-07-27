"""Retrieval interface over the existing Chroma collection + SQLite table
built by src/ingest_and_vectorize.py. Applies metadata pre-filters (province,
degree level) before semantic search, per the project's retrieval strategy."""
from __future__ import annotations

import re
import sqlite3
from typing import Any, Optional

import chromadb

from src.config import CHROMA_DIR, INGEST_DB
from src.vector_store import get_local_embeddings

COLLECTION_NAME = "university_semantic_chunks"

# Short forms/abbreviations a student is likely to type, mapped to the
# university_id used throughout the pipeline - lets a follow-up question like
# "how easy is it to get into NED" get filtered to just that university's
# chunks instead of searching the whole collection unfiltered.
UNIVERSITY_ALIASES: dict[str, list[str]] = {
    "dha_suffa": ["dha suffa", "dsu"],
    "ned_university": ["ned"],
    "iba": ["iba"],
    "habib_university": ["habib"],
    "szabist": ["szabist"],
    "fast_university": ["fast", "nu.edu", "nu-ces", "nuces"],
}


def detect_university_id(text: str) -> Optional[str]:
    """Best-effort match of a specific university named in free text, via
    word-boundary matching against known aliases - not exhaustive, but covers
    the common way students refer to these six schools."""
    lower = text.lower()
    for university_id, aliases in UNIVERSITY_ALIASES.items():
        for alias in aliases:
            if re.search(r"\b" + re.escape(alias) + r"\b", lower):
                return university_id
    return None


# Matches the categories chunks are actually tagged with in src/chunker.py.
# Without this, a plain semantic search for "is there any scholarship
# available" can pull back fee/eligibility chunks that happen to be textually
# similar instead of the dedicated scholarships chunks - biasing toward the
# right category up front gets much more relevant, groundable results.
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "scholarships": ["scholarship", "financial aid", "fee concession", "bursary", "grant", "need-based", "need based"],
    "hostel": ["hostel", "dormitory", "accommodation", "residence", "boarding"],
    "fee_structure": ["fee", "tuition", "cost", "afford", "expensive", "cheap"],
    "eligibility": ["eligib", "requirement", "admission criteria", "how easy", "how hard", "merit", "cut off", "cutoff"],
    "test_pattern": ["entry test", "aptitude test", "admission test", "test pattern"],
    "offered_courses": ["program", "course", "degree offered", "majors", "specialization"],
}


def detect_category_hint(text: str) -> Optional[str]:
    lower = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    return None


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


def _run_query(collection, query_vector: list[float], where: Optional[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    result = collection.query(query_embeddings=[query_vector], n_results=top_k, where=where)
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    dists = result.get("distances", [[]])[0]
    return [
        {"text": doc, "metadata": meta, "distance": dist}
        for doc, meta, dist in zip(docs, metas, dists)
    ]


def retrieve_for_question(
    question: str,
    university_id: Optional[str] = None,
    category: Optional[str] = None,
    top_k: int = 6,
) -> list[dict[str, Any]]:
    """Semantic search using the student's own follow-up question as the
    query (e.g. "tell me about DHA Suffa's scholarships"), rather than a
    query built from profile fields - used for answering a specific question
    where re-running the whole profile-based recommendation query would just
    return the same generic list instead of the thing actually asked about.
    `category` (e.g. "scholarships") biases toward the matching chunk
    category from src/chunker.py, since plain semantic similarity alone can
    pull back a textually-similar but wrong-category chunk (e.g. a fee row
    instead of the actual scholarships section)."""
    collection = _get_collection()
    query_vector = get_local_embeddings([question])[0]

    clauses = []
    if university_id:
        clauses.append({"university_id": university_id})
    if category:
        clauses.append({"category": category})
    where = clauses[0] if len(clauses) == 1 else ({"$and": clauses} if clauses else None)

    hits = _run_query(collection, query_vector, where, top_k)
    # A category hint that happens to match nothing (e.g. no scholarship
    # chunks for that specific university) shouldn't come back empty when
    # broader results exist - fall back to just the university filter.
    if not hits and category and university_id:
        hits = _run_query(collection, query_vector, {"university_id": university_id}, top_k)
    if not hits and (category or university_id):
        hits = _run_query(collection, query_vector, None, top_k)
    return hits


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
