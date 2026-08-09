"""Persistent student profile storage — separate from LangGraph conversation state."""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from db.connection import get_connection

PROFILE_FIELD_WEIGHTS: dict[str, int] = {
    "name": 5,
    "field_of_study": 15,
    "academic_percentage": 15,
    "degree_level": 10,
    "budget_pkr_per_semester": 10,
    "preferred_province": 10,
    "current_education_level": 10,
    "student_city": 5,
    "student_area": 5,
    "scholarship_required": 5,
    "hostel_required": 5,
    "career_goals": 5,
    "priority_focus": 5,
}


def calculate_completeness(profile: dict[str, Any]) -> int:
    if not profile:
        return 0
    total_weight = sum(PROFILE_FIELD_WEIGHTS.values())
    earned = 0
    for field, weight in PROFILE_FIELD_WEIGHTS.items():
        value = profile.get(field)
        if value not in (None, "", [], {}):
            earned += weight
    return round(100 * earned / total_weight)


def profile_status_label(completeness: int) -> str:
    if completeness >= 85:
        return "Complete"
    if completeness >= 50:
        return "In Progress"
    return "Getting Started"


def ensure_student(session_id: str) -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM students WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row:
            return row["id"]
        student_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO students (id, session_id) VALUES (?, ?)",
            (student_id, session_id),
        )
        return student_id


def get_saved_profile(student_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT profile_json, completeness_pct, is_saved, saved_at, updated_at
            FROM student_profiles WHERE student_id = ?
            """,
            (student_id,),
        ).fetchone()
    if not row:
        return None
    profile = json.loads(row["profile_json"])
    return {
        "profile": profile,
        "completeness_pct": row["completeness_pct"],
        "is_saved": bool(row["is_saved"]),
        "saved_at": row["saved_at"],
        "updated_at": row["updated_at"],
    }


def save_profile(student_id: str, profile: dict[str, Any], *, mark_saved: bool = True) -> dict[str, Any]:
    completeness = calculate_completeness(profile)
    profile_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute("DELETE FROM student_profiles WHERE student_id = ?", (student_id,))
        conn.execute(
            """
            INSERT INTO student_profiles
                (id, student_id, profile_json, completeness_pct, is_saved, saved_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CASE WHEN ? THEN datetime('now') ELSE NULL END, datetime('now'))
            """,
            (
                profile_id,
                student_id,
                json.dumps(profile),
                completeness,
                1 if mark_saved else 0,
                1 if mark_saved else 0,
            ),
        )
        if profile.get("name") or profile.get("email"):
            conn.execute(
                """
                UPDATE students SET name = COALESCE(?, name), email = COALESCE(?, email),
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (profile.get("name"), profile.get("email"), student_id),
            )
    return {"completeness_pct": completeness, "is_saved": mark_saved}


def delete_profile(student_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM student_profiles WHERE student_id = ?", (student_id,))
