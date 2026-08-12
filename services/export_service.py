"""PDF / text exports for recommendations and student profile."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Optional

import fitz


def _safe(text: Any, fallback: str = "—") -> str:
    s = str(text if text is not None else "").strip()
    return s if s else fallback


def _wrap_lines(text: str, width: int = 92) -> list[str]:
    words = str(text or "").split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        trial = f"{cur} {w}"
        if len(trial) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _new_page(doc: fitz.Document) -> fitz.Page:
    return doc.new_page(width=595, height=842)  # A4


def _draw_header(page: fitz.Page, title: str, subtitle: str) -> float:
    y = 48
    page.insert_text((48, y), "UniMate", fontsize=11, fontname="helv", color=(0.06, 0.64, 0.50))
    y += 22
    page.insert_text((48, y), title, fontsize=18, fontname="helv", color=(0.05, 0.05, 0.05))
    y += 16
    page.insert_text((48, y), subtitle, fontsize=9, fontname="helv", color=(0.4, 0.4, 0.45))
    y += 10
    page.draw_line(fitz.Point(48, y), fitz.Point(547, y), color=(0.85, 0.85, 0.88), width=0.8)
    return y + 22


def _ensure_space(doc: fitz.Document, page: fitz.Page, y: float, need: float = 40) -> tuple[fitz.Page, float]:
    if y + need < 800:
        return page, y
    page = _new_page(doc)
    return page, 48


def build_recommendations_pdf(
    recommendations: list[dict[str, Any]],
    *,
    profile: Optional[dict[str, Any]] = None,
    title: str = "University recommendations",
) -> bytes:
    """Return PDF bytes for a ranked recommendation list."""
    doc = fitz.open()
    page = _new_page(doc)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    y = _draw_header(page, title, f"Generated {stamp}")

    if profile:
        bits = []
        for key, label in (
            ("field_of_study", "Field"),
            ("degree_level", "Degree"),
            ("academic_percentage", "Marks"),
            ("budget_pkr_per_semester", "Budget"),
            ("preferred_province", "Province"),
            ("student_city", "City"),
        ):
            val = profile.get(key)
            if val not in (None, "", []):
                if key == "budget_pkr_per_semester":
                    try:
                        val = f"{int(float(val)):,} PKR / semester"
                    except (TypeError, ValueError):
                        pass
                bits.append(f"{label}: {val}")
        if bits:
            page.insert_text((48, y), "Profile used", fontsize=10, fontname="helv", color=(0.06, 0.64, 0.50))
            y += 14
            for line in _wrap_lines(" · ".join(bits), 95):
                page, y = _ensure_space(doc, page, y, 14)
                page.insert_text((48, y), line, fontsize=9, fontname="helv", color=(0.25, 0.25, 0.28))
                y += 12
            y += 10

    if not recommendations:
        page.insert_text(
            (48, y),
            "No recommendations yet. Ask UniMate to recommend fits first.",
            fontsize=11,
            fontname="helv",
            color=(0.35, 0.35, 0.4),
        )
    else:
        for i, rec in enumerate(recommendations, start=1):
            page, y = _ensure_space(doc, page, y, 70)
            name = _safe(rec.get("university_name") or rec.get("university_id"), f"University {i}")
            score = rec.get("total_score", rec.get("match_score"))
            try:
                score_txt = f"{int(round(float(score)))}% match" if score is not None else ""
            except (TypeError, ValueError):
                score_txt = ""

            heading = f"{i}. {name}"
            if score_txt:
                heading += f"  —  {score_txt}"
            page.insert_text((48, y), heading, fontsize=12, fontname="helv", color=(0.05, 0.05, 0.05))
            y += 16

            reason = (rec.get("reasoning") or rec.get("reason") or "").strip()
            if reason:
                for line in _wrap_lines(reason, 95):
                    page, y = _ensure_space(doc, page, y, 12)
                    page.insert_text((56, y), line, fontsize=9, fontname="helv", color=(0.3, 0.3, 0.34))
                    y += 11

            for factor in (rec.get("factors") or [])[:6]:
                label = factor.get("label") or factor.get("criterion") or ""
                detail = factor.get("detail") or ""
                status = factor.get("status") or ""
                mark = "OK" if status == "pass" else "Note"
                line = f"[{mark}] {label}: {detail}".strip(": ")
                for wrapped in _wrap_lines(line, 90):
                    page, y = _ensure_space(doc, page, y, 12)
                    page.insert_text((56, y), wrapped, fontsize=8.5, fontname="helv", color=(0.35, 0.35, 0.4))
                    y += 11
            y += 14

    page, y = _ensure_space(doc, page, y, 30)
    page.insert_text(
        (48, y),
        "UniMate — Pakistani university admissions assistant. Verify fees & deadlines on official sites.",
        fontsize=8,
        fontname="helv",
        color=(0.55, 0.55, 0.58),
    )

    buf = BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def build_profile_pdf(profile: dict[str, Any], *, completeness_pct: int = 0) -> bytes:
    doc = fitz.open()
    page = _new_page(doc)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    y = _draw_header(page, "Student profile", f"Completeness {completeness_pct}% · {stamp}")

    sections = [
        (
            "About you",
            [
                ("name", "Name"),
                ("email", "Email"),
                ("phone", "Phone"),
                ("student_city", "City"),
                ("student_area", "Neighborhood"),
            ],
        ),
        (
            "Study goals",
            [
                ("field_of_study", "Field"),
                ("degree_level", "Degree"),
                ("academic_percentage", "Academic %"),
                ("current_education_level", "Current education"),
            ],
        ),
        (
            "Constraints",
            [
                ("preferred_province", "Province"),
                ("budget_pkr_per_semester", "Budget / semester"),
                ("hostel_required", "Hostel"),
                ("scholarship_required", "Scholarships"),
                ("priority_focus", "Priority"),
            ],
        ),
    ]

    for section_title, fields in sections:
        page, y = _ensure_space(doc, page, y, 36)
        page.insert_text((48, y), section_title, fontsize=11, fontname="helv", color=(0.06, 0.64, 0.50))
        y += 16
        for key, label in fields:
            val = profile.get(key)
            if val is None or val == "":
                continue
            if isinstance(val, bool):
                val = "Yes" if val else "No"
            if key == "budget_pkr_per_semester":
                try:
                    val = f"{int(float(val)):,} PKR"
                except (TypeError, ValueError):
                    pass
            page, y = _ensure_space(doc, page, y, 14)
            page.insert_text((56, y), f"{label}: {_safe(val)}", fontsize=10, fontname="helv", color=(0.15, 0.15, 0.18))
            y += 14
        y += 8

    buf = BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def recommendations_markdown(
    recommendations: list[dict[str, Any]],
    *,
    profile: Optional[dict[str, Any]] = None,
) -> str:
    lines = ["# UniMate recommendations", ""]
    if profile:
        bits = [
            f"{k.replace('_', ' ')}: {v}"
            for k, v in profile.items()
            if v not in (None, "", [], {}) and k in {
                "field_of_study", "degree_level", "academic_percentage",
                "budget_pkr_per_semester", "preferred_province", "student_city",
            }
        ]
        if bits:
            lines.append("Profile: " + " · ".join(bits))
            lines.append("")
    if not recommendations:
        lines.append("_No recommendations yet._")
    else:
        for i, rec in enumerate(recommendations, start=1):
            name = rec.get("university_name") or rec.get("university_id") or f"University {i}"
            score = rec.get("total_score", rec.get("match_score"))
            score_bit = f" — {int(round(float(score)))}% match" if score is not None else ""
            lines.append(f"## {i}. {name}{score_bit}")
            reason = (rec.get("reasoning") or rec.get("reason") or "").strip()
            if reason:
                lines.append(reason)
            for factor in rec.get("factors") or []:
                label = factor.get("label") or factor.get("criterion") or ""
                detail = factor.get("detail") or ""
                lines.append(f"- {label}: {detail}".rstrip(": "))
            lines.append("")
    lines.append("---")
    lines.append("Generated by UniMate. Verify details on official university sites.")
    return "\n".join(lines)
