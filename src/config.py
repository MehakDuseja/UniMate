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
AGENT_CHECKPOINT_DB = DATA_DIR / "agent_checkpoints.db"
UNIMATE_DB = DATA_DIR / "unimate.db"

GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
GOOGLE_API_KEY_ENV = "GOOGLE_API_KEY"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
EMBEDDING_API_KEY = os.getenv(GEMINI_API_KEY_ENV) or os.getenv(GOOGLE_API_KEY_ENV) or os.getenv(OPENAI_API_KEY_ENV)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-2")
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-3.1-flash-lite")

# Optional: set LANGSMITH_API_KEY in .env to trace every graph run and every
# individual Gemini call (agent/llm.py's generate_text/generate_json are
# decorated with @traceable) at smith.langchain.com - useful for seeing
# exactly what context/prompt produced a wrong answer. Just adding the key
# turns tracing on; nothing else needs to be set.
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
if LANGSMITH_API_KEY:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", os.getenv("LANGSMITH_PROJECT", "unimate"))

USER_AGENT = "Mozilla/5.0 (research/educational scraping bot; contact: you@example.com)"
REQUEST_DELAY_SECONDS = int(os.getenv("REQUEST_DELAY_SECONDS", "2"))
