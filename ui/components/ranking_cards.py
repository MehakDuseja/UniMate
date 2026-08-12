"""Explainable ranking cards for recommendations."""

from __future__ import annotations

import html
from typing import Any, Optional

import streamlit as st


def _uni_initials(name: str) -> str:
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:3].upper() if name else "UNI"


def render_ranking_bento(
    recommendations: list[dict[str, Any]],
    *,
    program_hint: Optional[str] = None,
) -> None:
    if not recommendations:
        return

    cards = []
    for i, rec in enumerate(recommendations[:5]):
        score = rec.get("total_score", rec.get("match_score", 0))
        name = html.escape(rec.get("university_name") or rec.get("university_id", "Unknown"))
        border = "primary" if i == 0 else "secondary"
        match_class = "primary" if i == 0 else "secondary"
        program = html.escape(program_hint or rec.get("field_of_study") or "See programs")
        initials = html.escape(_uni_initials(rec.get("university_name") or ""))
        cards.append(
            f"""
            <div class="um-rank-bento {border}">
                <div class="um-rank-bento-header">
                    <div class="um-rank-logo">{initials}</div>
                    <div class="um-rank-match">{score}% Match</div>
                </div>
                <div class="um-rank-uni-name">{name}</div>
                <div class="um-rank-program">{program}</div>
            </div>
            """
        )

    st.markdown(
        f"<div class='um-rank-scroll'>{''.join(cards)}</div>",
        unsafe_allow_html=True,
    )


def render_ranking_cards(recommendations: list[dict[str, Any]]) -> None:
    if not recommendations:
        return

    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:0.5rem;font-weight:600;font-size:1.05rem;margin:1rem 0 0.75rem;">
            <span class="material-symbols-outlined" style="color:var(--primary);font-size:1.25rem;">stars</span>
            Recommended Universities
        </div>
        """,
        unsafe_allow_html=True,
    )

    for i, rec in enumerate(recommendations[:5], start=1):
        score = rec.get("total_score", rec.get("match_score", 0))
        name = html.escape(rec.get("university_name") or rec.get("university_id", "Unknown"))
        border = "primary" if i == 1 else "secondary"
        factors_html = []
        for factor in rec.get("factors") or []:
            icon = "✓" if factor.get("status") == "pass" else "⚠"
            label = html.escape(factor.get("label") or factor.get("criterion", ""))
            detail = html.escape(factor.get("detail", ""))
            factors_html.append(f"<li>{icon} <strong>{label}</strong> — {detail}</li>")

        st.markdown(
            f"""
            <div class="um-rank-card um-rank-card-{border}">
                <div class="um-rank-card-header">
                    <span class="um-rank-position">#{i}</span>
                    <span class="um-rank-name">{name}</span>
                    <span class="um-rank-score">{score}% Match</span>
                </div>
                <ul class="um-rank-factors">{''.join(factors_html)}</ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
