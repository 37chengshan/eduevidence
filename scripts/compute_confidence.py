#!/usr/bin/env python3
"""compute_confidence.py — Deterministic confidence computation for final verdicts.

Pipeline entry for the Evidence Integrity Report (P0-05): reads the raw model
verdict plus the evidence registry and OVERRIDES the model's confidence values
with the deterministic rule-based computation, so the final verdict's
confidence is reproducible and auditable rather than model-generated.

Formula (identical policy to evidence_score.confidence, v2 — D-1/D-2):

    score = 0.30 * Evidence Quality + 0.25 * Consistency + 0.20 * Directness
            + 0.25 * Evidence Count (independent-study weighted)
            - Conflict Penalty - Unsupported Penalty

where Evidence Count = min(1.0, independent_studies / 4) — independent_samples
is reported separately instead of being added to the count term —,
Consistency is computed over decision_relation (support_adoption /
oppose_adoption / conditional / neutral) rather than relation_to_claim,
Conflict Penalty = 0.15 if any evidence opposes adoption, and
Unsupported Penalty = min(0.20, 0.05 * n_unsupported).

IMPORTANT: confidence_score is a rule-based index in [0, 1], NOT a
probability. It must never be presented as a percentage probability (e.g. "85%
confidence"); consumers should phrase it as an index/band (High | Moderate |
Low | Insufficient) with the policy version.

Usage:
    python3 scripts/compute_confidence.py --verdict raw_verdict.json \
        --evidence evidence.jsonl --out final_verdict.json

Output (final_verdict.json) carries the deterministic fields:
confidence / confidence_score / confidence_policy_version /
independent_studies / independent_samples / confidence_breakdown, plus the
raw model values preserved as raw_model_confidence* for audit comparison.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evidence_score import (CONFIDENCE_POLICY_VERSION,
                            decision_consistency_score, directness_score,
                            independent_samples, independent_studies)
from evidence_semantics import decision_relation


def compute_confidence(evidence_list: list[dict], *, target_outcome: str | None = None) -> dict:
    """Deterministic confidence over an evidence list (independent-study weighted).

    Returns a breakdown dict plus the final label (High | Moderate | Low |
    Insufficient). This is the P0-05 policy engine; the legacy
    evidence_score.confidence() remains for backward-compatible callers.
    """
    if not evidence_list:
        return {"confidence": "Insufficient",
                "confidence_policy_version": CONFIDENCE_POLICY_VERSION,
                "independent_studies": 0,
                "independent_samples": 0,
                "confidence_breakdown": {"evidence_count": 0}}

    # 1. Evidence Quality (mean of quality scores, scaled to 0-1)
    quality_values = [e.get("quality_score") for e in evidence_list]
    numeric = [q for q in quality_values if isinstance(q, (int, float))]
    avg_quality = sum(numeric) / len(numeric) if numeric else 0.0
    quality_term = avg_quality / 10.0

    # 2. Consistency (decision_relation based, D-2): claim-level evidence is
    #    usually extracted to support its claim, so relation_to_claim would
    #    overstate agreement about the final teaching decision.
    decisions = [decision_relation(e) for e in evidence_list]
    consistency = decision_consistency_score(decisions)

    # 3. Directness (0-2 -> 0-1)
    directness = directness_score(evidence_list) / 2.0

    # 4. Evidence count weighted by independent studies only (D-1): a typical
    #    study is 1 study + 1 sample, so adding independent_samples would count
    #    the same study twice. independent_samples is reported separately.
    studies = independent_studies(evidence_list)
    samples = independent_samples(evidence_list)
    count_term = min(1.0, studies / 4.0)

    # 5. Conflict penalty (0.15 when any evidence opposes adoption)
    conflict_penalty = 0.15 if "oppose_adoption" in decisions else 0.0

    # 6. Unsupported penalty (capped at 0.20)
    unsupported = [e for e in evidence_list if e.get("status") in ("UNSUPPORTED", "DOWNGRADE_CONFIDENCE")]
    unsupported_penalty = min(0.20, len(unsupported) * 0.05)

    score = (0.30 * quality_term + 0.25 * consistency + 0.20 * directness
             + 0.25 * count_term - conflict_penalty - unsupported_penalty)
    score = max(0.0, min(1.0, score))

    if target_outcome:
        relevant = [e for e in evidence_list if e.get("outcome_type") == target_outcome]
        if relevant:
            score *= 0.5 + 0.5 * (len(relevant) / max(1, len(evidence_list)))

    label = _confidence_label(score)
    return {
        "confidence": label,
        "confidence_policy_version": CONFIDENCE_POLICY_VERSION,
        "independent_studies": studies,
        "independent_samples": samples,
        "confidence_breakdown": {
            "score": round(score, 3),
            "evidence_quality": round(quality_term, 3),
            "consistency": round(consistency, 3),
            "directness": round(directness, 3),
            "evidence_count": len(evidence_list),
            "independent_studies": studies,
            "independent_samples": samples,
            "count_term": round(count_term, 3),
            "conflict_penalty": conflict_penalty,
            "unsupported_penalty": round(unsupported_penalty, 3),
        },
    }


def _confidence_label(score: float) -> str:
    if score >= 0.72:
        return "High"
    if score >= 0.45:
        return "Moderate"
    if score >= 0.2:
        return "Low"
    return "Insufficient"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute deterministic confidence and merge it into the final verdict")
    parser.add_argument("--verdict", required=True, help="Raw (model) verdict JSON file")
    parser.add_argument("--evidence", required=True, help="Evidence JSONL file")
    parser.add_argument("--out", required=True, help="Output final verdict JSON path")
    args = parser.parse_args()

    raw_verdict = json.loads(Path(args.verdict).read_text(encoding="utf-8"))
    evidence_list = []
    for lineno, line in enumerate(Path(args.evidence).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            evidence_list.append(json.loads(line))
        except json.JSONDecodeError as exc:
            print(f"{args.evidence}:{lineno}: invalid JSON line: {exc}", file=sys.stderr)
            return 1

    target_outcome = raw_verdict.get("target_outcome")
    computed = compute_confidence(evidence_list, target_outcome=target_outcome)

    # Override model-generated confidence fields with the deterministic values.
    final = dict(raw_verdict)
    final["confidence"] = computed["confidence"]
    final["confidence_score"] = computed["confidence_breakdown"].get("score")
    final["confidence_policy_version"] = computed["confidence_policy_version"]
    final["independent_studies"] = computed["independent_studies"]
    final["independent_samples"] = computed["independent_samples"]
    final["confidence_breakdown"] = computed["confidence_breakdown"]
    # 保留原始模型输出，供审计比对（模型值被覆盖而非丢弃）。
    final["raw_model_confidence"] = raw_verdict.get("confidence")
    final["raw_model_confidence_breakdown"] = raw_verdict.get("confidence_breakdown") or {}

    out_path = Path(args.out)
    out_path.write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"confidence={computed['confidence']} score={computed['confidence_breakdown']['score']} "
          f"studies={computed['independent_studies']} samples={computed['independent_samples']} "
          f"policy={CONFIDENCE_POLICY_VERSION} -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
