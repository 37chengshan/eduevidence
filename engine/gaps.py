"""Structured Knowledge Gap derivation.

A KnowledgeGap is not free-form "future work": it is derived from coverage —
the research frame's requested outcomes vs what the graph's Findings
actually measure. A task-performance Finding never covers a retention or
transfer gap.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.contracts import validate_record
from engine.graph_store import GraphStore
from engine.ids import new_local_id
from engine.synthesis import ClaimSynthesis

# outcome_type names for timepoint-like gaps (frame.requested_outcomes entries
# may carry outcome_type or be plain strings; we match on outcome_type)
_RETENTION_TYPES = {"retention", "long_term", "learning_retention"}
_TRANSFER_TYPES = {"transfer", "transfer_learning", "far_transfer"}
_TASK_PERFORMANCE = {"task_performance", "assignment_score", "task_completion"}
_LEARNING = {"learning"}


def derive_gaps(*, store: GraphStore,
                syntheses: tuple[ClaimSynthesis, ...] | None = None,
                frame: dict | None = None) -> list[dict]:
    """Derive structured gaps from graph coverage vs the research frame.

    `frame` carries `requested_outcomes` (list of outcome names/types) and
    optionally `target_population`. Findings' outcome types come from the
    graph's outcomes table.
    """
    frame = frame or {}
    requested = frame.get("requested_outcomes") or []
    if not requested and frame.get("target_outcomes"):
        requested = frame["target_outcomes"]

    findings = store.read_table("findings")
    outcomes = {o["outcome_id"]: o for o in store.read_table("outcomes")}
    covered_types: set[str] = set()
    covered_names: set[str] = set()
    for f in findings:
        o = outcomes.get(f["outcome_id"])
        if o:
            covered_types.add(o.get("outcome_type", ""))
            covered_names.add(o.get("name", ""))
    covered = covered_types | covered_names

    claims = store.read_table("claims")
    claim_ids = [c["claim_id"] for c in claims]
    outcome_ids = list(outcomes.keys())

    gaps: list[dict] = []
    rev = store.active_revision()

    def add(gap_type: str, priority: str, reasoning: str, related: list[str] | None = None):
        gaps.append({
            "gap_id": new_local_id("GAP", {g["gap_id"] for g in gaps}),
            "gap_type": gap_type,
            "related_claim_ids": related or claim_ids,
            "related_outcome_ids": outcome_ids,
            "priority": priority,
            "reasoning": reasoning,
            "status": "open",
            "derived_from_graph_revision": rev,
            "extensions": {},
        })

    # requested outcomes not covered at all
    for req in requested:
        if isinstance(req, dict):
            req_name = req.get("name", "")
            req_type = req.get("outcome_type", "")
        else:
            req_name, req_type = str(req), ""
        if req_name and req_name not in covered:
            if req_type in _RETENTION_TYPES or req_name.lower() in _RETENTION_TYPES:
                add("missing_retention", "high",
                    f"frame requests retention outcome {req_name!r} but the graph "
                    f"has no retention measurement")
            elif req_type in _TRANSFER_TYPES or req_name.lower() in _TRANSFER_TYPES:
                add("missing_transfer", "high",
                    f"frame requests transfer outcome {req_name!r} but the graph "
                    f"has no transfer measurement")
            elif req_type in _TASK_PERFORMANCE or req_name.lower() in _TASK_PERFORMANCE:
                add("missing_outcome", "medium",
                    f"frame requests task-performance outcome {req_name!r} without "
                    f"covering learning; task performance is not learning (RULE 3)")
            else:
                add("missing_outcome", "medium",
                    f"frame requests outcome {req_name!r} with no covering finding")

    # retention/transfer explicitly requested but only task performance covered
    wants_retention = any(
        (isinstance(r, dict) and r.get("outcome_type") in _RETENTION_TYPES)
        or (isinstance(r, str) and r.lower() in _RETENTION_TYPES) for r in requested)
    wants_transfer = any(
        (isinstance(r, dict) and r.get("outcome_type") in _TRANSFER_TYPES)
        or (isinstance(r, str) and r.lower() in _TRANSFER_TYPES) for r in requested)
    has_task_perf_only = bool(covered_types & _TASK_PERFORMANCE) and not (
        covered_types & (_LEARNING | _RETENTION_TYPES))
    if wants_retention and has_task_perf_only:
        add("missing_retention", "high",
            "graph covers task performance only; retention remains unmeasured — "
            "task performance does not imply retention (RULE 3)")
    if wants_transfer and has_task_perf_only:
        add("missing_transfer", "high",
            "graph covers task performance only; transfer remains unmeasured — "
            "AI-assisted performance does not imply no-AI transfer (RULE 3)")

    # contradiction gaps
    for syn in syntheses or ():
        if syn.status == "contested":
            add("unresolved_conflict", "high",
                f"claim {syn.claim_id} has independent contradictory studies "
                f"({', '.join(syn.study_ids)})", [syn.claim_id])

    # methodology weakness / insufficient independence
    if syntheses:
        for syn in syntheses:
            if syn.status == "insufficient" and len(syn.study_ids) < 2:
                add("insufficient_sample_independence", "medium",
                    f"claim {syn.claim_id} rests on fewer than two independent "
                    f"studies", [syn.claim_id])

    # validate each gap
    for g in gaps:
        errors = validate_record("knowledge-gap", g)
        if errors:
            raise ValueError(f"invalid gap: {errors}")
    return gaps


def save_gaps(project, *, graph_revision: int, gaps: list[dict]) -> Path:
    """Persist gaps under gaps/ (one JSONL file per revision)."""
    path = project.path / "gaps" / f"gaps-rev-{graph_revision:06d}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = "".join(json.dumps(g, ensure_ascii=False) + "\n" for g in gaps)
    path.write_text(lines, encoding="utf-8")
    return path
