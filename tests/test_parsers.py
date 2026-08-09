"""Tests for src/parsers.py extraction helpers."""
from __future__ import annotations

from src.parsers import (
    _FEE_CURRENCY_RE,
    extract_fee_structure,
    extract_snippets,
    is_noise_text,
    looks_like_program_name,
)


def test_extract_snippets_word_boundary_not_substring():
    # "support" inside "air-supported" must not match "support" as a keyword.
    text = "This passage describes an air-supported roof structure in detail."
    assert extract_snippets(text, ["support"]) == []


def test_extract_snippets_matches_plural():
    text = "The university offers several scholarships for eligible students."
    assert extract_snippets(text, ["scholarship"]) != []


def test_is_noise_text_flags_replacement_char_density():
    garbled = "�" * 5 + "some readable text follows here for padding purposes"
    assert is_noise_text(garbled)


def test_is_noise_text_allows_clean_text():
    assert not is_noise_text("Minimum 60% marks required in Intermediate or equivalent examination.")


def test_looks_like_program_name_requires_degree_prefix():
    assert looks_like_program_name("Bachelor of Science (Computer Science)")
    assert looks_like_program_name("BS-Computer Sciences")
    assert not looks_like_program_name("What is the job of Computer Science graduates?")
    assert not looks_like_program_name("Habib University's Bachelors of Computer Science degree cultivates")


def test_looks_like_program_name_rejects_garbled_table_text():
    # Too many commas / mismatched parens = flattened multi-column table row.
    garbled = "BS in Development Equivalent) Studies, (Maths, Statistics, Management Sciences"
    assert not looks_like_program_name(garbled)


def test_fee_currency_regex_rejects_bare_rs_substring():
    # "scholarships" contains the literal substring "rs" - must not count as
    # a currency mention on its own.
    assert not _FEE_CURRENCY_RE.search("the scholarships and fee concession policy")


def test_fee_currency_regex_matches_real_amounts():
    assert _FEE_CURRENCY_RE.search("tuition fee is rs. 500 per credit hour")
    assert _FEE_CURRENCY_RE.search("admission fee pkr 30,000")


def test_extract_fee_structure_ignores_program_only_headers():
    # An admission-schedule table with "Programs" in its header but no fee
    # data at all must not be captured as a fee entry.
    tables = [{
        "headers": ["Undergraduate Programs", "Graduate Programs"],
        "rows": [["May 20 - Jun 30", "May 20 - Jun 30"]],
    }]
    result = extract_fee_structure("", tables)
    assert result["fees"] == []


def test_extract_fee_structure_captures_real_fee_table():
    tables = [{
        "headers": ["Program", "Fee"],
        "rows": [["BBA / BS", "Rs. 12,000"]],
    }]
    result = extract_fee_structure("", tables)
    assert any(f["label"] == "BBA / BS" and "12,000" in f["value"] for f in result["fees"])
