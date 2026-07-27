"""Central project configuration for UniMate."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
DATA_DIR = ROOT / "data"
OUTPUT_JSON_DIR = ROOT / "output_json"
NORMALIZED_DIR = DATA_DIR / "normalized_universities"
SEMANTIC_CHUNKS_DIR = DATA_DIR / "semantic_chunks"
CHROMA_DIR = DATA_DIR / "chroma_db"
INGEST_DB = DATA_DIR / "university_ingest.db"

GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
GOOGLE_API_KEY_ENV = "GOOGLE_API_KEY"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
EMBEDDING_API_KEY = os.getenv(GEMINI_API_KEY_ENV) or os.getenv(GOOGLE_API_KEY_ENV) or os.getenv(OPENAI_API_KEY_ENV)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-2")
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-3.1-flash-lite")

USER_AGENT = "Mozilla/5.0 (research/educational scraping bot; contact: you@example.com)"
REQUEST_DELAY_SECONDS = int(os.getenv("REQUEST_DELAY_SECONDS", "2"))
