"""Streamlit session initialization and graph checkpoint helpers."""

from __future__ import annotations

import uuid
from typing import Any, Callable

import streamlit as st

from agent.state import initial_state
from services import conversation_service
from services import profile_service


def init_session_state(get_graph: Callable[[], Any]) -> None:
    graph = get_graph()

    if "student_session_id" not in st.session_state:
        url_sid = st.query_params.get("sid")
        st.session_state.student_session_id = url_sid or str(uuid.uuid4())
        st.query_params["sid"] = st.session_state.student_session_id

    st.session_state.student_id = profile_service.ensure_student(st.session_state.student_session_id)

    if "thread_id" not in st.session_state:
        url_thread_id = st.query_params.get("tid")
        st.session_state.thread_id = url_thread_id or str(uuid.uuid4())
        st.query_params["tid"] = st.session_state.thread_id

    if "active_chat_id" not in st.session_state:
        st.session_state.active_chat_id = st.session_state.thread_id

    if not conversation_service.get_conversation(st.session_state.thread_id):
        conversation_service.upsert_conversation(
            thread_id=st.session_state.thread_id,
            student_id=st.session_state.student_id,
            title="New Chat",
            university_filter=st.session_state.get("selected_university", "all"),
        )

    if "state" not in st.session_state:
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        checkpoint = graph.get_state(config)
        state = checkpoint.values if checkpoint and checkpoint.values else initial_state()
        state["messages"] = conversation_service.get_chat_messages(st.session_state.thread_id)
        st.session_state.state = state

    defaults = {
        "error": None,
        "audio_cache": {},
        "pending_voice": "",
        "current_view": "chat",
        "show_profile": False,
        "show_notifications": False,
        "voice_enabled": True,
        "voice_error": None,
        "selected_university": "all",
        "rename_thread_id": None,
        "saved_profile_meta": None,
        "notification_prefs": {},
        "_profile_draft": None,
        "active_chat_id": st.session_state.thread_id,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    saved = profile_service.get_saved_profile(st.session_state.student_id)
    st.session_state.saved_profile_meta = saved
    if saved and saved.get("is_saved") and not st.session_state.state.get("student_profile"):
        st.session_state.state["student_profile"] = saved["profile"]

    selected = st.session_state.get("selected_university", "all")
    if st.session_state.state.get("selected_university") != selected:
        st.session_state.state["selected_university"] = selected

    conversation_service.upsert_conversation(
        thread_id=st.session_state.thread_id,
        student_id=st.session_state.student_id,
        university_filter=selected,
    )


def sync_university_selection(selected: str) -> None:
    st.session_state.selected_university = selected
    st.session_state.state["selected_university"] = selected
    conversation_service.upsert_conversation(
        thread_id=st.session_state.thread_id,
        student_id=st.session_state.student_id,
        university_filter=selected,
    )


def checkpoint_profile(profile: dict[str, Any], get_graph: Callable[[], Any]) -> None:
    """Persist profile edits to LangGraph checkpoint immediately."""
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    graph = get_graph()
    graph.update_state(config, {"student_profile": profile})
    st.session_state.state = graph.get_state(config).values


def save_profile_to_db(profile: dict[str, Any]) -> dict[str, Any]:
    meta = profile_service.save_profile(st.session_state.student_id, profile, mark_saved=True)
    st.session_state.saved_profile_meta = profile_service.get_saved_profile(st.session_state.student_id)
    return meta


def delete_saved_profile() -> None:
    profile_service.delete_profile(st.session_state.student_id)
    st.session_state.saved_profile_meta = None


def start_new_chat(get_graph: Callable[[], Any]) -> None:
    """Activate a fresh, empty conversation without changing existing chats."""
    selected = st.session_state.get("selected_university", "all")
    new_thread_id = conversation_service.create_chat(
        st.session_state.student_id,
        "New Chat",
        university_filter=selected,
    )
    st.session_state.thread_id = new_thread_id
    st.session_state.active_chat_id = new_thread_id
    st.query_params["tid"] = new_thread_id

    fresh = initial_state()
    fresh["selected_university"] = selected
    saved = st.session_state.get("saved_profile_meta")
    if saved and saved.get("is_saved"):
        fresh["student_profile"] = dict(saved["profile"])
    fresh["messages"] = []
    st.session_state.state = fresh

    st.session_state.composer_prompt = ""
    st.session_state.pending_composer_text = ""
    st.session_state.transcribed_recording = None
    st.session_state.error = None
    st.session_state.audio_cache = {}
    st.session_state.pending_voice = ""
    st.session_state.voice_error = None
    conversation_service.upsert_conversation(
        thread_id=new_thread_id,
        student_id=st.session_state.student_id,
        title="New Chat",
        university_filter=selected,
    )


def switch_conversation(thread_id: str, get_graph: Callable[[], Any]) -> None:
    st.session_state.thread_id = thread_id
    st.session_state.active_chat_id = thread_id
    st.query_params["tid"] = thread_id

    base_state = initial_state()
    base_state["messages"] = conversation_service.get_chat_messages(thread_id)
    conv = conversation_service.get_conversation(thread_id)
    if conv:
        st.session_state.selected_university = conv.get("university_filter") or "all"
        base_state["selected_university"] = st.session_state.selected_university
    st.session_state.state = base_state
    st.session_state.error = None
    st.session_state.audio_cache = {}
    st.session_state.pending_voice = ""


def record_user_message(message: str) -> None:
    chat_id = st.session_state.get("active_chat_id") or st.session_state.get("thread_id")
    if not chat_id:
        return
    conversation_service.append_message(chat_id, "user", message)
    conversation_service.touch_conversation(chat_id, first_user_message=message)
