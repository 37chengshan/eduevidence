"""Tests for integrations/agent_mcp.py — Agent MCP Mandatory Confirmation Gate.

Phase 5-9 acceptance:
- safe_spawn() is the ONLY spawn entry; every gate failure returns
  AGENT_MCP_APPROVAL_REQUIRED with no spawn_call.
- No hardcoded model names: ROLE_REQUIREMENTS describes capabilities only.
- model_inventory.json / agent_mcp_approval.json shapes match the plan.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from integrations import agent_mcp
from integrations.agent_mcp import (
    AGENT_MCP_APPROVAL_REQUIRED,
    AGENT_MCP_UNAVAILABLE,
    ROLE_REQUIREMENTS,
    build_approval_record,
    build_recommendation_table,
    build_spawn_call,
    capability_profile,
    cross_model_review,
    is_approval_current,
    load_approval,
    safe_spawn,
    scan_cli_models,
    write_approval,
    write_model_inventory,
)

ROLES = sorted(ROLE_REQUIREMENTS)
APPROVAL_SCHEMA = ROOT / "schemas" / "agent-mcp-approval.schema.json"


def _roles(cli: str = "omp", model: str = "opencode-go/deepseek-v4-flash") -> dict:
    return {role: {"cli": cli, "model": model} for role in ROLES}


def _approval(**kwargs) -> dict:
    """Valid approval for all 8 roles on omp."""
    cli = kwargs.pop("cli", "omp")
    model = kwargs.pop("model", "opencode-go/deepseek-v4-flash")
    roles = kwargs.pop("roles", None) or _roles(cli=cli, model=model)
    allowed = kwargs.pop("allowed_clis", None) or [cli]
    return build_approval_record(roles, allowed, **kwargs)


# --------------------------------------------------------------------------
# Gate failures — 5 scenarios, all must return AGENT_MCP_APPROVAL_REQUIRED
# --------------------------------------------------------------------------

def test_gate_no_approval_blocks_spawn():
    result = safe_spawn("evidence-retriever", "prompt", None)
    assert result["status"] == AGENT_MCP_APPROVAL_REQUIRED
    assert result["spawn_call"] is None


def test_gate_hash_mismatch_blocks_spawn():
    # Tampering with the mapping after approval (without updating the hash)
    # must close the gate.
    approval = _approval()
    approval["roles"]["evidence-retriever"]["model"] = "tampered-model"
    result = safe_spawn("evidence-retriever", "prompt", approval)
    assert result["status"] == AGENT_MCP_APPROVAL_REQUIRED
    assert result["spawn_call"] is None


def test_gate_cli_not_allowed_blocks_spawn():
    approval = _approval(allowed_clis=["omp", "claude"])
    result = safe_spawn("evidence-retriever", "prompt", approval,
                        allowed_clis=["codex"])
    assert result["status"] == AGENT_MCP_APPROVAL_REQUIRED
    assert result["spawn_call"] is None


def test_gate_model_not_approved_blocks_spawn():
    approval = _approval()
    # Explicit model that differs from the approved mapping must be refused.
    result = safe_spawn("evidence-retriever", "prompt", approval,
                        target_cli="omp", model="some-other-model")
    assert result["status"] == AGENT_MCP_APPROVAL_REQUIRED
    assert result["spawn_call"] is None


def test_gate_cli_not_approved_blocks_spawn():
    approval = _approval()  # approved mapping uses omp only
    result = safe_spawn("evidence-retriever", "prompt", approval,
                        target_cli="claude", model="opencode-go/deepseek-v4-flash")
    assert result["status"] == AGENT_MCP_APPROVAL_REQUIRED
    assert result["spawn_call"] is None


def test_gate_role_not_approved_blocks_spawn():
    approval = _approval()
    del approval["roles"]["skeptic"]  # role removed from the approved set
    result = safe_spawn("skeptic", "prompt", approval)
    assert result["status"] == AGENT_MCP_APPROVAL_REQUIRED
    assert result["spawn_call"] is None


def test_gate_not_approved_flag_blocks_spawn():
    approval = _approval()
    approval["approved"] = False  # installation alone is never approval
    result = safe_spawn("evidence-retriever", "prompt", approval)
    assert result["status"] == AGENT_MCP_APPROVAL_REQUIRED


# --------------------------------------------------------------------------
# Gate success
# --------------------------------------------------------------------------

def test_gate_success_builds_spawn_call():
    approval = _approval()
    result = safe_spawn("evidence-retriever", "find evidence", approval)
    assert result["status"] == "READY"
    call = result["spawn_call"]
    assert call["tool"] == "spawn_agent"
    args = call["arguments"]
    assert args["task_name"] == "evidence-retriever"
    assert args["prompt"] == "find evidence"
    assert args["target_cli"] == "omp"
    assert args["model"] == "opencode-go/deepseek-v4-flash"
    # fast class (speed high + cost low) gets a compact summary budget
    assert call["routing_role"] == "fast"
    assert args["summary_chars"] == 600


def test_gate_success_uses_approved_mapping_when_not_given():
    approval = _approval(cli="codex", model="deepseek-v4-pro")
    result = safe_spawn("evidence-judge", "judge", approval)
    assert result["status"] == "READY"
    args = result["spawn_call"]["arguments"]
    assert args["target_cli"] == "codex"
    assert args["model"] == "deepseek-v4-pro"
    assert result["spawn_call"]["routing_role"] == "strong"


# --------------------------------------------------------------------------
# No hardcoded model names (Phase 5 acceptance)
# --------------------------------------------------------------------------

def test_role_requirements_contain_no_model_or_cli_names():
    for role, reqs in ROLE_REQUIREMENTS.items():
        assert "default_model" not in reqs, role
        assert "default_cli" not in reqs, role
        assert "model" not in reqs, role
        assert "cli" not in reqs, role
        assert isinstance(reqs["reasoning"], (str, type(None)))


def test_module_source_has_no_hardcoded_model_defaults():
    source = (ROOT / "integrations" / "agent_mcp.py").read_text(encoding="utf-8")
    assert "default_model" not in source
    assert "default_cli" not in source
    # No concrete model name may appear as a constant/fallback value.
    for banned in ("claude-opus", "gpt-5", "deepseek-v4", "glm-5", "kimi-k"):
        assert banned not in source, f"hardcoded model name {banned!r} found"


def test_build_spawn_call_refuses_missing_cli_or_model():
    with pytest.raises(ValueError):
        build_spawn_call("skeptic", "prompt", target_cli="claude", model="")
    with pytest.raises(ValueError):
        build_spawn_call("skeptic", "prompt", target_cli="", model="m")
    with pytest.raises(ValueError):
        build_spawn_call("no-such-role", "prompt", target_cli="claude", model="m")


# --------------------------------------------------------------------------
# Phase 5.3 — Model inventory
# --------------------------------------------------------------------------

def test_write_model_inventory_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_mcp, "scan_available_models",
                        lambda clis, timeout=20: {
                            "codex": {"available": True,
                                      "models": ["openai/gpt-5.6-luna"],
                                      "model_details": {}},
                            "omp": {"available": True, "models": [], "model_details": {}}})
    path, inventory = write_model_inventory(["codex", "omp"],
                                            runs_dir=str(tmp_path),
                                            run_id="test-run")
    assert path == tmp_path / "test-run" / "model_inventory.json"
    assert set(inventory) == {"scanned_at", "clis"}
    assert inventory["clis"]["codex"]["available"] is True
    assert inventory["clis"]["codex"]["models"] == ["openai/gpt-5.6-luna"]
    assert inventory["clis"]["omp"]["models"] == []
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["clis"]["codex"]["models"][0] == "openai/gpt-5.6-luna"


def test_scan_cli_models_parses_omp_table(monkeypatch):
    table = (
        "opencode-go (2)\n"
        "┌───────────┬─────────┬─────────┬───────────┬────────┐\n"
        "│ model     │ context │ max-out │ thinking  │ images │\n"
        "├───────────┼─────────┼─────────┼───────────┼────────┤\n"
        "│ deepseek-v4-flash │ 1M │ 384K │ high │ no │\n"
        "│ glm-5.2 │ 203K │ 33K │ high │ no │\n"
        "└───────────┴─────────┴─────────┴───────────┴────────┘\n"
    )
    monkeypatch.setattr(agent_mcp, "_run_cli_cmd", lambda argv, timeout=20: table)
    entry = scan_cli_models("omp")
    assert entry["available"] is True
    assert entry["models"] == ["opencode-go/deepseek-v4-flash",
                               "opencode-go/glm-5.2"]
    assert entry["model_details"]["opencode-go/deepseek-v4-flash"]["context"] == "1M"
    assert entry["model_details"]["opencode-go/glm-5.2"]["images"] == "no"


def test_scan_cli_models_unknown_cli_reports_empty(monkeypatch):
    # A CLI with no discovery command must report [] — never guessed.
    monkeypatch.setattr(agent_mcp, "shutil", type("S", (), {"which": lambda c: "/x"}))
    entry = scan_cli_models("kimi")
    assert entry["available"] is True
    assert entry["models"] == []


# --------------------------------------------------------------------------
# Phase 5.4 — Capability profile: verifiable only, else unknown
# --------------------------------------------------------------------------

def test_capability_profile_unknown_when_nothing_verified():
    profile = capability_profile("opencode-go/deepseek-v4-flash", None)
    for dim in ("reasoning", "speed", "cost", "structured_output",
                "context", "tool_use", "multimodal"):
        assert profile[dim] == "unknown", dim
    assert profile["family"] == "deepseek"
    assert profile["verified_sources"] == []


def test_capability_profile_uses_verified_facts():
    inventory = {"clis": {"omp": {"available": True,
                                  "models": ["opencode-go/glm-5.2"],
                                  "model_details": {"opencode-go/glm-5.2": {
                                      "context": "203K", "images": "no"}}}}}
    profile = capability_profile("opencode-go/glm-5.2", inventory)
    assert profile["context"] == "high"      # 203K >= 200K
    assert profile["multimodal"] == "no"
    assert profile["reasoning"] == "unknown"  # never guessed
    assert profile["family"] == "zhipu"


def test_capability_profile_never_guesses_model_family_as_verified_capability():
    profile = capability_profile("mystery-model-9000", None)
    assert profile["family"] == "unknown"
    assert profile["context"] == "unknown"


# --------------------------------------------------------------------------
# Phase 6-7 — Recommender table
# --------------------------------------------------------------------------

def _inventory() -> dict:
    return {"clis": {
        "omp": {"available": True,
                "models": ["opencode-go/glm-5.2", "opencode-go/deepseek-v4-flash"],
                "model_details": {
                    "opencode-go/glm-5.2": {"context": "203K", "images": "no"},
                    "opencode-go/deepseek-v4-flash": {"context": "1M", "images": "no"}}},
        "claude": {"available": True, "models": [], "model_details": {}},
    }}


def test_recommendation_table_shape():
    table = build_recommendation_table(["omp", "claude"], _inventory())
    assert {r["role"] for r in table["recommendations"]} == set(ROLES)
    for rec in table["recommendations"]:
        assert set(rec) >= {"role", "cli", "model", "reason", "task"}
        assert rec["score"] is None or 0.0 <= rec["score"] <= 1.0
    summary = table["summary"]
    assert summary["role_count"] == len(ROLES)
    assert summary["concurrency"] == len(ROLES)
    assert summary["memory_bank"] is True
    assert summary["cost_class"] == "Unknown"  # 不知道就 Unknown
    assert summary["cross_model_review"] in (True, False)


def test_recommendation_prefers_verified_context_on_tie():
    table = build_recommendation_table(["omp"], _inventory())
    # Both models tie on unknown capabilities; verified 1M context wins.
    rec = table["recommendations"][0]
    assert rec["model"] == "opencode-go/deepseek-v4-flash"
    assert "verified context high" in rec["reason"]


def test_recommendation_without_models_asks_user():
    table = build_recommendation_table(["claude"],
                                       {"clis": {"claude": {"available": True,
                                                            "models": [],
                                                            "model_details": {}}}})
    assert all(r["model"] is None for r in table["recommendations"])
    assert any("user must specify" in r["reason"]
               for r in table["recommendations"])


def test_skeptic_independence_flags_cross_model_review():
    inventory = {"clis": {
        "claude": {"available": True,
                   "models": ["claude-sonnet-5", "claude-opus-4-6"],
                   "model_details": {}},
        "omp": {"available": True,
                "models": ["opencode-go/deepseek-v4-flash"],
                "model_details": {}}}}
    table = build_recommendation_table(["claude", "omp"], inventory)
    # Same family for skeptic and judge -> not cross-model.
    assert table["summary"]["cross_model_review"] is False
    # Remove the anthropic models -> skeptic/judge fall onto deepseek -> same
    # family again; with only one family left the flag must be False (never
    # fake independence by re-spawning the same family).
    inventory["clis"]["claude"]["models"] = []
    table = build_recommendation_table(["claude", "omp"], inventory)
    assert table["summary"]["cross_model_review"] is False


# --------------------------------------------------------------------------
# Phase 8 — Approval record
# --------------------------------------------------------------------------

def test_approval_record_shape_and_stable_hash():
    record = _approval()
    assert record["approved"] is True
    assert set(record) >= {"approved", "approved_at", "allowed_clis",
                           "role_mapping_hash", "roles"}
    assert record["allowed_clis"] == ["omp"]
    assert record["schema_version"] == 1
    assert record["role_mapping_hash"] == _approval()["role_mapping_hash"]
    # Same mapping, different order -> same hash.
    reordered = {role: _approval()["roles"][role] for role in reversed(ROLES)}
    assert agent_mcp._role_mapping_hash(reordered) == record["role_mapping_hash"]


def test_approval_roundtrip_via_file(tmp_path):
    path = tmp_path / "agent_mcp_approval.json"
    record = write_approval(path, _roles(), ["omp"])
    loaded = load_approval(path)
    assert loaded == record
    assert loaded["role_mapping_hash"] == record["role_mapping_hash"]


def test_load_approval_missing_or_corrupt_returns_none(tmp_path):
    assert load_approval(tmp_path / "nope.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert load_approval(bad) is None


def test_is_approval_current_detects_every_reconfirmation_trigger():
    ok, changes = is_approval_current(_approval(), _roles(), ["omp"])
    assert ok and changes == []

    triggers = []
    approval = _approval()
    # 修改映射 (replaced model)
    approval["roles"]["skeptic"]["model"] = "other"
    approval["role_mapping_hash"] = agent_mcp._role_mapping_hash(approval["roles"])
    triggers.append(("mapping", _approval(), approval))

    approval = _approval()
    # 新增角色 / 修改映射 (role added to proposal)
    triggers.append(("new role",
                     {**_roles(), "new-role": {"cli": "omp", "model": "m"}},
                     approval))

    # 新增 CLI (allowed_clis changed)
    triggers.append(("cli", _approval(), _approval(allowed_clis=["omp", "claude"])))

    # 提高 budget
    triggers.append(("budget", _approval(), _approval(budget={"max_usd": 5})))

    # 新 provider
    triggers.append(("provider", _approval(), _approval(provider="ocxlocal")))

    for label, proposal, stored in triggers:
        ok, changes = is_approval_current(stored, proposal, stored["allowed_clis"])
        assert not ok, label
        assert changes, label


def test_approval_matches_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(APPROVAL_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(_approval(), schema)
    jsonschema.validate(_approval(budget={"max_usd": 3}, provider="ocxlocal"), schema)
    # Tampered record (mapping edited, hash stale) still matches shape — the
    # integrity check lives in the gate, not the schema.
    tampered = _approval()
    tampered["roles"]["skeptic"]["model"] = "x"
    jsonschema.validate(tampered, schema)
    # But a non-approved record must NOT validate: installation != approval.
    record = _approval()
    record["approved"] = False
    with pytest.raises(Exception):
        jsonschema.validate(record, schema)


# --------------------------------------------------------------------------
# Cross-Model Review gate
# --------------------------------------------------------------------------

def test_cross_model_review_requires_approval(monkeypatch):
    monkeypatch.setattr(agent_mcp, "detect_agent_mcp",
                        lambda: {"available": True, "mode": "agent_mcp_enhanced"})
    plan = cross_model_review({"decision": "PILOT"},
                              target_cli="omp",
                              model="opencode-go/deepseek-v4-flash")
    assert plan["status"] == AGENT_MCP_APPROVAL_REQUIRED
    assert "spawn_call" not in plan


def test_cross_model_review_spawns_only_with_approved_skeptic(monkeypatch):
    monkeypatch.setattr(agent_mcp, "detect_agent_mcp",
                        lambda: {"available": True, "mode": "agent_mcp_enhanced"})
    approval = _approval(cli="omp", model="opencode-go/deepseek-v4-flash")
    plan = cross_model_review({"decision": "PILOT"}, approval=approval,
                              target_cli="omp",
                              model="opencode-go/deepseek-v4-flash")
    assert plan["status"] == "READY"
    assert plan["spawn_call"]["arguments"]["task_name"] == "skeptic"
    assert plan["spawn_call"]["arguments"]["model"] == "opencode-go/deepseek-v4-flash"
    assert plan["flow"] == ["primary_analysis", "draft_verdict",
                            "independent_review", "judge", "final_verdict"]


def test_cross_model_review_degrades_when_unavailable(monkeypatch):
    monkeypatch.setattr(agent_mcp, "detect_agent_mcp",
                        lambda: {"available": False, "mode": "platform_native"})
    plan = cross_model_review({"decision": "PILOT"},
                              target_cli="omp",
                              model="opencode-go/deepseek-v4-flash")
    assert plan["status"] == AGENT_MCP_UNAVAILABLE
    assert plan["degraded_to"] == "native_self_review"
    assert "spawn_call" not in plan
