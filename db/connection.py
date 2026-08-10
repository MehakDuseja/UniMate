"""SQLite connection and schema for UniMate application data."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from src.config import UNIMATE_DB

_SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id              TEXT PRIMARY KEY,
    session_id      TEXT UNIQUE NOT NULL,
    email           TEXT,
    name            TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS student_profiles (
    id              TEXT PRIMARY KEY,
    student_id      TEXT NOT NULL REFERENCES students(id),
    profile_json    TEXT NOT NULL,
    completeness_pct INTEGER DEFAULT 0,
    is_saved        INTEGER DEFAULT 0,
    saved_at        TEXT,
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_student_profiles_student
    ON student_profiles(student_id);

CREATE TABLE IF NOT EXISTS conversations (
    id              TEXT PRIMARY KEY,
    student_id      TEXT NOT NULL REFERENCES students(id),
    title           TEXT DEFAULT 'New Chat',
    university_filter TEXT DEFAULT 'all',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    is_deleted      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id         TEXT NOT NULL REFERENCES conversations(id),
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    timestamp       TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_conversations_student
    ON conversations(student_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_messages_chat_ts
    ON messages(chat_id, timestamp ASC, id ASC);
"""


def init_db() -> None:
    UNIMATE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(UNIMATE_DB), check_same_thread=False)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    init_db()
    conn = sqlite3.connect(str(UNIMATE_DB), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
