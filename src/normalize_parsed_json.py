"""Normalize parsed university records into the final canonical schema."""
from __future__ import annotations

from .config import DATA_DIR
from .normalizer import normalize_all

PARSED_DIR = DATA_DIR / "parsed_universities"
NORMALIZED_DIR = DATA_DIR / "normalized_universities"
NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    normalize_all(PARSED_DIR, NORMALIZED_DIR)


if __name__ == "__main__":
    main()
