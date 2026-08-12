"""University explore + shortlist (in-app, no email)."""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from db.connection import get_connection
from src.config import INGEST_DB, NORMALIZED_DIR


def _ensure_shortlist_schema() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS student_shortlist (
                id           TEXT PRIMARY KEY,
                student_id   TEXT NOT NULL,
                university_id TEXT NOT NULL,
                created_at   TEXT DEFAULT (datetime('now')),
                UNIQUE(student_id, university_id)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_shortlist_student
            ON student_shortlist(student_id, created_at DESC)
            """
        )


def _format_fee(amount: Any, period: Any) -> Optional[str]:
    if amount in (None, "", 0):
        return None
    try:
        n = int(float(amount))
    except (TypeError, ValueError):
        return None
    label = (period or "").replace("_", " ").strip()
    pretty = f"{n:,} PKR"
    return f"{pretty} {label}".strip() if label else pretty


def _from_sqlite() -> list[dict[str, Any]]:
    import sqlite3

    if not INGEST_DB.exists():
        return []
    conn = sqlite3.connect(str(INGEST_DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT university_id, university_name, city, province,
                   tuition_fee_amount, tuition_fee_period,
                   min_eligibility_percentage, has_scholarships,
                   hostel_available, is_public, official_website,
                   offered_courses
            FROM university_data
            ORDER BY university_name
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

    out: list[dict[str, Any]] = []
    for row in rows:
        courses = []
        raw = row["offered_courses"]
        if raw:
            try:
                courses = json.loads(raw) if isinstance(raw, str) else list(raw)
            except json.JSONDecodeError:
                courses = []
        out.append(
            {
                "id": row["university_id"],
                "name": row["university_name"] or row["university_id"],
                "city": row["city"] or "",
                "province": row["province"] or "",
                "fee_label": _format_fee(row["tuition_fee_amount"], row["tuition_fee_period"]),
                "fee_amount": row["tuition_fee_amount"],
                "fee_period": row["tuition_fee_period"] or "",
                "eligibility": row["min_eligibility_percentage"],
                "has_scholarships": bool(row["has_scholarships"]),
                "hostel": None if row["hostel_available"] is None else bool(row["hostel_available"]),
                "is_public": None if row["is_public"] is None else bool(row["is_public"]),
                "website": row["official_website"] or "",
                "programs": courses[:6],
                "program_count": len(courses),
            }
        )
    return out


def _from_normalized_json() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not NORMALIZED_DIR.exists():
        return out
    for path in sorted(NORMALIZED_DIR.glob("*_normalized.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        uid = path.stem.replace("_normalized", "")
        courses = data.get("offered_courses") or []
        out.append(
            {
                "id": uid,
                "name": data.get("university") or uid.replace("_", " ").title(),
                "city": data.get("location") or "",
                "province": data.get("province") or "",
                "fee_label": _format_fee(data.get("tuition_fee_amount"), data.get("tuition_fee_period")),
                "fee_amount": data.get("tuition_fee_amount"),
                "fee_period": data.get("tuition_fee_period") or "",
                "eligibility": data.get("min_eligibility_percentage"),
                "has_scholarships": bool(data.get("scholarships")),
                "hostel": data.get("hostel_available"),
                "is_public": data.get("is_public"),
                "website": data.get("official_website") or "",
                "programs": courses[:6],
                "program_count": len(courses),
            }
        )
    return out


def list_universities() -> list[dict[str, Any]]:
    rows = _from_sqlite()
    return rows if rows else _from_normalized_json()


def get_shortlist_ids(student_id: str) -> list[str]:
    _ensure_shortlist_schema()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT university_id FROM student_shortlist
            WHERE student_id = ?
            ORDER BY created_at DESC
            """,
            (student_id,),
        ).fetchall()
    return [r["university_id"] for r in rows]


def set_shortlisted(student_id: str, university_id: str, saved: bool) -> dict[str, Any]:
    _ensure_shortlist_schema()
    university_id = (university_id or "").strip()
    if not university_id:
        raise ValueError("university_id required")
    with get_connection() as conn:
        if saved:
            conn.execute(
                """
                INSERT INTO student_shortlist (id, student_id, university_id)
                VALUES (?, ?, ?)
                ON CONFLICT(student_id, university_id) DO NOTHING
                """,
                (str(uuid.uuid4()), student_id, university_id),
            )
        else:
            conn.execute(
                """
                DELETE FROM student_shortlist
                WHERE student_id = ? AND university_id = ?
                """,
                (student_id, university_id),
            )
    return {"university_id": university_id, "saved": saved}


def shortlist_bulk(student_id: str, university_ids: list[str]) -> dict[str, Any]:
    """Add many universities to the shortlist; returns how many were newly added."""
    before = set(get_shortlist_ids(student_id))
    requested: list[str] = []
    for uid in university_ids:
        uid = (uid or "").strip()
        if not uid:
            continue
        requested.append(uid)
        set_shortlisted(student_id, uid, True)
    after = set(get_shortlist_ids(student_id))
    added = len(after - before)
    return {
        "added": added,
        "requested": len(requested),
        "shortlist_ids": list(after),
        "shortlist_count": len(after),
    }


def get_shortlist_details(student_id: str) -> list[dict[str, Any]]:
    ids = get_shortlist_ids(student_id)
    if not ids:
        return []
    by_id = {u["id"]: u for u in list_universities()}
    out: list[dict[str, Any]] = []
    for uid in ids:
        uni = by_id.get(uid)
        if uni:
            out.append(dict(uni))
        else:
            out.append({"id": uid, "name": uid.replace("_", " ").title()})
    return out


def explore_payload(student_id: str) -> dict[str, Any]:
    shortlist = set(get_shortlist_ids(student_id))
    universities = list_universities()
    for u in universities:
        u["saved"] = u["id"] in shortlist
    return {
        "universities": universities,
        "shortlist_ids": sorted(shortlist),
        "shortlist_count": len(shortlist),
    }
