"""Mobile bottom navigation bar."""

from __future__ import annotations

import streamlit as st


def render_bottom_nav() -> None:
    view = st.session_state.get("current_view", "chat")
    items = [
        ("chat", "Chat"),
        ("profile", "Profile"),
        ("notifications", "Alerts"),
    ]

    st.markdown("<div class='um-bottom-nav-wrap'>", unsafe_allow_html=True)
    nav_cols = st.columns(len(items))
    for col, (vid, label) in zip(nav_cols, items):
        with col:
            if st.button(
                label,
                key=f"bottom_nav_{vid}",
                use_container_width=True,
                type="primary" if view == vid else "secondary",
            ):
                st.session_state.current_view = vid
                st.session_state.show_profile = vid == "profile"
                st.session_state.show_notifications = vid == "notifications"
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
