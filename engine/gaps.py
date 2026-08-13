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
    for f in findings:
        o = outcomes.get(f["outcome_id"])
        if o:
            covered_types.add(o.get("outcome_type", ""))

    claims = store.read_table("claims")
    claim_ids = [c["claim_id"] for c in claims]

    gaps: list[dict] = []
    rev = store.active_revision()

    def add(gap_type: str, priority: str, reasoning: str,
            related_claims: list[str] | None = None,
            related_outcomes: list[str] | None = None):
        gaps.append({
            "gap_id": new_local_id("GAP", {g["gap_id"] for g in gaps}),
            "gap_type": gap_type,
            "related_claim_ids": related_claims or [],
            "related_outcome_ids": related_outcomes or [],
            "priority": priority,
            "reasoning": reasoning,
            "status": "open",
            "derived_from_graph_revision": rev,
            "extensions": {},
        })

    def _req_kind(req) -> tuple[str, str]:
        """Classify a requested outcome: retention | transfer |
        task_performance | learning | other. Type-aware: names are matched
        only within the outcome's declared type, never type-blind."""
        if isinstance(req, dict):
            req_name = str(req.get("name", "")).lower()
            req_type = str(req.get("outcome_type", "")).lower()
        else:
            req_name, req_type = str(req).lower(), ""
        if req_type in _RETENTION_TYPES or req_name in _RETENTION_TYPES:
            return "retention", req.get("name", "") if isinstance(req, dict) else str(req)
        if req_type in _TRANSFER_TYPES or req_name in _TRANSFER_TYPES:
            return "transfer", req.get("name", "") if isinstance(req, dict) else str(req)
        if req_type in _TASK_PERFORMANCE or req_name in _TASK_PERFORMANCE:
            return "task_performance", req.get("name", "") if isinstance(req, dict) else str(req)
        if req_type in _LEARNING or req_name in _LEARNING:
            return "learning", req.get("name", "") if isinstance(req, dict) else str(req)
        return "other", req.get("name", "") if isinstance(req, dict) else str(req)

    _RETENTION_COVER = _RETENTION_TYPES
    _TRANSFER_COVER = _TRANSFER_TYPES
    def covered_for_kind(kind: str) -> bool:
        if kind == "retention":
            return bool(covered_types & _RETENTION_COVER)
        if kind == "transfer":
            return bool(covered_types & _TRANSFER_COVER)
        if kind == "task_performance":
            return bool(covered_types & _TASK_PERFORMANCE)
        if kind == "learning":
            return bool(covered_types & _LEARNING)
        return False

    # one pass per requested outcome; each gap emitted exactly once
    seen: set[tuple[str, str]] = set()
    for req in requested:
        kind, label = _req_kind(req)
        if not label:
            continue
        key = (kind, label)
        if key in seen:
            continue
        seen.add(key)
        if covered_for_kind(kind):
            continue
        if kind == "retention":
            add("missing_retention", "high",
                f"frame requests retention outcome {label!r} but the graph has "
                f"no retention-type measurement; task-performance coverage does "
                f"not count (RULE 3)")
        elif kind == "transfer":
            add("missing_transfer", "high",
                f"frame requests transfer outcome {label!r} but the graph has "
                f"no transfer-type measurement; AI-assisted task performance "
                f"does not count (RULE 3)")
        elif kind == "task_performance":
            add("missing_outcome", "medium",
                f"frame requests task-performance outcome {label!r} with no "
                f"covering finding")
        elif kind == "learning":
            add("missing_outcome", "medium",
                f"frame requests learning outcome {label!r} with no covering "
                f"learning finding; task performance is not learning (RULE 3)")
        else:
            add("missing_outcome", "medium",
                f"frame requests outcome {label!r} with no covering finding")
    claim_outcomes = {c["claim_id"]: c.get("primary_outcome_ids", [])
                      for c in claims}

    # contradiction gaps
    for syn in syntheses or ():
        if syn.status == "contested":
            add("unresolved_conflict", "high",
                f"claim {syn.claim_id} has independent contradictory studies "
                f"({', '.join(syn.study_ids)})", [syn.claim_id],
                claim_outcomes.get(syn.claim_id, []))

    # methodology weakness / insufficient independence
    if syntheses:
        for syn in syntheses:
            if syn.status == "insufficient" and len(syn.study_ids) < 2:
                add("insufficient_sample_independence", "medium",
                    f"claim {syn.claim_id} rests on fewer than two independent "
                    f"studies", [syn.claim_id],
                    claim_outcomes.get(syn.claim_id, []))

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
