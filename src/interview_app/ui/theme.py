"""
Custom CSS theme for the Interview Coach UI.

Light/dark mode share one :root token system (semantic + Streamlit-facing ``--st-*``).
Component rules in ``_streamlit_widget_overrides`` always apply and read those tokens so
widgets, chat, and custom HTML stay aligned when the theme toggles.
"""

from __future__ import annotations

import html

import streamlit as st

from interview_app.app.ui_settings import UISettings
from interview_app.llm.model_settings import sidebar_label_for_preset

_FONT_IMPORT = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
</style>"""

_LIGHT_VARS = """
    --background-color: #ffffff;
    --secondary-background-color: #f8fafc;
    --text-color: #0f172a;
    --primary-color: #0f766e;
    --bg-primary: #ffffff;
    --bg-secondary: #f8fafc;
    --bg-tertiary: #f1f5f9;
    --bg-card: #ffffff;
    --bg-sidebar: #fafbfc;
    --bg-input: #ffffff;
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-tertiary: #64748b;
    --border-primary: #e2e8f0;
    --border-secondary: #f1f5f9;
    --accent: #0f766e;
    --accent-light: #0d9488;
    --accent-bg: #f0fdfa;
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
    --shadow-md: 0 4px 12px rgba(0,0,0,0.06);
    --success: #059669;
    --success-bg: #ecfdf5;
    --warning: #d97706;
    --warning-bg: #fffbeb;
    --error: #dc2626;
    --error-bg: #fef2f2;
    --info: #2563eb;
    --info-bg: #eff6ff;
    --header-gradient: linear-gradient(135deg, #0f766e 0%, #0d9488 50%, #14b8a6 100%);
    --card-gradient: linear-gradient(135deg, rgba(15,118,110,0.03), rgba(20,184,166,0.02));
    --surface: #ffffff;
    --surface-alt: #f8fafc;
    --text-muted: #64748b;
    --border: #e2e8f0;
    --accent-foreground: #f8fafc;
    --input-background: #ffffff;
    --input-foreground: #0f172a;
    --placeholder: #64748b;
    --st-surface: #ffffff;
    --st-surface-elevated: #f1f5f9;
    --st-input-bg: #ffffff;
    --st-input-border: #cbd5e1;
    --st-input-border-focus: #0f766e;
    --st-input-text: #0f172a;
    --st-placeholder: #64748b;
    --st-label: #334155;
    --st-caption: #475569;
    --st-muted: #64748b;
    --st-dropdown-bg: #ffffff;
    --st-dropdown-border: #cbd5e1;
    --st-dropdown-hover: #f1f5f9;
    --st-dropdown-text: #0f172a;
    --st-btn-primary-bg: #0f766e;
    --st-btn-primary-text: #f8fafc;
    --st-btn-secondary-bg: #ffffff;
    --st-btn-secondary-text: #0f172a;
    --st-btn-secondary-border: #cbd5e1;
    --st-focus-ring: rgba(15,118,110,0.35);
    --st-chat-user-bg: #f0fdfa;
    --st-chat-assistant-bg: #f8fafc;
    --st-tab-inactive: #64748b;
    --st-tab-active: #0f172a;
    --st-tab-hover-bg: rgba(15,118,110,0.08);
    --st-btn-disabled-bg: #e2e8f0;
    --st-btn-disabled-text: #475569;
    --st-btn-disabled-border: #cbd5e1;
    --st-segmented-track-bg: #f1f5f9;
    --st-segmented-inactive-text: #64748b;
    --st-chat-composer-border: #cbd5e1;
    --st-chat-placeholder: #64748b;
"""

_DARK_VARS = """
    --background-color: #111827;
    --secondary-background-color: #1a2332;
    --text-color: #f1f5f9;
    --primary-color: #2dd4bf;
    --bg-primary: #111827;
    --bg-secondary: #1a2332;
    --bg-tertiary: #243044;
    --bg-card: #1a2332;
    --bg-sidebar: #0f1520;
    --bg-input: #1e293b;
    --text-primary: #f1f5f9;
    --text-secondary: #cbd5e1;
    --text-tertiary: #94a3b8;
    --border-primary: #334155;
    --border-secondary: #243044;
    --accent: #2dd4bf;
    --accent-light: #5eead4;
    --accent-bg: rgba(45,212,191,0.14);
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.35);
    --shadow-md: 0 8px 24px rgba(0,0,0,0.45);
    --success: #4ade80;
    --success-bg: rgba(74,222,128,0.14);
    --warning: #fbbf24;
    --warning-bg: rgba(251,191,36,0.14);
    --error: #f87171;
    --error-bg: rgba(248,113,113,0.14);
    --info: #93c5fd;
    --info-bg: rgba(147,197,253,0.12);
    --header-gradient: linear-gradient(135deg, #0d3d38 0%, #134e48 50%, #115e56 100%);
    --card-gradient: linear-gradient(135deg, rgba(45,212,191,0.07), rgba(15,118,110,0.04));
    --surface: #151d30;
    --surface-alt: #1a2438;
    --text-muted: #94a3b8;
    --border: #334155;
    --accent-foreground: #042f2e;
    --input-background: #1a2438;
    --input-foreground: #f8fafc;
    --placeholder: #a3b4cc;
    --st-surface: #151d30;
    --st-surface-elevated: #1e293b;
    --st-input-bg: #1a2438;
    --st-input-border: #4b5e78;
    --st-input-border-focus: #2dd4bf;
    --st-input-text: #f8fafc;
    --st-placeholder: #a3b4cc;
    --st-label: #e2e8f0;
    --st-caption: #cbd5e1;
    --st-muted: #94a3b8;
    --st-dropdown-bg: #1a2438;
    --st-dropdown-border: #4b5e78;
    --st-dropdown-hover: #243047;
    --st-dropdown-text: #f8fafc;
    --st-btn-primary-bg: #0d9488;
    --st-btn-primary-text: #f0fdfa;
    --st-btn-secondary-bg: #1e293b;
    --st-btn-secondary-text: #f1f5f9;
    --st-btn-secondary-border: #4b5e78;
    --st-focus-ring: rgba(45,212,191,0.5);
    --st-chat-user-bg: rgba(45,212,191,0.12);
    --st-chat-assistant-bg: #141c2f;
    --st-tab-inactive: #e2e8f0;
    --st-tab-active: #ffffff;
    --st-tab-hover-bg: rgba(45,212,191,0.18);
    --st-btn-disabled-bg: #3d4f63;
    --st-btn-disabled-text: #e8edf4;
    --st-btn-disabled-border: #5a6d85;
    --st-segmented-track-bg: #243044;
    --st-segmented-inactive-text: #e2e8f0;
    --st-chat-composer-border: #5a6d85;
    --st-chat-placeholder: #b8c9dc;
"""


def _streamlit_widget_overrides() -> str:
    """
    Streamlit + Base Web styling for both themes.

    Uses :root semantic tokens so contrast is tuned in ``_LIGHT_VARS`` / ``_DARK_VARS`` only.
    Includes global [data-baseweb="popover"] rules because dropdown menus are often
    portaled outside the sidebar DOM.
    """
    return """
/* ----- Typography: labels, captions, help (sidebar + main) ----- */
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] label,
[data-testid="stSidebar"] label:not([data-baseweb="radio"]),
[data-testid="stMain"] [data-testid="stWidgetLabel"] p,
[data-testid="stMain"] [data-testid="stWidgetLabel"] label,
[data-testid="stMain"] label:not([data-baseweb="radio"]) {
    color: var(--st-label) !important;
}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stMain"] [data-testid="stCaptionContainer"] p,
[data-testid="stMain"] [data-testid="stCaptionContainer"] {
    color: var(--st-caption) !important;
}
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown li,
[data-testid="stMain"] .stMarkdown,
[data-testid="stMain"] .stMarkdown p,
[data-testid="stMain"] .stMarkdown li {
    color: var(--text-primary) !important;
}
[data-testid="stSidebar"] .stMarkdown strong {
    color: var(--st-input-text) !important;
    font-weight: 600 !important;
}
[data-testid="stSidebar"] a {
    color: var(--accent-light) !important;
}

/* ----- Text inputs & textareas (all) ----- */
[data-testid="stSidebar"] input:not([type="checkbox"]):not([type="radio"]),
[data-testid="stMain"] input:not([type="checkbox"]):not([type="radio"]),
[data-testid="stSidebar"] textarea,
[data-testid="stMain"] textarea {
    background-color: var(--st-input-bg) !important;
    color: var(--st-input-text) !important;
    border-color: var(--st-input-border) !important;
    caret-color: var(--st-input-text) !important;
}
[data-testid="stSidebar"] input::placeholder,
[data-testid="stMain"] input::placeholder,
[data-testid="stSidebar"] textarea::placeholder,
[data-testid="stMain"] textarea::placeholder {
    color: var(--st-placeholder) !important;
    opacity: 1 !important;
}
[data-testid="stSidebar"] [data-baseweb="input"],
[data-testid="stMain"] [data-baseweb="input"] {
    background-color: var(--st-input-bg) !important;
    border-color: var(--st-input-border) !important;
}
[data-testid="stSidebar"] [data-baseweb="input"]:focus-within,
[data-testid="stMain"] [data-baseweb="input"]:focus-within,
[data-testid="stSidebar"] [data-baseweb="textarea"]:focus-within,
[data-testid="stMain"] [data-baseweb="textarea"]:focus-within {
    border-color: var(--st-input-border-focus) !important;
    box-shadow: 0 0 0 1px var(--st-input-border-focus) !important;
}

/* ----- Selectbox: closed control (sidebar + main) ----- */
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stMain"] [data-baseweb="select"] > div {
    background-color: var(--st-input-bg) !important;
    border-color: var(--st-input-border) !important;
    color: var(--st-input-text) !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] div[class*="value"],
[data-testid="stMain"] [data-baseweb="select"] div[class*="value"] {
    color: var(--st-input-text) !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] svg,
[data-testid="stMain"] [data-baseweb="select"] svg {
    fill: var(--st-input-text) !important;
    color: var(--st-input-text) !important;
}
[data-testid="stSidebar"] [data-baseweb="select"]:focus-within > div,
[data-testid="stMain"] [data-baseweb="select"]:focus-within > div {
    border-color: var(--st-input-border-focus) !important;
    box-shadow: 0 0 0 1px var(--st-focus-ring) !important;
}

/* ----- Dropdown menus: portaled popovers (NOT under stSidebar) ----- */
div[data-baseweb="popover"] {
    background: transparent !important;
}
div[data-baseweb="popover"] [role="listbox"],
div[data-baseweb="popover"] ul[role="listbox"] {
    background-color: var(--st-dropdown-bg) !important;
    border: 1px solid var(--st-dropdown-border) !important;
    box-shadow: var(--shadow-md) !important;
}
div[data-baseweb="popover"] [role="option"],
div[data-baseweb="popover"] li[role="option"] {
    background-color: var(--st-dropdown-bg) !important;
    color: var(--st-dropdown-text) !important;
}
div[data-baseweb="popover"] [role="option"]:hover,
div[data-baseweb="popover"] [role="option"][aria-selected="true"] {
    background-color: var(--st-dropdown-hover) !important;
    color: var(--st-dropdown-text) !important;
}
div[data-baseweb="popover"] [role="option"] span {
    color: inherit !important;
}

/* Fallback: listbox still inside sidebar/main */
[data-testid="stSidebar"] [role="listbox"],
[data-testid="stMain"] [role="listbox"] {
    background-color: var(--st-dropdown-bg) !important;
    border: 1px solid var(--st-dropdown-border) !important;
}
[data-testid="stSidebar"] [role="option"],
[data-testid="stMain"] [role="option"] {
    background-color: var(--st-dropdown-bg) !important;
    color: var(--st-dropdown-text) !important;
}
[data-testid="stSidebar"] [role="option"]:hover,
[data-testid="stMain"] [role="option"]:hover {
    background-color: var(--st-dropdown-hover) !important;
}

/* ----- Sliders ----- */
[data-testid="stSidebar"] [data-baseweb="slider"] [data-baseweb="thumb"],
[data-testid="stMain"] [data-baseweb="slider"] [data-baseweb="thumb"] {
    background-color: var(--accent) !important;
}
[data-testid="stSidebar"] [data-baseweb="slider"] [data-baseweb="track"],
[data-testid="stMain"] [data-baseweb="slider"] [data-baseweb="track"] {
    background-color: var(--st-surface-elevated) !important;
}

/* ----- Toggle / checkbox (dark mode switch, etc.) ----- */
[data-testid="stSidebar"] [data-baseweb="checkbox"] label {
    color: var(--st-label) !important;
}
[data-testid="stSidebar"] [data-baseweb="checkbox"] > label > div:last-child,
[data-testid="stSidebar"] [data-baseweb="checkbox"] span {
    color: var(--st-label) !important;
}

/* ----- Expanders ----- */
[data-testid="stSidebar"] [data-testid="stExpander"] summary,
[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
[data-testid="stSidebar"] [data-testid="stExpander"] summary span,
[data-testid="stMain"] [data-testid="stExpander"] summary,
[data-testid="stMain"] [data-testid="stExpander"] summary p {
    color: var(--st-label) !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] details,
[data-testid="stMain"] [data-testid="stExpander"] details {
    background-color: var(--st-surface) !important;
    border: 1px solid var(--st-input-border) !important;
    border-radius: var(--radius-sm);
}

/* ----- Alerts ----- */
[data-testid="stSidebar"] [data-testid="stAlert"],
[data-testid="stMain"] [data-testid="stAlert"] {
    background-color: var(--st-surface-elevated) !important;
    border: 1px solid var(--st-input-border) !important;
}
[data-testid="stSidebar"] [data-testid="stAlert"] p,
[data-testid="stSidebar"] [data-testid="stAlert"] div,
[data-testid="stMain"] [data-testid="stAlert"] p,
[data-testid="stMain"] [data-testid="stAlert"] div {
    color: var(--text-primary) !important;
}

/* ----- Radio (sidebar usage mode only — native circles + labels) ----- */
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label,
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label p,
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label span {
    color: var(--st-label) !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] [data-baseweb="radio"] {
    border-color: var(--st-input-border) !important;
    background-color: var(--st-input-bg) !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] [data-baseweb="radio"][aria-checked="true"] {
    background-color: var(--accent) !important;
    border-color: var(--accent) !important;
}

/* ----- Buttons (Streamlit 1.55+ Base Web: `kind` is often NOT on the DOM) ----- */
[data-testid="stSidebar"] [data-testid="stButton"] button,
[data-testid="stMain"] [data-testid="stButton"] button,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button,
[data-testid="stMain"] [data-testid="stDownloadButton"] button {
    background-color: var(--st-btn-secondary-bg) !important;
    background-image: none !important;
    color: var(--st-btn-secondary-text) !important;
    border: 1px solid var(--st-btn-secondary-border) !important;
    -webkit-text-fill-color: var(--st-btn-secondary-text) !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button *,
[data-testid="stMain"] [data-testid="stButton"] button *,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button *,
[data-testid="stMain"] [data-testid="stDownloadButton"] button * {
    color: inherit !important;
    -webkit-text-fill-color: inherit !important;
    opacity: 1 !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover:not(:disabled),
[data-testid="stMain"] [data-testid="stButton"] button:hover:not(:disabled),
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button:hover:not(:disabled),
[data-testid="stMain"] [data-testid="stDownloadButton"] button:hover:not(:disabled) {
    background-color: var(--st-surface-elevated) !important;
    border-color: var(--accent-light) !important;
    filter: brightness(1.02) !important;
}
/* Legacy / future: explicit kind attribute */
[data-testid="stSidebar"] button[kind="primary"],
[data-testid="stMain"] button[kind="primary"],
[data-testid="stSidebar"] .stButton > button[kind="primary"],
[data-testid="stMain"] .stButton > button[kind="primary"],
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button[kind="primary"],
[data-testid="stMain"] [data-testid="stDownloadButton"] button[kind="primary"],
/* Primary actions keyed in the Python app (see layout.py, usage_mode_panel.py) */
[data-testid="stMain"] .st-key-main_save_session button,
[data-testid="stMain"] .st-key-btn_generate_questions button,
[data-testid="stMain"] .st-key-cv_btn_practice button,
[data-testid="stMain"] .st-key-cv_btn_evaluate_practice button,
[data-testid="stMain"] .st-key-btn_evaluate_answer button,
[data-testid="stSidebar"] .st-key-um_apply_btn button {
    background-color: var(--st-btn-primary-bg) !important;
    color: var(--st-btn-primary-text) !important;
    border: 1px solid var(--st-btn-primary-bg) !important;
    -webkit-text-fill-color: var(--st-btn-primary-text) !important;
}
[data-testid="stSidebar"] button[kind="primary"]:hover:not(:disabled),
[data-testid="stMain"] button[kind="primary"]:hover:not(:disabled),
[data-testid="stMain"] .st-key-main_save_session button:hover:not(:disabled),
[data-testid="stMain"] .st-key-btn_generate_questions button:hover:not(:disabled),
[data-testid="stMain"] .st-key-cv_btn_practice button:hover:not(:disabled),
[data-testid="stMain"] .st-key-cv_btn_evaluate_practice button:hover:not(:disabled),
[data-testid="stMain"] .st-key-btn_evaluate_answer button:hover:not(:disabled),
[data-testid="stSidebar"] .st-key-um_apply_btn button:hover:not(:disabled) {
    filter: brightness(1.08) !important;
}
[data-testid="stSidebar"] button[kind="secondary"],
[data-testid="stMain"] button[kind="secondary"],
[data-testid="stSidebar"] .stButton > button[kind="secondary"],
[data-testid="stMain"] .stButton > button[kind="secondary"] {
    background-color: var(--st-btn-secondary-bg) !important;
    color: var(--st-btn-secondary-text) !important;
    border: 1px solid var(--st-btn-secondary-border) !important;
}
[data-testid="stSidebar"] button:disabled,
[data-testid="stMain"] button:disabled,
[data-testid="stSidebar"] .stButton > button:disabled,
[data-testid="stMain"] .stButton > button:disabled,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button:disabled,
[data-testid="stMain"] [data-testid="stDownloadButton"] button:disabled,
[data-testid="stSidebar"] button[disabled],
[data-testid="stMain"] button[disabled],
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button[disabled],
[data-testid="stMain"] [data-testid="stDownloadButton"] button[disabled],
[data-testid="stSidebar"] button[aria-disabled="true"],
[data-testid="stMain"] button[aria-disabled="true"] {
    opacity: 1 !important;
    filter: none !important;
    cursor: not-allowed !important;
    background-color: var(--st-btn-disabled-bg) !important;
    color: var(--st-btn-disabled-text) !important;
    border-color: var(--st-btn-disabled-border) !important;
    -webkit-text-fill-color: var(--st-btn-disabled-text) !important;
}
[data-testid="stSidebar"] button:disabled *,
[data-testid="stMain"] button:disabled *,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button:disabled *,
[data-testid="stMain"] [data-testid="stDownloadButton"] button:disabled * {
    color: var(--st-btn-disabled-text) !important;
    -webkit-text-fill-color: var(--st-btn-disabled-text) !important;
    opacity: 1 !important;
}
[data-testid="stMain"] .st-key-main_save_session button:disabled,
[data-testid="stMain"] .st-key-main_save_session button[disabled],
[data-testid="stMain"] .st-key-main_new_session button:disabled,
[data-testid="stMain"] .st-key-main_new_session button[disabled],
[data-testid="stMain"] .st-key-mock_interview_export_download button:disabled,
[data-testid="stMain"] .st-key-mock_interview_export_download button[disabled] {
    background-color: var(--st-btn-disabled-bg) !important;
    color: var(--st-btn-disabled-text) !important;
    border-color: var(--st-btn-disabled-border) !important;
    -webkit-text-fill-color: var(--st-btn-disabled-text) !important;
}
[data-testid="stMain"] .st-key-main_save_session button:disabled *,
[data-testid="stMain"] .st-key-main_new_session button:disabled *,
[data-testid="stMain"] .st-key-mock_interview_export_download button:disabled * {
    color: var(--st-btn-disabled-text) !important;
    -webkit-text-fill-color: var(--st-btn-disabled-text) !important;
    opacity: 1 !important;
}

/* ----- Chat composer ----- */
[data-testid="stBottomBlockContainer"],
[data-testid="stBottom"],
section[data-testid="stBottom"],
[data-testid="stBottom"] > div {
    background-color: var(--bg-primary) !important;
    border-top: none !important;
    box-shadow: none !important;
    margin-top: 0 !important;
    padding-top: 0 !important;
}
[data-testid="stChatInputContainer"] {
    background-color: var(--bg-primary) !important;
    border-top: none !important;
    margin-top: 0.5rem !important;
    padding-top: 0 !important;
    box-shadow: none !important;
}
[data-testid="stChatInput"],
[data-testid="stChatInput"] > div {
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
}
[data-testid="stChatInput"] [data-baseweb="textarea"],
[data-testid="stChatInput"] [data-baseweb="input"],
[data-testid="stChatInput"] textarea {
    background-color: var(--st-input-bg) !important;
    color: var(--st-input-text) !important;
    border: 1px solid var(--st-chat-composer-border, var(--st-input-border)) !important;
    border-radius: var(--radius-lg) !important;
    min-height: 2.75rem !important;
    box-shadow: none !important;
}
[data-testid="stChatInput"] [data-baseweb="textarea"]:focus-within,
[data-testid="stChatInput"] [data-baseweb="input"]:focus-within {
    border-color: var(--st-input-border-focus) !important;
    box-shadow: 0 0 0 1px var(--st-focus-ring) !important;
}
[data-testid="stChatInput"] textarea::placeholder {
    color: var(--st-chat-placeholder, var(--st-placeholder)) !important;
    opacity: 1 !important;
}
[data-testid="stChatInputSubmitButton"],
[data-testid="stChatInput"] button,
[data-testid="stChatInput"] [data-testid="stBaseButton-secondary"] {
    background-color: transparent !important;
    color: var(--accent) !important;
    border: none !important;
    -webkit-text-fill-color: var(--accent) !important;
    opacity: 0.92 !important;
}
[data-testid="stChatInputSubmitButton"]:hover:not(:disabled),
[data-testid="stChatInput"] button:hover:not(:disabled) {
    background-color: var(--st-tab-hover-bg) !important;
    opacity: 1 !important;
}
[data-testid="stChatInputSubmitButton"] svg,
[data-testid="stChatInput"] button svg {
    fill: var(--accent) !important;
    color: var(--accent) !important;
}
/* Remove duplicate dividers above chat input */
[data-testid="stMain"] [data-testid="stChatInputContainer"] ~ hr,
[data-testid="stMain"] [data-testid="stChatInputContainer"] + hr,
[data-testid="stMain"] .st-key-mock_interview_export_download ~ hr,
[data-testid="stMain"] .ia-chat-panel + hr {
    display: none !important;
}

/* ----- Chat transcript (markdown inside bubbles) ----- */
[data-testid="stChatMessage"] {
    color: var(--text-primary) !important;
    border-color: var(--border-primary) !important;
    background-color: var(--bg-card) !important;
}
[data-testid="stChatMessage"] .stMarkdown,
[data-testid="stChatMessage"] .stMarkdownContainer,
[data-testid="stChatMessage"] .stMarkdown p,
[data-testid="stChatMessage"] .stMarkdown li,
[data-testid="stChatMessage"] .stMarkdown strong {
    color: var(--text-primary) !important;
}
[data-testid="stChatMessage"] a {
    color: var(--accent-light) !important;
}
[data-testid="stChatMessage"] code,
[data-testid="stChatMessage"] pre {
    background: var(--surface-alt) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-primary) !important;
}

/* ----- Metrics (evaluation dashboard) ----- */
[data-testid="stMain"] [data-testid="stMetric"] {
    background: var(--st-surface) !important;
    border: 1px solid var(--st-input-border) !important;
}
[data-testid="stMain"] [data-testid="stMetric"] [data-testid="stMetricLabel"] {
    color: var(--st-caption) !important;
}
[data-testid="stMain"] [data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: var(--st-input-text) !important;
}

/* ----- Code / debug expanders ----- */
[data-testid="stMain"] [data-testid="stCode"] {
    background: var(--bg-primary) !important;
}
[data-testid="stMain"] pre {
    background: var(--st-surface) !important;
    color: var(--st-input-text) !important;
    border: 1px solid var(--st-input-border) !important;
}

/* ----- Notifications / toast ----- */
[data-testid="stMain"] [data-baseweb="notification"] {
    background-color: var(--st-surface-elevated) !important;
    color: var(--st-input-text) !important;
    border: 1px solid var(--st-input-border) !important;
}
"""


def _dark_contrast_hardening() -> str:
    """
    Literal-color overrides for Streamlit Cloud when host theme wins over :root tokens.

    Scoped under ``stAppViewContainer`` for specificity; only injected in dark mode.
    """
    return """
/* ----- Dark mode contrast hardening (Cloud host theme fallback) ----- */
[data-testid="stAppViewContainer"] [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label,
[data-testid="stAppViewContainer"] [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label p,
[data-testid="stAppViewContainer"] [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label span {
    color: #f1f5f9 !important;
}
[data-testid="stAppViewContainer"] [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p,
[data-testid="stAppViewContainer"] [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
    color: #cbd5e1 !important;
}
[data-testid="stAppViewContainer"] [data-testid="stMain"] button:disabled,
[data-testid="stAppViewContainer"] [data-testid="stMain"] button[disabled],
[data-testid="stAppViewContainer"] [data-testid="stMain"] .st-key-main_save_session button:disabled,
[data-testid="stAppViewContainer"] [data-testid="stMain"] .st-key-mock_interview_export_download button:disabled {
    background-color: #3d4f63 !important;
    color: #e8edf4 !important;
    border-color: #5a6d85 !important;
    -webkit-text-fill-color: #e8edf4 !important;
}
[data-testid="stAppViewContainer"] [data-testid="stMain"] input::placeholder,
[data-testid="stAppViewContainer"] [data-testid="stMain"] textarea::placeholder,
[data-testid="stAppViewContainer"] [data-testid="stChatInput"] textarea::placeholder {
    color: #b8c9dc !important;
    opacity: 1 !important;
}
[data-testid="stAppViewContainer"] [data-testid="stChatInput"] textarea,
[data-testid="stAppViewContainer"] [data-testid="stChatInput"] [data-baseweb="textarea"] {
    border-color: #5a6d85 !important;
    color: #f8fafc !important;
}
"""


def _build_app_css(dark: bool = False) -> str:
    vars_block = _DARK_VARS if dark else _LIGHT_VARS
    streamlit_layer = _streamlit_widget_overrides()
    dark_patch = _dark_contrast_hardening() if dark else ""
    return f"""<style>
:root,
[data-testid="stAppViewContainer"],
[data-testid="stSidebar"],
[data-testid="stMain"] {{
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
    {vars_block}
}}
html, body, [data-testid="stAppViewContainer"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    color: var(--text-primary);
    background-color: var(--bg-primary);
}}
h1, h2, h3, h4 {{ color: var(--text-primary) !important; }}
.block-container {{
    padding-top: 0.75rem !important;
    padding-bottom: 1.75rem !important;
    max-width: min(1200px, 96vw) !important;
    margin-left: auto !important;
    margin-right: auto !important;
}}
.ia-workspace-stack {{
    margin-top: 0.15rem;
}}
[data-testid="stMain"] {{ background-color: var(--bg-primary) !important; }}
[data-testid="stSidebar"] {{
    background-color: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border-primary) !important;
}}
[data-testid="stHeader"] {{
    background: var(--header-gradient) !important;
}}
.ia-hero {{
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
    padding: 1.25rem 1.5rem;
    margin-bottom: 0.25rem;
    background: var(--card-gradient);
    box-shadow: var(--shadow-sm);
}}
.ia-hero-compact {{
    padding: 0.75rem 1rem !important;
    margin-bottom: 0.45rem !important;
}}
.ia-hero-title {{
    font-size: 1.85rem !important;
    font-weight: 800 !important;
    margin: 0 0 0.4rem 0 !important;
    letter-spacing: -0.03em;
    color: var(--text-primary) !important;
}}
.ia-hero-compact .ia-hero-title {{
    font-size: 1.45rem !important;
    font-weight: 700 !important;
    margin: 0 0 0.35rem 0 !important;
}}
.ia-hero-icon {{ margin-right: 0.4rem; }}
.ia-hero-subtitle {{
    margin: 0;
    font-size: 0.95rem;
    color: var(--text-secondary);
    line-height: 1.55;
}}
.ia-hero-compact .ia-hero-subtitle {{
    font-size: 0.88rem !important;
    line-height: 1.45 !important;
}}
.ia-config-card {{
    background: var(--bg-card);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-md);
    padding: 0.65rem 0.85rem 0.55rem 0.85rem;
    margin-bottom: 0.55rem;
    box-shadow: var(--shadow-sm);
}}
.ia-config-card-header {{
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-tertiary);
    margin: 0 0 0.45rem 0;
}}
.ia-config-chips {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem;
}}
.ia-pill {{
    display: inline-flex;
    align-items: center;
    padding: 0.22rem 0.62rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 500;
    color: var(--text-primary);
    background: var(--bg-secondary);
    border: 1px solid var(--border-primary);
    max-width: 100%;
    line-height: 1.35;
}}
.ia-config-tech {{
    margin-top: 0.45rem;
    padding-top: 0.35rem;
    border-top: 1px solid var(--border-secondary);
}}
.ia-config-tech summary {{
    cursor: pointer;
    list-style: none;
    font-size: 0.74rem;
    font-weight: 600;
    color: var(--text-secondary);
    user-select: none;
    padding: 0.15rem 0;
}}
.ia-config-tech summary::-webkit-details-marker {{
    display: none;
}}
.ia-config-tech summary::before {{
    content: "▸";
    display: inline-block;
    margin-right: 0.35rem;
    color: var(--text-tertiary);
    transition: transform 0.15s ease;
}}
.ia-config-tech[open] summary::before {{
    transform: rotate(90deg);
}}
.ia-config-tech[open] summary {{
    color: var(--text-primary);
    margin-bottom: 0.35rem;
}}
.ia-config-chips-tech {{
    padding-bottom: 0.15rem;
}}
.ia-config-chips-tech .ia-pill {{
    font-size: 0.74rem;
    color: var(--text-secondary);
    background: var(--bg-tertiary);
}}
.ia-workspace-nav-label {{
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--st-caption);
    margin: 0 0 0.35rem 0;
}}
.ia-session-card-header {{
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-tertiary);
    margin: 0 0 0.35rem 0;
}}
.ia-session-card {{
    background: var(--bg-card);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-md);
    padding: 0.65rem 0.85rem;
    margin-bottom: 0.75rem;
    box-shadow: var(--shadow-sm);
}}
.ia-session-status {{
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
    padding-top: 0.42rem;
    white-space: nowrap;
}}
[data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-session_title) {{
    padding: 0.5rem 0.65rem 0.55rem 0.65rem !important;
    margin-bottom: 0.65rem !important;
    background: var(--bg-card) !important;
}}
[data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-session_title) [data-testid="stHorizontalBlock"] {{
    gap: 0.35rem !important;
    align-items: end !important;
}}
[data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-session_title) [data-testid="column"] {{
    min-width: 0 !important;
}}
[data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-session_title) [data-testid="stTextInput"] input {{
    min-height: 2.35rem !important;
}}
[data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-session_title) [data-testid="stButton"] button,
[data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-session_title) [data-testid="stDownloadButton"] button {{
    min-height: 2.35rem !important;
    padding: 0.3rem 0.45rem !important;
    font-size: 0.82rem !important;
    width: 100% !important;
}}
.ia-chat-panel {{
    background: var(--bg-card);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
    padding: 0.75rem 1rem 1rem 1rem;
    margin-bottom: 0.5rem;
    min-height: 12rem;
}}
.ia-chat-panel [data-testid="stChatMessage"] {{
    margin-bottom: 0.65rem;
}}
.ia-instruction-hint {{
    font-size: 0.88rem;
    color: var(--text-secondary);
    line-height: 1.5;
    margin: 0;
}}
.ia-section-head {{
    margin: 0 0 0.75rem 0;
}}
.ia-section-title {{
    font-size: 1.28rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
    margin: 0 0 0.35rem 0 !important;
    color: var(--text-primary) !important;
}}
.ia-section-sub {{
    font-size: 0.9rem;
    line-height: 1.5;
    color: var(--text-secondary);
    margin: 0;
}}
.ia-sidebar-section {{
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em;
    color: var(--text-primary) !important;
    margin: 0 0 0.35rem 0 !important;
    padding: 0 !important;
}}
[data-testid="stSidebar"] .ia-usage-status-card {{
    margin: 0.65rem 0 0.5rem 0;
    padding: 0.65rem 0.75rem;
    border-radius: var(--radius-md);
    border: 1px solid var(--border-primary);
    background: var(--bg-secondary);
    line-height: 1.35;
}}
[data-testid="stSidebar"] .ia-usage-status-title {{
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 0.2rem 0;
}}
[data-testid="stSidebar"] .ia-usage-status-sub {{
    font-size: 0.74rem;
    color: var(--text-secondary);
    margin: 0;
}}
[data-testid="stSidebar"] .ia-usage-status-meta {{
    font-size: 0.68rem;
    color: var(--text-tertiary);
    margin: 0.45rem 0 0 0;
    letter-spacing: 0.01em;
}}
[data-testid="stSidebar"] .ia-usage-status-byo .ia-usage-status-title::before {{
    content: "";
    display: inline-block;
    width: 0.45rem;
    height: 0.45rem;
    margin-right: 0.4rem;
    border-radius: 2px;
    background: var(--accent);
    vertical-align: 0.05em;
}}
[data-testid="stSidebar"] .ia-saved-session-row [data-testid="stHorizontalBlock"] {{
    gap: 0.25rem !important;
    align-items: center !important;
}}
[data-testid="stSidebar"] .ia-saved-session-row [data-testid="column"] {{
    min-width: 0 !important;
}}
[data-testid="stSidebar"] .ia-saved-session-row [data-testid="stButton"] button {{
    white-space: nowrap !important;
    font-size: 0.72rem !important;
    padding: 0.22rem 0.4rem !important;
    min-height: 1.85rem !important;
    line-height: 1.1 !important;
    letter-spacing: -0.01em !important;
}}
[data-testid="stSidebar"] .st-key-sb_del_all_start button,
[data-testid="stSidebar"] .st-key-sb_del_all_yes button,
[data-testid="stSidebar"] .st-key-sb_del_all_no button {{
    white-space: nowrap !important;
}}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
    font-size: 0.78rem !important;
    color: var(--st-caption) !important;
    -webkit-text-fill-color: var(--st-caption) !important;
    opacity: 1 !important;
}}
[data-testid="stSidebar"] .st-key-um_draft_radio + [data-testid="stCaptionContainer"] p,
[data-testid="stSidebar"] .st-key-um_draft_radio ~ [data-testid="stCaptionContainer"] p {{
    color: var(--st-caption) !important;
}}
[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius: var(--radius-lg) !important;
    background: var(--bg-secondary) !important;
    border-color: var(--border-primary) !important;
    padding: 0.95rem 1.05rem 1rem 1.05rem !important;
    margin-bottom: 0.75rem !important;
}}
[data-testid="stMain"] .ia-session-card[data-testid="stVerticalBlockBorderWrapper"] {{
    padding: 0.65rem 0.85rem !important;
    margin-bottom: 0.75rem !important;
    background: var(--bg-card) !important;
}}
[data-testid="stMain"] .ia-chat-panel[data-testid="stVerticalBlockBorderWrapper"] {{
    padding: 0.75rem 1rem 1rem 1rem !important;
    margin-bottom: 0.5rem !important;
    background: var(--bg-card) !important;
    min-height: 12rem;
}}
[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"] button {{
    font-size: 0.92rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em !important;
}}
[data-testid="stSidebar"] hr {{
    margin: 1rem 0 !important;
    border-color: var(--border-primary) !important;
}}
[data-testid="stSidebar"] .block-container {{
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
}}
.ia-card {{
    background: var(--bg-card);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
    padding: 1.25rem;
    box-shadow: var(--shadow-sm);
    margin-bottom: 0.75rem;
}}
.ia-card-header {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-secondary);
}}
.ia-card-header h3 {{
    margin: 0 !important;
    font-size: 0.95rem !important;
    font-weight: 700 !important;
}}
.ia-card-accent {{ border-left: 3px solid var(--accent); }}
.ia-compare-col-head {{
    font-weight: 700;
    font-size: 0.95rem;
    color: var(--text-primary);
    margin-bottom: 0.35rem;
    padding: 0.35rem 0;
}}
.ia-compare-badge {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.5rem;
    height: 1.5rem;
    padding: 0 0.35rem;
    margin-right: 0.4rem;
    border-radius: var(--radius-sm);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    border: 1px solid var(--border-primary);
    vertical-align: middle;
}}
.ia-badge {{
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.2rem 0.65rem;
    border-radius: 100px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    text-transform: uppercase;
}}
.ia-badge-active {{
    background: var(--success-bg);
    color: var(--success);
    border: 1px solid var(--success);
}}
.ia-badge-idle {{
    background: var(--bg-tertiary);
    color: var(--text-tertiary);
    border: 1px solid var(--border-primary);
}}
.ia-badge-saved {{
    background: var(--info-bg);
    color: var(--info);
    border: 1px solid var(--info);
}}
.ia-meta {{
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
}}
.ia-meta-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.45rem 0;
    border-bottom: 1px solid var(--border-secondary);
}}
.ia-meta-row:last-child {{ border-bottom: none; }}
.ia-meta-label {{
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}
.ia-meta-value {{
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text-primary);
}}
.ia-empty {{
    text-align: center;
    padding: 1.5rem;
    color: var(--text-tertiary);
    font-size: 0.9rem;
}}
.eval-card {{
    background: var(--bg-card);
    border: 1px solid var(--border-primary);
    border-left: 4px solid var(--accent);
    padding: 1.25rem 1.5rem;
    border-radius: var(--radius-md);
    margin: 0.75rem 0;
}}
.eval-score {{
    font-size: 2rem;
    font-weight: 800;
    color: var(--accent);
}}
.eval-score-label {{
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}
[data-testid="stMetric"] {{
    background: var(--bg-card);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-md);
    padding: 0.75rem;
}}
/* Workspace nav uses native st.tabs */
[data-testid="stChatMessage"] {{
    border: 1px solid var(--border-primary);
    background: var(--bg-card) !important;
    border-radius: var(--radius-md);
}}
/* Workspace navigation — native st.tabs */
[data-testid="stMain"] .stTabs {{
    margin-bottom: 0.35rem !important;
}}
.stTabs [data-baseweb="tab-list"] {{
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border-primary) !important;
    border-radius: var(--radius-md);
    padding: 0.25rem !important;
    gap: 0.2rem !important;
}}
.stTabs [data-baseweb="tab"] {{
    color: var(--st-tab-inactive) !important;
    background: transparent !important;
    border-radius: var(--radius-sm) !important;
    font-size: 0.84rem !important;
    font-weight: 500 !important;
    padding: 0.4rem 0.65rem !important;
}}
.stTabs [data-baseweb="tab"] p,
.stTabs [data-baseweb="tab"] span {{
    color: inherit !important;
}}
.stTabs [data-baseweb="tab"]:hover {{
    background-color: var(--st-tab-hover-bg) !important;
    color: var(--st-tab-active) !important;
}}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{
    background-color: var(--st-btn-primary-bg) !important;
    color: var(--st-btn-primary-text) !important;
}}
.stTabs [data-baseweb="tab"][aria-selected="true"],
.stTabs [data-baseweb="tab"][aria-selected="true"] span,
.stTabs [data-baseweb="tab"][aria-selected="true"] p {{
    color: var(--st-btn-primary-text) !important;
    font-weight: 600 !important;
}}
.stTabs [data-baseweb="tab-highlight"] {{
    display: none !important;
}}
.stTabs [data-baseweb="tab-border"] {{
    display: none !important;
}}
{streamlit_layer}
{dark_patch}
</style>"""


def inject_theme() -> None:
    """Inject fonts + CSS for light/dark mode from session state."""
    dark = st.session_state.get("dark_mode", False)
    st.markdown(_FONT_IMPORT, unsafe_allow_html=True)
    st.markdown(_build_app_css(dark=dark), unsafe_allow_html=True)


def card_open(title: str = "", icon: str = "", accent: bool = False) -> str:
    """Opening HTML for a card wrapper."""
    cls = "ia-card ia-card-accent" if accent else "ia-card"
    header = ""
    if title:
        header = f'<div class="ia-card-header"><span>{icon}</span><h3>{title}</h3></div>'
    return f'<div class="{cls}">{header}'


def card_close() -> str:
    return "</div>"


def render_card_html(
    title: str = "", icon: str = "", content: str = "", accent: bool = False
) -> str:
    """Complete card HTML block."""
    return f"{card_open(title, icon, accent)}{content}{card_close()}"


def render_badge(text: str, variant: str = "idle") -> str:
    """Status badge HTML."""
    return f'<span class="ia-badge ia-badge-{variant}">{text}</span>'


def render_meta_row(label: str, value: str) -> str:
    """Metadata key-value row."""
    return (
        f'<div class="ia-meta-row">'
        f'<span class="ia-meta-label">{label}</span>'
        f'<span class="ia-meta-value">{value}</span>'
        f"</div>"
    )


def render_empty_state(icon: str, text: str) -> str:
    """Empty state placeholder."""
    return (
        f'<div class="ia-empty">'
        f'<div class="ia-empty-icon">{icon}</div>'
        f'<div class="ia-empty-text">{text}</div>'
        f"</div>"
    )


def _pill(text: str) -> str:
    safe = html.escape(text.strip() or "—")
    return f'<span class="ia-pill" title="{safe}">{safe}</span>'


def render_configuration_pill_bar(*, settings: UISettings) -> str:
    """
    Compact recruiter-friendly setup summary (main area, top of workspace).

    Shows role context by default; model sampling lives in a collapsed
    ``<details>`` block for technical reviewers.
    """
    if settings.usage_mode == "byo":
        usage_pill = "Personal API key"
    else:
        usage_pill = "Demo access"

    role_label = (settings.role_title or "").strip() or "Set role title"
    visible_pills = [
        _pill(usage_pill),
        _pill(role_label),
        _pill(settings.seniority),
        _pill(settings.interview_round),
        _pill(settings.interview_focus),
    ]
    technical_pills = [
        _pill(sidebar_label_for_preset(settings.model_preset)),
        _pill(f"Temperature · {settings.temperature:.2f}"),
        _pill(f"Top P · {settings.top_p:.2f}"),
        _pill(f"Max tokens · {settings.max_tokens}"),
    ]
    return (
        '<div class="ia-config-card" aria-label="Current setup summary">'
        '<div class="ia-config-card-header">Current Setup</div>'
        f'<div class="ia-config-chips">{"".join(visible_pills)}</div>'
        '<details class="ia-config-tech">'
        "<summary>Technical settings</summary>"
        f'<div class="ia-config-chips ia-config-chips-tech">{"".join(technical_pills)}</div>'
        "</details>"
        "</div>"
    )
