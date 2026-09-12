"""Structured Knowledge Gap derivation.

A KnowledgeGap is not free-form "future work": it is derived from coverage —
the research frame's requested outcomes vs what the graph's Findings
actually measure. A task-performance Finding never covers a retention or
transfer gap.

`gap_id` identifies one revision-local gap artifact. `extensions.autoresearch_key`
is a stable semantic lineage key so bounded research memory survives graph
revisions when the same unresolved gap is re-derived.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.contracts import validate_record
from engine.graph_store import GraphStore
from engine.ids import new_local_id
from engine.synthesis import ClaimSynthesis

#: Gap kind -> the outcome categories that count as covering it. Categories are
#: read from the domain registry, so a policy run classifies its outcomes with
#: the policy buckets (effectiveness / cost / equity / feasibility / risk)
#: instead of being measured against education vocabulary.
GAP_KIND_CATEGORIES: dict[str, tuple[str, ...]] = {
    "learning": ("learning",),
    "retention": ("learning",),
    "transfer": ("learning",),
    "task_performance": ("task_performance",),
    "process": ("process",),
    "risk": ("risk",),
    "effectiveness": ("effectiveness",),
    "cost": ("cost",),
    "equity": ("equity",),
    "feasibility": ("feasibility",),
}

#: Legacy aliases accepted when a frame names its requested outcomes with older
#: vocabulary; they resolve to a gap kind above.
GAP_KIND_ALIASES: dict[str, str] = {
    "long_term": "retention", "learning_retention": "retention",
    "transfer_learning": "transfer", "far_transfer": "transfer",
    "assignment_score": "task_performance", "task_completion": "task_performance",
    "policy_effectiveness": "effectiveness", "cost_effectiveness": "cost",
    "implementation_risk": "risk",
}


def _autoresearch_key(
    gap_type: str,
    *,
    related_claims: list[str],
    related_outcomes: list[str],
    semantic_token: str,
) -> str:
    payload = {
        "gap_type": gap_type,
        "related_claims": sorted(related_claims),
        "related_outcomes": sorted(related_outcomes),
        "semantic_token": semantic_token.strip().lower(),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:20]
    return f"KGK-{digest}"


def derive_gaps(*, store: GraphStore,
                syntheses: tuple[ClaimSynthesis, ...] | None = None,
                frame: dict | None = None) -> list[dict]:
    """Derive structured gaps from graph coverage vs the research frame."""
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
    gaps: list[dict] = []
    rev = store.active_revision()

    def add(gap_type: str, priority: str, reasoning: str,
            related_claims: list[str] | None = None,
            related_outcomes: list[str] | None = None,
            semantic_token: str = ""):
        related_claims = related_claims or []
        related_outcomes = related_outcomes or []
        key = _autoresearch_key(
            gap_type,
            related_claims=related_claims,
            related_outcomes=related_outcomes,
            semantic_token=semantic_token or reasoning,
        )
        gaps.append({
            "gap_id": new_local_id("GAP", {g["gap_id"] for g in gaps}),
            "gap_type": gap_type,
            "related_claim_ids": related_claims,
            "related_outcome_ids": related_outcomes,
            "priority": priority,
            "reasoning": reasoning,
            "status": "open",
            "derived_from_graph_revision": rev,
            "extensions": {"autoresearch_key": key},
        })

    def _req_kind(req) -> tuple[str, str]:
        if isinstance(req, dict):
            req_name = str(req.get("name", "")).lower()
            req_type = str(req.get("outcome_type", "")).lower()
        else:
            req_name, req_type = str(req).lower(), ""
        label = req.get("name", "") if isinstance(req, dict) else str(req)
        kind = GAP_KIND_ALIASES.get(req_type) or GAP_KIND_ALIASES.get(req_name)
        if kind is None:
            kind = req_type if req_type in GAP_KIND_CATEGORIES else req_name
        if kind in GAP_KIND_CATEGORIES:
            return kind, label
        return "other", label

    def covered_for_kind(kind: str) -> bool:
        """True when the graph already carries an outcome for this gap kind.

        ``covered_types`` holds the category buckets stored on outcomes, which
        is why this compares categories rather than V1 tokens.
        """
        expected = GAP_KIND_CATEGORIES.get(kind)
        if not expected:
            return False
        return bool(covered_types & set(expected))

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
            add(
                "missing_retention", "high",
                f"frame requests retention outcome {label!r} but the graph has "
                "no retention-type measurement; task-performance coverage does "
                "not count (RULE 3)",
                semantic_token=f"requested_outcome:{label}",
            )
        elif kind == "transfer":
            add(
                "missing_transfer", "high",
                f"frame requests transfer outcome {label!r} but the graph has "
                "no transfer-type measurement; AI-assisted task performance "
                "does not count (RULE 3)",
                semantic_token=f"requested_outcome:{label}",
            )
        elif kind == "task_performance":
            add(
                "missing_outcome", "medium",
                f"frame requests task-performance outcome {label!r} with no covering finding",
                semantic_token=f"requested_outcome:{label}",
            )
        elif kind == "learning":
            add(
                "missing_outcome", "medium",
                f"frame requests learning outcome {label!r} with no covering learning finding; "
                "task performance is not learning (RULE 3)",
                semantic_token=f"requested_outcome:{label}",
            )
        else:
            add(
                "missing_outcome", "medium",
                f"frame requests outcome {label!r} with no covering finding",
                semantic_token=f"requested_outcome:{label}",
            )

    claim_outcomes = {
        c["claim_id"]: c.get("primary_outcome_ids", [])
        for c in claims
    }

    for syn in syntheses or ():
        if syn.status == "contested":
            add(
                "unresolved_conflict", "high",
                f"claim {syn.claim_id} has independent contradictory studies "
                f"({', '.join(syn.study_ids)})",
                [syn.claim_id],
                claim_outcomes.get(syn.claim_id, []),
                semantic_token=f"claim:{syn.claim_id}",
            )

    if syntheses:
        for syn in syntheses:
            if syn.status == "insufficient" and len(syn.study_ids) < 2:
                add(
                    "insufficient_sample_independence", "medium",
                    f"claim {syn.claim_id} rests on fewer than two independent studies",
                    [syn.claim_id],
                    claim_outcomes.get(syn.claim_id, []),
                    semantic_token=f"claim:{syn.claim_id}",
                )

    for gap in gaps:
        errors = validate_record("knowledge-gap", gap)
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
