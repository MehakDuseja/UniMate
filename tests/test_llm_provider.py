"""LLM provider selection from env keys."""
from __future__ import annotations

import importlib


def _reload_config(monkeypatch, **env):
    monkeypatch.setenv("UNIMATE_SKIP_DOTENV", "1")
    for key in (
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "LLM_PROVIDER",
        "OPENAI_CHAT_MODEL",
        "GEMINI_CHAT_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    import src.config as config

    return importlib.reload(config)


def test_prefers_openai_when_openai_key_present(monkeypatch):
    config = _reload_config(
        monkeypatch,
        OPENAI_API_KEY="sk-test",
        GEMINI_API_KEY="gem-test",
    )
    assert config.LLM_PROVIDER == "openai"
    assert config.CHAT_MODEL == config.OPENAI_CHAT_MODEL


def test_uses_gemini_when_only_gemini_key(monkeypatch):
    config = _reload_config(monkeypatch, GEMINI_API_KEY="gem-test")
    assert config.LLM_PROVIDER == "gemini"
    assert config.CHAT_MODEL == config.GEMINI_CHAT_MODEL


def test_llm_provider_override(monkeypatch):
    config = _reload_config(
        monkeypatch,
        OPENAI_API_KEY="sk-test",
        GEMINI_API_KEY="gem-test",
        LLM_PROVIDER="gemini",
    )
    assert config.LLM_PROVIDER == "gemini"


def test_google_api_key_alias(monkeypatch):
    config = _reload_config(monkeypatch, GOOGLE_API_KEY="gem-test")
    assert config.LLM_PROVIDER == "gemini"
    assert config.GEMINI_API_KEY == "gem-test"
