"""Tests for scripts/evidence_matrix.py — Evidence Matrix construction."""
import json
from pathlib import Path

from evidence_matrix import evidence_matrix, render_markdown

ROOT = Path(__file__).resolve().parent.parent


def _ev(claim, outcome, direction, score=8.0, eid="E-1", directness=2):
    return {
        "evidence_id": eid,
        "claim": claim,
        "outcome_type": outcome,
        "direction": direction,
        "quality_score": score,
        "quality_dimensions": {"D5_directness": directness},
    }


def test_matrix_groups_by_claim_outcome():
    evs = [
        _ev("AI improves speed", "completion_time", "support", eid="E-1"),
        _ev("AI improves speed", "completion_time", "contradict", eid="E-2"),
        _ev("AI improves speed", "retention", "support", eid="E-3"),
    ]
    matrix = evidence_matrix(evs)
    assert len(matrix) == 2  # two (claim, outcome) pairs


def test_matrix_verdict_conflicted():
    evs = [
        _ev("AI improves speed", "completion_time", "support", eid="E-1"),
        _ev("AI improves speed", "completion_time", "contradict", eid="E-2"),
    ]
    matrix = evidence_matrix(evs)
    row = next(r for r in matrix if r["outcome"] == "completion_time")
    assert row["verdict"] == "CONFLICTED"


def test_matrix_verdict_supported():
    evs = [_ev("AI improves speed", "completion_time", "support", score=8.0)]
    matrix = evidence_matrix(evs)
    assert matrix[0]["verdict"] == "SUPPORTED"


def test_matrix_verdict_weak_low_quality():
    evs = [_ev("AI improves speed", "completion_time", "support", score=3.0)]
    matrix = evidence_matrix(evs)
    assert matrix[0]["verdict"] == "WEAK"


def test_matrix_verdict_contradicted_only():
    evs = [_ev("AI harms speed", "completion_time", "contradict")]
    matrix = evidence_matrix(evs)
    assert matrix[0]["verdict"] == "CONTRADICTED"


def test_render_markdown_has_header():
    evs = [_ev("AI improves speed", "completion_time", "support")]
    md = render_markdown(evidence_matrix(evs))
    assert "| Claim | Outcome | Support | Contradiction | Neutral | Quality | Directness | Verdict |" in md
    assert "|--" in md


def test_matrix_puts_neutral_in_neutral_column():
    evs = [
        _ev("AI improves speed", "completion_time", "support", eid="E-1"),
        _ev("AI improves speed", "completion_time", "neutral", eid="E-2"),
    ]
    matrix = evidence_matrix(evs)
    row = next(r for r in matrix if r["outcome"] == "completion_time")
    assert row["support"] == "E-1"
    assert row["contradiction"] == "-"
    assert row["neutral"] == "E-2"


def test_matrix_verdict_neutral_only():
    evs = [_ev("AI improves speed", "completion_time", "neutral", eid="E-2")]
    matrix = evidence_matrix(evs)
    assert matrix[0]["verdict"] == "NEUTRAL"


def test_matrix_verdict_conflicted_keeps_neutral_separate():
    evs = [
        _ev("AI improves speed", "completion_time", "support", eid="E-1"),
        _ev("AI improves speed", "completion_time", "contradict", eid="E-2"),
        _ev("AI improves speed", "completion_time", "neutral", eid="E-3"),
    ]
    matrix = evidence_matrix(evs)
    row = next(r for r in matrix if r["outcome"] == "completion_time")
    assert row["verdict"] == "CONFLICTED"
    assert row["neutral"] == "E-3"
    assert "E-3" not in row["contradiction"]


def test_example_pack_builds_matrix():
    evs = [json.loads(line) for line in
           (ROOT / "examples/ai-coding-assistant/evidence.jsonl").read_text(encoding="utf-8").splitlines()
           if line.strip()]
    matrix = evidence_matrix(evs)
    assert matrix, "matrix should not be empty"
    assert any(r["verdict"] == "CONTRADICTED" for r in matrix)
