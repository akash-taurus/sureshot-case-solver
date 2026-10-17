"""Sureshot — run the 5-phase case-solving algorithm (flow.md) on any case.

Entry point: `streamlit run streamlit_app.py`
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import TYPE_CHECKING

import streamlit as st

from sureshot.export import build_package, package_filename
from sureshot.llm import (
    DEFAULT_BASE_URL,
    PROVIDERS,
    fallback_models,
    fetch_models,
    make_client,
    stream_chat,
)
from sureshot.phases import PHASE_BY_ID, PHASES, Phase, cumulative_share
from sureshot.prompts import SYSTEM_PROMPTS, build_user_message

if TYPE_CHECKING:
    from openai import OpenAI

st.set_page_config(
    page_title="Sureshot — case solver",
    page_icon=":material/target:",
    layout="wide",
)

EXPORT_ID = "export"
STEPPER_IDS = [p.id for p in PHASES] + [EXPORT_ID]

SAMPLE_CASE = """VoltForge Components — board brief (practice case)

VoltForge is a ₹4,200 crore Indian maker of battery-pack components for electric two-wheelers. Its three plants run at 68% utilisation and EBITDA margin fell from 12.4% to 8.1% over FY23–FY25: Chinese imports now price 18% below domestic quotes, and OEM customers push annual price-downs of 4–6%.

The board wants a decision at the June meeting: should VoltForge
(a) double down on domestic OEM supply,
(b) pivot its component line to exports for Southeast Asian assemblers, or
(c) integrate forward into full battery-pack assembly for fleet operators?

Constraints: ₹350 crore capital available; any new capacity must be EBITDA-positive within 8 quarters; PLI incentives cover cells but not our component line; the union agreement blocks layoffs at the Pune plant until FY27.

Data provided: FY23–FY25 P&L by plant; top-10 customer concentration (top 3 = 61% of revenue); landed-cost teardowns of 4 competitor packs; a Southeast Asia demand model for 2W packs (2024: 1.1M units, CAGR 24%); a bolt-on acquisition shortlist (3 targets).

Deliver: a 10-slide investor-grade deck with a clear recommendation, the financial case (ROI, payback), an implementation roadmap and a risk register. Anything beyond 10 slides goes in the appendix.
"""


# --------------------------------------------------------------------------- #
# Session state
# --------------------------------------------------------------------------- #
def _secret(name: str) -> str:
    try:
        return str(st.secrets.get(name) or "")
    except Exception:
        return ""


def _initial_provider() -> str:
    if _secret(PROVIDERS["Groq"]["secret"]):
        return "Groq"
    if _secret(PROVIDERS["NVIDIA NIM"]["secret"]):
        return "NVIDIA NIM"
    return "Groq"  # recommended default; user can paste a key in the sidebar


_provider_default = _initial_provider()
_default_is_groq = "groq.com" in PROVIDERS[_provider_default]["base_url"]

for _key, _default in {
    "phase": PHASES[0].id,
    "results": {},  # phase id -> markdown
    "meta": {},  # phase id -> "model · time"
    "case_name": "",
    "case_prompt": "",
    "provider": _provider_default,
    "api_key": _secret(PROVIDERS[_provider_default]["secret"]),
    "base_url": PROVIDERS[_provider_default]["base_url"],
    "model": PROVIDERS[_provider_default]["model"],
    "temperature": 0.4,
    # Groq's free tier counts input + reserved output against 8k tokens/min.
    "max_tokens": 3072 if _default_is_groq else 4096,
    "budget_hours": 5.0,
    "team_size": 4,
    "slide_limit_manual": 0,
    "detected_slide_limit": None,
    "timer_start": None,
}.items():
    st.session_state.setdefault(_key, _default)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _goto(pid: str) -> None:
    st.session_state.phase = pid


def _apply_provider() -> None:
    """Provider preset: swap base URL, key (from secrets) and default model."""
    cfg = PROVIDERS.get(st.session_state.get("provider", "Groq"))
    if not cfg:
        return
    st.session_state.base_url = cfg["base_url"]
    st.session_state.model = cfg["model"]
    st.session_state.max_tokens = 3072 if "groq.com" in cfg["base_url"] else 4096
    secret = _secret(cfg["secret"])
    if secret:
        st.session_state.api_key = secret


def _start_timer() -> None:
    st.session_state.timer_start = time.time()


def _reset_timer() -> None:
    st.session_state.timer_start = None


def _load_sample() -> None:
    st.session_state.case_prompt = SAMPLE_CASE
    if not st.session_state.case_name.strip():
        st.session_state.case_name = "VoltForge board brief"


def _clear_prompt() -> None:
    st.session_state.case_prompt = ""


def _reset_case() -> None:
    st.session_state.results = {}
    st.session_state.meta = {}
    st.session_state.case_name = ""
    st.session_state.case_prompt = ""
    st.session_state.detected_slide_limit = None
    st.session_state.timer_start = None
    st.session_state.phase = PHASES[0].id
    for p in PHASES:
        for prefix in ("notes_", "feedback_", "edit_", "view_"):
            st.session_state.pop(f"{prefix}{p.id}", None)


def _edit_cb(pid: str) -> None:
    st.session_state.results[pid] = st.session_state.get(f"edit_{pid}", "")


def _phase_label(pid: str) -> str:
    if pid == EXPORT_ID:
        return ":material/download: 6. Export"
    p = PHASE_BY_ID[pid]
    return f"{p.icon} {p.num}. {p.title}"


def _fmt_dhm(seconds: float) -> str:
    minutes = max(0, int(seconds)) // 60
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins:02d}m" if hours else f"{mins}m"


def _result(pid: str) -> str:
    return (st.session_state.results.get(pid) or "").strip()


def _effective_slide_limit() -> int | None:
    manual = int(st.session_state.get("slide_limit_manual") or 0)
    if manual > 0:
        return manual
    return st.session_state.get("detected_slide_limit")


def _context_budget(base_url: str) -> int:
    """Chars allowed for the user message. Free tiers count input + reserved output
    against a per-minute token cap (Groq: 8k TPM for gpt-oss-120b), so keep requests
    there compact; other endpoints get a generous budget."""
    return 12000 if "groq.com" in base_url else 40000


@st.cache_resource(show_spinner=False)
def _cached_client(base_url: str, api_key: str) -> OpenAI:
    return make_client(base_url, api_key)


@st.fragment(run_every="5s")
def _timer_tick() -> None:
    start = st.session_state.get("timer_start")
    if not start:
        return
    elapsed = time.time() - start
    pid = st.session_state.get("phase", PHASES[0].id)
    if pid == EXPORT_ID:
        target_s = st.session_state.budget_hours * 3600
        label = "wrap-up target"
    else:
        p = PHASE_BY_ID[pid]
        target_s = st.session_state.budget_hours * cumulative_share(p.id) * 3600
        label = f"phase {p.num} target"
    badge = ":green-badge[on pace]" if elapsed <= target_s else ":orange-badge[behind]"
    st.markdown(
        f":material/timer: **{_fmt_dhm(elapsed)}** elapsed · {label} ≤ {_fmt_dhm(target_s)} {badge}"
    )


# --------------------------------------------------------------------------- #
# Phase workspace
# --------------------------------------------------------------------------- #
def render_phase(p: Phase) -> None:
    st.subheader(f"Phase {p.num} — {p.title}", icon=p.icon)
    target = _fmt_dhm(st.session_state.budget_hours * cumulative_share(p.id) * 3600)
    st.caption(f"{int(p.time_share * 100)}% of your budget · clock target ≤ {target} · {p.goal}")
    with st.expander("What the algorithm asks for in this phase", icon=":material/checklist:"):
        for step in p.steps:
            st.markdown(f"- {step}")

    api_key = st.session_state.get("api_key", "").strip()

    if p.num == 1:
        st.text_area(
            "Case prompt",
            key="case_prompt",
            height=260,
            persist_state="session",
            placeholder=(
                "Paste the full problem statement here — the ask, constraints, "
                "available data, deliverables and slide limits…"
            ),
        )
        with st.container(horizontal=True):
            st.button("Load sample case", icon=":material/science:", on_click=_load_sample)
            st.button("Clear prompt", icon=":material/delete:", on_click=_clear_prompt)
    else:
        with st.expander(p.notes_label, icon=":material/edit_note:"):
            st.text_area(
                "Notes",
                key=f"notes_{p.id}",
                height=150,
                label_visibility="collapsed",
                persist_state="session",
                placeholder=p.notes_placeholder,
            )

    case_prompt = st.session_state.get("case_prompt", "").strip()
    feedback = st.text_input(
        "Steering feedback for the next run",
        key=f"feedback_{p.id}",
        persist_state="session",
        placeholder="Optional — e.g. go more aggressive on market entry; use FY25 numbers; keep it under 400 words",
    )

    result = _result(p.id)
    run = st.button(
        f"Regenerate phase {p.num}" if result else f"Run {p.run_label}",
        type="primary",
        icon=":material/play_arrow:",
        disabled=not (api_key and case_prompt),
    )
    if not api_key:
        st.caption(
            ":orange-badge[key required] — add your API key in the sidebar under Model setup"
        )
    elif not case_prompt:
        st.caption(":orange-badge[case prompt required] — paste the problem statement in phase 1")

    result_area = st.container()
    just_streamed = False

    if run:
        user_message = build_user_message(
            phase_id=p.id,
            case_prompt=case_prompt,
            prior=[(q.num, q.title, _result(q.id)) for q in PHASES if q.num < p.num and _result(q.id)],
            notes=st.session_state.get(f"notes_{p.id}", ""),
            feedback=feedback,
            slide_limit=_effective_slide_limit(),
            team_size=int(st.session_state.team_size),
            context_budget_chars=_context_budget(
                st.session_state.base_url.strip() or DEFAULT_BASE_URL
            ),
        )
        model = st.session_state.model
        with result_area, st.container(border=True):
            status_line = st.empty()
            status_line.caption(
                f":shimmer[:material/progress_activity: {model} is thinking — "
                f"a cold start can take ~30s before the first token]"
            )
            try:
                client = _cached_client(
                    st.session_state.base_url.strip() or DEFAULT_BASE_URL, api_key
                )
                streamed = st.write_stream(
                    stream_chat(
                        client,
                        model=model,
                        system=SYSTEM_PROMPTS[p.id],
                        user=user_message,
                        temperature=float(st.session_state.temperature),
                        max_tokens=int(st.session_state.max_tokens),
                    ),
                    cursor="▌",
                )
                text = streamed.strip() if isinstance(streamed, str) else ""
                st.session_state.results[p.id] = text
                st.session_state[f"edit_{p.id}"] = text
                st.session_state.meta[p.id] = f"{model} · {datetime.now():%H:%M}"
                if p.num == 1:
                    match = re.search(r"\*\*Slide limit:\*\*\s*(\d{1,3})", text)
                    st.session_state.detected_slide_limit = (
                        int(match.group(1)) if match else None
                    )
                just_streamed = True
                status_line.caption(f"Result · {st.session_state.meta[p.id]}")
                st.toast(f"Phase {p.num} complete", icon=":material/check_circle:")
            except Exception as exc:
                status_line.empty()
                status = getattr(exc, "status_code", None)
                name = type(exc).__name__
                if status == 403:
                    hint = (
                        " — this model isn't enabled for your key, or a temporary rate "
                        "limit hit. Try another model from the sidebar list."
                    )
                elif status == 429:
                    hint = " — rate limit reached. Wait a few seconds and retry."
                elif status == 413:
                    hint = (
                        " — the request exceeded this endpoint's per-minute token limit. "
                        "Lower *Max output tokens* in the sidebar, or trim long notes."
                    )
                elif status in (404, 410):
                    hint = " — model retired or not found. Pick another model in the sidebar."
                elif "Timeout" in name:
                    hint = (
                        " — the model didn't respond in time. Retry, or switch to a "
                        "faster model in the sidebar."
                    )
                else:
                    hint = ""
                st.error(f"Model call failed — {name}: {exc}{hint}", icon=":material/error:")

    if _result(p.id) and not just_streamed:
        with result_area, st.container(border=True):
            st.caption(f"Result · {st.session_state.meta.get(p.id, '')}")
            view = st.segmented_control(
                "Result view",
                ["Preview", "Edit"],
                key=f"view_{p.id}",
                default="Preview",
                label_visibility="collapsed",
            )
            if view == "Edit":
                st.text_area(
                    "Edit result",
                    key=f"edit_{p.id}",
                    height=420,
                    label_visibility="collapsed",
                    on_change=_edit_cb,
                    args=(p.id,),
                    persist_state="session",
                )
            else:
                st.markdown(_result(p.id))

    idx = [q.id for q in PHASES].index(p.id)
    with st.container(horizontal=True):
        if idx > 0:
            prev = PHASES[idx - 1]
            st.button(
                f"Back to phase {prev.num}",
                icon=":material/arrow_back:",
                on_click=_goto,
                args=(prev.id,),
            )
        if idx + 1 < len(PHASES):
            nxt = PHASES[idx + 1]
            verb = "Continue" if _result(p.id) else "Skip"
            st.button(
                f"{verb} to phase {nxt.num} — {nxt.title}",
                icon=":material/arrow_forward:",
                on_click=_goto,
                args=(nxt.id,),
            )
        else:
            st.button(
                "Continue to export package",
                icon=":material/download:",
                on_click=_goto,
                args=(EXPORT_ID,),
            )


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
def render_export() -> None:
    st.subheader("Export package", icon=":material/download:")
    st.caption(
        "Every completed phase, assembled into one Markdown package — "
        "for the team, your notes, or the submission appendix."
    )

    done = sum(1 for p in PHASES if _result(p.id))
    missing = [p.title for p in PHASES if not _result(p.id)]
    c1, c2, c3 = st.columns(3)
    c1.metric("Phases complete", f"{done}/5")
    limit = _effective_slide_limit()
    c2.metric("Slide limit", f"{limit} slides" if limit else "not set")
    start = st.session_state.get("timer_start")
    c3.metric("Time on the clock", _fmt_dhm(time.time() - start) if start else "timer off")

    if missing:
        st.warning(
            f"Not run yet: {', '.join(missing)} — they'll appear as “Not completed”.",
            icon=":material/warning:",
        )

    package = build_package(
        case_name=st.session_state.case_name,
        case_prompt=st.session_state.case_prompt,
        results=st.session_state.results,
        slide_limit=limit,
        budget_hours=float(st.session_state.budget_hours),
        team_size=int(st.session_state.team_size),
    )
    st.download_button(
        "Download case package (.md)",
        data=package,
        file_name=package_filename(st.session_state.case_name),
        mime="text/markdown",
        icon=":material/download:",
        type="primary",
    )
    with st.expander("Preview the package", expanded=True, icon=":material/description:"):
        st.markdown(package)
    st.caption(
        "Markdown renders on GitHub, mermaid issue tree included. "
        "Paste sections into slide templates (Slide Geeks, Slidesgo) or Notion."
    )


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #
st.title(st.session_state.case_name.strip() or "Untitled case", icon=":material/target:")
st.caption(
    "Deconstruct → hypothesise → research → build → defend. "
    "Run each phase with the model, steer it with feedback, then export the package."
)

_phase_selection = st.pills(
    "Algorithm step",
    STEPPER_IDS,
    format_func=_phase_label,
    key="phase",
    required=True,
    label_visibility="collapsed",
)

with st.sidebar:
    st.markdown("#### :material/target: Sureshot")
    st.caption("The 5-phase case-solving algorithm — live.")

    with st.expander(
        "Model setup", icon=":material/settings:", expanded=not st.session_state.api_key.strip()
    ):
        st.segmented_control(
            "Provider preset",
            list(PROVIDERS),
            key="provider",
            on_change=_apply_provider,
            help="Swaps the base URL, API key (from secrets, if present) and default model. "
            "Paste a key manually or edit the base URL for any other OpenAI-compatible endpoint.",
        )
        st.text_input(
            "API key",
            type="password",
            key="api_key",
            placeholder="gsk_… or nvapi-…",
            help="Free keys: console.groq.com (Groq) or build.nvidia.com (NIM). "
            "Or set `groq_api_key` / `nvidia_api_key` in .streamlit/secrets.toml.",
        )
        st.text_input(
            "Base URL",
            key="base_url",
            help="Any OpenAI-compatible endpoint (Groq, NIM, OpenAI, OpenRouter, Ollama…).",
        )
        api_key = st.session_state.api_key.strip()
        base_url = st.session_state.base_url.strip() or DEFAULT_BASE_URL
        options: list[str] = fallback_models(base_url)
        fetched: list[str] = []
        if api_key:
            try:
                fetched = fetch_models(base_url, api_key)
                if fetched:
                    options = fetched
            except Exception:
                st.caption(":orange-badge[model list offline] — type any model id below")
        current = st.session_state.model
        if fetched and current not in fetched:
            st.caption(
                ":orange-badge[selected model not in the live list] — it may be retired "
                "or not enabled for this key"
            )
        if current not in options:
            options = [current, *options]
        st.selectbox(
            "Model",
            options,
            key="model",
            accept_new_options=True,
            help="Live list from the endpoint; you can also type any model id from build.nvidia.com.",
        )
        st.slider("Temperature", min_value=0.0, max_value=1.0, step=0.05, key="temperature")
        st.number_input(
            "Max output tokens", min_value=512, max_value=8192, step=256, key="max_tokens"
        )

    st.markdown("#### Case setup")
    st.text_input("Case name", key="case_name", placeholder="e.g. VoltForge board brief")
    setup_left, setup_right = st.columns(2)
    setup_left.number_input(
        "Budget (hours)", min_value=0.5, max_value=48.0, step=0.5, key="budget_hours"
    )
    setup_right.number_input("Team size", min_value=1, max_value=6, step=1, key="team_size")
    st.number_input(
        "Slide limit (0 = auto)",
        min_value=0,
        max_value=75,
        step=1,
        key="slide_limit_manual",
        help="Algorithm rule: if you don't know the slide limit, stop and find out. Phase 1 detects it from the prompt; set it here to override.",
    )
    if st.session_state.detected_slide_limit:
        st.caption(f"Detected from the prompt: {st.session_state.detected_slide_limit} slides")

    progress_done = sum(1 for p in PHASES if _result(p.id))
    st.markdown(f"#### Progress — {progress_done}/5 phases")
    for p in PHASES:
        icon = ":material/check_circle:" if _result(p.id) else ":material/radio_button_unchecked:"
        target = _fmt_dhm(st.session_state.budget_hours * cumulative_share(p.id) * 3600)
        st.markdown(f"{icon} **{p.num}. {p.title}** · {int(p.time_share * 100)}% · ≤ {target}")

    st.markdown("#### Clock")
    if st.session_state.timer_start is None:
        st.button("Start timer", icon=":material/timer:", on_click=_start_timer)
    else:
        _timer_tick()
        st.button("Reset timer", icon=":material/timer_off:", on_click=_reset_timer)

    st.button(
        "Start a new case",
        icon=":material/restart_alt:",
        on_click=_reset_case,
        help="Clears every phase result, note and the clock.",
    )

if _phase_selection == EXPORT_ID:
    render_export()
else:
    render_phase(PHASE_BY_ID[_phase_selection or PHASES[0].id])
