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
ALL_UNIVERSITIES = "all"

_UNIVERSITY_DISPLAY_NAMES: dict[str, str] = {
    "dha_suffa": "DHA Suffa University",
    "ned_university": "NED University",
    "iba": "IBA",
    "habib_university": "Habib University",
    "szabist": "SZABIST",
    "fast_university": "FAST-NUCES",
    "uit": "UIT University",
    "iqra_university": "Iqra University",
    "sir_syed_university": "Sir Syed University (SSUET)",
}

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
    "uit": ["uit", "uitu", "university of information technology"],
    "iqra_university": ["iqra", "iqra university"],
    "sir_syed_university": ["ssuet", "sir syed"],
}


def get_university_display_name(university_id: str) -> str:
    if university_id == ALL_UNIVERSITIES:
        return "All Universities"
    return _UNIVERSITY_DISPLAY_NAMES.get(university_id, university_id.replace("_", " ").title())


def get_university_options() -> list[dict[str, str]]:
    """Dropdown options: All Universities first, then every ingested school."""
    options = [{"id": ALL_UNIVERSITIES, "label": "All Universities"}]
    try:
        for row in list_all_universities():
            uid = row["university_id"]
            options.append({"id": uid, "label": get_university_display_name(uid)})
    except Exception:
        for uid, name in _UNIVERSITY_DISPLAY_NAMES.items():
            options.append({"id": uid, "label": name})
    return options


def is_university_locked(selected_university: Optional[str]) -> bool:
    return bool(selected_university and selected_university != ALL_UNIVERSITIES)


def resolve_retrieval_university_id(
    selected_university: Optional[str],
    message: str = "",
    assistant_message: str = "",
) -> Optional[str]:
    """When the UI dropdown locks a university, that filter always wins.
    Otherwise fall back to alias detection in the student's message or the
    assistant's previous reply (for pronoun follow-ups like "what's its fee?")."""
    if is_university_locked(selected_university):
        return selected_university
    return detect_university_id(message) or detect_university_id(assistant_message)


def detect_university_id(text: str) -> Optional[str]:
    """Best-effort match of a specific university named in free text, via
    word-boundary matching against known aliases - not exhaustive, but covers
    the common way students refer to these nine schools."""
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


def detect_category_hints(text: str) -> list[str]:
    """Returns every matching category, not just the first - a multi-intent
    question ("how easy is admission and what's the fee?") should bias
    retrieval toward both eligibility AND fee_structure, not lock onto
    whichever category's keyword happens to appear first in the dict."""
    lower = text.lower()
    return [category for category, keywords in _CATEGORY_KEYWORDS.items() if any(kw in lower for kw in keywords)]


def _get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(COLLECTION_NAME)


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
    category: Optional[str | list[str]] = None,
    top_k: int = 6,
    strict_university_filter: bool = False,
) -> list[dict[str, Any]]:
    """Semantic search using the student's own follow-up question as the
    query (e.g. "tell me about DHA Suffa's scholarships"), rather than a
    query built from profile fields - used for answering a specific question
    where re-running the whole profile-based recommendation query would just
    return the same generic list instead of the thing actually asked about.
    `category` (e.g. "scholarships", or several via detect_category_hints for
    a multi-intent question like "how easy is admission and what's the fee?")
    biases toward the matching chunk categor(y/ies) from src/chunker.py,
    since plain semantic similarity alone can pull back a textually-similar
    but wrong-category chunk (e.g. a fee row instead of the actual
    scholarships section)."""
    collection = _get_collection()
    query_vector = get_local_embeddings([question])[0]

    categories = [category] if isinstance(category, str) else list(category or [])

    clauses = []
    if university_id:
        clauses.append({"university_id": university_id})
    if len(categories) == 1:
        clauses.append({"category": categories[0]})
    elif len(categories) > 1:
        clauses.append({"category": {"$in": categories}})
    where = clauses[0] if len(clauses) == 1 else ({"$and": clauses} if clauses else None)

    hits = _run_query(collection, query_vector, where, top_k)
    # A category hint that happens to match nothing (e.g. no scholarship
    # chunks for that specific university) shouldn't come back empty when
    # broader results exist - fall back to just the university filter.
    if not hits and categories and university_id:
        hits = _run_query(collection, query_vector, {"university_id": university_id}, top_k)
    # When the UI locks a specific university, never widen to cross-university
    # results — returning another school's data would violate isolation.
    if not hits and not strict_university_filter and (categories or university_id):
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


def format_source_citations(hits: list[dict[str, Any]], max_sources: int = 5) -> str:
    """Build a markdown Sources block from retrieved chunk metadata."""
    seen: set[str] = set()
    lines: list[str] = []
    for hit in hits:
        meta = hit.get("metadata") or {}
        uni = meta.get("university_name") or ""
        pages = (meta.get("source_pages") or "").strip()
        if pages:
            for page in pages.split(" | "):
                page = page.strip()
                if not page or page in seen:
                    continue
                seen.add(page)
                label = f"{uni} — {page}" if uni else page
                if page.startswith("http"):
                    lines.append(f"• [{label}]({page})")
                else:
                    lines.append(f"• {label}")
        elif uni and uni not in seen:
            seen.add(uni)
            lines.append(f"• {uni} (official university data)")
        if len(lines) >= max_sources:
            break
    if not lines:
        return ""
    return "\n\n**Sources:**\n" + "\n".join(lines)


def append_source_citations(content: str, hits: list[dict[str, Any]]) -> str:
    citations = format_source_citations(hits)
    if not citations or citations in content:
        return content
    return f"{content.rstrip()}{citations}"


def list_all_universities() -> list[dict[str, Any]]:
    conn = sqlite3.connect(INGEST_DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM university_data").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _keep_chunk_for_degree_level(chunk_metadata: dict[str, Any], degree_level: Optional[str]) -> bool:
    """degree_levels is a comma-joined string per chunk (see
    src/chunker.py::make_chunk_metadata), detected from that chunk's own
    text - not every chunk mentions a level at all (a fee or hostel chunk
    usually doesn't), so an empty value means "not applicable", not "wrong
    level", and shouldn't be excluded. Only exclude a chunk that explicitly
    detected a level and it isn't the one asked for."""
    if not degree_level:
        return True
    levels = [lvl for lvl in (chunk_metadata.get("degree_levels") or "").split(",") if lvl]
    return not levels or degree_level in levels


def get_candidate_universities(
    profile: dict[str, Any],
    chunks_per_university: int = 4,
    university_filter: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Builds one candidate entry per university, starting from every
    structured row (list_all_universities()) rather than a loose pool of
    semantically-similar chunks - a single global top-k chunk search lets
    whichever university has the most/most-distinctive text (e.g. SZABIST's
    per-program fee tables) dominate the ranker's context while a
    thinly-documented school barely appears at all, even though there are
    only nine universities total and every one of them should get a fair,
    bounded slice of supporting context.

    Applies hard filters the ranker LLM can't be trusted to enforce reliably
    from prose alone (eligibility %, hostel availability, province), then
    attaches verified structured fields plus a bounded, degree-level-aware
    set of that university's own chunks for narrative grounding.
    """
    rows = list_all_universities()
    if is_university_locked(university_filter):
        rows = [row for row in rows if row["university_id"] == university_filter]

    academic_percentage = profile.get("academic_percentage")
    preferred_province = profile.get("preferred_province")
    hostel_required = profile.get("hostel_required")
    degree_level = profile.get("degree_level")

    candidates = []
    for row in rows:
        # Hard eligibility gate: never surface a university whose own
        # verified minimum the student's stated percentage doesn't meet.
        min_elig = row.get("min_eligibility_percentage")
        if academic_percentage is not None and min_elig is not None and academic_percentage < min_elig:
            continue
        # Hard hostel gate - but only when we KNOW there's no hostel.
        # hostel_available is None (unknown) must not be treated as
        # disqualifying; that would silently drop universities we simply
        # never confirmed one way or the other.
        if hostel_required and row.get("hostel_available") is not None and not row.get("hostel_available"):
            continue
        if preferred_province and row.get("province") and row["province"].strip().lower() != preferred_province.strip().lower():
            continue
        candidates.append(row)

    if not candidates:
        return []

    query_text = _build_query_text(profile)
    query_vector = get_local_embeddings([query_text])[0]
    collection = _get_collection()

    results = []
    for row in candidates:
        university_id = row["university_id"]
        raw_hits = _run_query(collection, query_vector, {"university_id": university_id}, chunks_per_university * 3)
        kept = [h for h in raw_hits if _keep_chunk_for_degree_level(h["metadata"], degree_level)][:chunks_per_university]
        results.append({"record": row, "chunks": kept})
    return results
