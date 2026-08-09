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
from langsmith import traceable

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


# @traceable is a no-op when LANGSMITH_API_KEY isn't set (src/config.py only
# enables tracing when a key is present), so this is safe to leave on
# unconditionally - when tracing IS on, it captures exactly the system
# prompt, user prompt, and raw response for every Gemini call, nested under
# that turn's graph run, which is the actual place a wrong recommendation or
# a bad retrieval-grounded answer traces back to.
@traceable(name="gemini.generate_text", run_type="llm")
def generate_text(system_prompt: str, user_prompt: str, model: str = GEMINI_CHAT_MODEL) -> str:
    """Free-form conversational text generation (e.g. asking the student a question)."""
    resp = _call_with_retry(
        model, user_prompt, types.GenerateContentConfig(system_instruction=system_prompt)
    )
    return (resp.text or "").strip()


_STRING_FIELD_ESCAPES = (("\\n", "\n"), ('\\"', '"'), ("\\t", "\t"), ("\\\\", "\\"))


def _unescape_json_string_delta(delta: str) -> str:
    for escaped, real in _STRING_FIELD_ESCAPES:
        delta = delta.replace(escaped, real)
    return delta


def generate_json_live(system_prompt: str, user_prompt: str, stream_fields: list[str], model: str = GEMINI_CHAT_MODEL):
    """Streams a JSON-mode call, yielding (field_name, delta) as each string
    field named in `stream_fields` is generated, then a final ("_result",
    dict) with the fully parsed JSON object once the call completes.

    This is what lets a UI show the model's OWN generated reasoning live
    (e.g. a "thinking" field genuinely written by the model this call,
    varying every time) instead of a hardcoded status string - and, for
    callers that put their real answer in a later string field of the same
    JSON object (e.g. {"thinking": ..., "answer": ...}), lets that answer
    stream too, all from a single call rather than two.

    Field extraction is a best-effort regex scan over the growing raw
    buffer (matching Gemini's actual JSON-mode output, not a real streaming
    JSON parser) - fine for the natural-language fields this is used for,
    but not robust against a field's value containing a literal unescaped
    quote mid-stream; worst case a field's live deltas glitch cosmetically
    while the final _result (parsed from the complete buffer) is still
    correct. Only the fields listed in `stream_fields`, in the order given,
    are streamed - list them in the same order your prompt's schema
    actually asks the model to emit them in, since a field can't stream
    before it starts appearing in the output.

    Like generate_text_stream, retry-on-429 only covers establishing the
    stream - a failure after some events were already yielded isn't
    retried. Not wrapped in @traceable - tracing expects a single return
    value, not a generator; log/use the final _result dict if that matters."""
    client = _get_client()
    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            stream = client.models.generate_content_stream(
                model=model,
                contents=user_prompt,
                config=types.GenerateContentConfig(system_instruction=system_prompt, response_mime_type="application/json"),
            )
            buf = ""
            emitted = {field: 0 for field in stream_fields}
            field_patterns = {
                field: re.compile(rf'"{re.escape(field)}"\s*:\s*"((?:[^"\\]|\\.)*)') for field in stream_fields
            }
            for chunk in stream:
                if not chunk.text:
                    continue
                buf += chunk.text
                for field in stream_fields:
                    match = field_patterns[field].search(buf)
                    if not match:
                        continue
                    value = match.group(1)
                    if len(value) > emitted[field]:
                        delta = value[emitted[field]:]
                        emitted[field] = len(value)
                        yield (field, _unescape_json_string_delta(delta))
            try:
                result = json.loads(buf)
            except json.JSONDecodeError:
                print(f"Warning: Gemini did not return valid JSON, dropping this turn's output. First 200 chars: {buf[:200]!r}")
                result = {}
            yield ("_result", result)
            return
        except errors.ClientError as e:
            if getattr(e, "code", None) != 429 or attempt == MAX_RETRIES:
                raise
            last_exc = e
            wait = _retry_delay_seconds(e)
            print(f"Gemini quota hit (attempt {attempt}/{MAX_RETRIES}), retrying in {wait:.0f}s...")
            time.sleep(wait)
    raise last_exc  # pragma: no cover - unreachable, loop always returns or raises


@traceable(name="gemini.generate_json", run_type="llm")
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
