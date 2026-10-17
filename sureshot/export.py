"""Assemble the full Sureshot case package as a single Markdown document."""

from __future__ import annotations

from datetime import datetime

from sureshot.phases import PHASES

CHECKLIST = (
    "Are we answering the actual prompt? (re-read the colour-coded breakdown)",
    "Is the analysis MECE? (no overlaps, no gaps)",
    "Is every recommendation backed by numbers? (if not, go back to research)",
    "Is any slide too text-heavy? (convert words into a visual framework)",
    "Too theoretical? (implementation roadmap, risk mitigation and ROI must be present)",
)


def build_package(
    *,
    case_name: str,
    case_prompt: str,
    results: dict[str, str],
    slide_limit: int | None,
    budget_hours: float,
    team_size: int,
) -> str:
    """Build the complete case package: prompt, all five phases, quality checklist."""
    name = (case_name or "").strip() or "Untitled case"
    lines: list[str] = [f"# {name} — Sureshot case package", ""]

    scope: list[str] = []
    if budget_hours:
        scope.append(f"time budget {budget_hours:g}h")
    if slide_limit:
        scope.append(f"slide limit {slide_limit}")
    scope.append(f"team of {team_size}")

    lines += [
        f"_Generated {datetime.now():%d %b %Y, %H:%M} · Sureshot case-solving algorithm_",
        "",
        f"_Scope: {' · '.join(scope)}_",
        "",
    ]

    if case_prompt.strip():
        lines += ["## Case prompt", ""]
        quoted: list[str] = []
        prev_blank = False
        for ln in case_prompt.strip().splitlines():
            blank = not ln.strip()
            if blank and prev_blank:
                continue
            quoted.append(">" if blank else f"> {ln}")
            prev_blank = blank
        lines += quoted
        lines += [""]
        lines += ["---", ""]

    for p in PHASES:
        text = (results.get(p.id) or "").strip()
        lines += [f"## Phase {p.num} — {p.title}", ""]
        lines += [text if text else "_Not completed._", ""]
        lines += ["---", ""]

    lines += ["## Sureshot quality checklist", ""]
    lines += [f"- [ ] {item}" for item in CHECKLIST]
    lines += [
        "",
        f"*Package assembled with Sureshot — "
        f"{sum(1 for p in PHASES if (results.get(p.id) or '').strip())}/{len(PHASES)} phases completed.*",
    ]
    return "\n".join(lines)


def package_filename(case_name: str) -> str:
    """A safe .md filename derived from the case name."""
    cleaned = "".join(c for c in (case_name or "") if c.isalnum() or c in " -_").strip()
    slug = cleaned.replace(" ", "_") or "case"
    return f"{slug}_sureshot_package.md"
