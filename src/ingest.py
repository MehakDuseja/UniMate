"""Ingestion pipeline for structured DB and semantic chunk storage."""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from .config import NORMALIZED_DIR, INGEST_DB
from .schema import UniversityDepartmentData


def sanitize_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value)
    text = re.sub(r"[^\d]", "", text)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS university_data (
            university_id TEXT PRIMARY KEY,
            university_name TEXT,
            department TEXT,
            city TEXT,
            min_eligibility_percentage REAL,
            entry_test_name TEXT,
            tuition_fee_amount INTEGER,
            tuition_fee_period TEXT,
            has_scholarships INTEGER,
            scholarship_details TEXT,
            test_pattern_summary TEXT,
            offered_courses TEXT,
            fee_details TEXT,
            source_pages TEXT,
            raw_text TEXT,
            hec_recognized INTEGER,
            official_website TEXT,
            province TEXT,
            is_public INTEGER,
            hostel_available INTEGER,
            hostel_details TEXT,
            latitude REAL,
            longitude REAL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_city ON university_data(city)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_min_eligibility ON university_data(min_eligibility_percentage)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tuition_fee_amount ON university_data(tuition_fee_amount)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_province ON university_data(province)")
    conn.commit()


def load_normalized_records() -> list[UniversityDepartmentData]:
    records: list[UniversityDepartmentData] = []
    for path in sorted(NORMALIZED_DIR.glob("*_normalized.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rec = UniversityDepartmentData(
            university_id=path.stem.replace("_normalized", ""),
            university_name=payload.get("university", ""),
            department=payload.get("university", ""),
            city=payload.get("location", ""),
            min_eligibility_percentage=payload.get("min_eligibility_percentage"),
            entry_test_name=payload.get("entry_test_name"),
            # Stored as an (amount, period) pair rather than one "annual"
            # figure: source fee tables mix per-credit-hour, per-semester,
            # and program-total numbers with no consistent labeling, so
            # forcing everything into a single annual figure would mean
            # silently guessing a conversion (e.g. an unconfirmed
            # credit-hours-per-semester count) - worse for a budget-matching
            # recommender than storing the real unit and leaving it unset
            # where the source itself doesn't say.
            tuition_fee_amount=payload.get("tuition_fee_amount"),
            tuition_fee_period=payload.get("tuition_fee_period"),
            has_scholarships=bool(payload.get("scholarships")),
            scholarship_details=" ".join(payload.get("scholarships", []))[:2000],
            test_pattern_summary=" ".join(payload.get("test_pattern", []))[:2000],
            offered_courses=payload.get("offered_courses", []),
            fee_details=" ".join(
                [f"{f.get('label')}: {f.get('value')}" for f in payload.get("fee_structure", {}).get("fees", []) if f.get("label") and f.get("value")]
            )[:2000],
            source_pages=payload.get("source_pages", []),
            raw_text=" ".join(
                [payload.get("location", ""), " ".join(payload.get("eligibility_criteria", [])), " ".join(payload.get("test_pattern", [])), " ".join(payload.get("scholarships", [])), " ".join(payload.get("offered_courses", []))]
            )[:4000],
            hec_recognized=payload.get("hec_recognized"),
            official_website=payload.get("official_website"),
            province=payload.get("province"),
            is_public=payload.get("is_public"),
            hostel_available=payload.get("hostel_available"),
            hostel_details=" ".join(payload.get("hostel_info", []))[:2000],
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
        )
        records.append(rec)
    return records


def insert_record(conn: sqlite3.Connection, record: UniversityDepartmentData) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO university_data (
            university_id, university_name, department, city,
            min_eligibility_percentage, entry_test_name, tuition_fee_amount, tuition_fee_period,
            has_scholarships, scholarship_details, test_pattern_summary,
            offered_courses, fee_details, source_pages, raw_text,
            hec_recognized, official_website, province, is_public,
            hostel_available, hostel_details, latitude, longitude
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.university_id,
            record.university_name,
            record.department,
            record.city,
            record.min_eligibility_percentage,
            record.entry_test_name,
            record.tuition_fee_amount,
            record.tuition_fee_period,
            int(record.has_scholarships),
            record.scholarship_details,
            record.test_pattern_summary,
            json.dumps(record.offered_courses, ensure_ascii=False),
            record.fee_details,
            json.dumps(record.source_pages, ensure_ascii=False),
            record.raw_text,
            record.hec_recognized if record.hec_recognized is None else int(record.hec_recognized),
            record.official_website,
            record.province,
            record.is_public if record.is_public is None else int(record.is_public),
            record.hostel_available if record.hostel_available is None else int(record.hostel_available),
            record.hostel_details,
            record.latitude,
            record.longitude,
        ),
    )


def ingest_to_sqlite() -> None:
    INGEST_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(INGEST_DB) as conn:
        create_schema(conn)
        records = load_normalized_records()
        for rec in records:
            insert_record(conn, rec)
        conn.commit()
        print(f"Inserted {len(records)} records into {INGEST_DB}")


if __name__ == "__main__":
    ingest_to_sqlite()
