"""University notification opt-in UI, backed by the real subscription store
and the change-detector's update feed (see notifications/subscription_service.py
and notifications/change_detector.py) - a background job checks official
university sites three times a day and emails subscribers on real changes."""

from __future__ import annotations

import streamlit as st

from agent.retriever import get_university_options
from notifications.subscription_service import (
    get_subscriptions_for_email,
    remove_subscription,
    upsert_subscription,
)


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

    profile = st.session_state.state.get("student_profile") or {}
    default_email = st.session_state.get("notif_email", profile.get("email", ""))
    email = st.text_input("Notification email", value=default_email, placeholder="you@example.com", key="notif_email")

    saved_ids = get_subscriptions_for_email(email) if email else []

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
    new_subs: set[str] = set()
    cols = st.columns(2)
    for i, opt in enumerate(options):
        with cols[i % 2]:
            checked = st.checkbox(opt["label"], value=opt["id"] in saved_ids, key=f"notif_{opt['id']}")
            if checked:
                new_subs.add(opt["id"])

    if st.button("Save notification preferences", type="primary", use_container_width=True):
        if not email.strip():
            st.warning("Add an email address to receive notifications.")
        elif not new_subs:
            st.info("Select at least one university to subscribe.")
        else:
            for uid in set(saved_ids) - new_subs:
                remove_subscription(email, uid)
            for uid in new_subs:
                upsert_subscription(email, uid)
            st.success(f"Subscribed to {len(new_subs)} universities — updates will be emailed to {email.strip()}.")

    updates = st.session_state.get("notification_updates", [])
    if updates:
        st.markdown(
            """
            <div class="um-glass-panel secondary" style="margin-top:1rem;">
                <div class="um-section-header">
                    <span class="material-symbols-outlined">campaign</span>
                    Recent verified updates
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for update in updates:
            st.markdown(
                f"<div class='um-notification'><div class='um-notification-title'>{update['title']}</div>"
                f"<div class='um-notification-detail'>{update['detail']}</div></div>",
                unsafe_allow_html=True,
            )

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
