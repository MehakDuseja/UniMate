"""Conversation metadata — thread list, titles, university scope."""

from __future__ import annotations

import re
from typing import Any, Optional

from db.connection import get_connection


def _title_from_message(message: str, max_len: int = 48) -> str:
    text = re.sub(r"\s+", " ", message.strip())
    if not text:
        return "New Chat"
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def upsert_conversation(
    *,
    thread_id: str,
    student_id: str,
    title: Optional[str] = None,
    university_filter: str = "all",
) -> None:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM conversations WHERE id = ?", (thread_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE conversations
                SET title = COALESCE(?, title),
                    university_filter = ?,
                    updated_at = datetime('now'),
                    is_deleted = 0
                WHERE id = ?
                """,
                (title, university_filter, thread_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO conversations (id, student_id, title, university_filter)
                VALUES (?, ?, ?, ?)
                """,
                (thread_id, student_id, title or "New Chat", university_filter),
            )


def touch_conversation(thread_id: str, *, first_user_message: Optional[str] = None) -> None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT title FROM conversations WHERE id = ?", (thread_id,)
        ).fetchone()
        if not row:
            return
        title = row["title"]
        if title == "New Chat" and first_user_message:
            title = _title_from_message(first_user_message)
        conn.execute(
            """
            UPDATE conversations SET title = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (title, thread_id),
        )


def list_conversations(student_id: str, limit: int = 30) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, university_filter, created_at, updated_at
            FROM conversations
            WHERE student_id = ? AND is_deleted = 0
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (student_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def rename_conversation(thread_id: str, title: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE conversations SET title = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (title.strip() or "New Chat", thread_id),
        )


def delete_conversation(thread_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE conversations SET is_deleted = 1, updated_at = datetime('now')
            WHERE id = ?
            """,
            (thread_id,),
        )


def get_conversation(thread_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, student_id, title, university_filter, created_at, updated_at
            FROM conversations WHERE id = ? AND is_deleted = 0
            """,
            (thread_id,),
        ).fetchone()
    return dict(row) if row else None
