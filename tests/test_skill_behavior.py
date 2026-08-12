"""Skill Behavior Tests — Phase 21 (Scenario A-G).

Deterministic, offline behavior tests for the EduEvidence skill contract.

Every scenario stubs the orchestration layer (no LLM calls, no network) and
verifies the behavioral guardrails against the deterministic core functions:

    claim_audit.audit_claims            (Citation Audit, plan §11)
    evidence_score.confidence           (legacy rule-based confidence, plan §13)
    compute_confidence.compute_confidence  (authoritative P0-05 confidence engine)
    retrieval.failures.classify_fetch / recovery_plan  (fetch failure routing)
    integrations.agent_mcp              (ROLE_REQUIREMENTS / build_spawn_call /
                                         safe_spawn / cross_model_review /
                                         AGENT_MCP_UNAVAILABLE)

Scenarios under test (Phase 21, Scenario A-G):

    A 用户要求跳过论文（Evidence）   -> 必须拒绝，不可跳过 Evidence 直接结论
    B Agent MCP 已安装但未确认模型表 -> 不得 spawn（AGENT_MCP_APPROVAL_REQUIRED）
    C 用户只允许 Codex + OMP         -> 只派发这两个 CLI
    D 用户拒绝某模型                 -> 该模型不进入推荐
    E 用户要求只找支持证据           -> 仍必须做 counter-evidence search
    F 网页抓取失败                   -> 不编造来源，标注 FETCH_FAILED / TOOL_FAILURE
    G 证据不足但用户要求 ADOPT       -> 拒绝高置信度，降级 INSUFFICIENT / PILOT
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from claim_audit import audit_claims
from compute_confidence import compute_confidence
from evidence_score import confidence as legacy_confidence
from integrations import agent_mcp
from retrieval.failures import classify_fetch, recovery_plan


# --------------------------------------------------------------------------
# Skill-contract policy stubs (mirror SKILL.md §Decision Rules / §Evidence
# Rules / §Failure Handling and docs/agent-mcp-enhanced-mode.md §8; they are
# deterministic by design and never call an LLM).
# --------------------------------------------------------------------------

def gate_skip_evidence(request: dict) -> dict:
    """Scenario A — Evidence 是强制环节：用户要求跳过 -> 拒绝，不允许直接给结论。

    A conclusion produced without evidence would necessarily fail the Citation
    Audit (UNSUPPORTED), so the gate refuses up front instead of emitting it.
    """
    if request.get("skip_evidence"):
        return {
            "allowed": False,
            "failure": "UNSUPPORTED_CLAIM",
            "reason": "evidence is mandatory; a conclusion without evidence "
                      "cannot be bound to a verifiable source",
        }
    return {"allowed": True}


def gate_agent_mcp_spawn(*, installed: bool, model_table_confirmed: bool) -> dict:
    """Scenario B — Agent MCP 派发门：已安装但模型表未确认 -> 禁止 spawn。

    docs/agent-mcp-enhanced-mode.md §8: 未安装 -> AGENT_MCP_UNAVAILABLE 降级；
    Phase 21: 已安装但未确认模型表 -> AGENT_MCP_APPROVAL_REQUIRED，不得派发。
    """
    if not installed:
        return {"allowed": False, "failure": "AGENT_MCP_UNAVAILABLE",
                "degrade": "platform_native"}
    if not model_table_confirmed:
        return {"allowed": False, "failure": "AGENT_MCP_APPROVAL_REQUIRED",
                "degrade": "platform_native"}
    return {"allowed": True}


def orchestrate_enhanced(availability: dict, *, model_table_confirmed: bool) -> dict:
    """Agent MCP 增强模式编排（确定性 stub；不真调 MCP 工具）。

    The gate has no hardcoded cli/model defaults: spawn payloads use the
    user-approved mapping (here a fixed demo mapping standing in for
    agent_mcp_approval.json).
    """
    demo_mapping = {
        "evidence-retriever": {"cli": "omp", "model": "fast-low-cost"},
        "evidence-analyst": {"cli": "claude", "model": "structured"},
    }
    if not availability.get("available"):
        return {"status": "AGENT_MCP_UNAVAILABLE", "spawn_calls": []}
    gate = gate_agent_mcp_spawn(installed=True, model_table_confirmed=model_table_confirmed)
    if not gate["allowed"]:
        return {"status": gate["failure"], "spawn_calls": []}
    return {"status": "READY", "spawn_calls": [
        agent_mcp.build_spawn_call(role, f"prompt for {role}",
                                   target_cli=demo_mapping[role]["cli"],
                                   model=demo_mapping[role]["model"])
        for role in ("evidence-retriever", "evidence-analyst")]}


def resolve_spawn_cli(role: str, allowed_clis: list[str], *, approved: dict | None = None) -> str | None:
    """Scenario C — 把 role 解析到用户允许的 CLI 集合内（确定性回退）。

    The role's approved CLI is kept when allowed; otherwise the first entry of
    the user's allowed list is used deterministically. Never returns a CLI the
    user did not authorize.
    """
    approved = approved or {}
    cli = approved.get(role, {}).get("cli")
    if cli in allowed_clis:
        return cli
    return allowed_clis[0] if allowed_clis else None


def filter_recommendations(rejected_models: set[str], *, mapping: dict | None = None) -> list[dict]:
    """Scenario D — 用户拒绝的模型不得进入推荐列表。

    The gate has no hardcoded model defaults: recommendations come from the
    user-approved proposal mapping (which the host agent must confirm).
    Models the user explicitly rejected are filtered out before display.
    """
    mapping = mapping or {role: {"cli": "claude", "model": f"model-{role}"}
                          for role in agent_mcp.ROLE_REQUIREMENTS}
    return [{"role": role, "cli": entry["cli"], "model": entry["model"]}
            for role, entry in mapping.items() if entry["model"] not in rejected_models]


def plan_search(user_instruction: str) -> dict:
    """Scenario E — 检索计划：反方证据检索是强制阶段，用户不能关闭。

    SKILL.md §Evidence Rules: 支持证据 + 独立反方证据检索；skeptic 必须独立
    寻找 null / negative / contradictory evidence。只要求支持证据的指令不能
    关闭 counter-evidence search。
    """
    return {
        "support_search": True,
        "counter_evidence_search": True,
        "note": "skeptic must independently search null/negative/contradictory "
                "evidence; support-only requests cannot disable it",
    }


def handle_tool_failure(exception: Exception) -> dict:
    """Scenario F — 工具/检索异常：如实上报 TOOL_FAILURE，不产生证据。"""
    return {"failure": "TOOL_FAILURE", "evidence_created": False,
            "message": f"tool failed: {type(exception).__name__}"}


def handle_fetch_failure(fetch_result: dict) -> dict:
    """Scenario F — 抓取失败：标注 FETCH_FAILED，跳过抽取，给出恢复计划。"""
    state = classify_fetch(fetch_result)
    if state == "FETCH_FAILED":
        return {
            "failure": "FETCH_FAILED",
            "extract": False,
            "plan": recovery_plan("FETCH_FAILED", context={
                "fallback_chain": fetch_result.get("fallback_chain", [])}),
        }
    return {"failure": None, "extract": True}


def decide_verdict(requested: str, confidence_label: str, *, has_positive: bool) -> str:
    """Scenario G — 四态决策（SKILL.md §Decision Rules）。

    High / Moderate 才允许 ADOPT；用户强求 ADOPT 而证据不足 -> 拒绝高置信度，
    有积极证据降级为 PILOT，否则 INSUFFICIENT。
    """
    if confidence_label in ("High", "Moderate"):
        return requested if requested in ("ADOPT", "PILOT", "REJECT") else "INSUFFICIENT"
    if requested == "ADOPT":
        return "PILOT" if has_positive else "INSUFFICIENT"
    return "INSUFFICIENT"


# --------------------------------------------------------------------------
# Scenario A — 用户要求跳过论文 -> 必须拒绝
# --------------------------------------------------------------------------

def test_a_skip_evidence_request_is_refused():
    req = {"education_question": "是否允许大一新生使用 AI 编程助手？",
           "skip_evidence": True}
    gate = gate_skip_evidence(req)
    assert gate["allowed"] is False
    assert gate["failure"] == "UNSUPPORTED_CLAIM"


def test_a_skipping_evidence_cannot_produce_supported_conclusion():
    # Deterministic core backing: a claim without evidence_ids fails the audit.
    results = audit_claims(
        [{"claim": "AI 编程助手提升学习效果", "evidence_ids": []}], [])
    assert results[0]["status"] == "UNSUPPORTED"
    # ... and confidence over zero evidence is Insufficient, never High.
    assert compute_confidence([])["confidence"] == "Insufficient"
    assert legacy_confidence([])["confidence"] == "Insufficient"


def test_a_normal_request_passes_the_gate():
    req = {"education_question": "是否允许大一新生使用 AI 编程助手？"}
    assert gate_skip_evidence(req)["allowed"] is True


# --------------------------------------------------------------------------
# Scenario B — Agent MCP 已安装但未确认模型表 -> 不得 spawn
# --------------------------------------------------------------------------

def test_b_installed_without_model_table_confirmation_blocks_spawn():
    availability = {"available": True, "mode": "agent_mcp_enhanced", "port": 8765,
                    "home": "~/.codex", "reasons": [],
                    "enhanced_features": {"multi_cli_dispatch": True,
                                          "cross_model_review": True,
                                          "memory_bank": True}}
    gate = gate_agent_mcp_spawn(installed=True, model_table_confirmed=False)
    assert gate["allowed"] is False
    assert gate["failure"] == "AGENT_MCP_APPROVAL_REQUIRED"

    plan = orchestrate_enhanced(availability, model_table_confirmed=False)
    assert plan["status"] == "AGENT_MCP_APPROVAL_REQUIRED"
    assert plan["spawn_calls"] == []  # 不得 spawn


def test_b_confirmed_model_table_allows_spawn():
    availability = {"available": True, "mode": "agent_mcp_enhanced", "port": 8765,
                    "home": "~/.codex", "reasons": [],
                    "enhanced_features": {"multi_cli_dispatch": True,
                                          "cross_model_review": True,
                                          "memory_bank": True}}
    plan = orchestrate_enhanced(availability, model_table_confirmed=True)
    assert plan["status"] == "READY"
    assert len(plan["spawn_calls"]) == 2
    for call in plan["spawn_calls"]:
        assert call["tool"] == "spawn_agent"
        assert call["arguments"]["target_cli"] in ("omp", "claude")


def test_b_unavailable_degrades_to_native_self_review(monkeypatch):
    # Real cross_model_review must degrade cleanly when agent-mcp is unavailable.
    monkeypatch.setattr(agent_mcp, "detect_agent_mcp", lambda: {
        "available": False, "mode": "platform_native", "port": 8765,
        "home": "~/.codex", "reasons": ["AGENT_MCP_INSTALLED env not set"],
        "enhanced_features": {"multi_cli_dispatch": False,
                              "cross_model_review": False, "memory_bank": False}})
    plan = agent_mcp.cross_model_review({"decision": "PILOT"},
                                        target_cli="omp",
                                        model="independent-model")
    assert plan["status"] == "AGENT_MCP_UNAVAILABLE"
    assert plan["degraded_to"] == "native_self_review"
    assert "spawn_call" not in plan  # 不 spawn


# --------------------------------------------------------------------------
# Scenario C — 用户只允许 Codex + OMP -> 只派发这两个 CLI
# --------------------------------------------------------------------------

def test_c_no_hardcoded_cli_or_model_defaults():
    # The gate must not ship default CLI/model choices: ROLE_REQUIREMENTS
    # describes capabilities only, so the CLI filter is never a no-op.
    for reqs in agent_mcp.ROLE_REQUIREMENTS.values():
        assert "default_cli" not in reqs
        assert "default_model" not in reqs


def test_c_only_allowed_clis_are_dispatched():
    allowed = ["codex", "omp"]
    # User-approved proposal mapping (the host agent must confirm it).
    approved = {role: {"cli": "claude", "model": "user-picked"}
                for role in agent_mcp.ROLE_REQUIREMENTS}
    payloads = []
    for role in agent_mcp.ROLE_REQUIREMENTS:
        cli = resolve_spawn_cli(role, allowed, approved=approved)
        assert cli in allowed, f"{role} resolved to unauthorized CLI {cli!r}"
        payloads.append(agent_mcp.build_spawn_call(role, "prompt", target_cli=cli,
                                                   model="user-picked"))
    for p in payloads:
        assert p["arguments"]["target_cli"] in allowed
        assert p["arguments"]["target_cli"] != "claude"


# --------------------------------------------------------------------------
# Scenario D — 用户拒绝某模型 -> 该模型不进入推荐
# --------------------------------------------------------------------------

def test_d_rejected_model_is_excluded_from_recommendations():
    rejected = {"reasoning"}
    # Proposal mapping contains 'reasoning' and 'fast-low-cost' so the filter
    # is not a no-op.
    mapping = {role: {"cli": "claude", "model": "reasoning"}
               for role in agent_mcp.ROLE_REQUIREMENTS}
    mapping["evidence-retriever"] = {"cli": "omp", "model": "fast-low-cost"}
    recs = filter_recommendations(rejected, mapping=mapping)
    assert recs, "recommendation list must not be empty"
    for rec in recs:
        assert rec["model"] not in rejected
    # Roles that mapped to the rejected model must be absent.
    dropped = {role for role, entry in mapping.items()
               if entry["model"] in rejected}
    assert dropped, "expected at least one role to map to the rejected model"
    assert {r["role"] for r in recs}.isdisjoint(dropped)


def test_d_multiple_rejected_models_all_excluded():
    rejected = {"reasoning", "fast-low-cost"}
    mapping = {role: {"cli": "claude", "model": "reasoning"}
               for role in agent_mcp.ROLE_REQUIREMENTS}
    mapping["evidence-retriever"] = {"cli": "omp", "model": "fast-low-cost"}
    recs = filter_recommendations(rejected, mapping=mapping)
    for rec in recs:
        assert rec["model"] not in rejected


# --------------------------------------------------------------------------
# Scenario E — 用户要求只找支持证据 -> 仍必须做 counter-evidence search
# --------------------------------------------------------------------------

def test_e_support_only_request_keeps_counter_evidence_search():
    plan = plan_search("只找支持证据，不要找反对证据")
    assert plan["support_search"] is True
    assert plan["counter_evidence_search"] is True  # 不可关闭


def test_e_counter_evidence_is_detected_and_priced_in():
    # Why the counter search matters, verified against the deterministic core:
    # (1) a contradicting evidence bound to a positive claim fails the audit ...
    results = audit_claims(
        [{"claim": "AI 助教提升成绩", "evidence_ids": ["E-1"]}],
        [{"evidence_id": "E-1", "source_id": "S-1", "source_location": "https://x",
          "direction": "contradict", "outcome_type": "retention"}])
    assert results[0]["status"] == "UNSUPPORTED"
    # (2) ... and conflict is penalized in the confidence score.
    weak = [
        {"evidence_id": "E-1", "direction": "support", "quality_score": 8,
         "outcome_type": "retention", "study_id": "S1", "sample_id": "P1"},
        {"evidence_id": "E-2", "direction": "contradict", "quality_score": 8,
         "outcome_type": "retention", "study_id": "S2", "sample_id": "P2"},
    ]
    breakdown = compute_confidence(weak)["confidence_breakdown"]
    assert breakdown["conflict_penalty"] == 0.15
    # Skipping the counter search would silently miss that penalty: the same
    # evidence without the contradiction scores strictly higher.
    support_only = [weak[0], {**weak[1], "direction": "support"}]
    assert compute_confidence(weak)["confidence"] == "Low"
    assert compute_confidence(weak)["confidence_breakdown"]["score"] < \
        compute_confidence(support_only)["confidence_breakdown"]["score"]


# --------------------------------------------------------------------------
# Scenario F — 网页抓取失败 -> 不编造来源，标注 FETCH_FAILED / TOOL_FAILURE
# --------------------------------------------------------------------------

def test_f_fetch_failure_marks_state_and_never_extracts():
    failed = {"fetch_status": "FETCH_FAILED", "content": "",
              "fallback_chain": ["builtin", "jina_reader", "defuddle", "markdown_new"]}
    assert classify_fetch(failed) == "FETCH_FAILED"
    handled = handle_fetch_failure(failed)
    assert handled["failure"] == "FETCH_FAILED"
    assert handled["extract"] is False          # 无内容 -> 跳过 Evidence 抽取
    assert failed["content"] == ""              # 没有内容可编造成来源
    plan = handled["plan"]
    assert plan["retry"] is False               # 不无限重试同一 URL
    assert "alternate" in plan["action"]


def test_f_partial_fetch_requires_confirmation_before_extraction():
    assert classify_fetch({"fetch_status": "FETCH_PARTIAL", "content": "partial"}) \
        == "FETCH_PARTIAL"
    plan = recovery_plan("FETCH_PARTIAL")
    assert "confirm" in plan["action"]


def test_f_fabricated_evidence_without_source_is_rejected():
    # Even if something tried to fabricate an evidence object after a failed
    # fetch (no source_location), the Citation Audit must reject it.
    results = audit_claims(
        [{"claim": "该网页支持 AI 助教", "evidence_ids": ["E-1"]}],
        [{"evidence_id": "E-1", "source_id": "S-1", "source_location": "",
          "direction": "support", "outcome_type": "retention"}])
    assert results[0]["status"] == "UNSUPPORTED"
    assert any("missing source_location" in i for i in results[0]["issues"])


def test_f_tool_failure_reported_without_evidence():
    err = RuntimeError("provider timeout")
    report = handle_tool_failure(err)
    assert report["failure"] == "TOOL_FAILURE"
    assert report["evidence_created"] is False
    assert "RuntimeError" in report["message"]


# --------------------------------------------------------------------------
# Scenario G — 证据不足但用户要求 ADOPT -> 拒绝高置信度，降级 INSUFFICIENT / PILOT
# --------------------------------------------------------------------------

def test_g_adopt_refused_when_confidence_insufficient():
    # Weak + conflicting evidence -> Insufficient confidence (both engines agree).
    weak = [
        {"evidence_id": "E-1", "direction": "support", "quality_score": 2,
         "outcome_type": "retention", "study_id": "S1", "sample_id": "P1"},
        {"evidence_id": "E-2", "direction": "contradict", "quality_score": 2,
         "outcome_type": "retention", "study_id": "S2", "sample_id": "P2"},
    ]
    label = compute_confidence(weak)["confidence"]
    assert label == "Insufficient"
    assert legacy_confidence(weak)["confidence"] == "Insufficient"
    # User demands ADOPT anyway -> never ADOPT; PILOT when positive evidence exists.
    assert decide_verdict("ADOPT", label, has_positive=True) == "PILOT"
    assert decide_verdict("ADOPT", label, has_positive=True) != "ADOPT"
    assert decide_verdict("ADOPT", label, has_positive=False) == "INSUFFICIENT"


def test_g_empty_evidence_never_yields_adopt():
    label = compute_confidence([])["confidence"]
    assert label == "Insufficient"
    # 空证据意味着不存在积极证据：has_positive 只能为 False -> INSUFFICIENT。
    assert decide_verdict("ADOPT", label, has_positive=False) == "INSUFFICIENT"
    assert decide_verdict("ADOPT", label, has_positive=False) != "ADOPT"


def test_g_strong_evidence_allows_adopt():
    strong = [
        {"direction": "support", "quality_score": 9,
         "quality_dimensions": {"D5_directness": 2},
         "study_id": f"S{i}", "sample_id": f"P{i}"}
        for i in range(4)
    ]
    label = compute_confidence(strong)["confidence"]
    assert label == "High"
    assert decide_verdict("ADOPT", label, has_positive=True) == "ADOPT"


def test_g_confidence_is_a_band_not_a_probability():
    # The rule-based index must be presented as a band label, never "85%".
    strong = [{"direction": "support", "quality_score": 9,
               "quality_dimensions": {"D5_directness": 2},
               "study_id": "S1", "sample_id": "P1"}]
    result = compute_confidence(strong)
    assert result["confidence"] in ("High", "Moderate", "Low", "Insufficient")
    # 规则化索引位于 breakdown；顶层只暴露标签与版本（避免被当作概率宣传）。
    score = result["confidence_breakdown"]["score"]
    assert isinstance(score, (int, float))
    assert 0.0 <= score <= 1.0
    assert result["confidence_policy_version"]
