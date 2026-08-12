"""Deterministic, explainable university ranking — no LLM scoring."""

from __future__ import annotations

import re
from typing import Any, Optional

from agent.geo import geocode_area, haversine_km
from agent.retriever import UNIVERSITY_ALIASES, extract_focus_university_ids, get_university_display_name

_FACTOR_LABELS = {
    "program_match": "Program available",
    "eligibility_match": "Meets eligibility",
    "budget_fit": "Fits budget",
    "scholarship_fit": "Scholarship available",
    "location_fit": "Preferred location",
    "goal_alignment": "Career goal alignment",
}

_BASE_WEIGHTS = {
    "program_match": 25,
    "eligibility_match": 20,
    "budget_fit": 20,
    "location_fit": 15,
    "scholarship_fit": 10,
    "goal_alignment": 10,
}

_PRIORITY_BOOST = {"fees": "budget_fit", "distance": "location_fit"}
_PRIORITY_BOOST_POINTS = 10


def _ranking_weights(priority_focus: Optional[str]) -> dict[str, int]:
    boost_key = _PRIORITY_BOOST.get((priority_focus or "").strip().lower())
    if not boost_key:
        return dict(_BASE_WEIGHTS)
    others = {k: v for k, v in _BASE_WEIGHTS.items() if k != boost_key}
    shrink_fraction = _PRIORITY_BOOST_POINTS / sum(others.values())
    weights = {boost_key: _BASE_WEIGHTS[boost_key] + _PRIORITY_BOOST_POINTS}
    for key, base in others.items():
        weights[key] = base - round(base * shrink_fraction)
    drift = 100 - sum(weights.values())
    if drift:
        biggest = max(others, key=others.get)
        weights[biggest] += drift
    return weights


def _normalize_fee_per_semester(record: dict[str, Any]) -> Optional[int]:
    amount = record.get("tuition_fee_amount")
    if not amount:
        return None
    period = (record.get("tuition_fee_period") or "").lower()
    if "year" in period:
        return int(amount / 2)
    if "credit" in period:
        return int(amount * 15)
    return int(amount)


def _field_matches_program(field_of_study: str, offered_courses: list[str]) -> bool:
    if not field_of_study or not offered_courses:
        return False
    needle = field_of_study.lower()
    tokens = [t for t in re.split(r"[\s,/]+", needle) if len(t) > 2]
    for course in offered_courses:
        lower = course.lower()
        if needle in lower or any(token in lower for token in tokens):
            return True
    return False


def _score_program(profile: dict[str, Any], record: dict[str, Any]) -> tuple[int, str, str]:
    field = profile.get("field_of_study") or ""
    courses = record.get("offered_courses") or []
    if not field:
        return 50, "warn", "Program preference not specified"
    if _field_matches_program(field, courses):
        return 100, "pass", f"{field} offered"
    if courses:
        return 35, "warn", f"{field} not clearly listed — verify program availability"
    return 40, "warn", "Program list unavailable"


def _score_eligibility(profile: dict[str, Any], record: dict[str, Any]) -> tuple[int, str, str]:
    student_pct = profile.get("academic_percentage")
    min_elig = record.get("min_eligibility_percentage")
    if student_pct is None or min_elig is None:
        return 60, "warn", "Eligibility data incomplete"
    margin = max(student_pct - min_elig, 0)
    if margin >= 15:
        return 100, "pass", f"{student_pct}% exceeds {min_elig}% minimum"
    if margin >= 0:
        return 70 + int(margin * 2), "pass", f"{student_pct}% meets {min_elig}% minimum"
    return 0, "warn", f"{student_pct}% below {min_elig}% minimum"


def _score_budget(profile: dict[str, Any], record: dict[str, Any]) -> tuple[int, str, str]:
    budget = profile.get("budget_pkr_per_semester")
    fee = _normalize_fee_per_semester(record)
    if not budget or not fee:
        return 55, "warn", "Budget or fee data incomplete"
    if fee <= budget:
        return 100, "pass", f"PKR {fee:,}/sem within PKR {budget:,} budget"
    over_pct = (fee - budget) / budget
    if over_pct <= 0.15:
        return 75, "warn", f"PKR {fee:,}/sem slightly above PKR {budget:,} budget"
    if over_pct <= 0.35:
        return 45, "warn", f"Higher fee: PKR {fee:,}/sem vs PKR {budget:,} budget"
    return 20, "warn", f"Significantly above budget (PKR {fee:,}/sem)"


def _score_scholarship(profile: dict[str, Any], record: dict[str, Any]) -> tuple[int, str, str]:
    required = profile.get("scholarship_required")
    has = bool(record.get("has_scholarships"))
    if not required:
        return 80 if has else 60, "pass" if has else "warn", (
            "Scholarships available" if has else "Scholarships not required"
        )
    if has:
        return 100, "pass", "Merit/need-based scholarships available"
    return 25, "warn", "Scholarships required but not confirmed available"


def _score_location(
    profile: dict[str, Any],
    record: dict[str, Any],
    distance_km: Optional[float],
) -> tuple[int, str, str]:
    preferred_cities = [c.lower() for c in (profile.get("preferred_cities") or [])]
    preferred_province = (profile.get("preferred_province") or "").lower()
    city = (record.get("city") or "").lower()
    province = (record.get("province") or "").lower()

    if preferred_cities and any(pc in city or city in pc for pc in preferred_cities):
        return 100, "pass", f"{record.get('city')} matches preferred city"
    if preferred_province and province and preferred_province in province:
        return 85, "pass", f"{record.get('province')} matches preferred province"

    if distance_km is not None:
        if distance_km <= 8:
            return 95, "pass", f"{distance_km:.1f} km from you"
        if distance_km <= 20:
            return 75, "pass", f"{distance_km:.1f} km away"
        return 45, "warn", f"Farther away ({distance_km:.1f} km)"

    return 60, "warn", "Location preference not fully matched"


def _score_goals(profile: dict[str, Any], record: dict[str, Any]) -> tuple[int, str, str]:
    goals = (profile.get("career_goals") or "").lower()
    field = (profile.get("field_of_study") or "").lower()
    if not goals:
        return 60, "warn", "Career goals not specified"
    courses = " ".join(record.get("offered_courses") or []).lower()
    if field and field in courses:
        return 90, "pass", "Program aligns with stated goals"
    goal_tokens = [t for t in re.split(r"[\s,]+", goals) if len(t) > 3]
    if any(token in courses for token in goal_tokens):
        return 80, "pass", "Related programs available"
    return 50, "warn", "Limited alignment with career goals"


def _student_coords(profile: dict[str, Any]) -> tuple[float, float] | None:
    area_text = profile.get("student_area") or profile.get("student_city")
    return geocode_area(area_text) if area_text else None


def score_candidate(
    profile: dict[str, Any],
    candidate: dict[str, Any],
    *,
    priority_focus: Optional[str] = None,
) -> dict[str, Any]:
    record = candidate["record"]
    weights = _ranking_weights(priority_focus)

    student_coords = _student_coords(profile)
    distance_km = None
    if student_coords and record.get("latitude") and record.get("longitude"):
        distance_km = haversine_km(
            student_coords[0], student_coords[1], record["latitude"], record["longitude"]
        )

    scorers = {
        "program_match": _score_program(profile, record),
        "eligibility_match": _score_eligibility(profile, record),
        "budget_fit": _score_budget(profile, record),
        "scholarship_fit": _score_scholarship(profile, record),
        "location_fit": _score_location(profile, record, distance_km),
        "goal_alignment": _score_goals(profile, record),
    }

    factors = []
    weighted_total = 0.0
    for key, weight in weights.items():
        score, status, detail = scorers[key]
        weighted_total += score * weight / 100
        factors.append(
            {
                "criterion": key,
                "label": _FACTOR_LABELS[key],
                "status": status,
                "detail": detail,
                "score": score,
                "weight": weight,
            }
        )

    total_score = round(weighted_total)
    uni_id = record["university_id"]
    return {
        "university_id": uni_id,
        "university_name": record.get("university_name") or get_university_display_name(uni_id),
        "total_score": total_score,
        "match_score": total_score,
        "factors": factors,
        "distance_km": round(distance_km, 1) if distance_km is not None else None,
    }


def rank_candidates(
    profile: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    priority_focus: Optional[str] = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    ranked = [
        score_candidate(profile, candidate, priority_focus=priority_focus)
        for candidate in candidates
    ]
    ranked.sort(key=lambda r: r["total_score"], reverse=True)
    return ranked[:limit]


def explain_ranking(recommendation: dict[str, Any]) -> str:
    """Plain-text explanation for 'Why is X ranked #N?' questions."""
    name = recommendation.get("university_name", "This university")
    score = recommendation.get("total_score", recommendation.get("match_score", 0))
    lines = [f"**{name}** scored **{score}% match** based on these factors:\n"]
    for factor in recommendation.get("factors") or []:
        icon = "✓" if factor.get("status") == "pass" else "⚠"
        label = factor.get("label") or factor.get("criterion", "")
        detail = factor.get("detail", "")
        lines.append(f"{icon} **{label}** — {detail}")
    return "\n".join(lines)


def format_recommendations_message(recommendations: list[dict[str, Any]]) -> str:
    if not recommendations:
        return "I couldn't find strong matches for your profile right now."
    lines = ["Here are my top recommendations based on your profile:\n"]
    for i, rec in enumerate(recommendations, start=1):
        score = rec.get("total_score", rec.get("match_score", 0))
        name = rec.get("university_name", rec.get("university_id", "Unknown"))
        lines.append(f"**{i}. {name} — {score}% Match**")
        for factor in rec.get("factors") or []:
            icon = "✓" if factor.get("status") == "pass" else "⚠"
            label = factor.get("label") or factor.get("criterion", "")
            detail = factor.get("detail", "")
            lines.append(f"  {icon} {label}: {detail}")
        lines.append("")
    lines.append(
        "Ask me **\"Why is [university] ranked #1?\"** for a detailed breakdown, "
        "or tell me if you'd like to adjust your preferences."
    )
    return "\n".join(lines)


def format_comparison_message(recommendations: list[dict[str, Any]]) -> str:
    """Side-by-side style message for an explicitly named compare/shortlist set."""
    if not recommendations:
        return (
            "I couldn't match those universities in my Karachi dataset. "
            "I cover FAST, NED, Habib, IBA, SZABIST, DHA Suffa, UIT, Iqra, and Sir Syed."
        )
    names = [r.get("university_name") or r.get("university_id") for r in recommendations]
    lines = [
        "Here's how the universities you asked me to compare stack up for your profile:\n",
        f"Comparing: {', '.join(n for n in names if n)}\n",
    ]
    for i, rec in enumerate(recommendations, start=1):
        score = rec.get("total_score", rec.get("match_score", 0))
        name = rec.get("university_name", rec.get("university_id", "Unknown"))
        lines.append(f"**{i}. {name} — {score}% fit**")
        for factor in rec.get("factors") or []:
            icon = "✓" if factor.get("status") == "pass" else "⚠"
            label = factor.get("label") or factor.get("criterion", "")
            detail = factor.get("detail", "")
            lines.append(f"  {icon} {label}: {detail}")
        lines.append("")

    leader = recommendations[0]
    lines.append(
        f"**Best overall fit in this set:** {leader.get('university_name')} "
        f"({leader.get('total_score', leader.get('match_score'))}% match). "
        "Ask me about fees, scholarships, hostel, or admissions difficulty for any of them."
    )
    return "\n".join(lines)


def find_recommendation(
    recommendations: list[dict[str, Any]],
    question: str,
) -> Optional[dict[str, Any]]:
    lower = question.lower()
    for rec in recommendations:
        name = (rec.get("university_name") or "").lower()
        uid = (rec.get("university_id") or "").replace("_", " ").lower()
        if name and name in lower:
            return rec
        if uid and uid in lower:
            return rec
        uni_id = rec.get("university_id") or ""
        for alias in UNIVERSITY_ALIASES.get(uni_id, []):
            if alias in lower:
                return rec
    if re.search(r"\b(first|#1|top|ranked highest|leading)\b", lower) and recommendations:
        return recommendations[0]
    return None


def is_ranking_explanation_question(question: str) -> bool:
    lower = question.lower()
    patterns = [
        r"\bwhy\b.*\b(rank|ranked|recommend|match|score|#1|first|top|fit)\b",
        r"\bwhy\b.*\b(higher|better|ideal|best)\b",
        r"\bexplain\b.*\b(rank|ranking|recommend|match|score|fit)\b",
        r"\bbreak\s*down\b.*\b(match|rank|factor|fit)\b",
        r"\bmatch factors?\b",
        r"\bhow\b.*\b(rank|ranked|score|match)\b",
        r"\bwhat makes\b.*\b(good|best|top|ideal|fit)\b",
    ]
    return any(re.search(p, lower) for p in patterns)


_EXPLICIT_RERANK_RE = re.compile(
    r"\b("
    r"re-?rank|new (ranked )?list|updated? (list|ranking|recommendations)|"
    r"show (me )?(new )?(options|fits|recommendations|universities)|"
    r"recommend (the )?(best |top )?((university |school )?fits|universities|schools|options)|"
    r"change (my )?(budget|priority|field|province|city|criteria)"
    r")\b",
    re.IGNORECASE,
)

_FOLLOWUP_QA_RE = re.compile(
    r"\b("
    r"why|how (do|to|can|should|does|is|are)|"
    r"explain|break\s*down|tell me|"
    r"what (are|is|does|do|about)|"
    r"fees?|tuition|budget|costs?|afford|"
    r"scholarships?|eligib\w*|hostel|admissions?|deadlines?|documents?|"
    r"entry tests?|aptitude tests?|apply|application|"
    r"next steps|application plan|how to apply|"
    r"fit for|match factors?|limit the answer|answer about"
    r")\b",
    re.IGNORECASE,
)


def is_explicit_rerank_request(message: str) -> bool:
    """True when the student clearly wants a fresh ranked list / criteria change."""
    return bool(_EXPLICIT_RERANK_RE.search(message or ""))


def is_university_followup_question(message: str) -> bool:
    """True for factual/advisory follow-ups that must use Q&A, not re-ranking.

    Naming a single university (or saying "limit to X only") is NOT enough to
    re-run recommendations — that was causing "Why is FAST a fit?" / "application
    plan for FAST" to reprint the ranked list.
    """
    text = message or ""
    if extract_focus_university_ids(text):
        return False
    if is_explicit_rerank_request(text) and not _FOLLOWUP_QA_RE.search(text):
        return False
    return bool(_FOLLOWUP_QA_RE.search(text)) or is_ranking_explanation_question(text)
