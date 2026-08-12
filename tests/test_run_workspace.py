"""Tests for scripts/run_workspace.py — Run Workspace & Run Manifest (Phase 12-13)."""
import json

import pytest

from run_workspace import (STAGES, WORKSPACE_FILES, RunWorkspace, build_manifest,
                           load_jsonl, next_run_id, utc_now)


@pytest.fixture
def ws(tmp_path):
    workspace = RunWorkspace(tmp_path, "test-run")
    workspace.create()
    return workspace


def test_create_materializes_every_workspace_file(ws):
    """The full artifact contract must exist after create()."""
    for name in WORKSPACE_FILES:
        path = ws.path / name
        assert path.exists(), f"missing workspace artifact {name}"
    assert (ws.path / "fetch").is_dir()
    assert (ws.path / "task-briefs").is_dir()


def test_manifest_has_all_phase13_fields(ws):
    manifest = build_manifest(
        "run-1", "Should students use AI?",
        execution_mode="platform_native",
        agent_mcp_available=False, agent_mcp_approved=False,
        scp_available=False)
    for field in ("run_id", "skill_version", "git_commit", "started_at",
                  "question", "execution_mode", "scp_available",
                  "agent_mcp_available", "agent_mcp_approved",
                  "resource_policy_version", "confidence_policy_version"):
        assert field in manifest, f"manifest missing {field}"
    assert manifest["run_id"] == "run-1"
    assert manifest["execution_mode"] == "platform_native"
    assert manifest["confidence_policy_version"]


def test_manifest_roundtrip(ws):
    manifest = build_manifest("run-1", "Q?", execution_mode="platform_native",
                              agent_mcp_available=False, agent_mcp_approved=True)
    ws.save_manifest(manifest)
    loaded = ws.load_manifest()
    assert loaded["run_id"] == "run-1"
    assert loaded["agent_mcp_approved"] is True
    assert loaded["question"] == "Q?"


def test_state_seeded_with_all_stages_pending(ws):
    state = ws.load_state()
    assert state["status"] == "running"
    for stage in STAGES:
        assert state["stages"][stage]["status"] == "pending"


def test_state_roundtrip_and_mark_stage(ws):
    ws.mark_stage("frame", "completed", detail="schema-valid", artifacts=["frame.json"])
    state = ws.load_state()
    assert state["stages"]["frame"]["status"] == "completed"
    assert state["stages"]["frame"]["artifacts"] == ["frame.json"]
    assert state["updated_at"]


def test_trace_appends_jsonl(ws):
    ws.trace("stage_started", stage="frame", detail="x")
    ws.trace("stage_completed", stage="frame")
    records = load_jsonl(ws.path / "trace.jsonl")
    assert [r["event"] for r in records] == ["workspace_created", "stage_started", "stage_completed"]
    assert records[-1]["stage"] == "frame"


def test_write_brief_creates_handoff_prompt(ws):
    path = ws.write_brief("retrieve", "Q?", "find sources")
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    assert "retrieve" in content and "Q?" in content


def test_next_run_id_unique_and_timestamped(tmp_path):
    first = next_run_id(tmp_path)
    assert first.startswith("20")
    tmp_path.joinpath(first).mkdir()
    second = next_run_id(tmp_path)
    assert second != first
    assert second.startswith(first.split("-")[0])


def test_load_jsonl_skips_blank_and_bad_lines(tmp_path):
    path = tmp_path / "x.jsonl"
    path.write_text('{"a": 1}\n\nnot json\n{"b": 2}\n', encoding="utf-8")
    assert load_jsonl(path) == [{"a": 1}, {"b": 2}]


def test_utc_now_rfc3339():
    value = utc_now()
    assert "T" in value and value.endswith("+00:00")
