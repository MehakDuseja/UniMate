"""University explore + shortlist (in-app, no email)."""

from __future__ import annotations

import json
import re
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


# --- Field-of-study options derived from offered_courses in the dataset ---

_DEGREE_LEAD_RE = re.compile(
    r"^(?:"
    r"bachelor(?:\s+of\s+(?:science|arts|business administration|education|engineering|laws?|architecture|interior design))?|"
    r"master(?:\s+of\s+(?:science|arts|business administration|philosophy|engineering))?|"
    r"doctor of philosophy|phd|"
    r"b\.?\s*s\.?|b\.?\s*e\.?|b\.?\s*a\.?|b\.?\s*ba|bs|be|bba|ba|"
    r"m\.?\s*s\.?|m\.?\s*ba|m\.?\s*engg\.?|ms|mba|mem|m\.?sc|b\.?sc|"
    r"b\.?\s*ed\.?|pharm\.?\s*d\.?|dpt"
    r")\b[\s.\-]*",
    re.IGNORECASE,
)

_JUNK_FIELD_RE = re.compile(
    r"(admission|required|instruction|overview|curriculum|faculty|dissertation|"
    r"equivalent|cgpa|hec|years of|valid for|compulsory|ranked by|accredited|"
    r"cr\.?\s*hrs|4-year program|weekend|evening|thesis is|plo\b)",
    re.IGNORECASE,
)

_FIELD_ALIASES: dict[str, str] = {
    "computer sciences": "Computer Science",
    "in computer science": "Computer Science",
    "in computer engineering": "Computer Engineering",
    "in electrical engineering": "Electrical Engineering",
    "in business administration": "Business Administration",
    "accounting and finance": "Accounting & Finance",
    "computer network & security": "Computer Networks & Security",
    "computer networks and security": "Computer Networks & Security",
    "business analytics and programming": "Business Analytics & Programming",
    "international relation": "International Relations",
    "master of business administration": "Business Administration",
    "bba / bba honors": "Business Administration",
    "business administration": "Business Administration",
    "pharm.d.": "Pharmacy (Pharm.D.)",
    "pharm.d": "Pharmacy (Pharm.D.)",
    "dpt": "Doctor of Physical Therapy",
    "b.ed": "Education (B.Ed)",
    "textile sciences.": "Textile Sciences",
    "media sciences) the": "Media Sciences",
}


def _title_field(text: str) -> str:
    small = {"and", "of", "with", "in", "for", "the", "a", "an"}
    words: list[str] = []
    for i, raw in enumerate(text.replace(" and ", " & ").split()):
        w = raw.strip()
        if not w:
            continue
        low = w.lower()
        if low in small and i > 0:
            words.append("&" if w == "&" else low)
        elif low in {"ai", "cs", "it", "se", "mba", "bba", "ms", "bs"}:
            words.append(low.upper())
        elif w.isupper() and len(w) <= 4:
            words.append(w)
        else:
            words.append(w[0].upper() + w[1:] if len(w) > 1 else w.upper())
    return " ".join(words)


def program_to_field_label(raw: str) -> str | None:
    """Turn a noisy offered_courses string into a clean field-of-study label."""
    text = re.sub(r"\s+", " ", (raw or "").strip())
    text = text.replace("Gamming", "Gaming")
    if not text or len(text) > 90:
        return None
    if _JUNK_FIELD_RE.search(text):
        return None

    paren = re.search(r"\(([^)]{3,55})\)\s*$", text)
    if paren:
        text = paren.group(1).strip()
    else:
        text = _DEGREE_LEAD_RE.sub("", text).strip(" -–—:()")
        text = re.sub(r"^of\s+", "", text, flags=re.IGNORECASE).strip()

    text = re.sub(r"\s+", " ", text).strip(" -.")
    if len(text) < 3 or len(text) > 48:
        return None
    if text.lower().startswith("in ") and " " in text[3:]:
        text = text[3:].strip()
    if text.lower().startswith(("programme", "program ", "m.engg", "mem programme")):
        return None
    if "(" in text or ")" in text or text.endswith(("+", "*", ".")):
        return None
    # Collapse accidental duplicated phrases: "Development Studies Development Studies"
    parts = text.split()
    if len(parts) >= 4 and len(parts) % 2 == 0:
        half = len(parts) // 2
        if [p.lower() for p in parts[:half]] == [p.lower() for p in parts[half:]]:
            text = " ".join(parts[:half])
    if _JUNK_FIELD_RE.search(text):
        return None
    if text.lower() in {"the", "and", "of", "cls & ri", "per 3 cr.hrs"}:
        return None

    alias = _FIELD_ALIASES.get(text.lower())
    if alias:
        return alias
    return _title_field(text)


def _all_offered_courses() -> list[str]:
    courses: list[str] = []
    # Prefer full lists from normalized JSON (complete).
    if NORMALIZED_DIR.exists():
        for path in sorted(NORMALIZED_DIR.glob("*_normalized.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            raw = data.get("offered_courses") or []
            if isinstance(raw, str):
                raw = [raw]
            courses.extend(str(c) for c in raw if c)
    if courses:
        return courses
    for uni in list_universities():
        courses.extend(uni.get("programs") or [])
    return courses


def list_field_of_study_options(*, include: str | None = None) -> list[str]:
    """Distinct field-of-study labels derived from university offered_courses."""
    seen: dict[str, str] = {}  # lower -> display
    for raw in _all_offered_courses():
        label = program_to_field_label(raw)
        if not label:
            continue
        key = label.lower()
        # Prefer the longer/clearer spelling if we collide on aliases already merged
        if key not in seen or len(label) > len(seen[key]):
            seen[key] = label

    options = sorted(seen.values(), key=lambda s: s.lower())
    current = (include or "").strip()
    if current and current.lower() not in {o.lower() for o in options}:
        options = [current] + options
    return options


# --- Current education options from eligibility language in the dataset ---

# Each option is a student-status label that also matches agent eligibility
# gating (agent.nodes._stage_rank). Patterns detect whether that pathway
# appears in university eligibility text.
_EDUCATION_OPTION_SPECS: list[tuple[str, tuple[str, ...]]] = [
    (
        "Matric / O-Levels in progress",
        (r"\bmatric(?:ulation)?\b", r"\bo[\s\-]?levels?\b"),
    ),
    (
        "Matric / O-Levels completed",
        (r"\bmatric(?:ulation)?\b", r"\bo[\s\-]?levels?\b"),
    ),
    (
        "Intermediate / FSc (Pre-Engineering) in progress",
        (r"\bpre[\s\-]?engineering\b", r"\bintermediate\b", r"\bf\.?\s*sc\b", r"\bhssc\b"),
    ),
    (
        "Intermediate / FSc (Pre-Engineering) completed",
        (r"\bpre[\s\-]?engineering\b", r"\bintermediate\b", r"\bf\.?\s*sc\b", r"\bhssc\b"),
    ),
    (
        "Intermediate / FSc (Pre-Medical) in progress",
        (r"\bpre[\s\-]?medical\b", r"\bintermediate\b"),
    ),
    (
        "Intermediate / FSc (Pre-Medical) completed",
        (r"\bpre[\s\-]?medical\b", r"\bintermediate\b"),
    ),
    (
        "Intermediate / ICS (Computer Science) completed",
        (r"\bics\b", r"\bcomputer science\b.*\bintermediate\b", r"\bintermediate\b.*\bcomputer science\b"),
    ),
    (
        "Intermediate / Commerce completed",
        (r"\bcommerce\b", r"\bintermediate\b"),
    ),
    (
        "A-Levels in progress",
        (r"\ba[\s\-]?levels?\b",),
    ),
    (
        "A-Levels completed",
        (r"\ba[\s\-]?levels?\b",),
    ),
    (
        "DAE (Diploma of Associate Engineering) completed",
        (r"\bdae\b", r"\bdiploma of associate\b"),
    ),
    (
        "Bachelor's degree in progress",
        (r"\bbachelor", r"\bbs\b", r"\bbba\b", r"\bundergraduate\b"),
    ),
    (
        "Bachelor's degree completed",
        (r"\bbachelor", r"\bbs\b", r"\bbba\b", r"\b16 years\b"),
    ),
    (
        "Master's / MS / MPhil completed",
        (r"\bmaster", r"\bmphil\b", r"\bms\b", r"\b18 years\b"),
    ),
]


def _eligibility_corpus() -> str:
    """Concatenate eligibility-related text from normalized university JSON."""
    parts: list[str] = []
    if not NORMALIZED_DIR.exists():
        return ""
    for path in sorted(NORMALIZED_DIR.glob("*_normalized.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key in ("eligibility_criteria", "test_pattern", "scholarships", "offered_courses"):
            value = data.get(key)
            if isinstance(value, list):
                parts.extend(str(item) for item in value if item)
            elif value:
                parts.append(str(value))
        if data.get("raw_text"):
            parts.append(str(data["raw_text"]))
    return "\n".join(parts)


def list_education_level_options(*, include: str | None = None) -> list[str]:
    """Education-stage options grounded in qualifications mentioned in the dataset."""
    corpus = _eligibility_corpus()
    corpus_l = corpus.lower()
    options: list[str] = []
    for label, patterns in _EDUCATION_OPTION_SPECS:
        if any(re.search(pat, corpus_l, flags=re.IGNORECASE) for pat in patterns):
            options.append(label)

    # Always keep a minimal viable set so the form works even if data is thin.
    if not options:
        options = [
            "Matric / O-Levels completed",
            "Intermediate / FSc (Pre-Engineering) completed",
            "A-Levels completed",
            "Bachelor's degree completed",
        ]

    current = (include or "").strip()
    if current and current not in options:
        options = [current] + options
    return options
