"""Tests for agent/retriever.py - alias/category detection are pure and
always run; the candidate-building hard filters need the actual local
pipeline output (SQLite + Chroma), so those are skipped if it hasn't been
built yet (run `python3 -m src.ingest_and_vectorize` first)."""
from __future__ import annotations

import pytest

from agent.retriever import (
    detect_category_hints,
    detect_university_id,
    get_candidate_universities,
)
from src.config import CHROMA_DIR, INGEST_DB

pipeline_built = INGEST_DB.exists() and CHROMA_DIR.exists()
requires_pipeline = pytest.mark.skipif(not pipeline_built, reason="run python3 -m src.ingest_and_vectorize first")


def test_detect_university_id_matches_common_aliases():
    assert detect_university_id("how easy is it to get into NED") == "ned_university"
    assert detect_university_id("tell me about dsu hostel") == "dha_suffa"
    assert detect_university_id("what about the weather in karachi") is None


def test_detect_category_hints_returns_all_matches_for_multi_intent_question():
    categories = detect_category_hints("how easy is admission and what's the fee at NED")
    assert "eligibility" in categories
    assert "fee_structure" in categories


def test_detect_category_hints_empty_for_unrelated_text():
    assert detect_category_hints("hello there") == []


@requires_pipeline
def test_candidate_universities_excludes_below_eligibility_threshold():
    profile = {"academic_percentage": 55.0}
    candidates = get_candidate_universities(profile)
    ids = {c["record"]["university_id"] for c in candidates}
    for candidate in candidates:
        min_elig = candidate["record"].get("min_eligibility_percentage")
        if min_elig is not None:
            assert 55.0 >= min_elig, f"{candidate['record']['university_id']} should have been filtered out"
    # IBA's verified minimum (60%) must exclude a 55% student.
    assert "iba" not in ids


@requires_pipeline
def test_candidate_universities_hostel_hard_filter():
    profile = {"hostel_required": True}
    candidates = get_candidate_universities(profile)
    for candidate in candidates:
        assert candidate["record"].get("hostel_available") is not False


@requires_pipeline
def test_candidate_universities_gives_every_survivor_bounded_chunks():
    # Regression guard for the "one university dominates the context" bug -
    # every candidate should get a small, equal-ish slice, not zero.
    candidates = get_candidate_universities({"field_of_study": "Computer Science"}, chunks_per_university=4)
    assert len(candidates) >= 1
    for candidate in candidates:
        assert len(candidate["chunks"]) <= 4
