#!/usr/bin/env python3
"""evidence_score.py — Deterministic quality scoring and confidence computation.

Two rule-based engines:

1. Quality score (five dimensions, each 0-2, total 0-10):
   D1 Study Design, D2 Sample Quality, D3 Measurement Validity,
   D4 Temporal Strength, D5 Directness.
   Level mapping (references/evidence-quality.md): 8-10 strong, 5-7 moderate,
   2-4 weak, 0-1 very_weak.

2. Confidence (rule-based, NOT model-generated):
   Evidence Quality + Consistency + Directness + Evidence Count
   - Conflict Penalty - Unsupported Penalty
   -> High | Moderate | Low | Insufficient

The authoritative pipeline entry for final verdicts is
scripts/compute_confidence.py (independent-studies/samples-weighted formula
with confidence_policy_version); the `confidence()` function below remains the
backward-compatible engine used by example reproducibility checks.

IMPORTANT: the confidence score is a rule-based index in [0, 1], NOT a
probability. Never present it as "85% confidence" or any probabilistic claim.
"""
from __future__ import annotations

from typing import Any

DIMENSIONS = ["D1_study_design", "D2_sample_quality", "D3_measurement_validity",
              "D4_temporal_strength", "D5_directness"]

#: Version of the deterministic confidence policy (bump on any formula change).
CONFIDENCE_POLICY_VERSION = "2026-08-12.v1"


def quality_score(dimensions: dict[str, int]) -> float:
    """Sum the five 0-2 dimension scores into a 0-10 quality score."""
    total = 0.0
    for dim in DIMENSIONS:
        val = dimensions.get(dim, 0)
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            raise ValueError(f"dimension {dim} must be numeric, got {val!r}")
        total += max(0.0, min(2.0, float(val)))
    return total


def quality_level(score: float) -> str:
    """Map a 0-10 quality score to a level (references/evidence-quality.md)."""
    if score >= 8:
        return "strong"
    if score >= 5:
        return "moderate"
    if score >= 2:
        return "weak"
    return "very_weak"


def direction_of(evidence: dict[str, Any]) -> str:
    """Direction of one evidence object.

    Prefers the new contract field ``relation_to_claim`` (support | contradict |
    neutral) and falls back to the legacy ``direction`` field, kept for backward
    compatibility. Returns 'neutral' when neither is present/valid.
    """
    relation = evidence.get("relation_to_claim")
    if relation in ("support", "contradict", "neutral"):
        return relation
    return evidence.get("direction", "neutral")


def independent_studies(evidence_list: list[dict[str, Any]]) -> int:
    """Number of distinct studies behind the evidence.

    Counts unique non-empty ``study_id`` values; falls back to unique
    ``source_id`` values when ``study_id`` is absent.
    """
    ids = [e.get("study_id") or e.get("source_id") for e in evidence_list]
    return len({i for i in ids if i})


def independent_samples(evidence_list: list[dict[str, Any]]) -> int:
    """Number of distinct samples behind the evidence.

    Counts unique non-empty ``sample_id`` values. When ``sample_id`` is missing
    entirely, falls back to study-level ids (each study contributes at least one
    sample), so the count stays a deterministic lower-bound estimate.
    """
    ids = [e.get("sample_id") or e.get("study_id") or e.get("source_id") for e in evidence_list]
    return len({i for i in ids if i})


def consistency_score(directions: list[str]) -> float:
    """Consistency in [0,1]: proportion of non-neutral evidence agreeing with the majority direction."""
    non_neutral = [d for d in directions if d in ("support", "contradict")]
    if not non_neutral:
        return 0.0
    majority = max(non_neutral.count("support"), non_neutral.count("contradict"))
    return majority / len(non_neutral)


def directness_score(evidence_list: list[dict[str, Any]]) -> float:
    """Average D5 Directness (0-2) across evidence; 0 if empty."""
    if not evidence_list:
        return 0.0
    values = [e.get("quality_dimensions", {}).get("D5_directness", 0) for e in evidence_list]
    return sum(float(v) for v in values) / len(values)


def confidence(evidence_list: list[dict[str, Any]], *, target_outcome: str | None = None) -> dict[str, Any]:
    """Rule-based confidence computation per plan section 13.

    Normalized implementation (weights sum to 1.0 so the score stays in [0, 1]):

        score = 0.30*Evidence Quality + 0.25*Consistency + 0.20*Directness
                + 0.25*Evidence Count - Conflict Penalty - Unsupported Penalty

    where Conflict Penalty = 0.15 if any contradicting evidence exists, and
    Unsupported Penalty = min(0.20, 0.05 * n_unsupported). The raw quality /
    consistency / directness terms are scaled to [0, 1] first.

    Returns breakdown dict plus final label (High | Moderate | Low | Insufficient).
    """
    if not evidence_list:
        return {"confidence": "Insufficient",
                "confidence_policy_version": CONFIDENCE_POLICY_VERSION,
                "confidence_breakdown": {"evidence_count": 0}}

    # 1. Evidence Quality (mean of quality scores, scaled to 0-1 range)
    quality_values = [e.get("quality_score") for e in evidence_list]
    numeric = [q for q in quality_values if isinstance(q, (int, float))]
    avg_quality = sum(numeric) / len(numeric) if numeric else 0.0
    quality_term = avg_quality / 10.0  # 0-1

    # 2. Consistency (relation_to_claim preferred, legacy direction fallback)
    directions = [direction_of(e) for e in evidence_list]
    consistency = consistency_score(directions)

    # 3. Directness (0-2 -> 0-1)
    directness = directness_score(evidence_list) / 2.0

    # 4. Evidence count (capped at 1) — 独立研究 + 独立样本双计权，防止同一研究的
    #    多个 Evidence Object 重复放大信心（审查 P0-03）；公式与 compute_confidence.py 一致
    n_studies = independent_studies(evidence_list)
    n_samples = independent_samples(evidence_list)
    count_term = min(1.0, (n_studies + n_samples) / 8.0)

    # 5. Conflict penalty (0.15 when contradiction exists)
    conflict_penalty = 0.15 if "contradict" in directions else 0.0

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
        "confidence_score": round(score, 3),
        "confidence_policy_version": CONFIDENCE_POLICY_VERSION,
        "independent_studies": n_studies,
        "independent_samples": n_samples,
        "confidence_breakdown": {
            "score": round(score, 3),
            "evidence_quality": round(quality_term, 3),
            "consistency": round(consistency, 3),
            "directness": round(directness, 3),
            "evidence_count": len(evidence_list),
            "independent_studies": n_studies,
            "independent_samples": n_samples,
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


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 2:
        print("usage: evidence_score.py <evidence.jsonl>", file=sys.stderr)
        sys.exit(2)
    with open(sys.argv[1], encoding="utf-8") as fh:
        evs = [json.loads(line) for line in fh if line.strip()]
    for ev in evs:
        if ev.get("quality_dimensions") and ev.get("quality_score") is None:
            ev["quality_score"] = quality_score(ev["quality_dimensions"])
    print(json.dumps(confidence(evs), ensure_ascii=False, indent=2))
