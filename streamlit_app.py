"""UniMate's Streamlit chat workspace.  RAG and persistence remain in their services."""

from __future__ import annotations

from hashlib import sha256
from typing import Any

import streamlit as st

from agent.graph import build_graph
from agent.retriever import ALL_UNIVERSITIES, get_university_options
from agent.voice import synthesize_speech, transcribe_audio
from notifications.subscription_service import (
    get_subscriptions_for_email,
    remove_subscription,
    upsert_subscription,
)
from services import conversation_service, profile_service
from services.profile_service import calculate_completeness
from ui.session import (
    checkpoint_profile,
    init_session_state,
    record_user_message,
    start_new_chat,
    switch_conversation,
    sync_university_selection,
)


@st.cache_resource
def get_graph():
    return build_graph()


def message_parts(message: Any) -> tuple[str, str]:
    if isinstance(message, dict):
        role = message.get("role", "assistant")
        content = message.get("content", "")
        if role in ("human", "user"):
            role = "user"
        elif role in ("ai", "assistant"):
            role = "assistant"
        return role, content

    role = getattr(message, "type", "")
    if role in ("human", "user"):
        return "user", getattr(message, "content", "")
    if role in ("ai", "assistant"):
        return "assistant", getattr(message, "content", "")
    return "assistant", getattr(message, "content", "")


def strip_sources(content: str) -> str:
    """RAG citations remain in the model output but are intentionally not student-visible."""
    return content.partition("**Sources:**")[0].rstrip()


def run_chat(prompt: str) -> None:
    prompt = prompt.strip()
    if not prompt:
        return

    chat_id = st.session_state.get("active_chat_id") or st.session_state.get("thread_id")
    if not chat_id:
        chat_id = conversation_service.create_chat(
            st.session_state.student_id,
            "New Chat",
            university_filter=st.session_state.get("selected_university", "all"),
        )
        st.session_state.active_chat_id = chat_id
        st.session_state.thread_id = chat_id

    current_messages = st.session_state.state.setdefault("messages", [])
    if not any(message_parts(msg)[0] == "user" and message_parts(msg)[1] == prompt for msg in current_messages):
        current_messages.append({"role": "user", "content": prompt})

    saved_messages = conversation_service.get_chat_messages(chat_id)
    if not any(item.get("content") == prompt for item in saved_messages if item.get("role") == "user"):
        record_user_message(prompt)

    try:
        graph = get_graph()
        config = {"configurable": {"thread_id": chat_id}}
        with st.status("UniMate is checking official university information…", expanded=False):
            for _mode, _payload in graph.stream(st.session_state.state, config=config, stream_mode=["updates", "custom"]):
                pass
        final_state = graph.get_state(config).values
        st.session_state.state = final_state

        for message in final_state.get("messages", []):
            role, content = message_parts(message)
            content = (content or "").strip()
            if role == "assistant" and content:
                existing = conversation_service.get_chat_messages(chat_id)
                if not any(item.get("role") == "assistant" and item.get("content") == content for item in existing):
                    conversation_service.append_message(chat_id, "assistant", content)
        st.session_state.error = None
    except Exception as exc:
        st.session_state.error = str(exc)
    st.rerun()


def delete_chat_from_sidebar(chat_id: str) -> None:
    if conversation_service.delete_chat(chat_id):
        if st.session_state.get("active_chat_id") == chat_id:
            start_new_chat(get_graph)
    st.rerun()


def render_sidebar() -> None:
    with st.sidebar:
        st.title("Chats")
        if st.button("New chat"):
            start_new_chat(get_graph)
            st.rerun()

        chat_search = st.text_input("Search chats", placeholder="Search chats", key="chat_search")
        conversations = conversation_service.list_conversations(st.session_state.student_id)
        if chat_search:
            query = chat_search.casefold().strip()
            conversations = [chat for chat in conversations if query in (chat.get("title") or "").casefold()]

        if not conversations:
            st.caption("No previous chats yet.")
        else:
            for conversation in conversations:
                active = conversation["id"] == st.session_state.active_chat_id
                title = conversation.get("title") or "New chat"
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.button(
                        ("● " if active else "") + title,
                        key=f"chat_{conversation['id']}",
                        use_container_width=True,
                        on_click=open_previous_chat,
                        args=(conversation["id"],),
                    )
                with col2:
                    st.button(
                        "X",
                        key=f"delete_chat_{conversation['id']}",
                        use_container_width=True,
                        on_click=delete_chat_from_sidebar,
                        args=(conversation["id"],),
                    )


def render_notifications() -> None:
    unread = st.session_state.get("notifications_unread", 0)
    label = f"🔔 {unread}" if unread else "🔔"
    with st.popover(label, help="Notifications", use_container_width=False):
        st.subheader("Notifications")
        updates = st.session_state.get("notification_updates", [])
        if updates:
            for update in updates:
                st.markdown(f"<div class='um-notification'><div class='um-notification-title'>{update['title']}</div><div class='um-notification-detail'>{update['detail']}</div></div>", unsafe_allow_html=True)
        else:
            st.caption("No new verified university updates. New official-site changes will appear here.")
        if st.button("Mark all as read", use_container_width=True):
            st.session_state.notifications_unread = 0
            st.rerun()
        if st.button("View all notifications", use_container_width=True):
            st.toast("No additional verified notifications.")
        st.button("Notification settings", key="open_notification_settings", use_container_width=True, on_click=open_notification_settings)


def save_profile_from_form() -> None:
    profile = dict(st.session_state.state.get("student_profile") or {})
    preferred_cities = [
        city.strip()
        for city in st.session_state.profile_preferred_cities.split(",")
        if city.strip()
    ]
    profile.update({
        "name": st.session_state.profile_name.strip(), "email": st.session_state.profile_email.strip(),
        "current_education_level": st.session_state.profile_education,
        "degree_level": st.session_state.profile_degree_level,
        "academic_percentage": float(st.session_state.profile_academic_percentage) if st.session_state.profile_academic_percentage else None,
        "field_of_study": st.session_state.profile_program.strip(),
        "target_universities": st.session_state.profile_universities,
        "budget_pkr_per_semester": int(st.session_state.profile_budget) if st.session_state.profile_budget else None,
        "scholarship_required": st.session_state.profile_scholarship,
        "hostel_required": st.session_state.profile_hostel,
        "student_city": st.session_state.profile_city.strip(),
        "student_area": st.session_state.profile_area.strip(),
        "preferred_province": st.session_state.profile_province,
        "preferred_cities": preferred_cities,
        "career_goals": st.session_state.profile_career_goals.strip(),
        "priority_focus": st.session_state.profile_priority_focus,
    })
    checkpoint_profile(profile, get_graph)
    profile_service.save_profile(st.session_state.student_id, profile, mark_saved=True)
    st.session_state.saved_profile_meta = profile_service.get_saved_profile(st.session_state.student_id)
    st.session_state.edit_profile = False
    st.toast("Profile saved")


def toggle_edit_profile() -> None:
    st.session_state.edit_profile = not st.session_state.edit_profile


def open_edit_profile() -> None:
    st.session_state.edit_profile = True


def open_profile_drawer() -> None:
    st.session_state.profile_drawer_open = True


def close_profile_drawer() -> None:
    st.session_state.profile_drawer_open = False
    st.session_state.edit_profile = False


def toggle_sidebar() -> None:
    st.session_state.sidebar_open = not st.session_state.get("sidebar_open", True)


def open_previous_chat(thread_id: str) -> None:
    """Switch threads before the chat UI is rendered for this rerun."""
    switch_conversation(thread_id, get_graph)
    st.session_state.sidebar_open = True
    st.session_state.state["messages"] = conversation_service.get_chat_messages(thread_id)


def open_notification_settings() -> None:
    st.session_state.notification_settings_open = True


def close_notification_settings() -> None:
    st.session_state.notification_settings_open = False


def render_profile_panel() -> None:
    if "edit_profile" not in st.session_state:
        st.session_state.edit_profile = False
    if not st.session_state.get("profile_drawer_open", False):
        return
    profile = st.session_state.state.get("student_profile") or {}
    with st.container(border=True):
        st.markdown("<div class='um-drawer-marker'></div><div class='um-profile'>", unsafe_allow_html=True)
        close_col, _ = st.columns([1, 5])
        with close_col:
            st.button("✕", key="close_profile_drawer", help="Close profile", on_click=close_profile_drawer)
        st.subheader("Student profile")
        st.markdown(f"<div class='um-profile-name'>{profile.get('name') or 'Your profile'}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='um-profile-meta'>{profile.get('current_education_level') or 'Add your education'}</div>", unsafe_allow_html=True)
        st.button(
            "Edit profile" if not st.session_state.edit_profile else "Cancel",
            key="edit_profile_btn",
            use_container_width=True,
            on_click=toggle_edit_profile,
        )
        if st.session_state.get("edit_profile"):
            with st.form("profile_editor"):
                st.text_input("Name", value=profile.get("name", ""), key="profile_name")
                st.text_input("Email", value=profile.get("email", ""), key="profile_email")
                education_options = ["", "A-Levels", "FSc", "ICS", "Intermediate", "Bachelor's", "Other"]
                st.selectbox("Education", education_options, key="profile_education", index=education_options.index(profile.get("current_education_level")) if profile.get("current_education_level") in education_options else 0)
                degree_options = ["", "Bachelor", "Master", "PhD"]
                st.selectbox("Degree level", degree_options, key="profile_degree_level", index=degree_options.index(profile.get("degree_level")) if profile.get("degree_level") in degree_options else 0)
                st.number_input("Academic percentage", min_value=0.0, max_value=100.0, value=float(profile.get("academic_percentage") or 0.0), step=0.1, key="profile_academic_percentage", help="Enter 0 if you have not received a percentage yet.")
                st.text_input("Preferred program", value=profile.get("field_of_study", ""), key="profile_program")
                opts = get_university_options()[1:]
                labels = [o["label"] for o in opts]
                existing = profile.get("target_universities") or []
                st.multiselect("Preferred universities", labels, default=[x for x in existing if x in labels], key="profile_universities")
                st.number_input("Budget per semester (PKR)", min_value=0, value=int(profile.get("budget_pkr_per_semester") or 0), step=25000, key="profile_budget")
                st.checkbox("Scholarship needed", value=bool(profile.get("scholarship_required")), key="profile_scholarship")
                st.checkbox("Hostel needed", value=bool(profile.get("hostel_required")), key="profile_hostel")
                st.divider()
                st.caption("Location and admission preferences")
                st.text_input("Your city", value=profile.get("student_city", ""), key="profile_city", placeholder="e.g. Karachi")
                st.text_input("Your area / neighbourhood", value=profile.get("student_area", ""), key="profile_area", placeholder="e.g. Gulshan-e-Iqbal")
                province_options = ["", "Sindh", "Punjab", "Khyber Pakhtunkhwa", "Balochistan", "Islamabad Capital Territory", "Other"]
                st.selectbox("Preferred province", province_options, key="profile_province", index=province_options.index(profile.get("preferred_province")) if profile.get("preferred_province") in province_options else 0)
                st.text_input("Preferred cities", value=", ".join(profile.get("preferred_cities") or []), key="profile_preferred_cities", placeholder="e.g. Karachi, Islamabad")
                st.text_area("Career goals", value=profile.get("career_goals", ""), key="profile_career_goals", placeholder="What do you want to do after graduation?")
                priority_options = ["both", "fees", "distance"]
                st.selectbox("Main priority", priority_options, key="profile_priority_focus", index=priority_options.index(profile.get("priority_focus")) if profile.get("priority_focus") in priority_options else 0, format_func=lambda item: {"both": "Fees and distance", "fees": "Lower fees", "distance": "Closer location"}[item])
                st.form_submit_button("Save profile", type="primary", use_container_width=True, on_click=save_profile_from_form)
        else:
            location = ", ".join(filter(None, [profile.get("student_area"), profile.get("student_city")]))
            completion = calculate_completeness(profile)
            st.caption("PROFILE COMPLETION")
            st.progress(completion, text=f"{completion}% complete")
            fields = [("Education", profile.get("current_education_level")), ("Interested programs", profile.get("field_of_study")), ("Preferred universities", ", ".join(profile.get("target_universities") or [])), ("Location", location), ("Budget", f"PKR {int(profile['budget_pkr_per_semester']):,}/semester" if profile.get("budget_pkr_per_semester") else None), ("Preferences", ", ".join(x for x, yes in [("Scholarship", profile.get("scholarship_required")), ("Hostel", profile.get("hostel_required"))] if yes))]
            for title, value in fields:
                st.markdown(f"<div class='um-profile-item'><small>{title}</small>{value or 'Not added'}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


def render_notification_settings() -> None:
    if not st.session_state.get("notification_settings_open"):
        return
    with st.container(border=True):
        st.markdown("<div class='um-settings-drawer-marker'></div>", unsafe_allow_html=True)
        close_col, _ = st.columns([1, 5])
        with close_col:
            st.button("✕", key="close_notification_settings", help="Close notification settings", on_click=close_notification_settings)
        st.subheader("Notification settings")
        profile = st.session_state.state.get("student_profile") or {}
        email = st.text_input("Email for updates", value=profile.get("email", ""), key="notif_email")
        options = get_university_options()[1:]
        ids, labels = [x["id"] for x in options], [x["label"] for x in options]
        saved_ids = get_subscriptions_for_email(email) if email else []
        selected_labels = st.multiselect("Universities", labels, default=[label for uid, label in zip(ids, labels) if uid in saved_ids])
        st.multiselect("Alert types", ["Admission deadlines", "Merit lists", "Entry tests", "Applications", "Fee deadlines", "Document requirements", "Important announcements"], default=["Admission deadlines", "Important announcements"])
        st.selectbox("Email frequency", ["As updates happen", "Daily digest", "Weekly digest"])
        if st.button("Save notification settings", type="primary"):
            if not email:
                st.warning("Add an email address to save subscriptions.")
            else:
                selected_ids = {ids[labels.index(label)] for label in selected_labels}
                for uid in set(saved_ids) - selected_ids: remove_subscription(email, uid)
                for uid in selected_ids: upsert_subscription(email, uid)
                st.success("Notification settings saved.")


def render_chat() -> None:
    options = get_university_options()
    ids, labels = [x["id"] for x in options], [x["label"] for x in options]
    current = st.session_state.get("selected_university", ALL_UNIVERSITIES)
    if current not in ids:
        current = ALL_UNIVERSITIES

    header_col, profile_col, notify_col = st.columns([3, 1, 1])
    with header_col:
        st.title("UniMate AI")
    with profile_col:
        if st.button("Profile"):
            open_profile_drawer()
    with notify_col:
        if st.button("Notifications"):
            st.session_state.notification_settings_open = True

    choice = st.selectbox("University", labels, index=ids.index(current))
    selected_id = ids[labels.index(choice)]
    if selected_id != current:
        sync_university_selection(selected_id)
        st.rerun()

    messages = st.session_state.state.get("messages", [])
    if not messages:
        st.write("Ask about admissions, programs, fees, scholarships, and deadlines.")
        for text in ["Admission requirements", "Programs", "Fees and scholarships", "Entry tests"]:
            if st.button(text):
                run_chat(text)

    for idx, message in enumerate(messages):
        role, content = message_parts(message)
        with st.chat_message("user" if role == "user" else "assistant"):
            st.markdown(strip_sources(content))

    if st.session_state.get("error"):
        st.error(st.session_state.error)

    prompt = st.chat_input("Ask UniMate about admissions…")
    if prompt:
        run_chat(prompt)

    render_profile_panel()
    render_notification_settings()


st.set_page_config(
    page_title="UniMate",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_session_state(get_graph)
render_sidebar()
render_chat()
