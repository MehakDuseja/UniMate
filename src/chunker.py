"""Chunk university JSON data for semantic embedding and metadata tagging."""
from __future__ import annotations

import json
import re
from typing import Any

from .config import NORMALIZED_DIR, SEMANTIC_CHUNKS_DIR as CHUNKS_DIR

CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

MAX_CHARS = 1200
OVERLAP_CHARS = 150

DEGREE_LEVEL_PATTERNS = [
    ("PhD", re.compile(r"\bph\.?\s?d\b", re.I)),
    ("Master", re.compile(r"\b(ms|m\.s\.|mba|master(?:'s)?|master of)\b", re.I)),
    ("Bachelor", re.compile(r"\b(bs|b\.s\.|bba|bachelor(?:'s)?|bachelor of)\b", re.I)),
]


def detect_degree_levels(text: str) -> list[str]:
    return [label for label, pattern in DEGREE_LEVEL_PATTERNS if pattern.search(text)]


def _ensure_sentence_spacing(text: str) -> str:
    """HTML-to-text extraction sometimes drops the space after a period where
    two list items got concatenated (e.g. "...admission.Any incorrect...").
    Insert one back so sentence splitting doesn't produce giant run-on blocks.
    """
    return re.sub(r"(?<=[.!?])(?=[A-Z])", " ", text)


def split_sentences(text: str) -> list[str]:
    text = _ensure_sentence_spacing(re.sub(r"\s+", " ", text).strip())
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _pack_units(units: list[str], max_chars: int, overlap: int) -> list[str]:
    """Greedily pack whole units (sentences or list items) into chunks up to
    max_chars, never splitting a unit itself. Carries trailing units into the
    next chunk for overlap."""
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for unit in units:
        unit_len = len(unit) + 1
        if current and current_len + unit_len > max_chars:
            chunks.append(" ".join(current))
            carried: list[str] = []
            carried_len = 0
            for u in reversed(current):
                if carried_len + len(u) + 1 > overlap:
                    break
                carried.insert(0, u)
                carried_len += len(u) + 1
            current, current_len = carried, carried_len
        current.append(unit)
        current_len += unit_len
    if current:
        chunks.append(" ".join(current))
    return chunks


def chunk_text(text: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """Sentence-safe chunking of a single blob of text. Never cuts mid-word."""
    return _pack_units(split_sentences(text), max_chars, overlap)


def chunk_items(items: list[str], max_chars: int = MAX_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """Pack a list of naturally-bounded items (e.g. one string per program
    block, or one fee line) into chunks, keeping each item intact whenever it
    fits. Only an oversized single item gets split further, by sentence."""
    units: list[str] = []
    for item in items:
        item = item.strip()
        if not item:
            continue
        if len(item) > max_chars:
            units.extend(split_sentences(item))
        else:
            units.append(item)
    return _pack_units(units, max_chars, overlap)


def make_chunk_metadata(record: dict[str, Any], category: str, text: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "university_id": record["university"].lower().replace(" ", "_").replace("-", "_").replace("/", "_").strip(),
        "university_name": record["university"],
        "city": record.get("location", ""),
        "province": record.get("province") or "",
        "department": category,
        "category": category,
        "degree_levels": ",".join(detect_degree_levels(text)),
        "source_pages": " | ".join(record.get("source_pages", [])),
        "length_chars": len(text),
    }
    # Chroma metadata values must be scalar; only set is_public when known
    # rather than sending None, which some Chroma versions reject on upsert.
    if record.get("is_public") is not None:
        metadata["is_public"] = bool(record.get("is_public"))
    return metadata


def build_chunks() -> None:
    for path in sorted(NORMALIZED_DIR.glob("*_normalized.json")):
        data = json.loads(path.read_text(encoding="utf-8"))

        list_categories = {
            "eligibility": data.get("eligibility_criteria", []),
            "test_pattern": data.get("test_pattern", []),
            "scholarships": data.get("scholarships", []),
            "offered_courses": data.get("offered_courses", []),
            "fee_structure": [
                f"{f.get('label')}: {f.get('value')}"
                for f in data.get("fee_structure", {}).get("fees", [])
                if f.get("label") and f.get("value")
            ],
            "hostel": data.get("hostel_info", []),
        }

        all_chunks: list[dict[str, Any]] = []
        for category, items in list_categories.items():
            for i, chunk_text_value in enumerate(chunk_items(items)):
                chunk = {
                    "chunk_id": f"{path.stem}_{category}_{i}",
                    "category": category,
                    "text": f"[University: {data.get('university')} | Category: {category}] {chunk_text_value}",
                    "metadata": make_chunk_metadata(data, category, chunk_text_value),
                }
                all_chunks.append(chunk)

        out_path = CHUNKS_DIR / f"{path.stem}_chunks.json"
        out_path.write_text(json.dumps(all_chunks, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {len(all_chunks)} chunks for {path.name}")


if __name__ == "__main__":
    build_chunks()
