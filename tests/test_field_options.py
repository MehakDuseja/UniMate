"""Field-of-study options derived from university offered_courses."""

from __future__ import annotations

from services.explore_service import list_field_of_study_options, program_to_field_label


def test_program_to_field_label_common_shapes():
    assert program_to_field_label("Bachelor of Science (Computer Science)") == "Computer Science"
    assert program_to_field_label("BS(Software Engineering)") == "Software Engineering"
    assert program_to_field_label("Bachelor of Science (Artificial Intelligence)") == "Artificial Intelligence"
    assert program_to_field_label("BS(Multimedia & Gamming)") == "Multimedia & Gaming"


def test_program_to_field_label_rejects_junk():
    assert program_to_field_label("Admission test is designed to gauge suitability") is None
    assert program_to_field_label("4-Year Program") is None


def test_list_field_of_study_options_includes_core_fields():
    options = list_field_of_study_options()
    assert options, "expected fields from normalized university data"
    lowered = {o.lower() for o in options}
    assert "computer science" in lowered
    assert "software engineering" in lowered or "data science" in lowered
    # Custom saved value is preserved even if not in dataset
    with_custom = list_field_of_study_options(include="Astrobiology")
    assert with_custom[0] == "Astrobiology"


def test_list_education_level_options_from_eligibility_data():
    from services.explore_service import list_education_level_options

    options = list_education_level_options()
    assert options
    blob = " | ".join(options).lower()
    assert "intermediate" in blob or "a-levels" in blob
    assert "matric" in blob or "o-levels" in blob
    # Custom saved value preserved
    with_custom = list_education_level_options(include="Grade 8")
    assert with_custom[0] == "Grade 8"
