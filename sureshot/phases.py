"""Phase metadata for the Sureshot case-solving algorithm (see flow.md)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Phase:
    id: str
    num: int
    title: str
    icon: str
    time_share: float  # fraction of the total time budget the algorithm allocates
    goal: str
    steps: tuple[str, ...]
    run_label: str
    notes_label: str
    notes_placeholder: str


PHASES: tuple[Phase, ...] = (
    Phase(
        id="deconstruct",
        num=1,
        title="Deconstruct",
        icon=":material/search:",
        time_share=0.10,
        goal="Understand exactly what the judges want.",
        steps=(
            "Read the problem statement twice.",
            "Highlight yellow: the main objective.",
            "Highlight blue: constraints (budget, time, regulations).",
            "Highlight green: available data.",
            "Highlight red: deliverables & slide limits.",
            "If you don't know the slide limit, stop and find out.",
            "Classify the core issue and pick exactly one.",
        ),
        run_label="deconstruction",
        notes_label="Extra context (optional)",
        notes_placeholder="Anything the brief implies but doesn't state — judging criteria you've heard about, format rules from the info session…",
    ),
    Phase(
        id="strategy",
        num=2,
        title="Strategic setup",
        icon=":material/account_tree:",
        time_share=0.20,
        goal="Build the skeleton before adding the meat.",
        steps=(
            "Write down your best guess of the answer immediately (initial hypothesis).",
            "If the data falsifies it, pivot; if it confirms it, build around it.",
            "Use a standard framework if it fits perfectly; otherwise customise one.",
            "Give a custom framework a catchy name and 3–5 pillars in the client's language.",
            "Build a MECE issue tree: no overlaps, no gaps.",
        ),
        run_label="strategic setup",
        notes_label="Facts & decisions to respect (optional)",
        notes_placeholder="Team decisions, facts you already verified, constraints from the brief that the hypothesis must respect…",
    ),
    Phase(
        id="research",
        num=3,
        title="Research & ideation",
        icon=":material/travel_explore:",
        time_share=0.30,
        goal="Gather the evidence and form the solution.",
        steps=(
            "Five-layer research dive: company, industry, customer, competitors, misc (regulation / ESG / tech).",
            "Triangulate — never rely on a single data point. Cite sources.",
            "Brainstorm individually first, then filter with the F.I.A. test (Feasibility, Impact, Alignment).",
            "Pre-mortem: imagine the solution failed — why? Build mitigations in.",
        ),
        run_label="research & ideation",
        notes_label="Your research data & sources (optional)",
        notes_placeholder="Paste statistics, report findings, URLs, interview quotes — the more real data you give, the sharper the synthesis.",
    ),
    Phase(
        id="build",
        num=4,
        title="The build",
        icon=":material/slideshow:",
        time_share=0.20,
        goal="Create a visually clean, top-down presentation.",
        steps=(
            "SCQA storyline: Situation → Complication → Question → Answer in the executive summary.",
            "Action titles: write the \u201cso what\u201d as the slide title.",
            "Slide economy: cut anything that doesn't support the storyline.",
            "Tie the recommendation to ROI, NPV, or cost savings.",
            "Insight on the slide, model in the appendix.",
        ),
        run_label="deck build",
        notes_label="Deck constraints & figures (optional)",
        notes_placeholder="Template rules, mandatory exhibits, numbers that must appear, house style, appendix requirements…",
    ),
    Phase(
        id="delivery",
        num=5,
        title="Delivery & defense",
        icon=":material/record_voice_over:",
        time_share=0.20,
        goal="Nail the presentation and the Q&A.",
        steps=(
            "Rehearse transitions — know exactly how you hand off to the next speaker.",
            "Q&A protocol: listen fully, stay composed, link the answer back to the core recommendation.",
            "Pass factual questions to the teammate who built that part.",
            "After the event: connect with judges and winning teams on LinkedIn.",
        ),
        run_label="delivery prep",
        notes_label="Team names & roles (optional)",
        notes_placeholder="e.g. Priya — finance & slides 3–4; Arjun — ops & slides 5–6; you — exec summary & close. Used for the hand-off plan.",
    ),
)

PHASE_BY_ID: dict[str, Phase] = {p.id: p for p in PHASES}


def cumulative_share(phase_id: str) -> float:
    """Share of the total budget that should be spent by the end of this phase."""
    total = 0.0
    for p in PHASES:
        total += p.time_share
        if p.id == phase_id:
            return total
    return 1.0
