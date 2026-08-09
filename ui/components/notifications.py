"""University notification opt-in UI (scheduler integration pending)."""

from __future__ import annotations

import streamlit as st

from agent.retriever import get_university_options


def render_notifications() -> None:
    st.markdown(
        """
        <div class="um-topbar" style="border:none;padding-bottom:0;">
            <div>
                <div class="um-topbar-title">Notifications</div>
                <div class="um-topbar-sub">Get emailed when official admission pages change — checked 3× daily with deduplicated updates only.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "notification_prefs" not in st.session_state:
        st.session_state.notification_prefs = {}

    email = st.text_input(
        "Notification email",
        value=st.session_state.notification_prefs.get("email", ""),
        placeholder="you@example.com",
    )

    st.markdown(
        """
        <div class="um-glass-panel">
            <div class="um-section-header">
                <span class="material-symbols-outlined">notifications_active</span>
                University subscriptions
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    options = [o for o in get_university_options() if o["id"] != "all"]
    subscribed = st.session_state.notification_prefs.get("universities", set())

    new_subs: set[str] = set()
    cols = st.columns(2)
    for i, opt in enumerate(options):
        with cols[i % 2]:
            checked = st.checkbox(
                opt["label"],
                value=opt["id"] in subscribed,
                key=f"notif_{opt['id']}",
            )
            if checked:
                new_subs.add(opt["id"])

    if st.button("Save notification preferences", type="primary", use_container_width=True):
        st.session_state.notification_prefs = {
            "email": email.strip(),
            "universities": new_subs,
        }
        if email.strip() and new_subs:
            st.success(f"Subscribed to {len(new_subs)} universities — updates will be emailed to {email.strip()}.")
        elif not email.strip():
            st.warning("Add an email address to receive notifications.")
        else:
            st.info("Select at least one university to subscribe.")

    st.markdown(
        """
        <div class="um-glass-panel tertiary" style="margin-top:1rem;">
            <div class="um-section-header">
                <span class="material-symbols-outlined">schedule</span>
                How it works
            </div>
            <p style="color:var(--on-surface-variant);font-size:0.9rem;line-height:1.6;margin:0;">
                A background job scrapes official university sites three times per day.
                Only meaningful changes (deadlines, fees, eligibility) trigger an email —
                duplicate or cosmetic updates are filtered out automatically.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
