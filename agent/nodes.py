"""LangGraph node functions. Each takes the current AgentState and returns a
partial-state dict to merge in - standard LangGraph node contract."""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from .geo import geocode_area, haversine_km
from .llm import generate_json, generate_text
from .prompts import (
    PRESENTER_SYSTEM,
    PROFILE_BUILDER_SYSTEM,
    RANKER_SYSTEM,
    REFINE_CLASSIFIER_SYSTEM,
)
from .retriever import get_structured_record, retrieve_universities
from .state import REQUIRED_PROFILE_FIELDS, AgentState

PRIORITY_NOTES = {
    "fees": "This student has told you fees/affordability matters more to them than distance - let a clearly "
    "better budget fit tip close calls in a university's favor.",
    "distance": "This student has told you distance/location matters more to them than fees - let a clearly "
    "closer, more convenient location tip close calls in a university's favor.",
    "both": "This student cares about both fees and distance roughly equally - weigh budget_fit and "
    "location_fit evenly against each other.",
}

# Deterministic backstop for the eligibility gate: the LLM is asked to set
# "eligibility_blocked" itself, but that's a soft instruction a model can slip
# on under rephrasing/pressure ("ignore that, just show me schools"). This
# gives a rule the LLM can't talk its way around. Each pattern is the highest
# schooling stage it implies; a degree_level's requirement is the minimum
# stage that must be reached (in progress counts) before that degree applies.
_STAGE_RANK_PATTERNS: list[tuple[int, re.Pattern[str]]] = [
    (0, re.compile(r"\bgrade\s*(?:[1-9]|10)\b|\bclass\s*(?:[1-9]|10)\b|\bprimary\b|\bmiddle\s*school\b|"
                   r"\belementary\b|\bjunior\s*school\b", re.I)),
    (1, re.compile(r"\bmatric(?:ulation)?\b|\bo[\s\-]?levels?\b", re.I)),
    (2, re.compile(r"\bintermediate\b|\bf\.?sc\b|\ba[\s\-]?levels?\b|\bhssc\b", re.I)),
    (3, re.compile(r"\bbachelor|\bbs\b|\bbba\b", re.I)),
    (4, re.compile(r"\bmaster|\bms\b|\bmba\b", re.I)),
    (5, re.compile(r"\bph\.?d\b", re.I)),
]

_MIN_STAGE_FOR_DEGREE = {"Bachelor": 2, "Master": 3, "PhD": 4}

_DEGREE_PREREQUISITE_TEXT = {
    "Bachelor": "Matriculation/O-Levels and then Intermediate/FSc or A-Levels (or a qualifying test like SAT)",
    "Master": "a completed Bachelor's degree",
    "PhD": "a completed Master's degree",
}


def _stage_rank(current_education_level: str) -> Optional[int]:
    matched = [rank for rank, pattern in _STAGE_RANK_PATTERNS if pattern.search(current_education_level)]
    return max(matched) if matched else None


def _deterministic_eligibility_block(profile: dict[str, Any]) -> bool:
    degree_level = profile.get("degree_level")
    edu_text = profile.get("current_education_level")
    required_rank = _MIN_STAGE_FOR_DEGREE.get(degree_level)
    if not required_rank or not edu_text:
        return False
    stage_rank = _stage_rank(edu_text)
    return stage_rank is not None and stage_rank < required_rank


def _missing_fields(profile: dict[str, Any]) -> list[str]:
    return [f for f in REQUIRED_PROFILE_FIELDS if not profile.get(f)]


def _sanitize_profile_updates(updates: Any) -> dict[str, Any]:
    """Bounds-check the fields most likely to silently corrupt ranking if a
    model hallucinates or misparses a number - a garbled 9500% academic
    percentage or a billion-PKR budget should be dropped, not merged in
    unquestioned."""
    if not isinstance(updates, dict):
        return {}
    cleaned = dict(updates)

    if "academic_percentage" in cleaned:
        try:
            pct = float(cleaned["academic_percentage"])
        except (TypeError, ValueError):
            cleaned.pop("academic_percentage", None)
        else:
            if 0 <= pct <= 100:
                cleaned["academic_percentage"] = pct
            else:
                cleaned.pop("academic_percentage", None)

    if "budget_pkr_per_semester" in cleaned:
        try:
            budget = float(cleaned["budget_pkr_per_semester"])
        except (TypeError, ValueError):
            cleaned.pop("budget_pkr_per_semester", None)
        else:
            if 0 < budget <= 50_000_000:
                cleaned["budget_pkr_per_semester"] = int(budget)
            else:
                cleaned.pop("budget_pkr_per_semester", None)

    if isinstance(cleaned.get("entry_test_scores"), dict):
        scores: dict[str, float] = {}
        for name, score in cleaned["entry_test_scores"].items():
            try:
                score = float(score)
            except (TypeError, ValueError):
                continue
            if 0 <= score <= 2000:
                scores[name] = score
        cleaned["entry_test_scores"] = scores

    return cleaned


def _last_user_message(state: AgentState) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, dict):
            if msg.get("role") in ("human", "user"):
                return msg.get("content", "")
        else:
            role = getattr(msg, "type", "")
            if role in ("human", "user"):
                return getattr(msg, "content", "")
    return ""


def _merge_profile_updates(profile: dict[str, Any], updates: Any) -> dict[str, Any]:
    if not isinstance(updates, dict):
        return profile
    merged = dict(profile)
    for key, value in updates.items():
        if value not in (None, "", [], {}):
            merged[key] = value
    return merged


def profile_builder_node(state: AgentState) -> dict[str, Any]:
    """Extracts profile updates from the latest message and drafts the next
    question in a single LLM call (rather than two) - the free-tier Gemini
    quota is tight enough (5 req/min) that halving calls-per-turn matters."""
    profile = dict(state.get("student_profile") or {})
    last_message = _last_user_message(state)
    missing_before = _missing_fields(profile)

    result = generate_json(
        PROFILE_BUILDER_SYSTEM.format(profile=json.dumps(profile), missing_fields=missing_before),
        f"Student's latest message: {last_message}" if last_message else "The conversation is just starting.",
    )
    updates = _sanitize_profile_updates(result.get("profile_updates", {}) if isinstance(result, dict) else {})
    reply = result.get("reply", "") if isinstance(result, dict) else ""
    wants_recommendations = bool(result.get("wants_recommendations")) if isinstance(result, dict) else False
    eligibility_blocked = bool(result.get("eligibility_blocked")) if isinstance(result, dict) else False

    profile = _merge_profile_updates(profile, updates)
    missing_after = _missing_fields(profile)

    # Deterministic backstop: don't just trust the LLM's own eligibility_blocked
    # flag, since a rephrased or pushy message could talk it out of setting
    # that. If the stated current_education_level plainly hasn't reached the
    # degree_level's prerequisite stage, force the block regardless of what
    # the model returned, and write our own explanation for it.
    if not eligibility_blocked and _deterministic_eligibility_block(profile):
        eligibility_blocked = True
        degree_level = profile.get("degree_level")
        reply = (
            f"It looks like you're not quite at the stage yet for a {degree_level}'s degree - based on what "
            f"you mentioned ({profile.get('current_education_level')}), you'd typically need "
            f"{_DEGREE_PREREQUISITE_TEXT.get(degree_level, 'the prerequisite qualification')} first. "
            "Feel free to come back once you're closer to that!"
        )

    # Having every required field does NOT mean we recommend - only route to
    # matching once the student has actually asked to see options. Otherwise
    # we'd surprise-recommend the moment the last required field lands,
    # which is exactly the premature-recommendation behavior that's wrong.
    # eligibility_blocked is a hard stop (e.g. a grade-5 student asking about
    # a Bachelor's) enforced here too, not just trusted from the prompt, so a
    # model slip-up on wants_recommendations can't route around it.
    if not missing_after and wants_recommendations and not eligibility_blocked:
        return {
            "student_profile": profile,
            "profile_complete": True,
            "current_phase": "matching",
        }

    if not reply:
        reply = (
            "Could you tell me a bit more so I can find the best options for you?"
            if missing_after
            else "I have enough to find some good matches - want me to show you recommendations now, "
            "or is there anything else you'd like to add first?"
        )

    return {
        "messages": [{"role": "assistant", "content": reply}],
        "student_profile": profile,
        "profile_complete": False,
        "current_phase": "profiling",
    }


def retriever_node(state: AgentState) -> dict[str, Any]:
    hits = retrieve_universities(state["student_profile"], top_k=10)
    return {"retrieved_universities": hits, "current_phase": "matching"}


def _student_coords(profile: dict[str, Any]) -> tuple[float, float] | None:
    area_text = profile.get("student_area") or profile.get("student_city")
    return geocode_area(area_text) if area_text else None


def ranker_node(state: AgentState) -> dict[str, Any]:
    profile = state["student_profile"]
    universities = state.get("retrieved_universities") or []

    if not universities:
        return {"recommendations": [], "current_phase": "presenting"}

    student_coords = _student_coords(profile)
    distance_cache: dict[str, Optional[float]] = {}

    def _distance_for(university_id: str) -> Optional[float]:
        if not student_coords or not university_id:
            return None
        if university_id not in distance_cache:
            record = get_structured_record(university_id)
            if record and record.get("latitude") and record.get("longitude"):
                distance_cache[university_id] = haversine_km(
                    student_coords[0], student_coords[1], record["latitude"], record["longitude"]
                )
            else:
                distance_cache[university_id] = None
        return distance_cache[university_id]

    context_lines = []
    for u in universities:
        meta = u["metadata"]
        distance_km = _distance_for(meta.get("university_id", ""))
        distance_note = f" (approx {distance_km:.1f} km from student)" if distance_km is not None else ""
        context_lines.append(f"[{meta.get('university_name')} | {meta.get('category')}]{distance_note} {u['text']}")
    context = "\n\n".join(context_lines)

    priority_note = PRIORITY_NOTES.get((profile.get("priority_focus") or "").strip().lower(), "")

    ranked = generate_json(
        RANKER_SYSTEM.format(priority_note=priority_note),
        f"Student profile: {json.dumps(profile)}\n\nUniversity context:\n{context}",
    )
    if isinstance(ranked, dict):
        ranked = ranked.get("results") or ranked.get("universities") or []
    if not isinstance(ranked, list):
        ranked = []

    return {"recommendations": ranked[:5], "current_phase": "presenting"}


def presenter_node(state: AgentState) -> dict[str, Any]:
    recommendations = state.get("recommendations") or []
    if not recommendations:
        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    "I couldn't find any matching universities in our current dataset for your "
                    "preferences. Would you like to loosen a constraint, like budget or location?"
                ),
            }],
            "current_phase": "presenting",
        }

    response = generate_text(
        PRESENTER_SYSTEM,
        f"Recommendations JSON: {json.dumps(recommendations)}",
    )
    return {
        "messages": [{"role": "assistant", "content": response}],
        "current_phase": "presenting",
    }


def refine_node(state: AgentState) -> dict[str, Any]:
    last_message = _last_user_message(state)
    result = generate_json(REFINE_CLASSIFIER_SYSTEM, f"Student's message: {last_message}")

    action = "end"
    updates: Any = {}
    if isinstance(result, dict):
        action = result.get("action", "end")
        updates = result.get("updates", {})

    profile = _merge_profile_updates(state.get("student_profile") or {}, _sanitize_profile_updates(updates))

    return {
        "student_profile": profile,
        "current_phase": "refining",
        "refine_action": action,
    }
