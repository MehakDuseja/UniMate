"""Chat message rendering and graph invocation."""

from __future__ import annotations

import html
from typing import Any, Callable

import streamlit as st

from agent.voice import synthesize_speech

SUGGESTIONS = [
    "What are the admission requirements?",
    "Compare universities for CS",
    "Scholarship options in Karachi",
    "Application deadlines this year",
]


def role_and_content(msg) -> tuple[str, str]:
    if isinstance(msg, dict):
        return msg.get("role", ""), msg.get("content", "")
    msg_type = getattr(msg, "type", "")
    role = "user" if msg_type == "human" else "assistant"
    return role, getattr(msg, "content", "")


def render_trace_html(steps: list[str], live_text: str, live_answer: str) -> str:
    parts = [html.escape(s) for s in steps]
    if live_text:
        parts.append(html.escape(live_text) + "▌")
    elif live_answer:
        parts.append(html.escape(live_answer) + "▌")
    return " *Thinking:* " + " ".join(parts)


def invoke_graph(status_placeholder, get_graph: Callable[[], Any]) -> None:
    try:
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        graph = get_graph()
        steps: list[str] = []
        live_kind: str | None = None
        live_text = ""
        live_answer = ""

        def finalize_live():
            nonlocal live_kind, live_text
            if live_kind and live_text:
                steps.append(live_text)
            live_kind, live_text = None, ""

        for mode, payload in graph.stream(
            st.session_state.state,
            config=config,
            stream_mode=["updates", "custom"],
        ):
            if mode == "updates":
                finalize_live()
                status_placeholder.markdown(
                    render_trace_html(steps, live_text, live_answer)
                )
                continue
            kind = payload.get("type")
            text = payload.get("text", "")
            if kind == "token":
                finalize_live()
                live_answer += text
            elif kind == "thought":
                if live_kind != "thought":
                    finalize_live()
                    live_kind = "thought"
                live_text += text
            else:
                finalize_live()
                steps.append(text)
            status_placeholder.markdown(
                render_trace_html(steps, live_text, live_answer)
            )

        st.session_state.state = graph.get_state(config).values
        st.session_state.error = None
    except Exception as exc:
        st.session_state.error = str(exc)
    finally:
        status_placeholder.empty()


def render_welcome() -> None:
    st.markdown(
        """
        <div class="um-welcome-icon"><span>🎓</span></div>
        <div class="um-welcome-title">How can I help you?</div>
        """,
        unsafe_allow_html=True,
    )


def render_welcome_suggestions(on_select: Callable[[str], None] | None = None) -> None:
    cols = st.columns(len(SUGGESTIONS))
    for col, suggestion in zip(cols, SUGGESTIONS):
        with col:
            st.markdown("<div class='um-suggestion-btn'>", unsafe_allow_html=True)
            if st.button(suggestion, key=f"suggest_{suggestion[:20]}", use_container_width=True):
                if on_select:
                    on_select(suggestion)
            st.markdown("</div>", unsafe_allow_html=True)


def render_chat_messages(messages: list[Any]) -> None:
    voice_enabled = st.session_state.get("voice_enabled", True)
    st.markdown("<div class='um-chat-wrap'>", unsafe_allow_html=True)
    for i, msg in enumerate(messages):
        role, content = role_and_content(msg)
        css_class = "um-chat-bubble-user" if role in ("user", "human") else "um-chat-bubble-ai"
        formatted = html.escape(content).replace("\n", "<br>")
        st.markdown(f"<div class='{css_class}'>{formatted}</div>", unsafe_allow_html=True)
        if role in ("assistant", "ai") and voice_enabled:
            if i in st.session_state.audio_cache:
                st.audio(st.session_state.audio_cache[i], format="audio/mp3")
            elif st.button("🔊 Listen", key=f"play_{i}"):
                try:
                    audio_bytes = synthesize_speech(content)
                    st.session_state.audio_cache[i] = audio_bytes
                    st.audio(audio_bytes, format="audio/mp3")
                except Exception as exc:
                    st.warning(f"Audio unavailable: {exc}")
    st.markdown("</div>", unsafe_allow_html=True)


def render_error_banner() -> None:
    if st.session_state.error:
        st.markdown(
            f"<div class='um-error-banner'>{html.escape(st.session_state.error)}</div>",
            unsafe_allow_html=True,
        )
