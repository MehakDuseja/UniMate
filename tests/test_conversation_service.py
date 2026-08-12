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


def test_title_from_message_strips_tool_boilerplate():
    title = conversation_service._title_from_message(
        "Always use my saved profile (Computer Science, Bachelor). Do not ask me to restate these "
        "unless something is missing. Answer about FAST University only. Do not recommend other "
        "universities. Why is FAST University a fit for my profile?"
    )
    assert "Always use my saved profile" not in title
    assert "Why is FAST" in title


def test_chat_history_persistence_and_restore():
    student_id = profile_service.ensure_student(str(uuid.uuid4()))
    chat_id = conversation_service.create_chat(student_id, "NED admission requirements")

    conversation_service.append_message(chat_id, "user", "What are the admission requirements for NED?", "2026-08-10T10:00:00")
    conversation_service.append_message(chat_id, "assistant", "NED requires...", "2026-08-10T10:00:01")

    restored = conversation_service.get_chat_messages(chat_id)
    assert [item["role"] for item in restored] == ["user", "assistant"]
    assert restored[0]["content"] == "What are the admission requirements for NED?"

    rows = conversation_service.list_conversations(student_id)
    assert rows[0]["id"] == chat_id
    assert rows[0]["title"] == "NED admission requirements"

    deleted = conversation_service.delete_chat(chat_id)
    assert deleted is True
    assert conversation_service.get_chat_messages(chat_id) == []
