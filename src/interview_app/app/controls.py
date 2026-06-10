"""Streamlit sidebar: session access, interview profile, saved sessions.

Model preset, question difficulty mode, sampling parameters, and optional prompt debug
flow through `UISettings` into services and the OpenAI client. Advanced tuning controls
are hidden on the recruiter-facing demo branch; defaults are seeded in session state.
"""

from __future__ import annotations

import html

import streamlit as st

from interview_app.app.conversation_state import (
    clear_messages,
    load_session_into_state,
)
from interview_app.app.interview_form_config import (
    INTERVIEW_ROUNDS,
    QUESTION_DIFFICULTY_SIDEBAR_MODES,
    ROLE_CATEGORIES,
    SENIORITY_OPTIONS,
    build_focus_options,
    default_focus_for_round,
    default_persona_for_round,
    infer_difficulty_from_context,
    role_title_placeholder,
    validate_role_title,
)
from interview_app.app.ui_settings import (
    PROMPT_STRATEGY_OPTIONS,
    WORKSPACE_TAB_LABELS,
    UISettings,
    prompt_strategy_key_from_label,
)
from interview_app.app.usage_mode import KEY_BYO_KEY_HINT, KEY_USAGE_MODE, UsageMode
from interview_app.config.settings import show_sidebar_diagnostics
from interview_app.llm import MODEL_PRESETS
from interview_app.llm.model_settings import (
    DEFAULT_MODEL_PRESET_KEY,
    ModelConfig,
)
from interview_app.prompts.personas import PERSONA_KEYS
from interview_app.storage.sessions import (
    delete_all_sessions,
    delete_session,
    list_sessions,
    load_session,
)
from interview_app.ui.presentation import sanitize_recruiter_demo_session_state
from interview_app.ui.sidebar_diagnostics import render_sidebar_diagnostics
from interview_app.ui.usage_mode_panel import render_usage_mode_setup
from interview_app.utils.language import DEFAULT_LANGUAGE


def _session_defaults_for_preset(preset: ModelConfig) -> tuple[float, float, int]:
    """Initial temperature, top_p, max_tokens for session state (matches prior internal defaults)."""
    default_top_p = float(preset.default_top_p) if preset.default_top_p is not None else 1.0
    return (
        float(preset.default_temperature),
        default_top_p,
        int(preset.default_max_tokens or 800),
    )


def _sidebar_section_title(title: str, hint: str | None = None) -> None:
    st.sidebar.markdown(
        f'<p class="ia-sidebar-section">{html.escape(title)}</p>',
        unsafe_allow_html=True,
    )
    if hint:
        st.sidebar.caption(hint)


def _sidebar_branding() -> None:
    st.sidebar.markdown(
        """
<div class="ia-sidebar-brand" aria-label="App branding">
  <p class="ia-sidebar-brand-title">AI Interview Coach</p>
  <p class="ia-sidebar-brand-tagline">Practice smarter. Interview better.</p>
</div>
""",
        unsafe_allow_html=True,
    )


def _ensure_llm_control_defaults() -> None:
    """Seed model and sampling session keys when advanced sidebar controls are hidden."""
    if "ia_model_preset_select" not in st.session_state:
        st.session_state.ia_model_preset_select = DEFAULT_MODEL_PRESET_KEY

    model_preset = str(st.session_state.ia_model_preset_select)
    if model_preset not in MODEL_PRESETS:
        model_preset = DEFAULT_MODEL_PRESET_KEY
        st.session_state.ia_model_preset_select = DEFAULT_MODEL_PRESET_KEY

    tracked = st.session_state.get("_ia_model_preset_track")
    if tracked != model_preset:
        preset_cfg = MODEL_PRESETS[model_preset]
        t_sync, p_sync, m_sync = _session_defaults_for_preset(preset_cfg)
        st.session_state.ia_gen_temperature = t_sync
        st.session_state.ia_gen_top_p = p_sync
        st.session_state.ia_gen_max_tokens = m_sync
        st.session_state._ia_model_preset_track = model_preset

    preset = MODEL_PRESETS[model_preset]
    if "ia_gen_temperature" not in st.session_state:
        t0, p0, m0 = _session_defaults_for_preset(preset)
        st.session_state.ia_gen_temperature = t0
    if "ia_gen_top_p" not in st.session_state:
        _, p0, _ = _session_defaults_for_preset(preset)
        st.session_state.ia_gen_top_p = p0
    if "ia_gen_max_tokens" not in st.session_state:
        _, _, m0 = _session_defaults_for_preset(preset)
        st.session_state.ia_gen_max_tokens = m0

    if "ia_prompt_strategy_select" not in st.session_state:
        strategy_labels = [lbl for lbl, _ in PROMPT_STRATEGY_OPTIONS]
        st.session_state.ia_prompt_strategy_select = strategy_labels[0]


def _ensure_profile_defaults(*, interview_round: str, seniority: str) -> str:
    """Keep hidden profile fields on sensible defaults for the simplified sidebar."""
    if "ia_role_category" not in st.session_state:
        st.session_state.ia_role_category = ROLE_CATEGORIES[0]
    role_category = str(st.session_state.ia_role_category)

    if "ia_question_difficulty_mode" not in st.session_state:
        st.session_state.ia_question_difficulty_mode = QUESTION_DIFFICULTY_SIDEBAR_MODES[0]

    if st.session_state.get("response_language") is None:
        st.session_state.setdefault("ia_response_lang_select", "Auto (detect)")

    focus_options = build_focus_options(role_category, seniority)
    if st.session_state.get("interview_focus_sel") not in focus_options:
        st.session_state.interview_focus_sel = focus_options[0]

    if st.session_state.get("_ia_round_tracker") != interview_round:
        st.session_state._ia_round_tracker = interview_round
        focus_opts = build_focus_options(role_category, seniority)
        d = default_focus_for_round(interview_round)
        st.session_state.interview_focus_sel = d if d in focus_opts else focus_opts[0]
        st.session_state.persona_sel = default_persona_for_round(
            interview_round, persona_keys=PERSONA_KEYS
        )

    if "persona_sel" not in st.session_state:
        st.session_state.persona_sel = default_persona_for_round(
            interview_round, persona_keys=PERSONA_KEYS
        )

    return role_category


def render_sidebar_configuration() -> UISettings:
    """
    Render the full configuration sidebar and return a frozen `UISettings` snapshot.

    Recruiter demo: Getting started, Interview profile, Saved sessions.
    Developer diagnostics when enabled (dev + SHOW_DIAGNOSTICS).
    """
    sb = st.sidebar

    sanitize_recruiter_demo_session_state(dict(st.session_state))

    _sidebar_branding()
    render_usage_mode_setup()

    sb.divider()

    _sidebar_section_title(
        "Interview profile",
        "Tell us about the role you are preparing for.",
    )

    seniority = sb.selectbox(
        "Seniority",
        options=list(SENIORITY_OPTIONS),
        index=2,
        help="Level you are targeting.",
    )

    interview_round = sb.selectbox(
        "Interview round",
        options=list(INTERVIEW_ROUNDS),
        index=0,
        help="Hiring stage to simulate.",
        key="ia_interview_round_select",
    )

    role_category = _ensure_profile_defaults(
        interview_round=interview_round,
        seniority=seniority,
    )

    focus_options = build_focus_options(role_category, seniority)
    if st.session_state.get("interview_focus_sel") not in focus_options:
        st.session_state.interview_focus_sel = focus_options[0]

    placeholder = role_title_placeholder(role_category)
    role_title_raw = sb.text_input(
        "Target role",
        value="",
        placeholder=placeholder,
        help="Job title or role you want to practice for.",
    )

    sb.selectbox(
        "Focus area",
        options=focus_options,
        key="interview_focus_sel",
        help="Skills and topics to emphasize.",
    )

    job_description = sb.text_area(
        "Job description (optional)",
        value="",
        height=100,
        placeholder="Paste key requirements for more tailored questions.",
        help="Optional but recommended for realistic prompts.",
    )

    _ensure_llm_control_defaults()

    sb.divider()

    with sb.expander("Saved sessions", expanded=False):
        _render_sidebar_session_list()
        _render_sidebar_delete_all_sessions()

    response_language = st.session_state.get("response_language") or DEFAULT_LANGUAGE
    _, role_title_trimmed = validate_role_title(role_title_raw)

    interview_focus = str(st.session_state.get("interview_focus_sel", focus_options[0]))
    persona = str(st.session_state.get("persona_sel", PERSONA_KEYS[1]))

    question_difficulty_mode = str(st.session_state.get("ia_question_difficulty_mode", "Auto"))
    temperature = float(st.session_state.ia_gen_temperature)
    top_p = float(st.session_state.ia_gen_top_p)
    max_tokens = int(st.session_state.ia_gen_max_tokens)
    show_debug = False
    effective_difficulty = infer_difficulty_from_context(
        seniority=seniority,
        interview_round=interview_round,
        manual_mode=question_difficulty_mode,
    )

    prompt_strategy = prompt_strategy_key_from_label(
        str(st.session_state.get("ia_prompt_strategy_select", PROMPT_STRATEGY_OPTIONS[0][0]))
    )
    model_preset = str(st.session_state.get("ia_model_preset_select", DEFAULT_MODEL_PRESET_KEY))
    if model_preset not in MODEL_PRESETS:
        model_preset = DEFAULT_MODEL_PRESET_KEY
        st.session_state.ia_model_preset_select = DEFAULT_MODEL_PRESET_KEY

    usage_m = str(st.session_state.get(KEY_USAGE_MODE) or UsageMode.DEMO.value)
    byo_hint = st.session_state.get(KEY_BYO_KEY_HINT)
    byo_disp = byo_hint if usage_m == UsageMode.BYO.value else None

    settings = UISettings(
        role_category=role_category,
        role_title=role_title_trimmed,
        seniority=seniority,
        interview_round=interview_round,
        interview_focus=interview_focus,
        job_description=job_description,
        persona=persona,
        question_difficulty_mode=question_difficulty_mode,
        effective_question_difficulty=effective_difficulty,
        prompt_strategy=prompt_strategy,
        model_preset=model_preset,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        show_debug=show_debug,
        response_language=response_language,
        usage_mode=usage_m,
        byo_key_hint=byo_disp,
    )
    if show_sidebar_diagnostics():
        render_sidebar_diagnostics(settings)
    return settings


def _format_ts(raw: str) -> str:
    from datetime import datetime

    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%b %d · %H:%M")
    except (ValueError, TypeError):
        return raw[:16].replace("T", " ")


def _clear_session_if_deleted(deleted_id: str) -> None:
    """If the active session file was removed, reset in-memory chat state."""
    if st.session_state.get("current_session_id") != deleted_id:
        return
    st.session_state.current_session_id = None
    st.session_state.session_meta = None
    clear_messages()


def _render_sidebar_session_list() -> None:
    sessions = list_sessions(dict(st.session_state))
    if not sessions:
        st.caption("No saved sessions yet.")
        return

    for s in sessions[:10]:
        sid = s.get("id", "")
        title = s.get("title", "Untitled")
        created = _format_ts(s.get("created_at", ""))
        with st.container(border=True):
            st.markdown('<div class="ia-saved-session-card"></div>', unsafe_allow_html=True)
            st.caption(f"**{title}**")
            if created:
                st.caption(created)
            if st.button(
                "Open session",
                key=f"sb_open_{sid}",
                use_container_width=True,
            ):
                loaded = load_session(sid, dict(st.session_state))
                if loaded:
                    meta, messages = loaded
                    load_session_into_state(sid, meta, messages)
                    st.session_state.current_session_id = sid
                    st.session_state.ia_workspace_tab = WORKSPACE_TAB_LABELS[0]
                    st.toast("Session loaded. Open Mock Interview to continue.")
                    st.rerun()
                else:
                    st.error("**Load failed**")
                    st.caption(f"Could not load session {sid}.")
            if st.button(
                "Delete session",
                key=f"sb_del_{sid}",
                use_container_width=True,
                help="Delete this saved session",
            ):
                if delete_session(sid, dict(st.session_state)):
                    _clear_session_if_deleted(sid)
                    st.toast("Session deleted.")
                    st.rerun()
                else:
                    st.warning("Could not delete this session (file missing or not removable).")


def _render_sidebar_delete_all_sessions() -> None:
    """Optional bulk delete with a confirmation step."""
    key = "sb_confirm_delete_all"
    if key not in st.session_state:
        st.session_state[key] = False

    scoped_sessions = list_sessions(dict(st.session_state))
    has_sessions = bool(scoped_sessions)

    if not has_sessions and not st.session_state[key]:
        return

    if st.session_state[key]:
        st.warning("Delete **all** saved sessions? This cannot be undone.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Confirm", key="sb_del_all_yes", use_container_width=True):
                n = delete_all_sessions(dict(st.session_state))
                st.session_state[key] = False
                st.session_state.current_session_id = None
                st.session_state.session_meta = None
                clear_messages()
                st.toast(f"Deleted {n} session(s).")
                st.rerun()
        with c2:
            if st.button("Cancel", key="sb_del_all_no", use_container_width=True):
                st.session_state[key] = False
                st.rerun()
        return

    if st.button(
        "Delete all sessions",
        key="sb_del_all_start",
        use_container_width=True,
    ):
        st.session_state[key] = True
        st.rerun()
