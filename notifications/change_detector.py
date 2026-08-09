"""Fetch official pages, detect meaningful changes, and deduplicate alerts."""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from notifications.db import get_connection
from notifications.targets import get_monitor_urls

logger = logging.getLogger(__name__)

MEANINGFUL_KEYWORDS: dict[str, list[str]] = {
    "deadline": [
        "deadline", "last date", "due date", "closing date", "apply by",
        "schedule", "admission date", "test date", "entry test", "open day",
    ],
    "fee": [
        "fee", "tuition", "pkr", "rs.", "rs ", "cost", "charges", "payment",
        "refund", "installment",
    ],
    "eligibility": [
        "eligibility", "minimum", "requirement", "criteria", "merit",
        "percentage", "cgpa", "a-level", "intermediate", "hsc", "ssc",
    ],
    "scholarship": [
        "scholarship", "financial aid", "need-based", "merit-based", "concession",
    ],
    "program": [
        "program", "programme", "bscs", "bs ", "admission", "apply online",
        "prospectus", "announcement",
    ],
}

NOISE_PATTERNS = [
    re.compile(r"\blast updated\b.*", re.I),
    re.compile(r"\bcopyright\b.*", re.I),
    re.compile(r"\ball rights reserved\b.*", re.I),
]


@dataclass
class DetectedChange:
    id: str
    university_id: str
    url: str
    page_title: str
    change_type: str
    summary: str
    content_hash: str


def normalize_content(text: str) -> str:
    text = text or ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for pattern in NOISE_PATTERNS:
        text = pattern.sub("", text)
    return text.strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_content(text).encode("utf-8")).hexdigest()


def _keyword_hits(text: str) -> dict[str, list[str]]:
    lower = text.lower()
    hits: dict[str, list[str]] = {}
    for category, words in MEANINGFUL_KEYWORDS.items():
        matched = [w for w in words if w in lower]
        if matched:
            hits[category] = matched
    return hits


def _extract_changed_sentences(old_text: str, new_text: str, limit: int = 3) -> list[str]:
    old_parts = re.split(r"(?<=[.!?])\s+", old_text)
    new_parts = re.split(r"(?<=[.!?])\s+", new_text)
    old_set = {normalize_content(p) for p in old_parts if len(p) > 20}
    snippets: list[str] = []
    for part in new_parts:
        norm = normalize_content(part)
        if len(norm) < 20 or norm in old_set:
            continue
        if _keyword_hits(part):
            snippets.append(part.strip()[:240])
        if len(snippets) >= limit:
            break
    return snippets


def classify_change(old_text: str, new_text: str, page_title: str) -> tuple[str, str]:
    new_hits = _keyword_hits(new_text)
    categories = list(new_hits.keys()) or ["general"]
    primary = categories[0]
    if "deadline" in new_hits:
        primary = "deadline"
    elif "fee" in new_hits:
        primary = "fee"
    elif "scholarship" in new_hits:
        primary = "scholarship"
    elif "eligibility" in new_hits:
        primary = "eligibility"

    snippets = _extract_changed_sentences(old_text, new_text)
    if snippets:
        summary = f"{page_title}: " + " | ".join(snippets)
    elif new_hits:
        labels = ", ".join(sorted(set(categories)))
        summary = f"{page_title}: updates detected related to {labels}."
    else:
        summary = f"{page_title}: official page content changed."

    return primary, summary[:500]


def is_meaningful_change(old_text: str, new_text: str) -> bool:
    old_norm = normalize_content(old_text)
    new_norm = normalize_content(new_text)
    if not new_norm:
        return False
    if not old_norm:
        return bool(_keyword_hits(new_text))

    ratio = SequenceMatcher(None, old_norm, new_norm).ratio()
    if ratio >= 0.99:
        return False

    new_hits = _keyword_hits(new_text)
    old_hits = _keyword_hits(old_text)
    if new_hits and new_hits != old_hits:
        return True

    # New keywords appeared in changed regions.
    snippets = _extract_changed_sentences(old_text, new_text, limit=1)
    if snippets:
        return True

    # Large content shift on an admissions page is worth flagging.
    len_delta = abs(len(new_norm) - len(old_norm)) / max(len(old_norm), 1)
    return len_delta >= 0.05 and ratio < 0.97


def _fetch_page(url: str) -> tuple[str, str]:
    from university_scraper import scrape_page

    data = scrape_page(url)
    title = data.get("page_title") or url
    content = data.get("content") or ""
    tables = data.get("tables") or []
    for table in tables:
        for row in table.get("rows") or []:
            content += " " + " ".join(str(c) for c in row)
    return title, content.strip()


def _get_snapshot(university_id: str, url: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT content_hash, normalized_text, page_title
            FROM page_snapshots WHERE university_id = ? AND url = ?
            """,
            (university_id, url),
        ).fetchone()
    return dict(row) if row else None


def _save_snapshot(
    university_id: str,
    url: str,
    page_title: str,
    normalized: str,
    digest: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO page_snapshots (id, university_id, url, content_hash, normalized_text, page_title, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(university_id, url) DO UPDATE SET
                content_hash = excluded.content_hash,
                normalized_text = excluded.normalized_text,
                page_title = excluded.page_title,
                scraped_at = datetime('now')
            """,
            (str(uuid.uuid4()), university_id, url, digest, normalized, page_title),
        )


def _record_change(change: DetectedChange) -> bool:
    """Insert change if this exact content state was not seen before. Returns True if new."""
    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT id, notified_at FROM detected_changes
            WHERE university_id = ? AND url = ? AND content_hash = ?
            """,
            (change.university_id, change.url, change.content_hash),
        ).fetchone()
        if existing:
            return False
        conn.execute(
            """
            INSERT INTO detected_changes (
                id, university_id, url, page_title, change_type, summary,
                content_hash, is_meaningful
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                change.id,
                change.university_id,
                change.url,
                change.page_title,
                change.change_type,
                change.summary,
                change.content_hash,
            ),
        )
    return True


def check_page(university_id: str, url: str) -> Optional[DetectedChange]:
    try:
        page_title, raw_content = _fetch_page(url)
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        raise

    normalized = normalize_content(raw_content)
    digest = content_hash(raw_content)
    prior = _get_snapshot(university_id, url)

    if prior and prior["content_hash"] == digest:
        return None

    old_text = prior["normalized_text"] if prior else ""
    if prior and not is_meaningful_change(old_text, normalized):
        _save_snapshot(university_id, url, page_title, normalized, digest)
        logger.info("Cosmetic-only change ignored for %s", url)
        return None

    change_type, summary = classify_change(old_text, normalized, page_title)
    change = DetectedChange(
        id=str(uuid.uuid4()),
        university_id=university_id,
        url=url,
        page_title=page_title,
        change_type=change_type,
        summary=summary,
        content_hash=digest,
    )

    if _record_change(change):
        _save_snapshot(university_id, url, page_title, normalized, digest)
        return change

    _save_snapshot(university_id, url, page_title, normalized, digest)
    return None


def check_university(university_id: str) -> list[DetectedChange]:
    urls = get_monitor_urls(university_id)
    if not urls:
        logger.warning("No monitor URLs configured for %s", university_id)
        return []

    changes: list[DetectedChange] = []
    for url in urls:
        try:
            change = check_page(university_id, url)
            if change:
                changes.append(change)
        except Exception as exc:
            logger.error("Error checking %s (%s): %s", university_id, url, exc)
    return changes


def mark_change_notified(change_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE detected_changes SET notified_at = datetime('now') WHERE id = ?",
            (change_id,),
        )


def list_pending_changes(university_id: str) -> list[DetectedChange]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, university_id, url, page_title, change_type, summary, content_hash
            FROM detected_changes
            WHERE university_id = ? AND notified_at IS NULL AND is_meaningful = 1
            ORDER BY detected_at ASC
            """,
            (university_id,),
        ).fetchall()
    return [
        DetectedChange(
            id=row["id"],
            university_id=row["university_id"],
            url=row["url"],
            page_title=row["page_title"] or row["url"],
            change_type=row["change_type"],
            summary=row["summary"],
            content_hash=row["content_hash"],
        )
        for row in rows
    ]
