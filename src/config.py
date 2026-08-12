"""Central project configuration for UniMate."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
# Process env wins over .env (standard dotenv behavior). Skip entirely when
# UNIMATE_SKIP_DOTENV=1 so unit tests can control keys in isolation.
if os.getenv("UNIMATE_SKIP_DOTENV") != "1":
    load_dotenv(ROOT / ".env", override=False)

# Vercel (and similar) only allow writes under /tmp — using data/*.db there
# causes intermittent 503s when SQLite/checkpoints can't be created.
IS_SERVERLESS = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
_RUNTIME_DIR = Path(os.getenv("UNIMATE_RUNTIME_DIR") or ("/tmp/unimate" if IS_SERVERLESS else str(ROOT / "data")))
if IS_SERVERLESS:
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR = ROOT / "data"
OUTPUT_JSON_DIR = ROOT / "output_json"
NORMALIZED_DIR = DATA_DIR / "normalized_universities"
SEMANTIC_CHUNKS_DIR = DATA_DIR / "semantic_chunks"
CHROMA_DIR = (_RUNTIME_DIR / "chroma_db") if IS_SERVERLESS else (DATA_DIR / "chroma_db")
INGEST_DB = (_RUNTIME_DIR / "university_ingest.db") if IS_SERVERLESS else (DATA_DIR / "university_ingest.db")
AGENT_CHECKPOINT_DB = (_RUNTIME_DIR / "agent_checkpoints.db") if IS_SERVERLESS else (DATA_DIR / "agent_checkpoints.db")
UNIMATE_DB = (_RUNTIME_DIR / "unimate.db") if IS_SERVERLESS else (DATA_DIR / "unimate.db")

OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()

# Optional force: LLM_PROVIDER=openai|gemini. Otherwise auto-pick from keys:
# OpenAI if OPENAI_API_KEY is set, else Gemini if GEMINI/GOOGLE key is set.
_provider_override = (os.getenv("LLM_PROVIDER") or "").strip().lower()
if _provider_override in ("openai", "gemini"):
    LLM_PROVIDER = _provider_override
elif OPENAI_API_KEY:
    LLM_PROVIDER = "openai"
elif GEMINI_API_KEY:
    LLM_PROVIDER = "gemini"
else:
    LLM_PROVIDER = ""

OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-3.1-flash-lite")
CHAT_MODEL = OPENAI_CHAT_MODEL if LLM_PROVIDER == "openai" else GEMINI_CHAT_MODEL

# Embeddings keep their own key preference so an OpenAI-only chat setup can
# still embed with Gemini (or vice versa) when both keys exist. Prefer Gemini
# embeddings when a Gemini key is present (matches existing Chroma indexes);
# fall back to OpenAI embeddings when only OpenAI is configured.
if GEMINI_API_KEY:
    EMBEDDING_PROVIDER = "gemini"
    EMBEDDING_API_KEY = GEMINI_API_KEY
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-2")
elif OPENAI_API_KEY:
    EMBEDDING_PROVIDER = "openai"
    EMBEDDING_API_KEY = OPENAI_API_KEY
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
else:
    EMBEDDING_PROVIDER = ""
    EMBEDDING_API_KEY = ""
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-2")

# Back-compat aliases used across older call sites
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
GOOGLE_API_KEY_ENV = "GOOGLE_API_KEY"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"

# Optional: set LANGSMITH_API_KEY in .env to trace every graph run and every
# individual LLM call (agent/llm.py's generate_text/generate_json are
# decorated with @traceable) at smith.langchain.com - useful for seeing
# exactly what context/prompt produced a wrong answer. Just adding the key
# turns tracing on; nothing else needs to be set.
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
if LANGSMITH_API_KEY:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", os.getenv("LANGSMITH_PROJECT", "unimate"))

USER_AGENT = "Mozilla/5.0 (research/educational scraping bot; contact: you@example.com)"
REQUEST_DELAY_SECONDS = int(os.getenv("REQUEST_DELAY_SECONDS", "2"))
