"""Streamlit chat frontend for the UniMate LangGraph agent.

Streamlit runs plain Python, so this talks to the agent in-process (via
graph.invoke()) rather than through a separate API layer. Run with:
    streamlit run streamlit_app.py
"""
from __future__ import annotations

import streamlit as st

from agent.graph import build_graph
from agent.state import initial_state

st.set_page_config(page_title="UniMate", page_icon="🎓", layout="centered")


@st.cache_resource
def get_graph():
    return build_graph()


def _role_and_content(msg) -> tuple[str, str]:
    """Messages start as plain dicts but LangGraph's add_messages reducer
    normalizes them into BaseMessage objects after the first graph.invoke(),
    so both shapes need handling."""
    if isinstance(msg, dict):
        return msg.get("role", ""), msg.get("content", "")
    msg_type = getattr(msg, "type", "")
    role = "user" if msg_type == "human" else "assistant"
    return role, getattr(msg, "content", "")


def _invoke_graph() -> None:
    """Runs the graph on the current state. Errors (e.g. Gemini's free-tier
    rate limit) are surfaced via session_state.error rather than raised, so
    the already-appended user message isn't lost and a retry just re-invokes."""
    try:
        st.session_state.state = get_graph().invoke(st.session_state.state)
        st.session_state.error = None
    except Exception as e:
        st.session_state.error = str(e)


if "state" not in st.session_state:
    st.session_state.state = initial_state()
if "error" not in st.session_state:
    st.session_state.error = None

st.title("🎓 UniMate")
st.caption("Find the right Pakistani university for you - powered by LangGraph + Gemini.")

with st.sidebar:
    st.subheader("Your profile so far")
    profile = st.session_state.state.get("student_profile") or {}
    if profile:
        for key, value in profile.items():
            st.markdown(f"**{key.replace('_', ' ').title()}:** {value}")
    else:
        st.caption("Nothing yet - just start chatting!")

    st.divider()
    if st.button("Start over", use_container_width=True):
        st.session_state.state = initial_state()
        st.session_state.error = None
        st.rerun()

if not st.session_state.state["messages"]:
    with st.chat_message("assistant"):
        st.markdown(
            "Hi! I'm UniMate. Tell me a bit about what you'd like to study, and I'll help you "
            "find the best-fit university in Pakistan for you."
        )

for msg in st.session_state.state["messages"]:
    role, content = _role_and_content(msg)
    with st.chat_message(role):
        st.markdown(content)

if st.session_state.error:
    st.error(f"Something went wrong talking to Gemini: {st.session_state.error}")
    if st.button("Retry"):
        with st.spinner("Retrying..."):
            _invoke_graph()
        st.rerun()

user_input = st.chat_input("Type your message...")
if user_input:
    st.session_state.state["messages"].append({"role": "user", "content": user_input})
    with st.spinner("Thinking..."):
        _invoke_graph()
    st.rerun()
