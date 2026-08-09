from __future__ import annotations

import streamlit as st

from agent.graph import build_graph
from agent.retriever import get_university_display_name
from ui.components.bottom_nav import render_bottom_nav
from ui.components.chat_area import (
    invoke_graph,
    render_chat_messages,
    render_error_banner,
    render_welcome,
    render_welcome_suggestions,
)
from ui.components.notifications import render_notifications
from ui.components.profile_form import render_profile_form
from ui.components.ranking_cards import render_ranking_cards
from ui.components.sidebar import render_sidebar
from ui.components.university_selector import render_university_selector
from ui.components.voice_input import render_voice_input
from ui.session import init_session_state, record_user_message, start_new_chat, switch_conversation
from ui.theme import inject_theme


@st.cache_resource
def get_graph():
    return build_graph()


st.set_page_config(page_title="UniMate AI", page_icon="🎓", layout="wide")
inject_theme()
init_session_state(get_graph)


def _handle_user_message(text: str) -> None:
    text = text.strip()
    if not text:
        return
    st.session_state.state.setdefault("messages", [])
    st.session_state.state["messages"].append({"role": "user", "content": text})
    record_user_message(text)
    invoke_graph(st.empty(), get_graph)
    st.rerun()


def _on_new_chat() -> None:
    start_new_chat(get_graph)
    st.rerun()


def _on_switch_chat(thread_id: str) -> None:
    switch_conversation(thread_id, get_graph)
    st.rerun()


render_sidebar(
    get_graph=get_graph,
    on_new_chat=_on_new_chat,
    on_switch_chat=_on_switch_chat,
)

view = st.session_state.get("current_view", "chat")

# ── Top bar (shared) ──
top_left, top_mid, top_right = st.columns([4, 2, 1])
with top_left:
    if view == "chat":
        selected = st.session_state.get("selected_university", "all")
        badge = ""
        if selected and selected != "all":
            badge = f"<span class='um-university-badge'>{get_university_display_name(selected)}</span>"
        st.markdown(
            f"""
            <div class="um-topbar" style="border:none;padding-bottom:0;margin-bottom:0.5rem;">
                <div>
                    <div class="um-topbar-title">UniMate AI{badge}</div>
                    <div class="um-topbar-sub">Ask about admissions, programs, fees, scholarships, and deadlines.</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
with top_mid:
    if view == "chat":
        render_university_selector(compact=True)
with top_right:
    voice_on = st.toggle("Voice", value=st.session_state.get("voice_enabled", True), key="voice_toggle")
    st.session_state.voice_enabled = voice_on

render_error_banner()

if st.session_state.get("voice_error"):
    st.warning(st.session_state.voice_error)

# ── View routing ──
if view == "profile":
    render_profile_form(get_graph)
elif view == "notifications":
    render_notifications()
else:
    messages = st.session_state.state.get("messages", [])
    is_empty = not messages

    if is_empty:
        render_welcome()
        render_welcome_suggestions(on_select=_handle_user_message)
        messages = [
            {
                "role": "assistant",
                "content": (
                    "Hi! I'm UniMate. Tell me what program or city you're interested in, "
                    "and I'll help you find the best university options in Karachi."
                ),
            }
        ]

    render_chat_messages(messages)

    recommendations = st.session_state.state.get("recommendations") or []
    if recommendations and st.session_state.state.get("current_phase") in ("presenting", "refining"):
        render_ranking_cards(recommendations)

    voice_text = render_voice_input()
    if voice_text:
        _handle_user_message(voice_text)

    user_input = st.chat_input("Ask anything about admissions...", key="chat_input")
    if user_input:
        _handle_user_message(user_input)

render_bottom_nav()
