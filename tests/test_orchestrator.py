"""Tests for scripts/orchestrator.py — Run Orchestrator (Phase 11), Resume (Phase 32),
Failure Matrix (Phase 33), and the `eduevidence run` CLI entry."""
import json

import pytest

from orchestrator import (FAILURE_MATRIX, STAGE_SPEC, STAGES, advance, handle_failure,
                          init_run, main)
from run_workspace import RunWorkspace, load_json, load_jsonl

ROOT = pytest.importorskip("pathlib").Path(__file__).resolve().parent.parent
DEMO_PACK = ROOT / "examples" / "ai-coding-assistant"


def run_cli(argv):
    return main(argv)


# ------------------------------------------------------------------ init


def test_init_creates_workspace_and_manifest(tmp_path):
    assert run_cli(["run", "--question", "Q?", "--depth", "deep",
                    "--run-id", "r1", "--runs-dir", str(tmp_path), "--dry-run"]) == 0
    ws = RunWorkspace(tmp_path, "r1")
    assert ws.exists()
    manifest = ws.load_manifest()
    for field in ("run_id", "skill_version", "git_commit", "started_at", "question",
                  "execution_mode", "scp_available", "agent_mcp_available",
                  "agent_mcp_approved", "resource_policy_version",
                  "confidence_policy_version"):
        assert field in manifest
    assert manifest["run_id"] == "r1"
    assert manifest["question"] == "Q?"
    # planning artifacts
    for name in ("capability_plan.json", "resource_plan.json", "execution_plan.json",
                 "model_inventory.json", "agent_mcp_approval.json"):
        assert (ws.path / name).is_file(), name
    execution = json.loads((ws.path / "execution_plan.json").read_text(encoding="utf-8"))
    assert [s["name"] for s in execution["stages"]] == STAGES
    assert (ws.path / "agent_mcp_approval.json").read_text(encoding="utf-8")
    state = ws.load_state()
    assert state["stages"]["frame"]["status"] == "pending"
    assert state["current_stage"] == "frame"


def test_init_depth_alias_maps_to_manifest(tmp_path):
    ws = init_run(tmp_path, "Q?", depth="deep", run_id="r-deep")
    assert ws.load_state()["depth"] == "L"
    with pytest.raises(ValueError):
        init_run(tmp_path, "Q?", depth="bogus", run_id="r-bad")


def test_manifest_agent_mcp_approval_flag(tmp_path):
    ws = init_run(tmp_path, "Q?", run_id="r-approve", approve_agent_mcp=True)
    assert ws.load_manifest()["agent_mcp_approved"] is True
    approval = json.loads((ws.path / "agent_mcp_approval.json").read_text(encoding="utf-8"))
    assert approval["approved"] is True


# ------------------------------------------------------------ full demo run


def test_full_demo_run_completes_all_stages(tmp_path):
    assert run_cli(["run", "--question", "Should first-year C students use AI coding assistants?",
                    "--depth", "M", "--run-id", "demo", "--runs-dir", str(tmp_path),
                    "--demo-pack", str(DEMO_PACK)]) == 0
    ws = RunWorkspace(tmp_path, "demo")
    state = ws.load_state()
    assert state["status"] == "completed"
    for stage in STAGES:
        assert state["stages"][stage]["status"] == "completed", stage

    final = load_json(ws.path / "final_verdict.json")
    assert final["confidence"] == "Moderate"
    assert final["confidence_score"] == pytest.approx(0.526, abs=0.01)
    assert final["confidence_policy_version"]
    assert final["raw_model_confidence"] == "Moderate"  # preserved for audit

    gate = json.loads((ws.path / "gate_report.json").read_text(encoding="utf-8"))
    assert gate["post"]["passed"] is True
    assert gate["final_confidence"] == "Moderate"

    result = load_json(ws.path / "result.json")
    assert result["meta"]["skill"] == "eduevidence"
    assert result["decision"]["recommended_action"] == "pilot"
    assert all("claim_id" in c for c in result["claims"])
    assert (ws.path / "result.zh.json").is_file()
    assert (ws.path / "report_spec.json").is_file()
    assert (ws.path / "report.html").is_file()


def test_fresh_run_blocks_on_external_frame_and_writes_brief(tmp_path):
    assert run_cli(["run", "--question", "Q?", "--run-id", "fresh",
                    "--runs-dir", str(tmp_path)]) == 0
    ws = RunWorkspace(tmp_path, "fresh")
    state = ws.load_state()
    assert state["stages"]["frame"]["status"] == "pending"
    assert state["current_stage"] == "frame"
    assert (ws.path / "task-briefs" / "frame.md").is_file()
    assert load_jsonl(ws.path / "trace.jsonl")


# ------------------------------------------------------------------ resume


def test_resume_continues_from_first_pending_stage(tmp_path):
    run_cli(["run", "--question", "Q?", "--run-id", "res", "--runs-dir", str(tmp_path)])
    ws = RunWorkspace(tmp_path, "res")
    # simulate an external agent delivering the frame artifact
    (ws.path / "frame.json").write_bytes((DEMO_PACK / "frame.json").read_bytes())
    assert run_cli(["resume", "--run-id", "res", "--runs-dir", str(tmp_path)]) == 0
    state = ws.load_state()
    assert state["stages"]["frame"]["status"] == "completed"
    assert state["stages"]["retrieve"]["status"] == "pending"
    assert state["current_stage"] == "retrieve"


def test_resume_reruns_completed_stage_with_lost_artifact(tmp_path):
    run_cli(["run", "--question", "Q?", "--run-id", "full", "--runs-dir", str(tmp_path),
             "--demo-pack", str(DEMO_PACK)])
    ws = RunWorkspace(tmp_path, "full")
    assert ws.load_state()["status"] == "completed"
    # artifact loss (crash/corruption) must trigger re-run on resume
    (ws.path / "result.json").unlink()
    assert run_cli(["resume", "--run-id", "full", "--runs-dir", str(tmp_path),
                    "--demo-pack", str(DEMO_PACK)]) == 0
    state = ws.load_state()
    assert state["status"] == "completed"
    assert (ws.path / "result.json").is_file()
    assert state["stages"]["present"]["status"] == "completed"
    # completed stages stay completed (no re-seeding side effects)
    assert state["stages"]["frame"]["status"] == "completed"


def test_resume_unknown_run_id_errors(tmp_path):
    assert run_cli(["resume", "--run-id", "nope", "--runs-dir", str(tmp_path)]) == 2


# ------------------------------------------------------------- failure matrix


def test_failure_matrix_covers_retrieval_and_orchestration_states():
    for token in ("TOOL_FAILURE", "SCHEMA_INVALID", "STAGE_ARTIFACT_MISSING",
                  "GATE_CRITICAL_FAILURE", "FETCH_FAILED", "FETCH_PARTIAL",
                  "SEARCH_NO_RESULT", "INSUFFICIENT_EVIDENCE",
                  "AGENT_MCP_UNAVAILABLE", "REPORT_INVALID",
                  "INSUFFICIENT_SOURCES", "NEEDS_USER_CONTEXT",
                  "AGENT_MCP_APPROVAL_REQUIRED", "PRE_VERDICT_FAILED"):
        assert token in FAILURE_MATRIX
        entry = FAILURE_MATRIX[token]
        assert entry["action"] and "retry" in entry


def test_handle_failure_returns_action():
    plan = handle_failure("FETCH_FAILED")
    assert plan["state"] == "FETCH_FAILED"
    assert plan["action"] == "alternate_fetch_provider_then_alternate_source"
    assert plan["retry"] is True
    plan = handle_failure("SCHEMA_INVALID")
    assert plan["retry"] is False
    assert plan["action"] == "block_stage_advance_and_fix_artifact"
    with pytest.raises(ValueError):
        handle_failure("NOT_A_STATE")


def test_schema_invalid_failure_blocks_run(tmp_path):
    run_cli(["run", "--question", "Q?", "--run-id", "bad", "--runs-dir", str(tmp_path),
             "--demo-pack", str(DEMO_PACK)])
    ws = RunWorkspace(tmp_path, "bad")
    # corrupt the seeded frame so the schema gate fails on resume
    (ws.path / "frame.json").write_text('{"question": 123}', encoding="utf-8")
    ws.mark_stage("frame", "pending", detail="forced re-validation")
    assert run_cli(["resume", "--run-id", "bad", "--runs-dir", str(tmp_path),
                    "--demo-pack", str(DEMO_PACK)]) == 1
    state = ws.load_state()
    assert state["stages"]["frame"]["status"] == "failed"


def test_status_and_list_commands(tmp_path, capsys):
    run_cli(["run", "--question", "Q?", "--run-id", "s1", "--runs-dir", str(tmp_path)])
    assert run_cli(["status", "--run-id", "s1", "--runs-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "s1" in out and "frame" in out
    assert run_cli(["list", "--runs-dir", str(tmp_path)]) == 0
    assert "s1" in capsys.readouterr().out
    assert run_cli(["status", "--run-id", "missing", "--runs-dir", str(tmp_path)]) == 2


def test_gate_subcommand_runs_gate(tmp_path):
    run_cli(["run", "--question", "Q?", "--run-id", "g1", "--runs-dir", str(tmp_path),
             "--demo-pack", str(DEMO_PACK)])
    assert run_cli(["gate", "--run-id", "g1", "--runs-dir", str(tmp_path),
                    "--require-final"]) == 0
