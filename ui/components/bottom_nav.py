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

    # A plain st.markdown("<div>") / st.markdown("</div>") pair does NOT
    # actually wrap the widgets rendered between them - each st.markdown call
    # is its own isolated element, so the open/close tags never nest around
    # the buttons in the real DOM and any CSS scoped to that div silently
    # never matches. st.container(key=...) is the real mechanism: it emits a
    # genuine parent element carrying a stable `st-key-<key>` class (see
    # ui/theme.py's `.st-key-bottom_nav` rule) that its children truly live
    # inside.
    with st.container(key="bottom_nav"):
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
                    st.rerun()
