"""Map pipeline university IDs to monitored admission-page URLs."""

from __future__ import annotations

import re
from typing import Any

# Scraper dict keys → canonical university_id used across UniMate.
SCRAPER_NAME_TO_ID: dict[str, str] = {
    "NED University": "ned_university",
    "FAST University": "fast_university",
    "HABIB University": "habib_university",
    "IBA": "iba",
    "SZABIST": "szabist",
    "DHA Suffa": "dha_suffa",
    "UIT": "uit",
    "Iqra University": "iqra_university",
    "Sir Syed University": "sir_syed_university",
}

UNIVERSITY_DISPLAY_NAMES: dict[str, str] = {
    "dha_suffa": "DHA Suffa University",
    "ned_university": "NED University",
    "iba": "IBA",
    "habib_university": "Habib University",
    "szabist": "SZABIST",
    "fast_university": "FAST-NUCES",
    "uit": "UIT University",
    "iqra_university": "Iqra University",
    "sir_syed_university": "Sir Syed University (SSUET)",
}


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name.lower()).strip("_")


def get_university_display_name(university_id: str) -> str:
    return UNIVERSITY_DISPLAY_NAMES.get(
        university_id, university_id.replace("_", " ").title()
    )


def _load_scraper_universities() -> dict[str, list[Any]]:
    try:
        from university_scraper import UNIVERSITIES

        return UNIVERSITIES
    except Exception:
        return {}


def get_monitor_urls(university_id: str) -> list[str]:
    """HTTP(S) URLs to poll for a university. Manual entries are skipped."""
    scraper_data = _load_scraper_universities()
    for scraper_name, sources in scraper_data.items():
        if SCRAPER_NAME_TO_ID.get(scraper_name) != university_id:
            if _slug(scraper_name) != university_id:
                continue
        urls: list[str] = []
        for src in sources:
            if isinstance(src, str) and src.startswith(("http://", "https://")):
                urls.append(src)
        if urls:
            return urls

    # Fallback: one admissions URL per school if scraper import fails.
    fallbacks = {
        "ned_university": ["https://www.neduet.edu.pk/admission"],
        "fast_university": ["https://www.nu.edu.pk/Admissions/Schedule"],
        "habib_university": ["https://habib.edu.pk/admissions/admissions-faqs/"],
        "iba": ["https://cs.iba.edu.pk/bscs/eligibility-criteria.php"],
        "szabist": ["https://szabist.edu.pk/admission-requirements/"],
        "dha_suffa": ["https://www.dsu.edu.pk/admission-merit-criteria/"],
        "uit": ["https://uitu.edu.pk/how-to-apply/"],
        "iqra_university": ["https://iqra.edu.pk/admission-hub/"],
        "sir_syed_university": ["https://www.ssuet.edu.pk/admissions/undergraduate-admissions/"],
    }
    return fallbacks.get(university_id, [])


def all_university_ids() -> list[str]:
    scraper_data = _load_scraper_universities()
    if scraper_data:
        return [
            SCRAPER_NAME_TO_ID.get(name, _slug(name))
            for name in scraper_data
        ]
    return list(UNIVERSITY_DISPLAY_NAMES.keys())
