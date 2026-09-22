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
    write_approval,
)
from integrations.jev.config import JEV_APPROVAL_REQUIRED, TIER0_TOOLS  # noqa: E402


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
