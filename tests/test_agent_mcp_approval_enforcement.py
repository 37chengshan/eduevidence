"""Enforcement tests: recommendations only from user-usable scanned models,
and no unconfirmed model can ever be dispatched."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import pytest

from integrations import agent_mcp as agent_mcp_mod
from integrations.agent_mcp import (
    AGENT_MCP_APPROVAL_REQUIRED,
    ROLE_REQUIREMENTS,
    build_approval_record,
    build_recommendation_table,
    cross_model_review,
    is_approval_current,
    safe_spawn,
    write_approval,
)

ALL_ROLES = sorted(ROLE_REQUIREMENTS)


def _approval(model: str = "scanned-model-a") -> dict:
    roles = {role: {"cli": "omp", "model": model} for role in ALL_ROLES}
    return build_approval_record(roles, ["omp"])


def _inventory(models: list[str]) -> dict:
    details = {
        m: {"context": "128K", "images": "no"} for m in models
    }
    return {"clis": {"omp": {"available": True, "models": models,
                             "model_details": details}},
            "clis2": {}}


def test_recommendations_are_scan_driven_not_fixed():
    first = {"opencode-go/deepseek-v4-flash", "jbb/gpt-5.6-luna"}
    second = {"opencode-go/deepseek-v4-flash", "jbb/claude-opus-5"}
    table1 = build_recommendation_table(["omp"], _inventory(sorted(first)))
    table2 = build_recommendation_table(["omp"], _inventory(sorted(second)))
    for table, scanned in ((table1, first), (table2, second)):
        for row in table["recommendations"]:
            assert row.get("cli") in ("omp", None)
            if row.get("model"):
                assert row["model"] in scanned, f"unscanned model leaked: {row['model']}"
    # 换扫描集合必须能改变推荐（不允许固定推荐表）
    models1 = {r["model"] for r in table1["recommendations"] if r.get("model")}
    models2 = {r["model"] for r in table2["recommendations"] if r.get("model")}
    assert models1 != models2


def test_cross_model_review_requires_approval(monkeypatch):
    monkeypatch.setattr(agent_mcp_mod, "detect_agent_mcp", lambda: {"available": True})
    result = cross_model_review({"verdict": "PILOT"}, target_cli="omp",
                                model="opencode-go/deepseek-v4-flash", approval=None)
    assert result["status"] == AGENT_MCP_APPROVAL_REQUIRED
    assert "spawn_call" not in result


def test_cross_model_review_refuses_unapproved_model(monkeypatch):
    monkeypatch.setattr(agent_mcp_mod, "detect_agent_mcp", lambda: {"available": True})
    approval = _approval(model="scanned-model-a")
    result = cross_model_review({"verdict": "PILOT"}, target_cli="omp",
                                model="not-confirmed-model", approval=approval)
    assert result["status"] == AGENT_MCP_APPROVAL_REQUIRED


def test_cross_model_review_accepts_approved_model_only(monkeypatch):
    monkeypatch.setattr(agent_mcp_mod, "detect_agent_mcp", lambda: {"available": True})
    approval = _approval(model="scanned-model-a")
    result = cross_model_review({"verdict": "PILOT"}, target_cli="omp",
                                model="scanned-model-a", approval=approval)
    assert result["status"] == "READY"
    spawn = result["spawn_call"]["arguments"]
    assert spawn["model"] == "scanned-model-a" and spawn["target_cli"] == "omp"


def test_safe_spawn_refuses_any_model_outside_approval():
    approval = _approval(model="scanned-model-a")
    for model in ("", "opencode-go/deepseek-v4-flash", "other/claude-x"):
        result = safe_spawn("evidence-retriever", "p", approval,
                            target_cli="omp", model=model)
        assert result["status"] == AGENT_MCP_APPROVAL_REQUIRED, model


def test_global_approval_roundtrip_and_tamper(tmp_path, monkeypatch):
    import scripts.orchestrator as orch  # noqa: PLC0415

    monkeypatch.setenv("EDUEVIDENCE_HOME", str(tmp_path))
    path = orch._global_approval_path()
    roles = {role: {"cli": "omp", "model": "scanned-model-a"} for role in ALL_ROLES}
    write_approval(path, roles, ["omp"])
    loaded = orch.load_global_approval()
    assert loaded and loaded["approved"] is True
    assert loaded["role_mapping_hash"]
    ok, changes = is_approval_current(loaded, roles, ["omp"])
    assert ok and not changes
    # 篡改（换模型不改 hash）必须失效
    loaded["roles"]["evidence-retriever"]["model"] = "tampered"
    ok, changes = is_approval_current(loaded, roles, ["omp"])
    assert not ok and changes
    result = safe_spawn("evidence-retriever", "p", loaded)
    assert result["status"] == AGENT_MCP_APPROVAL_REQUIRED


def test_non_tty_startup_returns_false_without_prompting(monkeypatch, capsys):
    import scripts.orchestrator as orch  # noqa: PLC0415

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    result = orch.interactive_agent_mcp_setup(False)
    assert result is False
    assert "非交互终端" in capsys.readouterr().out


def test_benchmark_cli_driver_fails_closed_without_explicit_model(monkeypatch):
    import subprocess  # noqa: PLC0415

    from benchmark_v3 import CliDriver  # noqa: PLC0415

    monkeypatch.delenv("EDUEVIDENCE_LLM_MODEL", raising=False)
    driver = CliDriver()
    assert driver.available() is False
    assert driver.model == ""
