"""Streamlit sidebar: deployment, appearance, role, interview setup, saved sessions.

Model preset, question difficulty mode, sampling parameters, and optional prompt debug
flow through `UISettings` into services and the OpenAI client.
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
    TECHNICAL_CATEGORIES,
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
    MODEL_PRESET_LABELS,
    MODEL_PRESET_SIDEBAR_OPTIONS,
    ModelConfig,
)
from interview_app.prompts.personas import PERSONA_KEYS
from interview_app.storage.sessions import (
    delete_all_sessions,
    delete_session,
    list_sessions,
    load_session,
)
from interview_app.ui.sidebar_deployment import render_sidebar_deployment_content
from interview_app.ui.sidebar_diagnostics import render_sidebar_diagnostics
from interview_app.ui.usage_mode_panel import render_usage_mode_setup
from interview_app.utils.language import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    get_language_name,
    langdetect_available,
)


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


def render_sidebar_configuration() -> UISettings:
    """
    Render the full configuration sidebar and return a frozen `UISettings` snapshot.

    Sections: Session setup, Interview configuration, Advanced settings (collapsed),
    Saved sessions (collapsed). Developer diagnostics when enabled (dev + SHOW_DIAGNOSTICS).
    """
    sb = st.sidebar

    render_usage_mode_setup()

    sb.divider()

    # ── Interview configuration ──
    _sidebar_section_title(
        "Interview configuration",
        "Target role, interview stage, and response settings.",
    )
    role_category = sb.selectbox(
        "Category",
        options=list(ROLE_CATEGORIES),
        index=0,
        help="Job family for tailored scenarios.",
    )
    seniority = sb.selectbox(
        "Seniority",
        options=list(SENIORITY_OPTIONS),
        index=2,
        help="Level you are targeting.",
    )
    placeholder = role_title_placeholder(role_category)
    role_title_raw = sb.text_input(
        "Role title",
        value="",
        placeholder=placeholder,
        help="Exact title as listed on the job posting or target role.",
    )
    job_description = sb.text_area(
        "Job description",
        value="",
        height=100,
        placeholder="Paste the job description or key requirements (recommended).",
        help="Optional; strongly recommended for realistic prompts.",
    )

    focus_options = build_focus_options(role_category, seniority)
    if st.session_state.get("interview_focus_sel") not in focus_options:
        st.session_state.interview_focus_sel = focus_options[0]

    interview_round = sb.selectbox(
        "Interview round",
        options=list(INTERVIEW_ROUNDS),
        index=0,
        help="Hiring stage to simulate.",
        key="ia_interview_round_select",
    )
    if st.session_state.get("_ia_round_tracker") != interview_round:
        st.session_state._ia_round_tracker = interview_round
        focus_opts = build_focus_options(role_category, seniority)
        d = default_focus_for_round(interview_round)
        st.session_state.interview_focus_sel = d if d in focus_opts else focus_opts[0]
        st.session_state.persona_sel = default_persona_for_round(
            interview_round, persona_keys=PERSONA_KEYS
        )

    focus_options = build_focus_options(role_category, seniority)
    if st.session_state.get("interview_focus_sel") not in focus_options:
        st.session_state.interview_focus_sel = focus_options[0]

    sb.selectbox(
        "Interview focus",
        options=focus_options,
        key="interview_focus_sel",
        help="Skills and format to emphasize.",
    )
    sb.selectbox(
        "Interviewer persona",
        options=list(PERSONA_KEYS),
        key="persona_sel",
        help="Who is asking and how they evaluate.",
    )

    if "ia_question_difficulty_mode" not in st.session_state:
        st.session_state.ia_question_difficulty_mode = QUESTION_DIFFICULTY_SIDEBAR_MODES[0]
    sb.selectbox(
        "Question difficulty",
        options=list(QUESTION_DIFFICULTY_SIDEBAR_MODES),
        key="ia_question_difficulty_mode",
        help="Auto infers level from seniority and round. Easy / Medium / Hard fix the calibrated level for "
        "Interview Questions, mock interview, and Feedback / Evaluation.",
    )

    lang_options = ["Auto (detect)"] + [
        f"{name} ({code})" for code, name in SUPPORTED_LANGUAGES.items()
    ]
    current = st.session_state.get("response_language")
    if current:
        try:
            lidx = list(SUPPORTED_LANGUAGES.keys()).index(current) + 1
        except ValueError:
            lidx = 0
    else:
        lidx = 0
    lang_choice = sb.selectbox(
        "Response language",
        options=lang_options,
        index=lidx,
        help="Output language for model responses.",
        key="ia_response_lang_select",
    )
    if lang_choice == "Auto (detect)":
        st.session_state.response_language = None
    else:
        code = lang_choice.split("(")[-1].rstrip(")")
        st.session_state.response_language = (
            code if code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        )
    if current:
        sb.caption(f"Active: {get_language_name(current)}")
    if lang_choice == "Auto (detect)" and not langdetect_available():
        sb.warning(
            "Install `langdetect` for automatic language detection (`pip install langdetect`)."
        )

    if role_category in TECHNICAL_CATEGORIES:
        sb.caption("Technical and architecture-style content is emphasized.")

    interview_focus = str(st.session_state.get("interview_focus_sel", focus_options[0]))
    persona = str(st.session_state.get("persona_sel", PERSONA_KEYS[1]))

    with sb.expander("Advanced settings", expanded=False):
        sb.caption("Appearance, model tuning, and workspace shortcuts.")
        dark = sb.toggle(
            "Dark mode",
            value=st.session_state.get("dark_mode", False),
            key="dark_mode_toggle",
            help="Switch between light and dark theme.",
        )
        if dark != st.session_state.get("dark_mode", False):
            st.session_state.dark_mode = dark
            st.rerun()

        sb.markdown("**Prompt strategy**")
        strategy_labels = [lbl for lbl, _ in PROMPT_STRATEGY_OPTIONS]
        selected_label = sb.selectbox(
            "Prompt strategy",
            options=strategy_labels,
            key="ia_prompt_strategy_select",
            help="Choose a prompting technique. Use “Compare Prompt Strategies” on the Interview Questions tab to preview several at once.",
        )
        prompt_strategy = prompt_strategy_key_from_label(selected_label)

        allowed_model_keys = tuple(k for _, k in MODEL_PRESET_SIDEBAR_OPTIONS)
        if "ia_model_preset_select" not in st.session_state:
            st.session_state.ia_model_preset_select = DEFAULT_MODEL_PRESET_KEY

        sb.markdown("**Generation**")
        sb.selectbox(
            "Model",
            options=list(allowed_model_keys),
            key="ia_model_preset_select",
            format_func=lambda k: MODEL_PRESET_LABELS[k],
            help="OpenAI model for interview questions, mock interview, feedback, and CV prep.",
        )
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

        sb.checkbox(
            "Show debug prompts",
            key="ia_show_debug",
            help="Show effective system/user prompts and parameters on workspace tabs when available.",
        )
        sb.slider(
            "Temperature",
            min_value=0.0,
            max_value=2.0,
            step=0.05,
            key="ia_gen_temperature",
            help="Higher values increase variety; lower values are more focused and deterministic.",
        )
        sb.slider(
            "Top-p",
            min_value=0.0,
            max_value=1.0,
            step=0.01,
            key="ia_gen_top_p",
            help="Nucleus sampling: considers tokens up to this cumulative probability mass.",
        )
        sb.number_input(
            "Max tokens",
            min_value=1,
            max_value=32000,
            step=50,
            key="ia_gen_max_tokens",
            help="Upper bound on the length of each model response.",
        )

        sb.markdown("**Workspace shortcuts**")
        b1, b2, b3 = sb.columns(3)
        with b1:
            if sb.button(
                "Generate questions",
                use_container_width=True,
                key="sb_btn_generate",
                help="Open Interview Questions and run generation.",
            ):
                st.session_state.ia_workspace_tab = WORKSPACE_TAB_LABELS[1]
                st.session_state.ia_pending_generate = True
                st.rerun()
        with b2:
            if sb.button(
                "CV prep",
                use_container_width=True,
                key="sb_btn_cv",
                help="Open CV-based interview preparation.",
            ):
                st.session_state.ia_workspace_tab = WORKSPACE_TAB_LABELS[2]
                st.rerun()
        with b3:
            if sb.button(
                "Mock interview",
                use_container_width=True,
                key="sb_btn_mock",
                help="Open the live chat workspace.",
            ):
                st.session_state.ia_workspace_tab = WORKSPACE_TAB_LABELS[0]
                st.rerun()

        if sb.button(
            "Reset transcript",
            use_container_width=True,
            key="sb_btn_reset",
            help="Clear chat messages; configuration stays as set.",
        ):
            clear_messages()
            st.session_state.current_session_id = None
            st.session_state.session_meta = None
            st.toast("Transcript cleared. Sidebar settings are unchanged.")
            st.rerun()

        with sb.expander("Developer notes", expanded=False):
            render_sidebar_deployment_content()

    # Resolve prompt strategy / model preset when advanced expander was not opened this run
    if "ia_prompt_strategy_select" in st.session_state:
        prompt_strategy = prompt_strategy_key_from_label(
            str(st.session_state.ia_prompt_strategy_select)
        )
    else:
        strategy_labels = [lbl for lbl, _ in PROMPT_STRATEGY_OPTIONS]
        prompt_strategy = prompt_strategy_key_from_label(strategy_labels[0])

    model_preset = str(st.session_state.get("ia_model_preset_select", DEFAULT_MODEL_PRESET_KEY))
    if model_preset not in MODEL_PRESETS:
        model_preset = DEFAULT_MODEL_PRESET_KEY
        st.session_state.ia_model_preset_select = DEFAULT_MODEL_PRESET_KEY

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

    sb.divider()

    with sb.expander("Saved sessions", expanded=False):
        _render_sidebar_session_list()
        _render_sidebar_delete_all_sessions()

    response_language = st.session_state.get("response_language") or DEFAULT_LANGUAGE
    _, role_title_trimmed = validate_role_title(role_title_raw)

    question_difficulty_mode = str(st.session_state.get("ia_question_difficulty_mode", "Auto"))
    temperature = float(st.session_state.ia_gen_temperature)
    top_p = float(st.session_state.ia_gen_top_p)
    max_tokens = int(st.session_state.ia_gen_max_tokens)
    show_debug = bool(st.session_state.get("ia_show_debug", False))
    effective_difficulty = infer_difficulty_from_context(
        seniority=seniority,
        interview_round=interview_round,
        manual_mode=question_difficulty_mode,
    )

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
        col_a, col_b, col_c = st.columns([2, 1, 1])
        with col_a:
            st.caption(f"**{title}**")
            if created:
                st.caption(created)
        with col_b:
            if st.button("Open", key=f"sb_open_{sid}", use_container_width=True):
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
        with col_c:
            if st.button(
                "Del",
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
