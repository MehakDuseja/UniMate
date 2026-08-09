"""University scope selector — drives hard retrieval filtering."""

from __future__ import annotations

import streamlit as st

from agent.retriever import ALL_UNIVERSITIES, get_university_options
from ui.session import sync_university_selection


def render_university_selector(*, compact: bool = False) -> str:
    options = get_university_options()
    labels = [opt["label"] for opt in options]
    ids = [opt["id"] for opt in options]

    current = st.session_state.get("selected_university", ALL_UNIVERSITIES)
    if current not in ids:
        current = ALL_UNIVERSITIES

    label = "University scope" if not compact else "University"
    selected_label = st.selectbox(
        label,
        labels,
        index=ids.index(current),
        help="When a specific university is selected, answers use only that university's data.",
        label_visibility="collapsed" if compact else "visible",
    )
    selected_id = ids[labels.index(selected_label)]
    if selected_id != st.session_state.get("selected_university"):
        sync_university_selection(selected_id)
    return selected_id
