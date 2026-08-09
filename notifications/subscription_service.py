"""Notification subscription persistence."""

from __future__ import annotations

import uuid
from typing import Optional

from notifications.db import get_connection


def upsert_subscription(email: str, university_id: str) -> None:
    email = email.strip().lower()
    if not email or not university_id:
        raise ValueError("email and university_id are required")
    sub_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO notification_subscriptions (id, email, university_id, is_active)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(email, university_id) DO UPDATE SET
                is_active = 1,
                updated_at = datetime('now')
            """,
            (sub_id, email, university_id),
        )


def remove_subscription(email: str, university_id: str) -> None:
    email = email.strip().lower()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE notification_subscriptions
            SET is_active = 0, updated_at = datetime('now')
            WHERE email = ? AND university_id = ?
            """,
            (email, university_id),
        )


def list_subscribers(university_id: str) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT email FROM notification_subscriptions
            WHERE university_id = ? AND is_active = 1
            ORDER BY email
            """,
            (university_id,),
        ).fetchall()
    return [row["email"] for row in rows]


def list_subscribed_university_ids() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT university_id FROM notification_subscriptions
            WHERE is_active = 1
            ORDER BY university_id
            """
        ).fetchall()
    return [row["university_id"] for row in rows]


def get_subscriptions_for_email(email: str) -> list[str]:
    email = email.strip().lower()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT university_id FROM notification_subscriptions
            WHERE email = ? AND is_active = 1
            ORDER BY university_id
            """,
            (email,),
        ).fetchall()
    return [row["university_id"] for row in rows]


def count_active_subscriptions() -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM notification_subscriptions WHERE is_active = 1"
        ).fetchone()
    return int(row["n"]) if row else 0
