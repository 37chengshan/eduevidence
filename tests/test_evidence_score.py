"""Tests for scripts/evidence_score.py — quality scoring and confidence computation."""
import json
from pathlib import Path

import pytest

from evidence_score import (confidence, consistency_score, directness_score,
                            quality_level, quality_score)

ROOT = Path(__file__).resolve().parent.parent

SAMPLE_DIMS = {
    "D1_study_design": 2,
    "D2_sample_quality": 2,
    "D3_measurement_validity": 2,
    "D4_temporal_strength": 2,
    "D5_directness": 2,
}


def test_quality_score_max():
    assert quality_score(SAMPLE_DIMS) == 10.0


def test_quality_score_mid():
    dims = {k: 1 for k in SAMPLE_DIMS}
    assert quality_score(dims) == 5.0


def test_quality_score_clamps():
    dims = {**SAMPLE_DIMS, "D1_study_design": 99}
    assert quality_score(dims) == 10.0


def test_quality_levels():
    assert quality_level(9) == "strong"
    assert quality_level(6) == "moderate"
    assert quality_level(3.5) == "weak"
    assert quality_level(2) == "weak"      # references/evidence-quality.md: 2-4 weak
    assert quality_level(1) == "very_weak"
    assert quality_level(0) == "very_weak"


def test_consistency_score():
    assert consistency_score(["support", "support", "contradict"]) == 2 / 3
    assert consistency_score(["support", "contradict"]) == 0.5
    assert consistency_score(["neutral", "neutral"]) == 0.0


def test_confidence_high_for_consistent_strong_evidence():
    evs = [
        {"direction": "support", "quality_score": 8, "quality_dimensions": {"D5_directness": 2},
         "outcome_type": "retention", "status": "SUPPORTED"}
        for _ in range(8)
    ]
    result = confidence(evs)
    assert result["confidence"] == "High"


def test_confidence_insufficient_for_empty():
    assert confidence([])["confidence"] == "Insufficient"


def test_confidence_penalized_by_conflict():
    strong = [{"direction": "support", "quality_score": 8,
               "quality_dimensions": {"D5_directness": 2},
               "outcome_type": "retention", "status": "SUPPORTED"} for _ in range(6)]
    conflicted = strong + [{"direction": "contradict", "quality_score": 8,
                            "quality_dimensions": {"D5_directness": 2},
                            "outcome_type": "retention", "status": "SUPPORTED"}]
    breakdown = confidence(conflicted)["confidence_breakdown"]
    assert breakdown["conflict_penalty"] == 0.15
    assert breakdown["score"] < confidence(strong)["confidence_breakdown"]["score"]


def test_confidence_penalized_by_unsupported():
    evs = [{"direction": "support", "quality_score": 8,
            "quality_dimensions": {"D5_directness": 2},
            "outcome_type": "retention", "status": "UNSUPPORTED"} for _ in range(4)]
    breakdown = confidence(evs)["confidence_breakdown"]
    assert breakdown["unsupported_penalty"] == pytest.approx(0.20)  # capped


def test_confidence_score_in_unit_range():
    evs = [{"direction": "support", "quality_score": 8,
            "quality_dimensions": {"D5_directness": 2},
            "outcome_type": "retention", "status": "SUPPORTED"} for _ in range(8)]
    score = confidence(evs)["confidence_breakdown"]["score"]
    assert 0.0 <= score <= 1.0


def test_example_confidence_reproducible():
    """confidence() recomputed from each example's evidence must match its shipped
    verdict.json confidence_breakdown (auditability guarantee)."""
    for ex in ("ai-coding-assistant", "ai-writing-assistant", "ai-tutor"):
        evidence = [json.loads(line) for line in
                    (ROOT / f"examples/{ex}/evidence.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip()]
        verdict = json.loads((ROOT / f"examples/{ex}/verdict.json").read_text(encoding="utf-8"))
        computed = confidence(evidence)
        assert computed["confidence"] == verdict["confidence"], ex
        for key, value in verdict["confidence_breakdown"].items():
            assert computed["confidence_breakdown"][key] == pytest.approx(value), \
                f"{ex}: breakdown[{key}] mismatch"
