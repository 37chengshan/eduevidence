"""Tests for scripts/benchmark.py — benchmark harness (plan sections 30-36)."""
import json
from pathlib import Path

from benchmark import (evaluate, load_questions, metric_citation_support_precision,
                       metric_contradiction_discovery, metric_scope_calibration,
                       metric_unsupported_claim_rate, validate_questions)

ROOT = Path(__file__).resolve().parent.parent


def test_validate_questions_on_real_set():
    questions = load_questions(ROOT / "benchmarks/questions.jsonl")
    issues = validate_questions(questions)
    assert issues == [], f"issues: {issues}"


def test_validate_questions_catches_bad_level():
    questions = [{"id": "Q1", "level": "XL", "domain": "ai_higher_education",
                  "expected_outcomes": ["retention"]}]
    issues = validate_questions(questions)
    assert any("bad level" in i for i in issues)


def test_citation_support_precision():
    result = {"citations": [
        {"supports_claim": True}, {"supports_claim": True}, {"supports_claim": False}]}
    assert metric_citation_support_precision(result) == pytest.approx(2 / 3)


def test_unsupported_claim_rate():
    result = {"claims": [
        {"status": "SUPPORTED"}, {"status": "UNSUPPORTED"}, {"status": "SUPPORTED"}]}
    assert metric_unsupported_claim_rate(result) == pytest.approx(1 / 3)


def test_contradiction_discovery():
    result = {"discovered_contradictions": ["novelty effect found", "null result in X"]}
    annotation = {"known_contradictions": ["novelty effect", "unrelated thing"]}
    assert metric_contradiction_discovery(result, annotation) == pytest.approx(0.5)


def test_scope_calibration():
    result = {"verdicts": [
        {"exceeds_evidence_boundary": False},
        {"exceeds_evidence_boundary": True}]}
    assert metric_scope_calibration(result) == pytest.approx(0.5)


def test_contradiction_discovery_empty_known():
    # Nothing known to find: perfect only if the system also reported nothing.
    assert metric_contradiction_discovery(
        {"discovered_contradictions": []}, {"known_contradictions": []}) == 1.0
    assert metric_contradiction_discovery(
        {"discovered_contradictions": ["spurious"]}, {"known_contradictions": []}) == 0.0


def test_contradiction_discovery_ignores_non_strings():
    result = {"discovered_contradictions": [{"obj": "not a string"}, "novelty effect"]}
    annotation = {"known_contradictions": ["novelty effect", "other"]}
    assert metric_contradiction_discovery(result, annotation) == pytest.approx(0.5)


def test_evaluate_with_annotation():
    result = {
        "citations": [{"supports_claim": True}],
        "claims": [{"status": "SUPPORTED"}],
        "evidence": [{"outcome_type": "retention"}],
        "verdicts": [{"exceeds_evidence_boundary": False}],
        "discovered_contradictions": ["x"],
    }
    annotation = {"known_contradictions": ["x"]}
    metrics = evaluate(result, annotation)
    assert metrics["citation_support_precision"] == 1.0
    assert metrics["unsupported_claim_rate"] == 0.0
    assert metrics["outcome_separation_accuracy"] == 1.0
    assert metrics["scope_calibration"] == 1.0
    assert metrics["contradiction_discovery_rate"] == 1.0


def test_baseline_and_ablation_catalogs_defined():
    from benchmark import ABLATIONS, BASELINES
    assert len(BASELINES) == 5
    assert len(ABLATIONS) == 7


import pytest  # noqa: E402  (kept at end to avoid circular import confusion in linters)
