"""Orchestrate downloading PDFs referenced in output_json/*.json and parsing them.

Usage: run inside the project venv:
    python3 src/download_and_parse.py
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = ROOT / "output_json"
RAW_PDF_DIR = ROOT / "data" / "raw_pdfs"
PARSED_DIR = ROOT / "data" / "parsed_pdfs"

sys.path.insert(0, str(ROOT / "src"))

from downloads import download_file
from parsers import parse_pdf


def find_pdf_urls_in_university_json(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    urls = []
    for page in data.get("pages", []):
        u = page.get("url")
        if not u:
            continue
        if ".pdf" in u.lower():
            urls.append(u)
    return urls


def main():
    RAW_PDF_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_DIR.mkdir(parents=True, exist_ok=True)

    json_files = list(OUTPUT_JSON.glob("*.json"))
    print(f"Found {len(json_files)} university JSON files")

    for jf in json_files:
        uni = jf.stem
        print(f"Processing {uni}")
        urls = find_pdf_urls_in_university_json(jf)
        print(f"  Found {len(urls)} PDF URLs")
        for url in urls:
            try:
                saved_path, sha = download_file(url, RAW_PDF_DIR)
            except Exception as e:
                print(f"  Failed to download {url}: {e}")
                continue

            print(f"  Downloaded to {saved_path} (sha={sha[:8]})")

            try:
                parsed = parse_pdf(str(saved_path))
            except Exception as e:
                print(f"  Failed to parse {saved_path}: {e}")
                continue

            out_path = PARSED_DIR / f"{saved_path.stem}.json"
            out = {"source_url": url, "saved_path": str(saved_path), "sha256": sha, "parsed": parsed}
            out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  Parsed output saved to {out_path}")


if __name__ == "__main__":
    main()
