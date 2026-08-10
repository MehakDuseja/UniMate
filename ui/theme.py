"""Minimal styling for the current Streamlit-only UniMate interface."""

from __future__ import annotations

import streamlit as st


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
        :root { --ink:#ffffff; --muted:#b7b7bd; --line:#29292f; --red:#e32636; --soft:#151519; }
        html, body, [class*="css"] { font-family:'DM Sans', sans-serif; }
        .stApp { background:#080809; color:var(--ink); }
        .stApp, .stApp p, .stApp span, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp li { color:var(--ink); }
        #MainMenu, footer, header { visibility:hidden; height:0; }
        [data-testid="stSidebar"] { background:#101011; border-right:1px solid var(--line); }
        [data-testid="stSidebar"] > div:first-child { padding-top:1.15rem; }
        [data-testid="stSidebar"]:has(.um-sidebar-closed) { display:none; }
        [data-testid="stSidebar"] .stButton button { text-align:left; border:0; background:transparent; color:#fff; border-radius:8px; }
        [data-testid="stSidebar"] .stButton button:hover { background:#241114; color:#fff; }
        .stButton button, [data-testid="stPopover"] button { color:#e32636; border-color:#663038; background:#151116; }
        .stButton button:hover, [data-testid="stPopover"] button:hover { color:#fff; border-color:#e32636; background:#341217; }
        .stButton button[kind="primary"] { color:#fff; background:#e32636; border-color:#e32636; }
        section.main .block-container { max-width:1540px; padding:1.2rem 1.7rem 6.5rem; }
        .um-brand { font-size:1.32rem; font-weight:700; letter-spacing:-.04em; color:var(--red); }
        .um-brand span { color:var(--red); }
        .um-side-label { color:#e32636; font-size:.72rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; margin:1.5rem 0 .45rem; }
        .um-header { display:flex; align-items:center; justify-content:space-between; padding:0 0 1rem; border-bottom:1px solid var(--line); margin-bottom:1.2rem; }
        .um-header-title { font-size:1.15rem; font-weight:700; color:#fff; }
        .um-chat-title { font-size:.86rem; color:var(--muted); margin-top:.2rem; }
        /* The bordered Streamlit container carrying this marker becomes an overlay drawer,
           so it never consumes a permanent right-hand chat column. */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.um-drawer-marker),
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.um-settings-drawer-marker) {
            position:fixed !important; top:0; right:0; z-index:1000; width:min(430px, 94vw);
            height:100vh; overflow-y:auto; background:#101011; border-left:1px solid #3a3032;
            box-shadow:-18px 0 45px rgba(0,0,0,.45); padding:1.2rem; border-radius:0 !important;
        }
        .um-profile { padding:.15rem .25rem 2rem; min-height:72vh; }
        .um-profile-name { font-size:1.05rem; font-weight:700; margin-top:.85rem; }
        .um-profile-meta { color:var(--muted); font-size:.86rem; margin-top:.18rem; }
        .um-profile-item { padding:.7rem 0; border-bottom:1px solid #242429; }
        .um-profile-item small { display:block; color:var(--red); margin-bottom:.16rem; }
        .um-empty { padding:5.5rem 1rem 2rem; text-align:center; }
        .um-wave { font-size:2rem; margin-bottom:.55rem; }
        .um-empty h2 { margin:0 0 .5rem; font-size:1.65rem; letter-spacing:-.04em; }
        .um-empty p { color:var(--muted); margin:0; }
        .um-status { color:var(--muted); font-size:.78rem; margin-bottom:.75rem; }
        [data-testid="stChatMessage"] { background:transparent; padding:.75rem .2rem; color:#fff; max-width:900px; margin:0 auto; }
        [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] { line-height:1.65; }
        [data-testid="stChatInput"] { border:1px solid #3a3032; border-radius:14px; box-shadow:none; background:#151519; }
        [data-testid="stChatInput"] textarea, [data-testid="stChatInput"] textarea::placeholder { color:#fff; background:#151519; }
        [data-testid="stChatInput"] button, [data-testid="stAudioInput"] button { color:var(--red); }
        /* Keep the normal-state microphone beside the fixed chat composer. */
        [data-testid="stAudioInput"] { position:fixed; right:5rem; bottom:.45rem; z-index:998; width:2.4rem; }
        [data-testid="stAudioInput"] audio { display:none; }
        [data-testid="stVerticalBlock"]:has(.um-chat-scroll-marker) { padding-bottom:.5rem; }
        [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input, [data-testid="stSelectbox"] div[data-baseweb="select"] > div, [data-testid="stMultiSelect"] div[data-baseweb="select"] > div { color:#fff !important; background:#151519 !important; border-color:#413438 !important; }
        [data-baseweb="popover"], [data-baseweb="menu"] { background:#151519 !important; color:#fff !important; }
        .um-notification { border-bottom:1px solid #29292f; padding:.65rem 0; }
        .um-notification:last-child { border:0; }
        .um-notification-title { font-weight:600; font-size:.9rem; }
        .um-notification-detail { color:var(--muted); font-size:.8rem; margin-top:.15rem; }
        .um-composer-note { color:var(--muted); font-size:.75rem; text-align:center; margin-top:.4rem; }
        @media (max-width: 900px) { .um-profile { min-height:auto; } }
        </style>
        """,
        unsafe_allow_html=True,
    )
