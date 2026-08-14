#!/usr/bin/env python3
"""build_result.py — Assemble result.json from an example research pack.

result.json is the validated research-core output (总体实施计划 §27) consumed by
the visualization layer. It aggregates the pack files:

    frame.json + evidence.jsonl + methodology.json + verdict.json
    + intervention.json + evaluation.json  (+ optional sources.jsonl)

and computes the outcome-level aggregation and claim rows (Claim-Evidence
Contract). The report layer consumes ONLY this file and never edits it.

Usage:
    python3 scripts/build_result.py --pack examples/ai-coding-assistant \
        --out examples/ai-coding-assistant/result.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evidence_semantics import effect_direction

OUTCOME_ORDER = [
    "knowledge_gain", "concept_understanding", "retention", "transfer",
    "independent_problem_solving", "completion_time", "accuracy",
    "code_quality", "assignment_score", "engagement", "motivation",
    "cognitive_load", "help_seeking", "metacognition", "ai_dependency",
    "over_reliance", "reduced_effort", "reduced_transfer",
    "academic_integrity_risk", "false_confidence",
]


def _load_json(path: Path) -> dict[str, Any] | None:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _derive_source_from_evidence(ev: dict[str, Any]) -> dict[str, Any] | None:
    """Honest source fallback (review P1-2): a real DOI in the location
    yields tier1; otherwise the lowest authority is assumed and the record
    is flagged source_metadata_incomplete. Never fabricates a canonical URL."""
    from retrieval.source import parse_doi_from_url  # noqa: PLC0415

    loc = (ev.get("source_location") or "").strip()
    if not loc:
        return None
    doi = parse_doi_from_url(loc)
    authority = "tier1_paper_doi" if doi else "tier5_general_web"
    return {
        "source_id": ev.get("source_id", ""),
        "title": ev.get("title", ""),
        "year": ev.get("year"),
        "canonical_url": loc,
        "authority_level": authority,
        "source_location": loc,
        "extensions": {"source_metadata_incomplete": not doi},
    }


NOT_CAPTURED_USAGE: dict[str, Any] = {
    "measurement_status": "NOT_CAPTURED",
    "input_tokens": None,
    "output_tokens": None,
    "cost_usd": None,
    "latency_s": None,
}


def derive_provenance(sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate provenance from real Source.fetch records (P1-3).

    fetched_at only appears when an actual fetch recorded it (sources[].fetch.
    fetched_at); the result-assembly time is reported as meta.generated_at and
    must never be passed off as a fetch time. Unknown values stay unknown.
    """
    fetched = [
        s["fetch"]["fetched_at"] for s in sources
        if isinstance(s.get("fetch"), dict) and s["fetch"].get("fetched_at")
    ]
    providers = sorted({
        s["fetch"]["fetch_provider"] for s in sources
        if isinstance(s.get("fetch"), dict) and s["fetch"].get("fetch_provider")
    })
    provenance: dict[str, Any] = {"search_provider": ", ".join(providers) if providers else "n/a"}
    if fetched:
        provenance["fetched_at"] = min(fetched)
    return provenance


def aggregate_outcomes(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Outcome-level aggregation keyed by effect_direction (C-1).

    Outcome rows carry positive_count / negative_count / null_count (based on
    effect_direction) — not support/contradict counts, which are claim-level
    semantics and only belong in the claim trace (relation_to_claim).
    """
    by_outcome: dict[str, dict[str, Any]] = {}
    for ev in evidence:
        outcome = ev.get("outcome_type", "unknown")
        row = by_outcome.setdefault(outcome, {
            "outcome_type": outcome, "positive_count": 0,
            "negative_count": 0, "null_count": 0, "evidence_ids": [],
        })
        effect = effect_direction(ev)
        if effect == "positive":
            row["positive_count"] += 1
        elif effect == "negative":
            row["negative_count"] += 1
        else:
            row["null_count"] += 1
        row["evidence_ids"].append(ev.get("evidence_id", ""))
    return [by_outcome[o] for o in OUTCOME_ORDER if o in by_outcome]


def build_outcome_mapping(evidence: list[dict[str, Any]],
                          frame: dict[str, Any] | None = None) -> dict[str, Any]:
    """Frame-declared vs evidence-covered outcome map (OPEN-2).

    Every outcome type seen in the frame or in evidence gets exactly one
    entry with directional counts (support / contradict / neutral -- never
    mixed, consistent with the three-column Evidence Matrix) and an explicit
    status:

        supported / contested / contradicted / null_evidence_only / no_evidence

    Frame-declared outcomes with no covering evidence are surfaced in
    declared_without_evidence so a decision must disclose its gaps.
    """
    declared: set[str] = set()
    for group in ("primary", "secondary", "risk"):
        declared.update((frame or {}).get("outcomes", {}).get(group, []) or [])
    declared.discard("")

    by_outcome: dict[str, dict[str, Any]] = {}
    for ev in evidence:
        outcome = ev.get("outcome_type") or "unknown"
        row = by_outcome.setdefault(outcome, {
            "outcome_type": outcome,
            "support_count": 0, "contradict_count": 0, "neutral_count": 0,
            "evidence_ids": [],
        })
        direction = ev.get("direction", "neutral")
        if direction == "support":
            row["support_count"] += 1
        elif direction == "contradict":
            row["contradict_count"] += 1
        else:
            row["neutral_count"] += 1
        if ev.get("evidence_id"):
            row["evidence_ids"].append(ev["evidence_id"])

    entries: list[dict[str, Any]] = []
    for outcome in sorted(set(declared) | set(by_outcome)):
        row = by_outcome.get(outcome) or {
            "outcome_type": outcome, "support_count": 0,
            "contradict_count": 0, "neutral_count": 0, "evidence_ids": []}
        s, c, n = row["support_count"], row["contradict_count"], row["neutral_count"]
        if s > 0 and c > 0:
            status = "contested"
        elif s > 0:
            status = "supported"
        elif c > 0:
            status = "contradicted"
        elif n > 0:
            status = "null_evidence_only"
        else:
            status = "no_evidence"
        entries.append({
            "outcome_type": outcome,
            "declared_in_frame": outcome in declared,
            "status": status,
            "support_count": s,
            "contradict_count": c,
            "neutral_count": n,
            "evidence_ids": list(row["evidence_ids"]),
        })

    declared_without_evidence = sorted(d for d in declared if d not in by_outcome)
    return {"entries": entries, "declared_without_evidence": declared_without_evidence}

def build_claims(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Claim-level rows bound to evidence (Claim-Evidence Contract, A-3).

    claim_id comes from the evidence objects themselves (first-class field of
    the Evidence Contract), so Claim -> Evidence -> Source never depends on
    render-time renumbering. Legacy evidence without claim_id falls back to a
    deterministic C-{idx:03d} sequence.
    """
    claims: dict[str, dict[str, Any]] = {}
    for idx, ev in enumerate(evidence, 1):
        claim = ev.get("claim", "")
        outcome = ev.get("outcome_type", "")
        key = (claim, outcome)
        row = claims.setdefault(key, {
            "claim": claim, "outcome_type": outcome,
            "claim_id": ev.get("claim_id") or f"C-{idx:03d}",
            "evidence_ids": [], "status": "SUPPORTED",
        })
        row["evidence_ids"].append(ev.get("evidence_id", ""))
        status = ev.get("status")
        rank = {"CONTRADICT": 3, "UNSUPPORTED": 2, "DOWNGRADE_CONFIDENCE": 1}.get(status, 0)
        if rank > {"CONTRADICT": 3, "UNSUPPORTED": 2, "DOWNGRADE_CONFIDENCE": 1}.get(row["status"], 0):
            row["status"] = status
    return list(claims.values())


def build_result(pack_dir: Path, *, mode: str = "platform_native") -> dict[str, Any]:
    frame = _load_json(pack_dir / "frame.json") or {}
    evidence = _load_jsonl(pack_dir / "evidence.jsonl")
    # methodology.json is a single MethodologyAudit object (or a JSONL list)
    methodology_single = _load_json(pack_dir / "methodology.json")
    methodology = [methodology_single] if methodology_single else _load_jsonl(pack_dir / "methodology.jsonl")
    verdict = _load_json(pack_dir / "verdict.json") or {}
    intervention = _load_json(pack_dir / "intervention.json") or {}
    evaluation = _load_json(pack_dir / "evaluation.json") or {}
    sources = _load_jsonl(pack_dir / "sources.jsonl")

    if not sources:
        seen: dict[str, dict[str, Any]] = {}
        for ev in evidence:
            sid = ev.get("source_id", "")
            if sid and sid not in seen:
                derived = _derive_source_from_evidence(ev)
                if derived is not None:
                    seen[sid] = derived
        sources = list(seen.values())

    decision = verdict
    # execution summary derived from pack (complexity via frame target/depth is optional)
    execution = {
        "complexity": frame.get("complexity", "M"),
        "mode": mode,
        "agents": [],
        "usage": dict(NOT_CAPTURED_USAGE),
    }

    result = {
        "meta": {
            "skill": "eduevidence",
            "version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "question": frame.get("question", ""),
        },
        "execution": execution,
        "research_frame": frame,
        "decision": decision,
        "outcomes": aggregate_outcomes(evidence),
        "outcome_mapping": build_outcome_mapping(evidence, frame),
        "claims": build_claims(evidence),
        "sources": sources,
        "evidence": evidence,
        "methodology_reviews": methodology,
        "conflicts": [{"reason_for_disagreement": verdict.get("reason_for_disagreement", "")}]
        if verdict.get("reason_for_disagreement") else [],
        "applicability": verdict.get("applicability", {}),
        "intervention": intervention,
        "evaluation": evaluation,
        "benchmark": {},
        "provenance": derive_provenance(sources),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble result.json from an example pack")
    parser.add_argument("--pack", required=True, help="example pack directory")
    parser.add_argument("--out", required=True, help="output result.json path")
    parser.add_argument("--mode", choices=["platform_native", "agent_mcp_enhanced"],
                        default="platform_native")
    args = parser.parse_args()

    result = build_result(Path(args.pack), mode=args.mode)
    out = Path(args.out)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.out} (sources={len(result['sources'])}, evidence={len(result['evidence'])}, "
          f"claims={len(result['claims'])}, outcomes={len(result['outcomes'])})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
