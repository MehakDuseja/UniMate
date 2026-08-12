"""Persist last agent recommendations per student (for export / tools)."""

from __future__ import annotations

import json
from typing import Any

from db.connection import get_connection


def _ensure_schema() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS student_last_recommendations (
                student_id TEXT PRIMARY KEY,
                recommendations_json TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """
        )


def save_recommendations(student_id: str, recommendations: list[dict[str, Any]]) -> None:
    if not student_id:
        return
    _ensure_schema()
    payload = json.dumps(recommendations or [], ensure_ascii=False, default=str)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO student_last_recommendations (student_id, recommendations_json, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(student_id) DO UPDATE SET
                recommendations_json = excluded.recommendations_json,
                updated_at = datetime('now')
            """,
            (student_id, payload),
        )


def load_recommendations(student_id: str) -> list[dict[str, Any]]:
    if not student_id:
        return []
    _ensure_schema()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT recommendations_json FROM student_last_recommendations WHERE student_id = ?",
            (student_id,),
        ).fetchone()
    if not row:
        return []
    try:
        data = json.loads(row["recommendations_json"] or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []
