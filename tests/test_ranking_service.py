"""Tests for deterministic ranking service."""

from __future__ import annotations

from services.ranking_service import (
    explain_ranking,
    find_recommendation,
    format_recommendations_message,
    is_ranking_explanation_question,
    rank_candidates,
    score_candidate,
)


def _candidate(
    university_id: str,
    name: str,
    *,
    min_elig: float = 60,
    fee: int = 90000,
    courses: list[str] | None = None,
    scholarships: bool = True,
    city: str = "Karachi",
    province: str = "Sindh",
):
    return {
        "record": {
            "university_id": university_id,
            "university_name": name,
            "min_eligibility_percentage": min_elig,
            "tuition_fee_amount": fee,
            "tuition_fee_period": "per_semester",
            "offered_courses": courses or ["BS Computer Science", "BS Software Engineering"],
            "has_scholarships": scholarships,
            "city": city,
            "province": province,
            "latitude": 24.86,
            "longitude": 67.00,
        },
        "chunks": [],
    }


def test_rank_candidates_orders_by_score():
    profile = {
        "field_of_study": "Computer Science",
        "academic_percentage": 85,
        "budget_pkr_per_semester": 120000,
        "preferred_cities": ["Karachi"],
        "scholarship_required": True,
        "student_city": "Karachi",
    }
    ranked = rank_candidates(
        profile,
        [
            _candidate("fast_university", "FAST", fee=95000),
            _candidate("iba", "IBA", fee=180000, min_elig=70),
        ],
    )
    assert len(ranked) == 2
    assert ranked[0]["total_score"] >= ranked[1]["total_score"]
    assert all("factors" in r for r in ranked)


def test_explain_ranking_includes_factors():
    rec = score_candidate(
        {"field_of_study": "CS", "academic_percentage": 80, "budget_pkr_per_semester": 100000},
        _candidate("ned_university", "NED"),
    )
    text = explain_ranking(rec)
    assert "NED" in text
    assert "✓" in text or "⚠" in text


def test_is_ranking_explanation_question():
    assert is_ranking_explanation_question("Why is FAST ranked #1?")
    assert is_ranking_explanation_question("Explain the ranking for IBA")
    assert is_ranking_explanation_question(
        "Why is FAST University a fit for my profile? Break down the match factors"
    )
    assert not is_ranking_explanation_question("What is the fee at FAST?")


def test_is_university_followup_question_routes_qa_not_rerank():
    from services.ranking_service import is_explicit_rerank_request, is_university_followup_question

    assert is_university_followup_question(
        "Why is FAST University a fit for my profile? Break down the match factors using my saved details."
    )
    assert is_university_followup_question(
        "Give me a practical application plan for FAST University based on my profile: documents, entry tests, deadlines."
    )
    assert is_university_followup_question("Answer about FAST University only. What scholarships could I get?")
    assert not is_university_followup_question(
        "Compare Habib University, DHA Suffa, FAST University, and SZABIST for my profile."
    )
    assert is_explicit_rerank_request("Recommend the best university fits for me now.")
    assert not is_university_followup_question("Recommend the best university fits for me now.")


def test_find_recommendation_by_name_and_rank():
    recs = [
        {"university_id": "fast_university", "university_name": "FAST-NUCES", "total_score": 90},
        {"university_id": "iba", "university_name": "IBA", "total_score": 80},
    ]
    assert find_recommendation(recs, "why is FAST ranked higher")["university_id"] == "fast_university"
    assert find_recommendation(recs, "why is the first one best")["university_id"] == "fast_university"


def test_format_recommendations_message():
    recs = rank_candidates(
        {"field_of_study": "CS", "academic_percentage": 82, "budget_pkr_per_semester": 100000},
        [_candidate("fast_university", "FAST")],
    )
    msg = format_recommendations_message(recs)
    assert "FAST" in msg
    assert "% Match" in msg
