"""Canonical workflow registry for the Decision-Grade Evidence Engine.

The scientific protocol is deliberately independent from execution adapters and
projections.  A renderer may fail or be replaced without changing what counts
as completed scientific work.
"""
from __future__ import annotations

from dataclasses import dataclass


SCIENTIFIC_STAGE_IDS = (
    "frame", "retrieve", "extract", "challenge", "audit", "adjudicate",
    "applicability", "intervene", "evaluate",
)
PROJECTION_STAGE_ID = "projection"


@dataclass(frozen=True)
class WorkflowSpec:
    workflow_id: str
    title: str
    stage_ids: tuple[str, ...]
    capability_ids: tuple[str, ...]


_EVIDENCE_REVIEW = (
    "research_framing", "literature_search", "counter_evidence_search",
    "source_fetch", "source_validation", "study_extraction",
    "finding_extraction", "methodology_appraisal", "claim_linking",
    "evidence_synthesis", "tribunal", "applicability_analysis",
    "knowledge_gap_detection",
)

_WORKFLOWS = {
    "evidence_review": WorkflowSpec(
        "evidence_review", "Evidence Review",
        SCIENTIFIC_STAGE_IDS[:7], _EVIDENCE_REVIEW,
    ),
    "decision_and_pilot": WorkflowSpec(
        "decision_and_pilot", "Decision & Pilot",
        SCIENTIFIC_STAGE_IDS[:8], _EVIDENCE_REVIEW + ("intervention_design",),
    ),
    "evaluate_and_update": WorkflowSpec(
        "evaluate_and_update", "Evaluate & Update",
        ("evaluate",), ("evaluation_design", "data_validation", "data_analysis"),
    ),
    "full_research_cycle": WorkflowSpec(
        "full_research_cycle", "Full Research Cycle",
        SCIENTIFIC_STAGE_IDS,
        _EVIDENCE_REVIEW + ("intervention_design", "evaluation_design", "data_validation", "data_analysis"),
    ),
}


def workflow_registry() -> dict[str, WorkflowSpec]:
    """Return the immutable workflow catalogue keyed by user intent."""
    return dict(_WORKFLOWS)


def workflow(workflow_id: str) -> WorkflowSpec:
    try:
        return _WORKFLOWS[workflow_id]
    except KeyError as exc:
        raise ValueError(f"unknown workflow {workflow_id!r}") from exc


def execution_stages() -> tuple[str, ...]:
    """Canonical execution order, with Projection explicitly outside science."""
    return SCIENTIFIC_STAGE_IDS + (PROJECTION_STAGE_ID,)
