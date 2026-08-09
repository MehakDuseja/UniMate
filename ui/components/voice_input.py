"""Speech-to-text input via microphone."""

from __future__ import annotations

import streamlit as st
from streamlit_mic_recorder import mic_recorder

from agent.voice import transcribe_audio


def render_voice_input() -> str | None:
    """Returns transcribed text when the user finishes a recording."""
    if not st.session_state.get("voice_enabled", True):
        return None

    st.markdown(
        "<div class='um-glass-input-hint'>Tap the mic to speak, or type below</div>",
        unsafe_allow_html=True,
    )
    audio = mic_recorder(
        start_prompt="🎤 Speak",
        stop_prompt="⏹ Stop",
        just_once=False,
        use_container_width=True,
        key="um_mic_recorder",
    )
    if not audio:
        return None

    try:
        text = transcribe_audio(audio["bytes"])
        if not text:
            st.session_state.voice_error = "No speech detected. Please try again."
            return None
        st.session_state.voice_error = None
        return text
    except Exception as exc:
        st.session_state.voice_error = f"Speech recognition failed: {exc}"
        return None
