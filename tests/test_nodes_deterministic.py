"""Tests for the deterministic (non-LLM) guardrails in agent/nodes.py -
backstops that must hold regardless of what the model itself decides."""
from __future__ import annotations

from agent.nodes import (
    _deterministic_eligibility_block,
    _is_out_of_scope_region,
    _looks_like_question,
    _sanitize_profile_updates,
)


def test_eligibility_block_grade5_wanting_bachelor():
    profile = {"degree_level": "Bachelor", "current_education_level": "Grade 5"}
    assert _deterministic_eligibility_block(profile) is True


def test_eligibility_block_not_fooled_by_bare_aspirational_keyword():
    # The exploit: a bare mention of "BS"/"Bachelor" as the ASPIRED degree
    # must not register as evidence of having completed one.
    profile = {"degree_level": "Bachelor", "current_education_level": "grade 8 and want BS CS"}
    assert _deterministic_eligibility_block(profile) is True

    profile2 = {"degree_level": "Bachelor", "current_education_level": "Matric, preparing for Bachelors"}
    assert _deterministic_eligibility_block(profile2) is True


def test_eligibility_block_allows_genuinely_qualified_student():
    profile = {"degree_level": "Bachelor", "current_education_level": "Intermediate / FSc completed"}
    assert _deterministic_eligibility_block(profile) is False


def test_eligibility_block_allows_completed_bachelor_for_masters():
    profile = {"degree_level": "Master", "current_education_level": "I completed my Bachelor's in Business"}
    assert _deterministic_eligibility_block(profile) is False


def test_eligibility_block_no_op_when_fields_missing():
    assert _deterministic_eligibility_block({}) is False
    assert _deterministic_eligibility_block({"degree_level": "Bachelor"}) is False


def test_out_of_scope_region_flags_other_city():
    assert _is_out_of_scope_region({"preferred_cities": ["Lahore"], "preferred_province": "Punjab"}) is True


def test_out_of_scope_region_flags_other_sindh_city():
    # Same province as Karachi (Sindh) but a different city - still out of
    # scope, since the corpus only actually covers Karachi.
    assert _is_out_of_scope_region({"preferred_cities": ["Hyderabad"], "preferred_province": "Sindh"}) is True


def test_out_of_scope_region_allows_karachi():
    assert _is_out_of_scope_region({"preferred_cities": ["Karachi"], "preferred_province": "Sindh"}) is False
    assert _is_out_of_scope_region({"preferred_province": "Sindh"}) is False
    assert _is_out_of_scope_region({}) is False


def test_sanitize_drops_out_of_range_academic_percentage():
    assert "academic_percentage" not in _sanitize_profile_updates({"academic_percentage": 9500})


def test_sanitize_keeps_valid_academic_percentage():
    assert _sanitize_profile_updates({"academic_percentage": 82.5})["academic_percentage"] == 82.5


def test_sanitize_drops_negative_budget():
    assert "budget_pkr_per_semester" not in _sanitize_profile_updates({"budget_pkr_per_semester": -500})


def test_sanitize_filters_invalid_entry_test_scores():
    updates = {"entry_test_scores": {"NAT": 85, "garbage": "abc"}}
    cleaned = _sanitize_profile_updates(updates)
    assert cleaned["entry_test_scores"] == {"NAT": 85.0}


def test_looks_like_question_detects_question_mark_and_keywords():
    assert _looks_like_question("what is fee structure of fast")
    assert _looks_like_question("is there any scholarship available?")
    assert not _looks_like_question("I want a bachelor's in Computer Science")
