"""Tests for profile persistence service."""

from __future__ import annotations

import uuid

import pytest

from db.connection import init_db
from services import profile_service


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_unimate.db"
    monkeypatch.setattr("db.connection.UNIMATE_DB", db_path)
    monkeypatch.setattr("src.config.UNIMATE_DB", db_path)
    init_db()
    yield
    if db_path.exists():
        db_path.unlink()


def test_save_and_load_profile():
    session_id = str(uuid.uuid4())
    student_id = profile_service.ensure_student(session_id)
    profile = {
        "name": "Alex",
        "field_of_study": "Computer Science",
        "academic_percentage": 85,
        "degree_level": "Bachelor",
        "budget_pkr_per_semester": 120000,
    }
    meta = profile_service.save_profile(student_id, profile)
    assert meta["is_saved"] is True
    assert meta["completeness_pct"] > 0

    loaded = profile_service.get_saved_profile(student_id)
    assert loaded is not None
    assert loaded["profile"]["name"] == "Alex"
    assert loaded["is_saved"] is True


def test_delete_profile():
    session_id = str(uuid.uuid4())
    student_id = profile_service.ensure_student(session_id)
    profile_service.save_profile(student_id, {"name": "Test"})
    profile_service.delete_profile(student_id)
    assert profile_service.get_saved_profile(student_id) is None


def test_required_fields_gate_chat():
    incomplete = {"field_of_study": "CS", "name": "Alex"}
    assert profile_service.required_fields_complete(incomplete) is False
    assert "degree_level" in profile_service.missing_required_fields(incomplete)

    complete = {
        "field_of_study": "CS",
        "degree_level": "Bachelor",
        "budget_pkr_per_semester": 120000,
        "preferred_province": "Sindh",
        "academic_percentage": 85,
        "current_education_level": "Intermediate",
    }
    assert profile_service.required_fields_complete(complete) is True
    assert profile_service.missing_required_fields(complete) == []


def test_completeness_calculation():
    empty = profile_service.calculate_completeness({})
    partial = profile_service.calculate_completeness(
        {"field_of_study": "CS", "academic_percentage": 80, "degree_level": "Bachelor"}
    )
    assert empty < partial
