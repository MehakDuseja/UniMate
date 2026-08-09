"""Unit tests for notification change detection (run via pytest notifications/)."""

from __future__ import annotations

from notifications.change_detector import (
    classify_change,
    content_hash,
    is_meaningful_change,
    normalize_content,
)


def test_normalize_content_collapses_whitespace():
    assert normalize_content("  Hello   World  ") == "hello world"


def test_content_hash_stable():
    a = content_hash("Admission deadline is 15 March.")
    b = content_hash("  admission   deadline is 15 march.  ")
    assert a == b


def test_meaningful_change_detects_deadline_keyword():
    old = "Admission opens in January."
    new = "Admission deadline extended to 30 April 2026."
    assert is_meaningful_change(old, new)


def test_cosmetic_change_ignored():
    old = "Welcome to the admissions portal for undergraduate programs."
    new = "Welcome to the admissions portal for undergraduate programs!"
    assert not is_meaningful_change(old, new)


def test_classify_change_prefers_deadline():
    change_type, summary = classify_change(
        "Apply online now.",
        "Apply online now. Last date for fee submission is 20 May 2026.",
        "Admissions",
    )
    assert change_type == "deadline"
    assert "Admissions" in summary
