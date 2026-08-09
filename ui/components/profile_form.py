"""Profile builder page — Stitch design with glass sections."""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from agent.nodes import _merge_profile_updates, _sanitize_profile_updates
from agent.retriever import get_candidate_universities
from services.profile_service import calculate_completeness, profile_status_label
from services.ranking_service import rank_candidates
from ui.components.ranking_cards import render_ranking_bento
from ui.session import checkpoint_profile, delete_saved_profile, save_profile_to_db


_DEGREE_OPTIONS = ["", "Bachelor", "Master", "PhD"]
_PRIORITY_OPTIONS = ["", "fees", "distance", "both"]
_EDUCATION_OPTIONS = ["", "Intermediate", "A-Levels", "FSc Pre-Engineering", "FSc Pre-Medical", "ICS", "O-Levels"]


def _progress_ring_html(completeness: int, status: str) -> str:
    offset = max(0, min(100, 100 - completeness))
    return f"""
    <div class="um-progress-wrap">
        <div class="um-progress-ring">
            <svg viewBox="0 0 36 36">
                <circle class="um-progress-bg" cx="18" cy="18" r="16"></circle>
                <circle class="um-progress-fill" cx="18" cy="18" r="16"
                    stroke-dasharray="100" stroke-dashoffset="{offset}"></circle>
            </svg>
            <div class="um-progress-label">{completeness}%</div>
        </div>
        <div>
            <div class="um-progress-caption">Profile Status</div>
            <div class="um-progress-status">{status}</div>
        </div>
    </div>
    """


def _profile_matches(profile: dict[str, Any]) -> list[dict[str, Any]]:
    if calculate_completeness(profile) < 30:
        return []
    try:
        uni_filter = st.session_state.get("selected_university", "all")
        filter_arg = uni_filter if uni_filter != "all" else None
        candidates = get_candidate_universities(profile, university_filter=filter_arg)
        if not candidates:
            return []
        return rank_candidates(
            profile,
            candidates,
            priority_focus=profile.get("priority_focus"),
            limit=5,
        )
    except Exception:
        return []


def _read_draft(prof: dict[str, Any]) -> dict[str, Any]:
    budget_val = prof.get("budget_pkr_per_semester")
    try:
        budget_default = int(budget_val) if budget_val else 200000
    except (TypeError, ValueError):
        budget_default = 200000

    raw = {
        "name": st.session_state.get("pf_name", prof.get("name", "")),
        "email": st.session_state.get("pf_email", prof.get("email", "")),
        "field_of_study": st.session_state.get("pf_field", prof.get("field_of_study", "")),
        "degree_level": st.session_state.get("pf_degree", prof.get("degree_level", "")),
        "current_education_level": st.session_state.get("pf_edu", prof.get("current_education_level", "")),
        "academic_percentage": st.session_state.get("pf_academic", str(prof.get("academic_percentage") or "")),
        "budget_pkr_per_semester": st.session_state.get("pf_budget", min(max(budget_default, 50000), 500000)),
        "preferred_province": st.session_state.get("pf_province", prof.get("preferred_province", "")),
        "preferred_cities": [
            c.strip()
            for c in st.session_state.get("pf_cities", ", ".join(prof.get("preferred_cities") or [])).split(",")
            if c.strip()
        ],
        "student_city": st.session_state.get("pf_city", prof.get("student_city", "")),
        "student_area": st.session_state.get("pf_area", prof.get("student_area", "")),
        "hostel_required": st.session_state.get("pf_hostel", bool(prof.get("hostel_required", False))),
        "scholarship_required": st.session_state.get("pf_scholar", bool(prof.get("scholarship_required", False))),
        "priority_focus": st.session_state.get("pf_priority", prof.get("priority_focus", "")),
        "career_goals": st.session_state.get("pf_goals", prof.get("career_goals", "")),
    }
    return _sanitize_profile_updates(raw)


def render_profile_form(get_graph: Callable[[], Any]) -> None:
    prof = dict(st.session_state.state.get("student_profile") or {})
    saved_meta = st.session_state.get("saved_profile_meta")

    header_col, progress_col = st.columns([3, 1])
    draft = _read_draft(prof)
    completeness = calculate_completeness(draft)
    status = profile_status_label(completeness)

    with header_col:
        st.markdown(
            """
            <div class="um-topbar" style="border:none;padding-bottom:0;margin-bottom:0;">
                <div>
                    <div class="um-topbar-title">Student Profile Builder</div>
                    <div class="um-topbar-sub">Complete your profile to get personalized university recommendations and admission insights.</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with progress_col:
        st.markdown(_progress_ring_html(completeness, status), unsafe_allow_html=True)

    st.markdown(
        """
        <div class="um-glass-panel">
            <div class="um-section-header">
                <span class="material-symbols-outlined">badge</span>
                Personal Information
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        st.text_input("Full name", value=prof.get("name", ""), key="pf_name")
        st.text_input("Your city", value=prof.get("student_city", ""), key="pf_city")
    with c2:
        st.text_input("Email", value=prof.get("email", ""), key="pf_email")
        st.text_input("Area / neighborhood", value=prof.get("student_area", ""), key="pf_area")

    st.markdown(
        """
        <div class="um-glass-panel secondary">
            <div class="um-section-header">
                <span class="material-symbols-outlined">school</span>
                Academic Details
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    ac1, ac2, ac3 = st.columns(3)
    with ac1:
        st.selectbox("Degree level", _DEGREE_OPTIONS, index=_DEGREE_OPTIONS.index(prof.get("degree_level", "")) if prof.get("degree_level") in _DEGREE_OPTIONS else 0, key="pf_degree")
    with ac2:
        st.selectbox("Qualification", _EDUCATION_OPTIONS, index=_EDUCATION_OPTIONS.index(prof.get("current_education_level", "")) if prof.get("current_education_level") in _EDUCATION_OPTIONS else 0, key="pf_edu")
    with ac3:
        st.text_input("CGPA / Percentage", value=str(prof.get("academic_percentage") or ""), placeholder="e.g. 85% or 3 A*", key="pf_academic")
    st.text_input("Program interest", value=prof.get("field_of_study", ""), key="pf_field")

    st.markdown(
        """
        <div class="um-glass-panel tertiary">
            <div class="um-section-header">
                <span class="material-symbols-outlined">tune</span>
                Preferences
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    pref1, pref2 = st.columns(2)
    with pref1:
        st.text_input("Preferred province", value=prof.get("preferred_province", ""), key="pf_province")
        budget_val = prof.get("budget_pkr_per_semester")
        try:
            budget_default = int(budget_val) if budget_val else 200000
        except (TypeError, ValueError):
            budget_default = 200000
        st.slider("Annual budget (PKR/semester)", 50000, 500000, min(max(budget_default, 50000), 500000), 25000, key="pf_budget")
    with pref2:
        st.text_input("Preferred cities (comma-separated)", value=", ".join(prof.get("preferred_cities") or []), key="pf_cities")
        st.selectbox("Priority", _PRIORITY_OPTIONS, index=_PRIORITY_OPTIONS.index(prof.get("priority_focus", "")) if prof.get("priority_focus") in _PRIORITY_OPTIONS else 0, key="pf_priority")

    t1, t2 = st.columns(2)
    with t1:
        st.toggle("Financial aid / scholarships", value=bool(prof.get("scholarship_required", False)), key="pf_scholar")
    with t2:
        st.toggle("Hostel accommodation", value=bool(prof.get("hostel_required", False)), key="pf_hostel")
    st.text_area("Career goals", value=prof.get("career_goals", ""), height=80, key="pf_goals")

    draft = _read_draft(prof)
    matches = _profile_matches(draft)
    if matches:
        st.markdown(
            """
            <div style="display:flex;align-items:center;justify-content:space-between;margin:1.5rem 0 0.75rem;">
                <div style="display:flex;align-items:center;gap:0.5rem;font-weight:600;font-size:1.05rem;">
                    <span class="material-symbols-outlined" style="color:var(--primary);font-size:1.25rem;">stars</span>
                    Best Matches
                </div>
                <span style="font-family:Geist,monospace;font-size:0.68rem;font-weight:600;letter-spacing:0.05em;text-transform:uppercase;color:var(--outline);">Based on Profile</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_ranking_bento(matches, program_hint=draft.get("field_of_study"))

    st.markdown("<div class='um-save-bar'>", unsafe_allow_html=True)
    save_col, del_col = st.columns([4, 1])
    with save_col:
        if st.button("Save Profile ✓", type="primary", use_container_width=True, key="profile_save_sticky"):
            merged = _merge_profile_updates(prof, draft)
            checkpoint_profile(merged, get_graph)
            meta = save_profile_to_db(merged)
            st.success(f"Profile saved ({meta['completeness_pct']}% complete)")
            st.session_state.current_view = "chat"
            st.session_state.show_profile = False
            st.rerun()
    with del_col:
        if st.button("Delete", key="profile_delete"):
            delete_saved_profile()
            st.session_state.state["student_profile"] = {}
            st.warning("Saved profile deleted")
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    if saved_meta and saved_meta.get("is_saved"):
        st.caption(f"Last saved: {saved_meta.get('saved_at') or saved_meta.get('updated_at') or 'recently'}")
