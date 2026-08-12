"""Tests for scripts/pre_verdict_gate.py — 11-item Pre-Verdict Gate (Phase 15).

A valid demo workspace is built by the orchestrator's demo seeding path
(init_run + advance with the ai-coding-assistant example pack), so these tests
double as an end-to-end sanity check of the gate contract.
"""
import json
import shutil

import pytest

from pre_verdict_gate import (GATE_ITEMS, apply_enforcement, evaluate_workspace,
                              main as gate_main)
from run_workspace import RunWorkspace

ROOT = pytest.importorskip("pathlib").Path(__file__).resolve().parent.parent
DEMO_PACK = ROOT / "examples" / "ai-coding-assistant"

EXPECTED_ITEM_IDS = {
    "research_frame_valid", "sources_valid", "evidence_schema_valid",
    "source_dedupe", "counter_evidence_search", "methodology_audit",
    "claim_evidence_audit", "outcome_mapping", "scope_calibration",
    "independent_study_count", "deterministic_confidence",
}


def build_demo_workspace(tmp_path, run_id="demo"):
    """Run the demo seeding path and return the workspace path."""
    from orchestrator import advance, init_run
    init_run(tmp_path, "Should first-year C students use AI coding assistants?",
             depth="M", run_id=run_id, approve_agent_mcp=False)
    ws = RunWorkspace(tmp_path, run_id)
    summary = advance(ws, demo_pack=DEMO_PACK)
    assert summary["completed_all"], summary
    return ws.path


@pytest.fixture
def demo_ws(tmp_path):
    return build_demo_workspace(tmp_path)


def test_gate_has_exactly_eleven_items():
    assert len(GATE_ITEMS) == 11
    assert {spec["id"] for spec in GATE_ITEMS} == EXPECTED_ITEM_IDS


def test_gate_passes_for_valid_demo_workspace(demo_ws):
    report = evaluate_workspace(demo_ws, require_final=True)
    assert report["passed"] is True
    assert report["high_confidence_allowed"] is True
    assert report["max_confidence"] == "High"
    assert report["critical_failures"] == []
    for item in report["items"].values():
        assert item["status"] in ("pass", "warn"), item


def test_gate_fails_without_counter_evidence_search(demo_ws):
    (demo_ws / "skeptic.json").unlink()
    report = evaluate_workspace(demo_ws, require_final=True)
    assert report["passed"] is False
    assert "counter_evidence_search" in report["critical_failures"]
    assert report["high_confidence_allowed"] is False
    assert report["max_confidence"] == "Low"


def test_gate_fails_without_evidence(demo_ws):
    (demo_ws / "evidence.jsonl").unlink()
    report = evaluate_workspace(demo_ws, require_final=True)
    assert report["passed"] is False
    assert "evidence_schema_valid" in report["critical_failures"]
    assert report["max_confidence"] == "Low"


def test_gate_fails_on_duplicate_sources(demo_ws):
    sources = [(json.loads(line)) for line in
               (demo_ws / "sources.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    with (demo_ws / "sources.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(sources[0]) + "\n")
    report = evaluate_workspace(demo_ws, require_final=True)
    assert report["passed"] is False
    assert "source_dedupe" in report["critical_failures"]


def test_gate_fails_on_missing_final_verdict_when_required(demo_ws):
    (demo_ws / "final_verdict.json").unlink()
    report = evaluate_workspace(demo_ws, require_final=True)
    assert report["passed"] is False
    assert "deterministic_confidence" in report["critical_failures"]
    # without require_final the item is only a warning (adjudicate pending)
    report = evaluate_workspace(demo_ws, require_final=False)
    assert report["items"]["deterministic_confidence"]["status"] == "warn"


def test_gate_fails_on_methodology_fail(demo_ws):
    methodology = json.loads((demo_ws / "methodology.json").read_text(encoding="utf-8"))
    methodology["verdict"] = "FAIL"
    (demo_ws / "methodology.json").write_text(json.dumps(methodology), encoding="utf-8")
    report = evaluate_workspace(demo_ws, require_final=True)
    assert "methodology_audit" in report["critical_failures"]


def test_gate_blocks_high_for_single_independent_study(tmp_path):
    """One independent study -> warn (not critical) but High confidence blocked."""
    ws = build_demo_workspace(tmp_path, run_id="single")
    evidence = [json.loads(line) for line in
                (ws / "evidence.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    # keep only one study (two evidence rows from the same source)
    one_study = [e for e in evidence if e.get("source_id") == evidence[0].get("source_id")][:2]
    with (ws / "evidence.jsonl").open("w", encoding="utf-8") as fh:
        for ev in one_study:
            fh.write(json.dumps(ev) + "\n")
    # verdict must reference only surviving evidence ids
    verdict = json.loads((ws / "raw_verdict.json").read_text(encoding="utf-8"))
    ids = [ev["evidence_id"] for ev in one_study]
    verdict["supported_claims"] = [
        f"Claim bound to evidence — {ids[0]}, {ids[1]}.",
    ]
    verdict["uncertain_claims"] = []
    verdict["contradicted_claims"] = []
    (ws / "raw_verdict.json").write_text(json.dumps(verdict, ensure_ascii=False), encoding="utf-8")
    (ws / "final_verdict.json").unlink()

    report = evaluate_workspace(ws, require_final=False)
    assert report["passed"] is True
    assert report["items"]["independent_study_count"]["status"] == "warn"
    assert report["high_confidence_allowed"] is False
    assert report["max_confidence"] == "Moderate"


def test_apply_enforcement_caps_high_verdict_on_failed_gate(demo_ws):
    (demo_ws / "skeptic.json").unlink()
    gate = evaluate_workspace(demo_ws, require_final=True)
    verdict = {"decision_question": "q", "confidence": "High",
               "recommended_action": "adopt"}
    capped = apply_enforcement(verdict, gate)
    assert capped["confidence"] == "Low"
    assert capped["recommended_action"] == "pilot"
    enforcement = capped["extensions"]["gate_enforcement"]
    assert enforcement["passed"] is False
    assert enforcement["max_confidence"] == "Low"
    assert enforcement["confidence_before"] == "High"
    assert enforcement["action_before"] == "adopt"


def test_apply_enforcement_preserves_low_verdict(demo_ws):
    gate = evaluate_workspace(demo_ws, require_final=True)
    verdict = {"decision_question": "q", "confidence": "Insufficient",
               "recommended_action": "insufficient_evidence"}
    capped = apply_enforcement(verdict, gate)
    assert capped["confidence"] == "Insufficient"
    assert capped["recommended_action"] == "insufficient_evidence"


def test_apply_enforcement_keeps_action_when_passed_but_high_blocked(demo_ws):
    gate = evaluate_workspace(demo_ws, require_final=True)
    gate["max_confidence"] = "Moderate"
    gate["passed"] = True
    verdict = {"decision_question": "q", "confidence": "High",
               "recommended_action": "adopt"}
    capped = apply_enforcement(verdict, gate)
    assert capped["confidence"] == "Moderate"
    assert capped["recommended_action"] == "adopt"


def test_gate_cli_exit_codes(tmp_path, capsys):
    ws = build_demo_workspace(tmp_path, run_id="cli")
    assert gate_main(["--workspace", str(ws), "--require-final", "--json"]) == 0
    (ws / "skeptic.json").unlink()
    assert gate_main(["--workspace", str(ws), "--require-final", "--json"]) == 1
    out = capsys.readouterr().out
    assert '"passed": false' in out
    assert '"max_confidence": "Low"' in out


def test_gate_cli_apply_verdict_writes_capped_file(tmp_path):
    ws = build_demo_workspace(tmp_path, run_id="cli-apply")
    (ws / "skeptic.json").unlink()
    verdict_path = ws / "raw_verdict.json"
    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    verdict["confidence"] = "High"
    verdict["recommended_action"] = "adopt"
    verdict_path.write_text(json.dumps(verdict), encoding="utf-8")
    assert gate_main(["--workspace", str(ws), "--apply-verdict", str(verdict_path)]) == 1
    capped = json.loads(verdict_path.read_text(encoding="utf-8"))
    assert capped["confidence"] == "Low"
    assert capped["recommended_action"] == "pilot"
    assert capped["extensions"]["gate_enforcement"]["passed"] is False
