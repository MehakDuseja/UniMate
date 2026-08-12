"""Conversation metadata and persisted chat history."""

from __future__ import annotations

import re
import uuid
from typing import Any, Optional

from db.connection import get_connection


def _title_from_message(message: str, max_len: int = 72) -> str:
    """Build a short sidebar title from the first user message.

    Strips tool-prompt boilerplate so titles stay readable (e.g. "Why is FAST
    a fit…" instead of "Always use my saved profile…").
    """
    text = re.sub(r"\s+", " ", (message or "").strip())
    if not text:
        return "New Chat"

    # Drop injected / tool boilerplate that used to pollute conversation titles.
    lower = text.lower()
    if lower.startswith("always use my saved profile"):
        marker = re.search(r"unless something is missing\.?\s*", text, flags=re.IGNORECASE)
        text = text[marker.end() :].strip() if marker else re.sub(
            r"^Always use my saved profile\b[^.]*(?:\.[^.]*)?\.\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

    text = re.sub(
        r"^Answer about .+? only\.\s*(?:Do not recommend other universities\.\s*)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^Limit the answer to .+? only\s*[—\-–]?\s*(?:do not recommend other universities\.\s*)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        return "New Chat"

    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip(" ,;:") + "…"


def create_chat(student_id: str, title: str = "New Chat", *, university_filter: str = "all") -> str:
    chat_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO conversations (id, student_id, title, university_filter, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (chat_id, student_id, title or "New Chat", university_filter),
        )
    return chat_id


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


def append_message(chat_id: str, role: str, content: str, timestamp: Optional[str] = None) -> dict[str, Any]:
    content = (content or "").strip()
    if not chat_id or not content:
        return {}

    now = timestamp or __import__("datetime").datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT title FROM conversations WHERE id = ?",
            (chat_id,),
        ).fetchone()
        if existing is None:
            return {}

        title = existing["title"]
        if title == "New Chat" and role == "user":
            title = _title_from_message(content)
            conn.execute(
                "UPDATE conversations SET title = ?, updated_at = datetime('now') WHERE id = ?",
                (title, chat_id),
            )

        conn.execute(
            """
            INSERT INTO messages (chat_id, role, content, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, role, content, now),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
            (chat_id,),
        )
    return {"chat_id": chat_id, "role": role, "content": content, "timestamp": now}


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


def get_chat_messages(chat_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content, timestamp
            FROM messages
            WHERE chat_id = ?
            ORDER BY timestamp ASC, id ASC
            """,
            (chat_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_chat(chat_id: str) -> bool:
    with get_connection() as conn:
        deleted = conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,)).rowcount
        conn.execute("DELETE FROM conversations WHERE id = ?", (chat_id,))
    return deleted >= 0


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
