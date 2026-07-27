"""Normalizer for parsed university records.

This module defines a canonical schema and normalizes the extracted fields from
parsed HTML/PDF content into the final structure used for recommendation.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

UNIVERSITY_SEED_LOCATIONS = {
    "iba": "University Enclave, Karachi, 75270",
    "habib_university": "Block 18 University Ave, Gulistan-e-Johar, Karachi, 75290",
    "dha_suffa": "DHA City Karachi (DCK) Campus, Karachi",
    "szabist": "R2CH+5XP, 99 3rd Ave, Block 5 Clifton, Karachi, 75600",
    "fast_university": "Sector 17-D, Karachi",
    "ned_university": "Service Rd, NED University Of Engineering & Technology, Karachi",
}

# All six universities currently scraped are in Karachi, Sindh. is_public
# reflects well-known HEC sector status, not an inference from scraped text.
UNIVERSITY_SEED_PROVINCE = {
    "iba": "Sindh",
    "habib_university": "Sindh",
    "dha_suffa": "Sindh",
    "szabist": "Sindh",
    "fast_university": "Sindh",
    "ned_university": "Sindh",
}

UNIVERSITY_SEED_IS_PUBLIC = {
    "iba": True,
    "habib_university": False,
    "dha_suffa": False,
    "szabist": False,
    "fast_university": False,
    "ned_university": True,
}

# All six are well-established, degree-granting Pakistani universities - HEC
# recognition is a legal prerequisite for that, so this isn't scraped, it's a
# well-known fact. New universities added later should get this verified
# rather than assumed.
UNIVERSITY_SEED_HEC_RECOGNIZED = {
    "iba": True,
    "habib_university": True,
    "dha_suffa": True,
    "szabist": True,
    "fast_university": True,
    "ned_university": True,
}

# User-supplied campus coordinates (decimal degrees). NED's was given as DMS
# (24°55'56.3"N 67°06'51.8"E) and converted here. dha_suffa is confirmed to be
# the DHA City Karachi (DCK) campus, not Phase 7 Ext - UNIVERSITY_SEED_LOCATIONS
# above reflects that.
UNIVERSITY_SEED_LATLONG = {
    "iba": (24.9409937136334, 67.11560818232043),
    "ned_university": (24.932306, 67.114389),
    "dha_suffa": (25.010542459123045, 67.45820784122958),
    "szabist": (24.82024998032359, 67.03029595348134),
    "habib_university": (24.905225395627088, 67.13757276697827),
    "fast_university": (24.856928, 67.264802),
}

# Tuition figures confirmed directly against each university's own scraped fee
# page text (not guessed/converted), stored as (amount_pkr, period). Only
# entries where the source page itself states the billing period
# unambiguously are included here:
#  - habib_university: the fee page's own column header reads "Amount in PKR
#    (Per Semester payment)" next to this figure (DSSE/AHSS schools).
#  - iba: the page's own column header reads "Fee Per Credit Hour" (BS
#    programs) - a full-semester figure would need an unconfirmed
#    credit-hours-per-semester count, so this is left as-is rather than
#    silently converted.
# dha_suffa, szabist, ned_university, and fast_university are deliberately
# left out: each program/tier has a different rate bundled together in one
# scraped table (dha_suffa, szabist), the scraped page never actually states
# a fee figure at all (fast_university), or the one figure found has no
# stated billing period in the source text (ned_university's "Self-Finance
# Fee Rs. 890,000/-").
UNIVERSITY_SEED_TUITION = {
    "habib_university": (780_000, "per_semester"),
    "iba": (31_500, "per_credit_hour"),
}


def derive_official_website(source_pages: list[str]) -> str | None:
    """Derive the university's root domain from its scraped source URLs
    (most common netloc), rather than asking for a separate manually-curated
    homepage link."""
    netlocs = [urlparse(url).netloc for url in source_pages if url and urlparse(url).netloc]
    if not netlocs:
        return None
    most_common_netloc, _ = Counter(netlocs).most_common(1)[0]
    return f"https://{most_common_netloc}"


NOISE_PATTERNS = [
    "home about", "admissions undergraduate programs", "graduate programs", "postgraduate programs", "centers of excellence",
    "apply online", "program planning guide", "fee structure", "financial assistance", "aptitude tests", "samples faqs",
    "academics schools", "academic calendar", "office of the registrar", "life at iba", "student portal", "faculty portal",
    "portals", "menu", "social networks", "copyright", "©", "privacy policy", "terms of use", "contact us",
    "faculty students alumni staff", "search close menu"
]


def normalize_string(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\n", " ").strip())


def is_noise_text(text: str) -> bool:
    lower = text.lower()
    if len(text) < 20:
        return True
    if any(pattern in lower for pattern in NOISE_PATTERNS):
        return True
    # filter if too many non-alphanumeric characters and repeated site tokens
    if len(re.findall(r"[A-Za-z]", text)) < len(text) * 0.4:
        return True
    # PDFs with undecodable custom font encodings sometimes yield raw
    # control-byte garbage that still has enough scattered ASCII letters to
    # pass the alpha-ratio check above; catch it separately.
    control_chars = sum(1 for ch in text if ord(ch) < 32 and ch not in "\n\t\r")
    if control_chars > len(text) * 0.05:
        return True
    # The more common failure mode: undecodable bytes surface as the Unicode
    # replacement character (U+FFFD) rather than low control codes.
    if text.count("�") > len(text) * 0.02:
        return True
    return False


def normalize_fee_entries(fee_structures: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for structure in fee_structures:
        if not isinstance(structure, dict):
            continue
        for fee in structure.get("fees", []):
            label = normalize_string(fee.get("label", ""))
            value = normalize_string(fee.get("value", ""))
            if not label or not value:
                continue
            if is_noise_text(label) and is_noise_text(value):
                continue
            # drop generic menu noise within data rows
            if label.lower() in {"type of fee", "amount in pkr", "fee_snippet", "programs"} and not value:
                continue
            normalized.append({"label": label, "value": value})
    return normalized


def normalize_list(items: list[Any]) -> list[str]:
    normalized: list[str] = []
    for item in items:
        if isinstance(item, str):
            text = normalize_string(item)
            if not text or is_noise_text(text):
                continue
            if text not in normalized:
                normalized.append(text)
    return normalized


def extract_numeric_range(text: str) -> dict[str, Any] | None:
    text = text.replace("₹", "").replace("Rs", "").replace("PKR", "").replace("Rs.", "")
    numbers = re.findall(r"\d{1,3}(?:[\,\d]{0,})", text)
    if not numbers:
        return None
    values = [int(n.replace(",", "")) for n in numbers]
    if len(values) == 1:
        return {"amount_min": values[0], "amount_max": values[0], "currency": "PKR", "raw_text": text}
    return {"amount_min": min(values), "amount_max": max(values), "currency": "PKR", "raw_text": text}


# Requires "minimum"/"at least" to co-occur with the percentage, not just any
# "%...marks" combination - eligibility text also contains admission-test
# *weightage* percentages (e.g. "Weightage of Admission Test marks 33%"),
# which are a completely different thing and would silently corrupt this
# field if matched.
ELIGIBILITY_PERCENT_PATTERNS = [
    re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%\s*minimum\s*marks", re.I),
    re.compile(r"minimum\s*(\d{1,3}(?:\.\d+)?)\s*%", re.I),
    re.compile(r"at\s*least\s*(\d{1,3}(?:\.\d+)?)\s*%", re.I),
]


def extract_min_eligibility_percentage(eligibility_items: list[str]) -> float | None:
    text = " ".join(eligibility_items)
    values: list[float] = []
    for pattern in ELIGIBILITY_PERCENT_PATTERNS:
        values.extend(float(m) for m in pattern.findall(text))
    values = [v for v in values if 0 < v <= 100]
    return min(values) if values else None


KNOWN_ENTRY_TESTS = [
    "NAT", "ECAT", "MDCAT", "ETEA", "GAT", "HAT", "NTS", "SAT", "MCAT",
    "FAST-NUCES", "NU Admission Test", "ISSB",
]


def extract_entry_test_names(text_items: list[str]) -> str | None:
    text = " ".join(text_items)
    found = [t for t in KNOWN_ENTRY_TESTS if re.search(r"\b" + re.escape(t) + r"\b", text, re.I)]
    return ", ".join(found) if found else None


# SZABIST's own hostel text is a good example of why this can't be a simple
# "any hostel-related text found -> True": it explicitly says the university
# "does not operate its own on-campus student housing" while still mentioning
# nearby private hostels. Habib's page is the same situation phrased
# differently ("Being a non-residential campus...") - a naive keyword-presence
# check would wrongly mark both as hostel_available=True.
HOSTEL_NEGATION_RE = re.compile(
    r"does\s*not\s*(operate|have|provide|offer)|no\s*(on-?campus|onsite)\s*(hostel|housing|accommodation)|"
    r"not\s*available|non-?residential\s*campus",
    re.I,
)

# Some universities have this both ways depending on campus (e.g. DHA Suffa
# runs an official hostel at its DCK campus but not at its Phase 7 Ext main
# campus) - the aggregated text ends up containing both a clear positive
# statement and a negation about a *different* campus. A positive, specific
# "we operate/run an official hostel" statement should win over a co-occurring
# negation elsewhere, rather than the negation blanket-flipping the result.
HOSTEL_POSITIVE_RE = re.compile(
    r"operates?\s+(a|an|its own)?\s*(dedicated\s+)?[\w\s]{0,30}hostel|"
    r"official[\w\s]{0,20}hostel|dedicated[\w\s]{0,20}hostel|provides?[\w\s]{0,20}hostel",
    re.I,
)

# "Accommodation" is ambiguous in English: it also means a policy adjustment
# (academic/religious accommodation for disabilities or exam scheduling), not
# housing. Those false positives need filtering out before they either pad
# hostel_details with irrelevant text or (if a page happens to phrase a
# disability-accommodation policy in the negative) skew hostel_available.
HOSTEL_NOISE_MARKERS = [
    "academic accommodation", "religious accommodation", "disability",
    "examination schedule", "fyp showcase", "final year project",
]


def normalize_hostel_info(items: list[str]) -> list[str]:
    filtered = normalize_list(items)
    return [text for text in filtered if not any(marker in text.lower() for marker in HOSTEL_NOISE_MARKERS)]


def derive_hostel_available(hostel_items: list[str]) -> bool | None:
    if not hostel_items:
        return None
    text = " ".join(hostel_items)
    if HOSTEL_POSITIVE_RE.search(text):
        return True
    if HOSTEL_NEGATION_RE.search(text):
        return False
    return True


def normalize_fee_structure(fee_structures: list[Any]) -> dict[str, Any]:
    fees = normalize_fee_entries(fee_structures)
    numeric_entries = [extract_numeric_range(fee["value"]) for fee in fees if fee["value"]]
    numeric_entries = [n for n in numeric_entries if n]
    return {
        "fees": fees,
        "numeric_summary": numeric_entries,
    }


def normalize_program_record(record: dict[str, Any]) -> dict[str, Any]:
    university_id = re.sub(r"[\s\-/]+", "_", (record.get("university") or "").lower()).strip("_")
    eligibility_criteria = normalize_list(record.get("aggregated", {}).get("eligibility_criteria", []))
    test_pattern = normalize_list(record.get("aggregated", {}).get("test_pattern", []))
    source_pages = [page.get("url") for page in record.get("pages", []) if page.get("url")]

    latlong = UNIVERSITY_SEED_LATLONG.get(university_id)
    tuition = UNIVERSITY_SEED_TUITION.get(university_id)

    normalized = {
        "university": record.get("university"),
        "location": record.get("location") or UNIVERSITY_SEED_LOCATIONS.get(university_id),
        "latitude": latlong[0] if latlong else None,
        "longitude": latlong[1] if latlong else None,
        "tuition_fee_amount": tuition[0] if tuition else None,
        "tuition_fee_period": tuition[1] if tuition else None,
        "province": UNIVERSITY_SEED_PROVINCE.get(university_id),
        "is_public": UNIVERSITY_SEED_IS_PUBLIC.get(university_id),
        "hec_recognized": UNIVERSITY_SEED_HEC_RECOGNIZED.get(university_id),
        "official_website": derive_official_website(source_pages),
        "eligibility_criteria": eligibility_criteria,
        "test_pattern": test_pattern,
        "min_eligibility_percentage": extract_min_eligibility_percentage(eligibility_criteria),
        "entry_test_name": extract_entry_test_names(eligibility_criteria + test_pattern),
        "scholarships": normalize_list(record.get("aggregated", {}).get("scholarships", [])),
        "offered_courses": normalize_offered_courses(record.get("aggregated", {}).get("offered_courses", [])),
        "fee_structure": normalize_fee_structure(record.get("aggregated", {}).get("fee_structure", [])),
        "hostel_info": normalize_hostel_info(record.get("aggregated", {}).get("hostel_info", [])),
        "source_pages": source_pages,
    }
    normalized["hostel_available"] = derive_hostel_available(normalized["hostel_info"])
    return normalized


def normalize_offered_courses(courses: list[Any]) -> list[str]:
    # Validation of what counts as a real program name already happened in
    # parsers.extract_offered_courses (via looks_like_program_name); this
    # step only cleans whitespace and dedupes.
    filtered: list[str] = []
    for item in courses:
        if not isinstance(item, str):
            continue
        text = normalize_string(item)
        if not text or is_noise_text(text):
            continue
        if text not in filtered:
            filtered.append(text)
    return filtered


def normalize_all(parsed_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(parsed_dir.glob("*_parsed.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        normalized = normalize_program_record(record)
        out_path = out_dir / f"{path.stem.replace('_parsed', '_normalized')}.json"
        out_path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Normalized {path.name} -> {out_path.name}")
