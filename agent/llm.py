"""Thin Gemini chat wrapper for agent nodes.

Mirrors the google.genai client style already used in src/vector_store.py
rather than pulling in langchain-google-genai as an extra dependency.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Optional

import google.genai as genai
from google.genai import errors, types

from src.config import EMBEDDING_API_KEY, GEMINI_CHAT_MODEL

_client: Optional[genai.Client] = None

MAX_RETRIES = 4
DEFAULT_BACKOFF_SECONDS = 15.0


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not EMBEDDING_API_KEY:
            raise RuntimeError("No Gemini API key found. Set GEMINI_API_KEY in .env.")
        _client = genai.Client(api_key=EMBEDDING_API_KEY)
    return _client


def _retry_delay_seconds(exc: Exception) -> float:
    """The free tier's 429 responses include a retryDelay hint (e.g. '42s');
    honor it when present instead of guessing a fixed backoff."""
    match = re.search(r"'retryDelay': '(\d+(?:\.\d+)?)s'", str(exc))
    if match:
        return float(match.group(1)) + 1.0
    return DEFAULT_BACKOFF_SECONDS


def _call_with_retry(model: str, contents: str, config: types.GenerateContentConfig):
    client = _get_client()
    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return client.models.generate_content(model=model, contents=contents, config=config)
        except errors.ClientError as e:
            if getattr(e, "code", None) != 429 or attempt == MAX_RETRIES:
                raise
            last_exc = e
            wait = _retry_delay_seconds(e)
            print(f"Gemini quota hit (attempt {attempt}/{MAX_RETRIES}), retrying in {wait:.0f}s...")
            time.sleep(wait)
    raise last_exc  # pragma: no cover - unreachable, loop always returns or raises


def generate_text(system_prompt: str, user_prompt: str, model: str = GEMINI_CHAT_MODEL) -> str:
    """Free-form conversational text generation (e.g. asking the student a question)."""
    resp = _call_with_retry(
        model, user_prompt, types.GenerateContentConfig(system_instruction=system_prompt)
    )
    return (resp.text or "").strip()


def generate_json(system_prompt: str, user_prompt: str, model: str = GEMINI_CHAT_MODEL) -> Any:
    """Structured extraction/scoring calls that must return parseable JSON."""
    resp = _call_with_retry(
        model,
        user_prompt,
        types.GenerateContentConfig(system_instruction=system_prompt, response_mime_type="application/json"),
    )
    text = (resp.text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"Warning: Gemini did not return valid JSON, dropping this turn's output. First 200 chars: {text[:200]!r}")
        return {}
