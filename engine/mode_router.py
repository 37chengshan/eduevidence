"""Deterministic research-mode recommendation from a structured ResearchIntent.

The engine never classifies natural language; the Skill/model produces a
schema-valid ResearchIntent and the router maps its flags to a mode
deterministically. `decision_target` controls the requested deliverable;
`research_mode` controls lifecycle depth.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModeRecommendation:
    mode: str
    reasons: tuple[str, ...]
    requires_grounding_review: bool


def recommend_mode(intent: dict, *, explicit_mode: str | None = None,
                   project_has_grounding: bool = False) -> ModeRecommendation:
    """Recommend evidence_review vs full_research_cycle from intent flags.

    - explicit_mode wins, except when the intent already asks for data
      analysis: the data intent is preserved in a warning reason instead of
      being silently discarded.
    - A Full Research Cycle requires evidence grounding: when the project has
      no grounding yet, `requires_grounding_review` is True so the executor
      runs at least a minimum Evidence Review before designing a study.
    """
    reasons: list[str] = []
    wants_design = bool(intent.get("wants_study_design"))
    has_data = bool(intent.get("has_user_data"))
    wants_analysis = bool(intent.get("wants_data_analysis"))
    wants_update = bool(intent.get("wants_decision_update"))
    wants_existing = bool(intent.get("wants_existing_evidence"))

    full_cycle_flags = wants_design or has_data or wants_analysis or wants_update

    if explicit_mode is not None:
        if explicit_mode == "evidence_review" and wants_analysis:
            reasons.append(
                "explicit evidence_review conflicts with wants_data_analysis; "
                "data-analysis intent preserved — run it in a later full cycle"
            )
        mode = explicit_mode
    else:
        if full_cycle_flags:
            mode = "full_research_cycle"
            if wants_design:
                reasons.append("study design requested")
            if has_data or wants_analysis:
                reasons.append("user data analysis requested")
            if wants_update:
                reasons.append("decision update requested")
        else:
            mode = "evidence_review"
            reasons.append("existing evidence requested")

    if mode == "full_research_cycle":
        requires_grounding = not project_has_grounding
        if requires_grounding:
            reasons.append(
                "no project evidence grounding yet; minimum Evidence Review "
                "required before study design (no new study design without "
                "evidence grounding)")
    else:
        requires_grounding = False

    return ModeRecommendation(mode=mode, reasons=tuple(reasons),
                              requires_grounding_review=requires_grounding)
