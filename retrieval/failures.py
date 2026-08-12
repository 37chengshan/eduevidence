#!/usr/bin/env python3
"""failures.py — Failure states & recovery routing (Smart Web Fetch v3 §11-12).

Search failure and fetch failure are different problems and must be told apart:

    SEARCH_NO_RESULT     -> 重新搜索 / 换 discovery provider
    SEARCH_LOW_QUALITY   -> 放宽检索式 / 降级接受低权威来源
    FETCH_FAILED         -> 换 fetch provider / 回 Discovery 找替代来源
    FETCH_PARTIAL        -> 规则确认后才可进入 Evidence Extraction
    SOURCE_INVALID       -> 丢弃并找替代
    SOURCE_DUPLICATE     -> 去重合并，不算独立证据

Recovery principle (v3 §12): never infinite-retry the same fetch. After the
full degradation chain fails, return to Discovery and find an alternate source
for the same paper/fact.
"""
from __future__ import annotations

from typing import Any

FAILURE_STATES = (
    "SEARCH_NO_RESULT",
    "SEARCH_LOW_QUALITY",
    "FETCH_FAILED",
    "FETCH_PARTIAL",
    "SOURCE_INVALID",
    "SOURCE_DUPLICATE",
    "UNSUPPORTED_CLAIM",
    "CONFLICT_UNRESOLVED",
    "SCOPE_MISMATCH",
    "METHODOLOGY_TOO_WEAK",
    "INSUFFICIENT_EVIDENCE",
    "AGENT_MCP_UNAVAILABLE",
    "REPORT_INVALID",
)

RECOVERY_ACTION = {
    "SEARCH_NO_RESULT": "rerun_search_with_broader_terms",
    "SEARCH_LOW_QUALITY": "widen_query_or_accept_lower_authority_tier",
    "FETCH_FAILED": "alternate_fetch_provider_then_alternate_source",
    "FETCH_PARTIAL": "rule_confirm_or_human_confirm_before_extraction",
    "SOURCE_INVALID": "discard_and_find_alternate_source",
    "SOURCE_DUPLICATE": "merge_keep_highest_authority",
    "UNSUPPORTED_CLAIM": "downgrade_claim_or_drop",
    "CONFLICT_UNRESOLVED": "stay_uncertain_do_not_force_adjudication",
    "SCOPE_MISMATCH": "shrink_conclusion_scope",
    "METHODOLOGY_TOO_WEAK": "do_not_use_as_support",
    "INSUFFICIENT_EVIDENCE": "mark_insufficient_evidence",
    "AGENT_MCP_UNAVAILABLE": "degrade_to_platform_native_mode",
    "REPORT_INVALID": "block_publish_rerun_render",
}


def classify_fetch(fetch_result: dict[str, Any]) -> str:
    """Map a fetch result to the canonical failure/state token."""
    status = fetch_result.get("fetch_status", "FETCH_FAILED")
    if status == "FETCH_VALID":
        validation = fetch_result.get("validation", {})
        if validation.get("passed"):
            return "FETCH_VALID"
        return "FETCH_PARTIAL"
    if status == "FETCH_PARTIAL":
        return "FETCH_PARTIAL"
    return "FETCH_FAILED"


def recovery_plan(state: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the recovery plan for a failure state (no infinite retry)."""
    if state not in RECOVERY_ACTION:
        raise ValueError(f"unknown state {state!r}; known: {sorted(RECOVERY_ACTION)}")
    plan: dict[str, Any] = {
        "state": state,
        "action": RECOVERY_ACTION[state],
        "retry": False,
        "note": "",
    }
    ctx = context or {}
    if state == "FETCH_FAILED":
        plan["note"] = (
            f"degradation chain exhausted ({ctx.get('fallback_chain', [])}); "
            "do not retry the same URL — return to Discovery for an alternate source "
            "of the same paper/fact."
        )
    elif state == "FETCH_PARTIAL":
        plan["note"] = "content partially readable; require rule/human confirmation before Evidence Extraction (v3 §8)."
    elif state == "SEARCH_NO_RESULT":
        plan["note"] = "no results for the query; broaden terms or switch discovery provider."
    elif state == "SOURCE_DUPLICATE":
        plan["note"] = "same paper behind mirror URL; merge and keep the highest-authority entry."
    return plan
