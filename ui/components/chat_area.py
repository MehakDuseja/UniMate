"""Chat message rendering and graph invocation."""

from __future__ import annotations

import html
from typing import Any, Callable

import streamlit as st

from services import conversation_service

SUGGESTIONS = [
    "What are the admission requirements?",
    "Compare universities for CS",
    "Scholarship options in Karachi",
    "Application deadlines this year",
]


def role_and_content(msg) -> tuple[str, str]:
    if isinstance(msg, dict):
        role = msg.get("role", "")
        if role in ("human", "user"):
            role = "user"
        elif role in ("ai", "assistant"):
            role = "assistant"
        return role, msg.get("content", "")
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
    """Streams the graph run live into status_placeholder (real "thinking"
    text as the model generates it, not a static spinner), then persists
    any new assistant replies to the chat's DB history so they survive a
    conversation switch or reload."""
    chat_id = st.session_state.get("active_chat_id") or st.session_state.get("thread_id")
    try:
        config = {"configurable": {"thread_id": chat_id}}
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
                status_placeholder.markdown(render_trace_html(steps, live_text, live_answer))
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
            status_placeholder.markdown(render_trace_html(steps, live_text, live_answer))

        final_state = graph.get_state(config).values
        st.session_state.state = final_state

        if chat_id:
            existing = conversation_service.get_chat_messages(chat_id)
            for message in final_state.get("messages", []):
                role, content = role_and_content(message)
                content = (content or "").strip()
                if role == "assistant" and content:
                    if not any(item.get("role") == "assistant" and item.get("content") == content for item in existing):
                        conversation_service.append_message(chat_id, "assistant", content)
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
    for i, (col, suggestion) in enumerate(zip(cols, SUGGESTIONS)):
        with col:
            with st.container(key=f"suggest_wrap_{i}"):
                if st.button(suggestion, key=f"suggest_{suggestion[:20]}", use_container_width=True):
                    if on_select:
                        on_select(suggestion)


def render_chat_messages(messages: list[Any]) -> None:
    for msg in messages:
        role, content = role_and_content(msg)
        css_class = "um-chat-bubble-user" if role == "user" else "um-chat-bubble-ai"
        formatted = html.escape(content).replace("\n", "<br>")
        st.markdown(f"<div class='{css_class}'>{formatted}</div>", unsafe_allow_html=True)


def render_error_banner() -> None:
    if st.session_state.error:
        st.markdown(
            f"<div class='um-error-banner'>{html.escape(st.session_state.error)}</div>",
            unsafe_allow_html=True,
        )
