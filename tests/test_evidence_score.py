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


def test_decision_consistency_score():
    """D-2: consistency is computed over decision_relation, not relation_to_claim."""
    from evidence_score import decision_consistency_score
    # claim-level support for every evidence, but adoption-level opposition
    assert decision_consistency_score(
        ["support_adoption", "support_adoption", "oppose_adoption"]) == 2 / 3
    assert decision_consistency_score(
        ["support_adoption", "oppose_adoption"]) == 0.5
    # conditional / neutral are non-committal
    assert decision_consistency_score(
        ["conditional", "neutral", "support_adoption"]) == 1.0
    assert decision_consistency_score(["conditional", "neutral"]) == 0.0


def test_consistency_prefers_decision_relation_over_relation_to_claim():
    """D-2 acceptance: all-support claims can still disagree at decision level."""
    from evidence_score import confidence
    evs = [
        {"relation_to_claim": "support", "decision_relation": "support_adoption",
         "quality_score": 8, "quality_dimensions": {"D5_directness": 2},
         "outcome_type": "retention", "status": "SUPPORTED", "study_id": f"S{i}",
         "sample_id": f"P{i}"}
        for i in range(3)
    ] + [{"relation_to_claim": "support", "decision_relation": "oppose_adoption",
          "quality_score": 8, "quality_dimensions": {"D5_directness": 2},
          "outcome_type": "retention", "status": "SUPPORTED", "study_id": "S4",
          "sample_id": "P4"}]
    breakdown = confidence(evs)["confidence_breakdown"]
    # relation-level consistency would be 1.0; decision-level is 3/4
    assert breakdown["consistency"] == pytest.approx(0.75)
    assert breakdown["conflict_penalty"] == 0.15


def test_count_term_uses_studies_not_samples():
    """D-1 acceptance: count_term = min(1.0, independent_studies / 4).

    Multiple samples within the same study must not inflate the count term;
    independent_samples is reported separately.
    """
    from evidence_score import confidence
    one_study_two_samples = [
        {"direction": "support", "quality_score": 8,
         "quality_dimensions": {"D5_directness": 2},
         "outcome_type": "retention", "status": "SUPPORTED",
         "study_id": "S1", "sample_id": f"P{i}"}
        for i in range(8)  # 1 study, 8 samples
    ]
    breakdown = confidence(one_study_two_samples)["confidence_breakdown"]
    assert breakdown["independent_studies"] == 1
    assert breakdown["independent_samples"] == 8
    assert breakdown["count_term"] == pytest.approx(0.25)  # 1 / 4, not 9/8
    four_studies = [
        {"direction": "support", "quality_score": 8,
         "quality_dimensions": {"D5_directness": 2},
         "outcome_type": "retention", "status": "SUPPORTED",
         "study_id": f"S{i}", "sample_id": f"S{i}-P1"}
        for i in range(4)
    ]
    assert confidence(four_studies)["confidence_breakdown"]["count_term"] == pytest.approx(1.0)


def test_confidence_high_for_consistent_strong_evidence():
    evs = [
        {"direction": "support", "quality_score": 8, "quality_dimensions": {"D5_directness": 2},
         "outcome_type": "retention", "status": "SUPPORTED",
         "source_id": f"S-{i}", "study_id": f"STUDY-{i}", "sample_id": f"SAMPLE-{i}"}
        for i in range(8)
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
