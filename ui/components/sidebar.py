"""Sidebar navigation, chat history, and profile summary."""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from agent.retriever import get_university_display_name
from services import conversation_service
from services.profile_service import calculate_completeness, profile_status_label


def _user_initials(profile: dict) -> str:
    name = (profile.get("name") or "Student").strip()
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper() if name else "ST"


def _nav_button(label: str, view: str, *, active: bool = False) -> None:
    css_class = "um-nav-active" if active else ""
    st.markdown(f"<div class='{css_class}'>", unsafe_allow_html=True)
    if st.button(label, key=f"nav_{view}", use_container_width=True, type="primary" if active else "secondary"):
        st.session_state.current_view = view
        st.session_state.show_profile = view == "profile"
        st.session_state.show_notifications = view == "notifications"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_sidebar(
    *,
    get_graph: Callable[[], Any],
    on_new_chat: Callable[[], None],
    on_switch_chat: Callable[[str], None],
) -> None:
    profile = st.session_state.state.get("student_profile") or {}
    saved_meta = st.session_state.get("saved_profile_meta")
    completeness = (
        saved_meta["completeness_pct"]
        if saved_meta
        else calculate_completeness(profile)
    )
    status = profile_status_label(completeness)
    display_name = profile.get("name") or "Student"
    view = st.session_state.get("current_view", "chat")

    with st.sidebar:
        st.markdown(
            f"""
            <div class="um-sidebar-user">
                <div class="um-sidebar-avatar">{_user_initials(profile)}</div>
                <div>
                    <div class="um-sidebar-name">{display_name}</div>
                    <div class="um-sidebar-meta">Admissions Prep 2026</div>
                    <div class="um-sidebar-badge">{completeness}% · {status}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("＋ New Chat", use_container_width=True, type="primary", key="sidebar_new_chat"):
            st.session_state.current_view = "chat"
            st.session_state.show_profile = False
            st.session_state.show_notifications = False
            on_new_chat()

        st.markdown("<div class='um-nav-label'>Navigation</div>", unsafe_allow_html=True)
        _nav_button("💬  Chat", "chat", active=view == "chat")
        _nav_button("👤  Profile", "profile", active=view == "profile")
        _nav_button("🔔  Notifications", "notifications", active=view == "notifications")

        st.markdown("<div class='um-nav-label'>Recent Chats</div>", unsafe_allow_html=True)
        conversations = conversation_service.list_conversations(st.session_state.student_id)
        active_id = st.session_state.thread_id

        if not conversations:
            st.caption("No saved chats yet.")
        else:
            for conv in conversations[:12]:
                cid = conv["id"]
                title = conv.get("title") or "New Chat"
                is_active = cid == active_id
                css = "um-conv-active" if is_active else "um-conv-item"
                st.markdown(f"<div class='{css}'>", unsafe_allow_html=True)
                label = f"{'▸ ' if is_active else ''}{title[:28]}{'…' if len(title) > 28 else ''}"
                if st.button(label, key=f"conv_{cid}", use_container_width=True):
                    if cid != active_id:
                        st.session_state.current_view = "chat"
                        st.session_state.show_profile = False
                        st.session_state.show_notifications = False
                        on_switch_chat(cid)
                st.markdown("</div>", unsafe_allow_html=True)

                if is_active:
                    with st.expander("Chat actions", expanded=False):
                        new_title = st.text_input("Rename", value=title, key=f"rename_{cid}")
                        rc1, rc2 = st.columns(2)
                        with rc1:
                            if st.button("Save name", key=f"save_name_{cid}"):
                                conversation_service.rename_conversation(cid, new_title)
                                st.rerun()
                        with rc2:
                            if st.button("Delete", key=f"del_{cid}"):
                                conversation_service.delete_conversation(cid)
                                if cid == active_id:
                                    on_new_chat()
                                else:
                                    st.rerun()

        st.divider()
        st.markdown(
            f"<div class='um-profile-pill'>{completeness}% · {status}</div>",
            unsafe_allow_html=True,
        )
        visible = {k: v for k, v in profile.items() if v not in (None, "", [], {})}
        if visible:
            for key, value in list(visible.items())[:4]:
                st.markdown(f"**{key.replace('_', ' ').title()}:** {value}")
            if len(visible) > 4:
                st.caption(f"+ {len(visible) - 4} more fields")
        else:
            st.caption("Chat to build your profile, or open Profile to edit.")

        if saved_meta and saved_meta.get("is_saved"):
            st.success("Profile saved", icon="✅")

        selected = st.session_state.get("selected_university", "all")
        if selected and selected != "all":
            st.caption(f"Focused: {get_university_display_name(selected)}")
