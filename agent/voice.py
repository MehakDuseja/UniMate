"""Fish Audio wrapper for voice chat: text-to-speech and speech-to-text.

Mirrors agent/llm.py's thin-client style (lazy singleton, raise clearly if
the API key is missing) - kept as its own module rather than folded into
agent/llm.py since Fish Audio is a separate provider/account from Gemini,
not part of the chat model itself.
"""
from __future__ import annotations

from typing import Optional

from fish_audio_sdk import ASRRequest, Session, TTSRequest

from src.config import FISH_API_KEY

_session: Optional[Session] = None

# Not one of the fish_audio_sdk.schemas.Backends Literal values in this SDK
# version's type stub (that's just a type hint, not runtime-enforced - the
# string is forwarded to the API as-is), but the free-tier model to use here.
TTS_MODEL = "s2.1-pro-free"


def _get_session() -> Session:
    global _session
    if _session is None:
        if not FISH_API_KEY:
            raise RuntimeError("No Fish Audio API key found. Set FISH_API_KEY in .env.")
        _session = Session(FISH_API_KEY)
    return _session


def synthesize_speech(text: str) -> bytes:
    """Text -> complete MP3 bytes. Session.tts() streams chunks over the
    wire, but callers here (Streamlit's st.audio) just want one finished
    clip to hand to a <audio> element, not a live stream, so the chunks are
    concatenated before returning."""
    session = _get_session()
    return b"".join(session.tts(TTSRequest(text=text), backend=TTS_MODEL))


def transcribe_audio(audio_bytes: bytes) -> str:
    """Audio bytes -> transcribed text. Returns "" for silence/no speech
    rather than raising - callers should treat that like an empty
    st.chat_input (nothing to send), not an error."""
    session = _get_session()
    response = session.asr(ASRRequest(audio=audio_bytes, language="en"))
    return (response.text or "").strip()
