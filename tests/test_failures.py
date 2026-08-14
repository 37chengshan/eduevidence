"""Tests for retrieval/failures.py — failure states & recovery routing (v3 §11-12).

Search failure and fetch failure are different problems and must be told apart.
classify_fetch maps a fetch result to the canonical token; recovery_plan returns
the recovery action (never infinite retry). Pure functions — no network.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from retrieval.failures import (
    FAILURE_STATES,
    RECOVERY_ACTION,
    classify_fetch,
    recovery_plan,
)


# ------------------------------------------------------------- classify_fetch


def test_classify_fetch_valid_gate_passed():
    # FETCH_VALID + gate passed is the only fully-successful classification.
    assert classify_fetch({"fetch_status": "FETCH_VALID", "validation": {"passed": True}}) == "FETCH_VALID"


def test_classify_fetch_valid_but_gate_failed_is_partial():
    # P0-1: fetch_status FETCH_VALID alone is not enough — the Validation Gate
    # must pass; otherwise the content is only partial (rule-confirm needed).
    assert classify_fetch({"fetch_status": "FETCH_VALID", "validation": {"passed": False}}) == "FETCH_PARTIAL"


def test_classify_fetch_valid_without_validation_is_partial():
    # A fetch result that carries no validation verdict must not be treated as
    # confirmed evidence (fail closed).
    assert classify_fetch({"fetch_status": "FETCH_VALID"}) == "FETCH_PARTIAL"


def test_classify_fetch_partial():
    assert classify_fetch({"fetch_status": "FETCH_PARTIAL"}) == "FETCH_PARTIAL"


def test_classify_fetch_failed():
    assert classify_fetch({"fetch_status": "FETCH_FAILED"}) == "FETCH_FAILED"


def test_classify_fetch_missing_status_defaults_to_failed():
    assert classify_fetch({}) == "FETCH_FAILED"


# ------------------------------------------------------------- recovery_plan


@pytest.mark.parametrize("state", sorted(FAILURE_STATES))
def test_recovery_plan_every_state_has_action_and_never_retries(state):
    plan = recovery_plan(state)
    assert plan["state"] == state
    assert plan["action"] == RECOVERY_ACTION[state]
    assert plan["retry"] is False  # v3 §12: no infinite retry of the same fetch


def test_recovery_plan_fetch_failed_records_chain_and_no_retry():
    plan = recovery_plan("FETCH_FAILED", context={"fallback_chain": ["builtin:error", "jina_reader:error"]})
    assert "builtin:error" in plan["note"]
    assert "do not retry" in plan["note"]
    assert "alternate source" in plan["note"]


def test_recovery_plan_fetch_partial_requires_rule_confirmation():
    plan = recovery_plan("FETCH_PARTIAL")
    assert "confirmation" in plan["note"]


def test_recovery_plan_search_no_result_broadens_terms():
    plan = recovery_plan("SEARCH_NO_RESULT")
    assert "broaden" in plan["note"]


def test_recovery_plan_source_duplicate_merges_highest_authority():
    plan = recovery_plan("SOURCE_DUPLICATE")
    assert "merge" in plan["note"]


def test_recovery_plan_agent_mcp_unavailable_degrades_to_native():
    # The tool-failure-like state: AGENT_MCP_UNAVAILABLE routes to the platform
    # native mode. (TOOL_FAILURE is NOT a defined FAILURE_STATES token — an
    # MCP-tool outage is modelled by AGENT_MCP_UNAVAILABLE.)
    plan = recovery_plan("AGENT_MCP_UNAVAILABLE")
    assert plan["action"] == "degrade_to_platform_native_mode"


def test_recovery_plan_unknown_state_raises():
    with pytest.raises(ValueError):
        recovery_plan("TOOL_FAILURE")


def test_failure_states_cover_recovery_actions():
    # Every state must have a recovery action and vice versa.
    assert set(FAILURE_STATES) == set(RECOVERY_ACTION)
