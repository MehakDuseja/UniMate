"""Notification-specific SQLite schema on the shared UniMate database."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from src.config import UNIMATE_DB

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notification_subscriptions (
    id              TEXT PRIMARY KEY,
    email           TEXT NOT NULL,
    university_id   TEXT NOT NULL,
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(email, university_id)
);

CREATE INDEX IF NOT EXISTS idx_notification_subs_university
    ON notification_subscriptions(university_id, is_active);

CREATE INDEX IF NOT EXISTS idx_notification_subs_email
    ON notification_subscriptions(email, is_active);

CREATE TABLE IF NOT EXISTS page_snapshots (
    id              TEXT PRIMARY KEY,
    university_id   TEXT NOT NULL,
    url             TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    normalized_text TEXT,
    page_title      TEXT,
    scraped_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(university_id, url)
);

CREATE TABLE IF NOT EXISTS detected_changes (
    id              TEXT PRIMARY KEY,
    university_id   TEXT NOT NULL,
    url             TEXT NOT NULL,
    page_title      TEXT,
    change_type     TEXT NOT NULL,
    summary         TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    detected_at     TEXT DEFAULT (datetime('now')),
    notified_at     TEXT,
    is_meaningful   INTEGER DEFAULT 1,
    UNIQUE(university_id, url, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_detected_changes_pending
    ON detected_changes(university_id, notified_at)
    WHERE notified_at IS NULL;

CREATE TABLE IF NOT EXISTS notification_runs (
    id              TEXT PRIMARY KEY,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    universities_checked INTEGER DEFAULT 0,
    pages_checked   INTEGER DEFAULT 0,
    changes_found   INTEGER DEFAULT 0,
    emails_sent     INTEGER DEFAULT 0,
    errors_json     TEXT
);
"""


def init_notification_db() -> None:
    UNIMATE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(UNIMATE_DB), check_same_thread=False)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    init_notification_db()
    conn = sqlite3.connect(str(UNIMATE_DB), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
