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


def aggregate_outcomes(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_outcome: dict[str, dict[str, Any]] = {}
    for ev in evidence:
        outcome = ev.get("outcome_type", "unknown")
        row = by_outcome.setdefault(outcome, {
            "outcome_type": outcome, "support_count": 0,
            "contradict_count": 0, "neutral_count": 0, "evidence_ids": [],
        })
        direction = ev.get("direction", "neutral")
        if direction == "support":
            row["support_count"] += 1
        elif direction == "contradict":
            row["contradict_count"] += 1
        else:
            row["neutral_count"] += 1
        row["evidence_ids"].append(ev.get("evidence_id", ""))
    return [by_outcome[o] for o in OUTCOME_ORDER if o in by_outcome]


def build_claims(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claims: dict[str, dict[str, Any]] = {}
    for ev in evidence:
        claim = ev.get("claim", "")
        outcome = ev.get("outcome_type", "")
        key = (claim, outcome)
        row = claims.setdefault(key, {
            "claim": claim, "outcome_type": outcome,
            "evidence_ids": [], "status": "SUPPORTED",
        })
        row["evidence_ids"].append(ev.get("evidence_id", ""))
        if ev.get("status") == "UNSUPPORTED":
            row["status"] = "UNSUPPORTED"
        elif ev.get("status") == "DOWNGRADE_CONFIDENCE" and row["status"] != "UNSUPPORTED":
            row["status"] = "DOWNGRADE_CONFIDENCE"
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
                seen[sid] = {
                    "source_id": sid,
                    "title": ev.get("title", ""),
                    "year": ev.get("year"),
                    "canonical_url": ev.get("source_location", ""),
                    "authority_level": "tier1_paper_doi"
                    if (ev.get("source_location", "") or "").startswith(("https://doi.org", "https://doi.org/", "http://doi.org"))
                    else "tier3_professional_institution",
                    "source_location": ev.get("source_location", ""),
                }
        sources = list(seen.values())

    decision = verdict
    # execution summary derived from pack (complexity via frame target/depth is optional)
    execution = {
        "complexity": frame.get("complexity", "M"),
        "mode": mode,
        "agents": [],
        "usage": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "latency_s": 0.0},
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
        "provenance": {"search_provider": "n/a", "fetched_at": datetime.now(timezone.utc).isoformat()},
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
