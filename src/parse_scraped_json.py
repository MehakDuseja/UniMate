"""Parse scraped university JSON files into a structured record format."""
from __future__ import annotations

import json

from .config import DATA_DIR, OUTPUT_JSON_DIR

INPUT_DIR = OUTPUT_JSON_DIR
OUTPUT_DIR = DATA_DIR / "parsed_universities"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

from .parsers import parse_scraped_university


def main() -> None:
    for path in sorted(INPUT_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        location = None
        if path.stem == "iba":
            location = "University Enclave, Karachi, 75270"
        elif path.stem == "habib_university":
            location = "Block 18 University Ave, Gulistan-e-Johar, Karachi, 75290"
        elif path.stem == "dha_suffa":
            location = "Phase 7 Ext, Karachi, 75500"
        elif path.stem == "szabist":
            location = "R2CH+5XP, 99 3rd Ave, Block 5 Clifton, Karachi, 75600"
        elif path.stem == "fast_university":
            location = "Sector 17-D, Karachi"
        elif path.stem == "ned_university":
            location = "Service Rd, NED University Of Engineering & Technology, Karachi"
        elif path.stem == "uit":
            location = "ST-13, Block 7, Gulshan-e-Iqbal, Abul Hasan Isphahani Road, Karachi, 75300"
        elif path.stem == "iqra_university":
            location = "Iqra University Main Campus, Defence View, Karachi"
        elif path.stem == "sir_syed_university":
            location = "University Road, Karachi, 75300"

        parsed = parse_scraped_university(data, location=location)
        out_path = OUTPUT_DIR / f"{path.stem}_parsed.json"
        out_path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Parsed {path.name} -> {out_path.name}")


if __name__ == "__main__":
    main()
