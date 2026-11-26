"""P0 closeout tests: decision conflict semantics + Jev approval disk binding."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.decision_policy import decision_action, decision_outcome  # noqa: E402
from integrations.jev.approval import (  # noqa: E402
    _check_approval,
    _tools_hash,
    build_approval_record,
    is_approval_current,
    write_approval,
)
from integrations.jev.config import JEV_APPROVAL_REQUIRED, TIER0_TOOLS  # noqa: E402
from integrations import semantic_decide  # noqa: E402


def test_mixed_support_oppose_is_insufficient_not_adopt():
    out = decision_outcome(
        confidence_label="High",
        decisive_relations={"a": "support_adoption", "b": "oppose_adoption"},
        has_direct_primary_evidence=True,
    )
    assert out["action"] == "INSUFFICIENT_EVIDENCE"
    assert out["downgrade_reason"] == "unresolved_conflict"


def test_conditional_relation_blocks_adopt():
    out = decision_outcome(
        confidence_label="High",
        decisive_relations={"a": "conditional"},
        has_direct_primary_evidence=True,
    )
    assert out["action"] == "INSUFFICIENT_EVIDENCE"


def test_oppose_only_is_reject():
    out = decision_outcome(
        confidence_label="High",
        decisive_relations={"a": "oppose_adoption"},
        has_direct_primary_evidence=True,
    )
    assert out["action"] == "REJECT"


def test_high_support_direct_primary_is_adopt():
    assert decision_action(
        confidence_label="High",
        decisive_relations={"a": "support_adoption"},
        has_direct_primary_evidence=True,
    ) == "ADOPT"


def test_forged_approval_dict_rejected_without_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-key")
    monkeypatch.setenv("JEV_PROVIDER", "vercel")
    # Isolate from any live ~/.eduevidence/jev_mcp_approval.json on this machine.
    monkeypatch.setattr(
        "integrations.jev.approval.JEV_APPROVAL_PATH",
        str(tmp_path / "missing_approval.json"),
    )
    tools = list(TIER0_TOOLS)
    forged = {
        "approved": True,
        "tools": tools,
        "tools_hash": _tools_hash(tools),
        "provider": "vercel",
        "model": "typesafe-ai/jev",
        "endpoint": "https://ai-gateway.vercel.sh/typesafe/v1/systemone",
        "mode": 1,
    }
    assert _check_approval(forged, tools[0]) == JEV_APPROVAL_REQUIRED


def test_prefs_schema_allows_semdecide_key():
    schema = json.loads((ROOT / "schemas/v2/intake.schema.json").read_text())
    prefs = schema["definitions"]["Prefs"]
    assert "semdecide" in prefs["properties"]
    assert prefs["additionalProperties"] is False


def test_jev_current_approval_requires_matching_disk_record(tmp_path, monkeypatch):
    path = tmp_path / "approval.json"
    monkeypatch.setattr("integrations.jev.approval.JEV_APPROVAL_PATH", str(path))
    record = build_approval_record()

    assert is_approval_current(record) == (False, ["approval file missing on disk"])
    record = write_approval()
    assert is_approval_current(record) == (True, [])
    path.write_text(json.dumps({**record, "approved": False}), encoding="utf-8")
    assert is_approval_current(record) == (False, ["approval on disk is not approved"])
    path.write_text(json.dumps({**record, "tools_hash": "tampered"}), encoding="utf-8")
    assert is_approval_current(record) == (
        False, ["approval file tampered (disk tools_hash mismatch)"],
    )


def test_semdecide_decodes_json_and_round_trips_json_lines(monkeypatch):
    from subprocess import CompletedProcess

    monkeypatch.setattr(semantic_decide, "binary_path", lambda: "semdecide")
    monkeypatch.setattr(semantic_decide, "_env_file_values", dict)

    def fake_run(argv, **kwargs):
        if argv[1] == "is":
            return CompletedProcess(argv, 0, '{"verdict": true}', "")
        assert argv[1] == "filter"
        assert [json.loads(line) for line in kwargs["input"].splitlines()] == [{"text": "课程"}]
        return CompletedProcess(argv, 0, '{"text": "课程"}\n', "")

    monkeypatch.setattr(semantic_decide.subprocess, "run", fake_run)
    assert semantic_decide.is_predicate("课程", "learning")["verdict"] is True
    filtered = semantic_decide.filter_records([{"text": "课程"}], "learning")
    assert filtered["matched"] == [{"text": "课程"}]
