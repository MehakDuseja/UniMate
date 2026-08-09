"""Orchestrate page checks and subscriber email delivery."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from email_service import send_university_update_email
from notifications.change_detector import (
    DetectedChange,
    check_university,
    list_pending_changes,
    mark_change_notified,
)
from notifications.db import get_connection
from notifications.subscription_service import list_subscribers, list_subscribed_university_ids
from notifications.targets import get_university_display_name

logger = logging.getLogger(__name__)


@dataclass
class NotificationRunResult:
    universities_checked: int = 0
    pages_checked: int = 0
    changes_found: int = 0
    emails_sent: int = 0
    errors: list[str] = field(default_factory=list)


def _start_run() -> str:
    run_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO notification_runs (id, started_at) VALUES (?, ?)",
            (run_id, started),
        )
    return run_id


def _finish_run(run_id: str, result: NotificationRunResult) -> None:
    finished = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE notification_runs SET
                finished_at = ?,
                universities_checked = ?,
                pages_checked = ?,
                changes_found = ?,
                emails_sent = ?,
                errors_json = ?
            WHERE id = ?
            """,
            (
                finished,
                result.universities_checked,
                result.pages_checked,
                result.changes_found,
                result.emails_sent,
                json.dumps(result.errors) if result.errors else None,
                run_id,
            ),
        )


def _notify_subscribers(university_id: str, changes: list[DetectedChange]) -> tuple[int, list[str]]:
    subscribers = list_subscribers(university_id)
    if not subscribers or not changes:
        return 0, []

    university_name = get_university_display_name(university_id)
    errors: list[str] = []
    sent = 0

    for email in subscribers:
        try:
            send_university_update_email(
                to_email=email,
                university_name=university_name,
                changes=changes,
            )
            sent += 1
        except Exception as exc:
            msg = f"Email to {email} for {university_id} failed: {exc}"
            logger.error(msg)
            errors.append(msg)

    if sent == len(subscribers):
        for change in changes:
            mark_change_notified(change.id)
    elif sent > 0:
        errors.append(
            f"Partial delivery for {university_id}: {sent}/{len(subscribers)} emails sent; will retry pending changes."
        )

    return sent, errors


def run_notification_check(*, university_ids: list[str] | None = None) -> NotificationRunResult:
    """Check subscribed universities for page changes and email subscribers."""
    result = NotificationRunResult()
    run_id = _start_run()

    targets = university_ids or list_subscribed_university_ids()
    if not targets:
        logger.info("No active notification subscriptions — nothing to check.")
        _finish_run(run_id, result)
        return result

    for university_id in targets:
        result.universities_checked += 1
        try:
            from notifications.targets import get_monitor_urls

            result.pages_checked += len(get_monitor_urls(university_id))
            new_changes = check_university(university_id)
            result.changes_found += len(new_changes)

            pending = list_pending_changes(university_id)
            if pending:
                sent, email_errors = _notify_subscribers(university_id, pending)
                result.emails_sent += sent
                result.errors.extend(email_errors)
        except Exception as exc:
            msg = f"University check failed for {university_id}: {exc}"
            logger.exception(msg)
            result.errors.append(msg)

    _finish_run(run_id, result)
    logger.info(
        "Notification run complete: %s universities, %s changes, %s emails",
        result.universities_checked,
        result.changes_found,
        result.emails_sent,
    )
    return result
