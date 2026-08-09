"""Tests for conversation metadata service."""

from __future__ import annotations

import uuid

import pytest

from db.connection import init_db
from services import conversation_service, profile_service


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_unimate.db"
    monkeypatch.setattr("db.connection.UNIMATE_DB", db_path)
    monkeypatch.setattr("src.config.UNIMATE_DB", db_path)
    init_db()
    yield
    if db_path.exists():
        db_path.unlink()


def test_conversation_crud():
    student_id = profile_service.ensure_student(str(uuid.uuid4()))
    thread_id = str(uuid.uuid4())
    conversation_service.upsert_conversation(
        thread_id=thread_id,
        student_id=student_id,
        title="New Chat",
        university_filter="ned_university",
    )
    conversation_service.touch_conversation(thread_id, first_user_message="What is the NED admission deadline?")
    rows = conversation_service.list_conversations(student_id)
    assert len(rows) == 1
    assert "NED" in rows[0]["title"] or "deadline" in rows[0]["title"].lower()

    conversation_service.rename_conversation(thread_id, "NED deadlines")
    conversation_service.delete_conversation(thread_id)
    assert conversation_service.list_conversations(student_id) == []
