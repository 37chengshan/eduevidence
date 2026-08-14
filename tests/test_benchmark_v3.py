"""Tests for scripts/benchmark_v3.py + benchmark_evaluator.py (Layer B, v3)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest

import benchmark_v3
import benchmark_evaluator as be

ROOT = Path(__file__).resolve().parent.parent

GOLD = {
    "id": "Q01",
    "key_claims": ["AI编程助手可提高新手正确率"],
    "key_supporting_sources": ["Peng et al. (2023) Copilot on LeetCode 受控实验"],
    "known_contradictions": ["部分研究未发现对复杂任务的正确率有显著差异"],
    "correct_outcome_types": ["accuracy"],
    "allowed_scope": "仅限编程作业任务正确率，不扩展到长期编程能力",
    "known_methodological_limitations": ["短期单次任务"],
    "expected_decision_range": ["pilot"],
}

GOOD_RESPONSE = (
    '{"frame": {"question": "q"}, '
    '"claims": [{"claim": "Copilot 提高正确率", "outcome_type": "accuracy", '
    '"direction": "support", "source": "Peng et al. (2023)"}], '
    '"contradictions": ["部分研究未发现对复杂任务正确率有显著差异"], '
    '"scope": {"can_claim": ["任务正确率"], "cannot_claim": ["长期能力"], '
    '"exceeds_boundary": ["不扩展到学习效果"]}, '
    '"recommended_action": "pilot", "confidence": "Moderate"}'
)


def test_extract_json_block_and_outcomes():
    data = be.extract_json_block(GOOD_RESPONSE)
    assert data is not None
    assert data["recommended_action"] == "pilot"
    assert be.extract_outcomes(GOOD_RESPONSE) == {"accuracy"}
    assert be.extract_action(GOOD_RESPONSE) == "pilot"


def test_evaluate_attempt_gold_metrics():
    m = be.evaluate_attempt(GOOD_RESPONSE, GOLD)
    assert m["outcome_separation_accuracy"] == 1.0
    assert m["decision_calibration"] == 1.0
    assert m["contradiction_recall"] >= 0.5
    assert m["citation_support_recall"] >= 0.5
    assert m["scope_calibration"] == 1.0
    assert m["method"] == "heuristic"


def test_evaluate_attempt_poor_response():
    poor = "我觉得可以用。"
    m = be.evaluate_attempt(poor, GOLD)
    assert m["outcome_separation_accuracy"] == 0.0
    assert m["decision_calibration"] == 0.0
    assert m["citation_support_recall"] == 0.0


def test_run_sim_manifest_valid_and_budget(tmp_path):
    questions = [json.loads(l) for l in
                 (ROOT / "benchmarks" / "questions.jsonl").read_text(encoding="utf-8").splitlines()
                 if l.strip()][:2]
    out = tmp_path / "run"
    manifest = benchmark_v3.run_benchmark(
        questions=questions,
        baselines=["B2_standard_agent", "B3_eduevidence_single"],
        repeats=2, out_dir=out, driver_name="sim", budget_tokens=None)
    assert manifest["run_mode"] == "simulated"
    assert len(manifest["attempts"]) == 2 * 2 * 2
    assert all(a["status"] == "completed" for a in manifest["attempts"])
    assert all(a["artifacts"] for a in manifest["attempts"])
    # manifest must validate against its schema
    sys.path.insert(0, str(ROOT))
    from validate_schema import SchemaError, Validator
    schema = json.loads((ROOT / "schemas" / "v3" / "run-manifest.schema.json").read_text(encoding="utf-8"))
    data = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    Validator(schema).validate(data, schema, "$")


def test_run_budget_stops(tmp_path):
    questions = [json.loads(l) for l in
                 (ROOT / "benchmarks" / "questions.jsonl").read_text(encoding="utf-8").splitlines()
                 if l.strip()][:5]
    out = tmp_path / "run"
    manifest = benchmark_v3.run_benchmark(
        questions=questions, baselines=["B2_standard_agent"], repeats=3,
        out_dir=out, driver_name="sim", budget_tokens=1)
    assert any(a["status"] == "budget_stopped" for a in manifest["attempts"]) or \
        "BUDGET STOPPED" in manifest.get("notes", "")


def test_evaluate_run_and_report(tmp_path):
    questions = [json.loads(l) for l in
                 (ROOT / "benchmarks" / "questions.jsonl").read_text(encoding="utf-8").splitlines()
                 if l.strip()][:1]
    out = tmp_path / "run"
    manifest = benchmark_v3.run_benchmark(
        questions=questions, baselines=["B3_eduevidence_single"],
        repeats=2, out_dir=out, driver_name="sim", budget_tokens=None)
    # overwrite responses with the gold-matching response so metrics are meaningful
    for a in manifest["attempts"]:
        art = out / a["artifacts"][0]
        data = json.loads(art.read_text(encoding="utf-8"))
        data["response"] = GOOD_RESPONSE
        art.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = be.evaluate_run(out, manifest, ROOT / "benchmarks" / "annotations")
    pb = summary["per_baseline"]["B3_eduevidence_single"]
    assert pb["n"] == 2  # 1 question x 2 repeats
    assert pb["metrics"]["decision_calibration"]["mean"] == 1.0

    report_path = tmp_path / "report.md"
    md = be.report_from_run(out, manifest, report_path)
    assert "SIMULATED" in md
    assert "harness validation only" in md
