"""Tests for src/normalizer.py derived-field logic."""
from __future__ import annotations

from src.normalizer import (
    derive_hostel_available,
    derive_official_website,
    extract_min_eligibility_percentage,
)


def test_extract_min_eligibility_percentage_takes_the_stricter_value():
    # A university page mentioning both an easier and a harder threshold
    # must report the stricter one - understating it would let a student
    # through who doesn't actually qualify for the program they want.
    items = ["minimum 50% marks required for Arts", "minimum 60% marks required for Engineering and CS"]
    assert extract_min_eligibility_percentage(items) == 60.0


def test_extract_min_eligibility_percentage_ignores_test_weightage():
    # "Weightage of Admission Test marks 33%" is not an eligibility cutoff.
    items = ["Weightage of Admission Test marks 33%"]
    assert extract_min_eligibility_percentage(items) is None


def test_derive_hostel_available_true_when_positive_statement_present():
    items = ["DHA Suffa University operates a dedicated Girls Hostel located in Sector 3."]
    assert derive_hostel_available(items) is True


def test_derive_hostel_available_false_on_clear_negation():
    items = ["SZABIST does not operate its own on-campus student housing."]
    assert derive_hostel_available(items) is False


def test_derive_hostel_available_positive_overrides_negation_about_other_campus():
    # DHA Suffa's real case: an official hostel at one campus, explicitly no
    # hostel at another - the specific positive statement should win rather
    # than the negation blanket-flipping the whole result to False.
    items = [
        "DHA Suffa University operates a dedicated Girls Hostel at the DCK campus.",
        "The Main Campus in Phase 7 Extension does not have its own on-campus hostel.",
    ]
    assert derive_hostel_available(items) is True


def test_derive_hostel_available_none_when_no_info():
    assert derive_hostel_available([]) is None


def test_derive_official_website_picks_most_common_netloc():
    urls = [
        "https://www.iba.edu.pk/fee-structure.php",
        "https://www.iba.edu.pk/scholarships.php",
        "https://cs.iba.edu.pk/bscs/eligibility-criteria.php",
    ]
    assert derive_official_website(urls) == "https://www.iba.edu.pk"
