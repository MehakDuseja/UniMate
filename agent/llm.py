"""Chat LLM wrapper for agent nodes — OpenAI or Gemini.

Provider is chosen from .env (see src.config.LLM_PROVIDER):
  - OPENAI_API_KEY present → OpenAI
  - else GEMINI_API_KEY / GOOGLE_API_KEY → Gemini
  - optional LLM_PROVIDER=openai|gemini to force one when both keys exist
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Optional

try:
    from langsmith import traceable
except ImportError:  # pragma: no cover - langsmith is optional on slim deploys
    def traceable(*_args, **_kwargs):  # type: ignore[misc]
        def _decorator(fn):
            return fn

        return _decorator

from src.config import (
    GEMINI_API_KEY,
    GEMINI_CHAT_MODEL,
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_CHAT_MODEL,
)

MAX_RETRIES = 4
DEFAULT_BACKOFF_SECONDS = 15.0

_gemini_client = None
_openai_client = None


def active_provider() -> str:
    if LLM_PROVIDER in ("openai", "gemini"):
        return LLM_PROVIDER
    raise RuntimeError(
        "No LLM API key found. Set OPENAI_API_KEY or GEMINI_API_KEY in .env "
        "(optional: LLM_PROVIDER=openai|gemini when both are set)."
    )


def _default_model() -> str:
    return OPENAI_CHAT_MODEL if active_provider() == "openai" else GEMINI_CHAT_MODEL


def _retry_delay_seconds(exc: Exception) -> float:
    """Honor provider retry hints when present (Gemini free-tier 429s include retryDelay)."""
    match = re.search(r"'retryDelay': '(\d+(?:\.\d+)?)s'", str(exc))
    if match:
        return float(match.group(1)) + 1.0
    match = re.search(r"retry.after['\"].*?(\d+(?:\.\d+)?)", str(exc), re.IGNORECASE)
    if match:
        return float(match.group(1)) + 1.0
    return DEFAULT_BACKOFF_SECONDS


def _is_rate_limit(exc: Exception) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code == 429:
        return True
    name = type(exc).__name__.lower()
    if "ratelimit" in name or "resourceexhausted" in name:
        return True
    text = str(exc).lower()
    return "rate limit" in text or "quota" in text or "429" in text


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("No Gemini API key found. Set GEMINI_API_KEY in .env.")
        import google.genai as genai

        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("No OpenAI API key found. Set OPENAI_API_KEY in .env.")
        from openai import OpenAI

        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def _gemini_generate(system_prompt: str, user_prompt: str, *, model: str, json_mode: bool) -> str:
    from google.genai import errors, types

    client = _get_gemini_client()
    config_kwargs: dict[str, Any] = {"system_instruction": system_prompt}
    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"
    config = types.GenerateContentConfig(**config_kwargs)

    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.models.generate_content(model=model, contents=user_prompt, config=config)
            return (resp.text or "").strip()
        except errors.ClientError as e:
            if getattr(e, "code", None) != 429 or attempt == MAX_RETRIES:
                raise
            last_exc = e
            wait = _retry_delay_seconds(e)
            print(f"Gemini quota hit (attempt {attempt}/{MAX_RETRIES}), retrying in {wait:.0f}s...")
            time.sleep(wait)
    raise last_exc  # pragma: no cover


def _openai_generate(system_prompt: str, user_prompt: str, *, model: str, json_mode: bool) -> str:
    client = _get_openai_client()
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(**kwargs)
            return ((resp.choices[0].message.content if resp.choices else None) or "").strip()
        except Exception as e:
            if not _is_rate_limit(e) or attempt == MAX_RETRIES:
                raise
            last_exc = e
            wait = _retry_delay_seconds(e)
            print(f"OpenAI rate limit (attempt {attempt}/{MAX_RETRIES}), retrying in {wait:.0f}s...")
            time.sleep(wait)
    raise last_exc  # pragma: no cover


_STRING_FIELD_ESCAPES = (("\\n", "\n"), ('\\"', '"'), ("\\t", "\t"), ("\\\\", "\\"))


def _unescape_json_string_delta(delta: str) -> str:
    for escaped, real in _STRING_FIELD_ESCAPES:
        delta = delta.replace(escaped, real)
    return delta


def _stream_json_fields(buf_iter, stream_fields: list[str]):
    """Shared streaming JSON field extractor used by both providers."""
    buf = ""
    emitted = {field: 0 for field in stream_fields}
    field_patterns = {
        field: re.compile(rf'"{re.escape(field)}"\s*:\s*"((?:[^"\\]|\\.)*)') for field in stream_fields
    }
    for piece in buf_iter:
        if not piece:
            continue
        buf += piece
        for field in stream_fields:
            match = field_patterns[field].search(buf)
            if not match:
                continue
            value = match.group(1)
            if len(value) > emitted[field]:
                delta = value[emitted[field] :]
                emitted[field] = len(value)
                yield (field, _unescape_json_string_delta(delta))
    try:
        result = json.loads(buf)
    except json.JSONDecodeError:
        print(
            f"Warning: LLM did not return valid JSON, dropping this turn's output. "
            f"First 200 chars: {buf[:200]!r}"
        )
        result = {}
    yield ("_result", result)


def _gemini_generate_json_live(system_prompt: str, user_prompt: str, stream_fields: list[str], model: str):
    from google.genai import errors, types

    client = _get_gemini_client()
    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            stream = client.models.generate_content_stream(
                model=model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                ),
            )

            def _chunks():
                for chunk in stream:
                    if chunk.text:
                        yield chunk.text

            yield from _stream_json_fields(_chunks(), stream_fields)
            return
        except errors.ClientError as e:
            if getattr(e, "code", None) != 429 or attempt == MAX_RETRIES:
                raise
            last_exc = e
            wait = _retry_delay_seconds(e)
            print(f"Gemini quota hit (attempt {attempt}/{MAX_RETRIES}), retrying in {wait:.0f}s...")
            time.sleep(wait)
    raise last_exc  # pragma: no cover


def _openai_generate_json_live(system_prompt: str, user_prompt: str, stream_fields: list[str], model: str):
    client = _get_openai_client()
    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            stream = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                stream=True,
            )

            def _chunks():
                for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        yield delta

            yield from _stream_json_fields(_chunks(), stream_fields)
            return
        except Exception as e:
            if not _is_rate_limit(e) or attempt == MAX_RETRIES:
                raise
            last_exc = e
            wait = _retry_delay_seconds(e)
            print(f"OpenAI rate limit (attempt {attempt}/{MAX_RETRIES}), retrying in {wait:.0f}s...")
            time.sleep(wait)
    raise last_exc  # pragma: no cover


# @traceable is a no-op when LANGSMITH_API_KEY isn't set.
@traceable(name="llm.generate_text", run_type="llm")
def generate_text(system_prompt: str, user_prompt: str, model: str | None = None) -> str:
    """Free-form conversational text generation."""
    model = model or _default_model()
    if active_provider() == "openai":
        return _openai_generate(system_prompt, user_prompt, model=model, json_mode=False)
    return _gemini_generate(system_prompt, user_prompt, model=model, json_mode=False)


def generate_json_live(
    system_prompt: str,
    user_prompt: str,
    stream_fields: list[str],
    model: str | None = None,
):
    """Streams a JSON-mode call, yielding (field_name, delta) then ("_result", dict)."""
    model = model or _default_model()
    if active_provider() == "openai":
        yield from _openai_generate_json_live(system_prompt, user_prompt, stream_fields, model)
    else:
        yield from _gemini_generate_json_live(system_prompt, user_prompt, stream_fields, model)


@traceable(name="llm.generate_json", run_type="llm")
def generate_json(system_prompt: str, user_prompt: str, model: str | None = None) -> Any:
    """Structured extraction/scoring calls that must return parseable JSON."""
    model = model or _default_model()
    if active_provider() == "openai":
        text = _openai_generate(system_prompt, user_prompt, model=model, json_mode=True)
    else:
        text = _gemini_generate(system_prompt, user_prompt, model=model, json_mode=True)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(
            f"Warning: LLM did not return valid JSON, dropping this turn's output. "
            f"First 200 chars: {text[:200]!r}"
        )
        return {}
