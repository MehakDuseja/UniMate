"""Academic Ethereal design tokens — ported from the Stitch design reference
(see .design_ref/DESIGN.md and .design_ref/screen.png for the source spec)."""

from __future__ import annotations

import streamlit as st


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;600&family=Inter:wght@400;600;700&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0');

        :root {
            --primary: #3525cd;
            --primary-container: #4f46e5;
            --secondary: #712ae2;
            --secondary-container: #8a4cfc;
            --tertiary: #003fac;
            --surface: #faf8ff;
            --surface-container: #eaedff;
            --surface-container-low: #f2f3ff;
            --surface-container-high: #e2e7ff;
            --on-surface: #131b2e;
            --on-surface-variant: #464555;
            --outline: #777587;
            --outline-variant: #c7c4d8;
            --error: #ba1a1a;
            --sidebar-width: 280px;
        }

        html, body, [class*="css"] {
            font-family: 'Inter', 'Segoe UI', sans-serif;
        }

        .stApp {
            background: radial-gradient(circle at 20% 10%, #f2f0ff 0%, #faf8ff 40%, #ffffff 100%);
        }

        #MainMenu, footer, header { visibility: hidden; height: 0; }

        /* ── Sidebar ── */
        [data-testid="stSidebar"] {
            background: rgba(250, 248, 255, 0.92) !important;
            backdrop-filter: blur(24px);
            border-right: 1px solid rgba(255, 255, 255, 0.45);
            min-width: var(--sidebar-width) !important;
            max-width: var(--sidebar-width) !important;
            width: var(--sidebar-width) !important;
        }

        [data-testid="stSidebar"] > div:first-child {
            width: var(--sidebar-width) !important;
        }

        [data-testid="stSidebar"] .block-container {
            padding: 1.25rem 1rem 2rem 1rem;
        }

        [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {
            display: none;
        }

        /* ── Main area ── */
        section.main .block-container {
            padding-top: 1.5rem;
            padding-bottom: 7rem !important;
            max-width: 768px !important;
        }

        /* ── Brand / typography ── */
        .um-brand {
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--primary);
            letter-spacing: -0.02em;
            line-height: 1.2;
        }

        .um-brand-sub {
            font-size: 0.78rem;
            color: var(--on-surface-variant);
            margin-top: 0.15rem;
        }

        .um-sidebar-user {
            display: flex;
            align-items: center;
            gap: 0.85rem;
            padding: 0.35rem 0.25rem 1.1rem 0.25rem;
            margin-bottom: 0.5rem;
        }

        .um-sidebar-avatar {
            width: 48px;
            height: 48px;
            border-radius: 999px;
            background: linear-gradient(135deg, var(--primary-container), var(--secondary));
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 700;
            font-size: 1.1rem;
            flex-shrink: 0;
            border: 2px solid rgba(255,255,255,0.7);
            box-shadow: 0 2px 8px rgba(53,37,205,0.15);
        }

        .um-sidebar-name {
            font-weight: 600;
            color: var(--primary);
            font-size: 0.95rem;
            line-height: 1.2;
        }

        .um-sidebar-meta {
            font-size: 0.78rem;
            color: var(--on-surface-variant);
        }

        .um-sidebar-badge {
            font-family: 'Geist', monospace;
            font-size: 0.65rem;
            font-weight: 700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            color: var(--secondary);
            margin-top: 0.15rem;
        }

        .um-nav-label {
            font-family: 'Geist', monospace;
            font-size: 0.68rem;
            font-weight: 600;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            color: var(--outline);
            margin: 0.75rem 0 0.35rem 0.5rem;
        }

        /* ── Top bar ── */
        .um-topbar {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            padding: 0.5rem 0 1.25rem 0;
            margin-bottom: 0.5rem;
            gap: 1rem;
        }

        .um-topbar-title {
            font-size: 1.65rem;
            font-weight: 700;
            color: var(--on-surface);
            letter-spacing: -0.02em;
            line-height: 1.2;
        }

        .um-topbar-sub {
            font-size: 0.95rem;
            color: var(--on-surface-variant);
            margin-top: 0.35rem;
            line-height: 1.5;
            max-width: 36rem;
        }

        .um-university-badge {
            display: inline-block;
            background: rgba(113, 42, 226, 0.1);
            color: var(--secondary);
            border-radius: 999px;
            padding: 0.15rem 0.6rem;
            font-size: 0.72rem;
            font-weight: 600;
            margin-left: 0.45rem;
            vertical-align: middle;
        }

        /* ── Chat ── */
        .um-chat-bubble-user {
            background: var(--primary);
            color: white;
            padding: 12px 18px;
            border-radius: 18px 18px 4px 18px;
            max-width: 85%;
            margin-left: auto;
            word-wrap: break-word;
            box-shadow: 0 4px 14px rgba(53, 37, 205, 0.18);
            font-size: 0.95rem;
            line-height: 1.5;
        }

        .um-chat-bubble-ai {
            background: rgba(234, 237, 255, 0.85);
            backdrop-filter: blur(12px);
            color: var(--on-surface);
            padding: 12px 18px;
            border-radius: 18px 18px 18px 4px;
            max-width: 85%;
            word-wrap: break-word;
            border: 1px solid rgba(255, 255, 255, 0.6);
            font-size: 0.95rem;
            line-height: 1.5;
        }

        .um-welcome-icon {
            text-align: center;
            padding: 2rem 0 0.5rem;
        }

        .um-welcome-icon span {
            display: inline-flex;
            width: 56px;
            height: 56px;
            border-radius: 999px;
            background: linear-gradient(135deg, rgba(79,70,229,0.15), rgba(113,42,226,0.15));
            align-items: center;
            justify-content: center;
            font-size: 1.75rem;
        }

        .um-welcome-title {
            text-align: center;
            font-weight: 700;
            color: var(--primary);
            font-size: 1.25rem;
            margin-top: 0.5rem;
        }

        .um-suggestion-row {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            justify-content: center;
            margin: 1rem 0 1.5rem;
        }

        /* ── Glass panels (profile sections) ── */
        .um-glass-panel {
            background: rgba(255, 255, 255, 0.72);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.55);
            border-radius: 20px;
            padding: 1.25rem 1.35rem;
            margin-bottom: 1rem;
            position: relative;
            overflow: hidden;
            box-shadow: 0 2px 12px rgba(53, 37, 205, 0.04);
        }

        .um-glass-panel::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 4px;
            background: rgba(53, 37, 205, 0.25);
        }

        .um-glass-panel.secondary::before { background: rgba(113, 42, 226, 0.25); }
        .um-glass-panel.tertiary::before { background: rgba(0, 63, 172, 0.25); }

        .um-section-header {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.85rem;
            font-weight: 600;
            font-size: 1.05rem;
            color: var(--on-surface);
        }

        .um-section-header .material-symbols-outlined {
            font-size: 1.25rem;
            color: var(--primary);
        }

        .um-glass-panel.secondary .um-section-header .material-symbols-outlined { color: var(--secondary); }
        .um-glass-panel.tertiary .um-section-header .material-symbols-outlined { color: var(--tertiary); }

        .um-field-label {
            font-family: 'Geist', monospace;
            font-size: 0.68rem;
            font-weight: 600;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            color: var(--outline);
            margin-bottom: 0.15rem;
        }

        /* ── Progress ring ── */
        .um-progress-wrap {
            display: flex;
            align-items: center;
            gap: 1rem;
            background: rgba(242, 243, 255, 0.9);
            border: 1px solid rgba(255, 255, 255, 0.75);
            border-radius: 999px;
            padding: 0.65rem 1.1rem;
            width: fit-content;
            margin: 0.75rem 0 1.25rem 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.03);
        }

        .um-progress-ring { position: relative; width: 48px; height: 48px; }
        .um-progress-ring svg { width: 48px; height: 48px; transform: rotate(-90deg); }
        .um-progress-bg { fill: none; stroke: #e2e7ff; stroke-width: 3; }
        .um-progress-fill { fill: none; stroke: var(--primary); stroke-width: 3; stroke-linecap: round; }
        .um-progress-label {
            position: absolute; inset: 0;
            display: flex; align-items: center; justify-content: center;
            font-family: 'Geist', monospace;
            font-size: 0.68rem; font-weight: 700; color: var(--primary);
        }
        .um-progress-caption {
            font-family: 'Geist', monospace;
            font-size: 0.68rem; color: var(--on-surface-variant);
            text-transform: uppercase; letter-spacing: 0.05em;
        }
        .um-progress-status { font-size: 0.88rem; font-weight: 600; color: var(--primary); }

        /* ── Ranking cards ── */
        .um-rank-scroll {
            display: flex;
            gap: 1rem;
            overflow-x: auto;
            padding-bottom: 0.75rem;
            scroll-snap-type: x mandatory;
            -ms-overflow-style: none;
            scrollbar-width: none;
        }
        .um-rank-scroll::-webkit-scrollbar { display: none; }

        .um-rank-bento {
            flex: 0 0 260px;
            scroll-snap-align: start;
            background: rgba(255, 255, 255, 0.72);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.6);
            border-radius: 16px;
            padding: 1rem;
            box-shadow: 0 2px 12px rgba(53, 37, 205, 0.05);
        }

        .um-rank-bento.primary { border-top: 3px solid var(--primary); }
        .um-rank-bento.secondary { border-top: 3px solid var(--secondary); }

        .um-rank-bento-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 0.65rem;
        }

        .um-rank-logo {
            width: 48px; height: 48px;
            background: white;
            border-radius: 10px;
            border: 1px solid var(--surface-container-high);
            display: flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 0.75rem; color: var(--primary);
        }

        .um-rank-match {
            font-family: 'Geist', monospace;
            font-size: 0.65rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            padding: 0.2rem 0.55rem;
            border-radius: 999px;
            background: rgba(53, 37, 205, 0.1);
            color: var(--primary);
        }

        .um-rank-bento.secondary .um-rank-match {
            background: rgba(113, 42, 226, 0.1);
            color: var(--secondary);
        }

        .um-rank-uni-name { font-weight: 600; font-size: 0.95rem; }
        .um-rank-program { font-size: 0.82rem; color: var(--on-surface-variant); }

        .um-rank-card {
            background: rgba(255, 255, 255, 0.72);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.6);
            border-radius: 16px;
            padding: 1rem 1.1rem;
            margin-bottom: 0.75rem;
        }
        .um-rank-card-primary { border-top: 3px solid var(--primary); }
        .um-rank-card-secondary { border-top: 3px solid var(--secondary); }
        .um-rank-card-header { display: flex; align-items: center; gap: 0.65rem; margin-bottom: 0.5rem; flex-wrap: wrap; }
        .um-rank-position { font-weight: 700; color: var(--primary); }
        .um-rank-name { font-weight: 600; flex: 1; }
        .um-rank-score {
            background: rgba(53, 37, 205, 0.08);
            color: var(--primary);
            border-radius: 999px;
            padding: 0.15rem 0.6rem;
            font-size: 0.78rem;
            font-weight: 700;
        }
        .um-rank-factors { margin: 0; padding-left: 1.1rem; color: var(--on-surface-variant); font-size: 0.88rem; }
        .um-rank-factors li { margin-bottom: 0.25rem; }

        /* ── Profile pill / errors ── */
        .um-profile-pill {
            display: inline-block;
            background: rgba(79, 70, 229, 0.1);
            color: var(--primary);
            border-radius: 999px;
            padding: 0.25rem 0.75rem;
            font-size: 0.75rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }

        .um-error-banner {
            background: #ffdad6;
            color: #93000a;
            border-radius: 12px;
            padding: 0.75rem 1rem;
            margin-bottom: 1rem;
            font-size: 0.9rem;
        }

        /* ── Sticky save button ── */
        .st-key-profile_save_bar {
            position: fixed;
            bottom: 1.5rem;
            left: calc(var(--sidebar-width) + 50%);
            transform: translateX(-50%);
            width: min(720px, calc(100vw - var(--sidebar-width) - 3rem));
            z-index: 999;
            pointer-events: none;
        }

        .st-key-profile_save_bar .stButton > button {
            pointer-events: auto;
            width: 100%;
            background: linear-gradient(90deg, var(--primary), var(--secondary)) !important;
            color: white !important;
            border: 1px solid rgba(255,255,255,0.25) !important;
            border-radius: 12px !important;
            padding: 0.85rem 1.5rem !important;
            font-size: 1.05rem !important;
            font-weight: 600 !important;
            box-shadow: 0 10px 30px rgba(79, 70, 229, 0.3) !important;
            transition: transform 0.15s ease;
        }

        .st-key-profile_save_bar .stButton > button:hover {
            transform: scale(1.01);
            border-color: rgba(255,255,255,0.4) !important;
        }

        /* ── Mobile bottom nav ── */
        .st-key-bottom_nav {
            display: none;
        }

        @media (max-width: 768px) {
            [data-testid="stSidebar"] { display: none !important; }
            section.main .block-container { max-width: 100% !important; padding-bottom: 9rem !important; }
            .st-key-profile_save_bar {
                left: 50%;
                width: calc(100vw - 2rem);
            }
            .st-key-bottom_nav {
                display: block;
                position: fixed;
                bottom: 0; left: 0; right: 0;
                z-index: 998;
                background: rgba(250, 248, 255, 0.92);
                backdrop-filter: blur(24px);
                border-top: 1px solid rgba(255,255,255,0.35);
                padding: 0.5rem 0.75rem 1rem;
                box-shadow: 0 -10px 40px rgba(0,0,0,0.05);
            }
            .st-key-bottom_nav .stButton > button {
                border-radius: 12px !important;
                font-size: 0.78rem !important;
            }
        }

        /* ── Streamlit widget overrides ── */
        .stChatInput textarea {
            border-radius: 999px !important;
            border: 1px solid var(--outline-variant) !important;
            background: rgba(255, 255, 255, 0.82) !important;
            backdrop-filter: blur(12px);
            box-shadow: 0 8px 32px rgba(0,0,0,0.06) !important;
        }

        .stChatInput textarea:focus {
            border-color: var(--secondary) !important;
            box-shadow: 0 0 0 2px rgba(113, 42, 226, 0.15), 0 8px 32px rgba(0,0,0,0.06) !important;
        }

        div[data-testid="stSelectbox"] label,
        div[data-testid="stTextInput"] label,
        div[data-testid="stTextArea"] label,
        div[data-testid="stSlider"] label,
        div[data-testid="stCheckbox"] label,
        div[data-testid="stMultiSelect"] label {
            font-family: 'Geist', monospace !important;
            font-size: 0.68rem !important;
            font-weight: 600 !important;
            letter-spacing: 0.05em !important;
            text-transform: uppercase !important;
            color: var(--outline) !important;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea {
            background: transparent !important;
            border: none !important;
            border-bottom: 1px solid var(--outline-variant) !important;
            border-radius: 0 !important;
            padding-left: 0 !important;
        }

        div[data-testid="stTextInput"] input:focus,
        div[data-testid="stTextArea"] textarea:focus {
            border-bottom-color: var(--primary) !important;
            background: rgba(255,255,255,0.5) !important;
            border-radius: 8px !important;
            padding: 8px 12px !important;
            box-shadow: none !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 255, 255, 0.65);
            backdrop-filter: blur(16px);
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.55);
        }

        [data-testid="stSidebar"] .stButton > button {
            border-radius: 12px;
            border: none;
            background: transparent;
            color: var(--on-surface-variant);
            text-align: left;
            justify-content: flex-start;
            font-weight: 500;
            padding: 0.55rem 0.85rem;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            background: rgba(218, 226, 253, 0.5);
            color: var(--on-surface);
        }

        [data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background: rgba(79, 70, 229, 0.12) !important;
            color: var(--primary) !important;
            font-weight: 600;
        }

        [class*="st-key-suggest_wrap_"] .stButton > button {
            background: rgba(53, 37, 205, 0.06) !important;
            border: 1px solid rgba(53, 37, 205, 0.2) !important;
            border-radius: 999px !important;
            color: var(--primary) !important;
            font-size: 0.82rem !important;
            padding: 0.35rem 0.85rem !important;
            box-shadow: none !important;
        }

        [class*="st-key-suggest_wrap_"] .stButton > button:hover {
            background: rgba(53, 37, 205, 0.12) !important;
            border-color: var(--primary) !important;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )
