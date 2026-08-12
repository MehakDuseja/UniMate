"""Agent state definitions: the student profile being built up through
conversation, and the overall LangGraph state threaded through every node."""
from __future__ import annotations

from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph.message import add_messages


class StudentProfile(TypedDict, total=False):
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    age: Optional[int]
    student_city: Optional[str]
    student_area: Optional[str]  # neighborhood/locality, e.g. "Gulshan-e-Iqbal" - used for distance
    preferred_province: Optional[str]
    preferred_cities: Optional[list[str]]
    budget_pkr_per_semester: Optional[int]
    degree_level: Optional[str]  # "Bachelor" | "Master" | "PhD"
    field_of_study: Optional[str]
    current_education_level: Optional[str]
    board: Optional[str]
    academic_percentage: Optional[float]
    entry_test_scores: Optional[dict[str, float]]
    hostel_required: Optional[bool]
    transportation_preference: Optional[str]
    scholarship_required: Optional[bool]
    career_goals: Optional[str]
    priority_focus: Optional[str]  # "fees" | "distance" | "both" - which matters more when trading off
    target_universities: Optional[list[str]]


# Minimum information needed before we can meaningfully retrieve/rank
# universities. Everything else in StudentProfile is optional but valuable.
REQUIRED_PROFILE_FIELDS = [
    "field_of_study",
    "degree_level",
    "budget_pkr_per_semester",
    "preferred_province",
    "academic_percentage",
    "current_education_level",
]


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    student_profile: StudentProfile
    profile_complete: bool
    retrieved_universities: Optional[list[dict[str, Any]]]
    recommendations: Optional[list[dict[str, Any]]]
    current_phase: str  # "profiling" | "matching" | "presenting" | "refining"
    refine_action: Optional[str]  # "refine" | "end"
    # When the student names a compare/shortlist set, retrieval+ranking is
    # restricted to these university_ids for that turn.
    focus_university_ids: Optional[list[str]]
    # UI dropdown lock: "all" (or None) searches every university; a specific
    # university_id restricts retrieval to that school only — enforced in
    # agent/retriever.py, not just via prompt instructions.
    selected_university: Optional[str]
    # Sticky across turns: the student may ask to see recommendations before
    # every required field is known (e.g. "recommend me" while budget is
    # still missing). wants_recommendations itself is re-derived fresh from
    # only the latest message each turn (see PROFILE_BUILDER_SYSTEM), so
    # without this the request gets silently dropped the moment one turn
    # passes without every required field present - the student then has to
    # explicitly ask again after supplying the last missing field, which
    # just looks like the bot forgot / is stalling.
    recommendations_requested: bool


def initial_state() -> AgentState:
    return {
        "messages": [],
        "student_profile": {},
        "profile_complete": False,
        "retrieved_universities": None,
        "recommendations": None,
        "current_phase": "profiling",
        "refine_action": None,
        "focus_university_ids": None,
        "recommendations_requested": False,
        "selected_university": "all",
    }
