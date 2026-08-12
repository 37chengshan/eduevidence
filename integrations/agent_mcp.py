#!/usr/bin/env python3
"""agent_mcp.py — Conditional Agent MCP integration (总体实施计划 §22-26).

Agent MCP is **directly installed, never migrated**. EduEvidence only does:

    detect -> call -> fallback

It does NOT re-implement queue / resume / steer / memory / verify / multi-CLI /
daemon — those all live in the agent-mcp project and are used as-is when present.

When agent-mcp is installed and its daemon is reachable, advanced features
become available:
  - multi-CLI dispatch (fast / strong / independent model routing)
  - Cross-Model Review (an independent model verifies the draft verdict)
  - Memory Bank (memory_store / memory_recall for long-running research)

When unavailable, everything degrades to Platform Native Mode (single-agent
serial execution of the 8-role protocol) with no behavioral break.

This module is a helper for the host agent: it detects availability, builds
exact tool-call payloads matching the agent-mcp MCP contract, and parses the
responses. It never spins up its own daemon.
"""
from __future__ import annotations

import json
import os
import socket
from typing import Any

AGENT_MCP_PORT = int(os.environ.get("AGENT_MCP_PORT", "8765"))
AGENT_MCP_HOME = os.environ.get("AGENT_MCP_HOME", os.environ.get("CODEX_HOME", "~/.codex"))
AGENT_MCP_INSTALLED = os.environ.get("AGENT_MCP_INSTALLED", "").lower() in ("1", "true", "yes")

# Failure state per 总体实施计划 §54
AGENT_MCP_UNAVAILABLE = "AGENT_MCP_UNAVAILABLE"

# Role presets shipped with this repo (skill/agents/*.md), mapped to the
# agent-mcp routing philosophy: fast collects, strong reasons, independent verifies.
ROLE_ROUTING = {
    "education-planner": {"role": "strong", "default_cli": "claude", "default_model": "reasoning"},
    "evidence-retriever": {"role": "fast", "default_cli": "omp", "default_model": "fast-low-cost"},
    "evidence-analyst": {"role": "strong", "default_cli": "claude", "default_model": "structured"},
    "skeptic": {"role": "independent", "default_cli": "claude", "default_model": "reasoning"},
    "method-reviewer": {"role": "strong", "default_cli": "claude", "default_model": "reasoning"},
    "evidence-judge": {"role": "strong", "default_cli": "claude", "default_model": "reasoning"},
    "intervention-designer": {"role": "strong", "default_cli": "claude", "default_model": "reasoning"},
    "evaluation-designer": {"role": "strong", "default_cli": "claude", "default_model": "reasoning"},
}


class AgentMCPUnavailable(RuntimeError):
    """Raised when agent-mcp is not installed or its daemon is not reachable."""


def detect_agent_mcp() -> dict[str, Any]:
    """Probe availability: env marker + daemon health endpoint.

    Returns an availability report (never raises).
    """
    reasons: list[str] = []
    available = False

    if AGENT_MCP_INSTALLED:
        available = True
    else:
        reasons.append("AGENT_MCP_INSTALLED env not set")

    # Daemon health probe (best-effort; a missing daemon is not fatal if the
    # host agent can still start one via the MCP layer).
    try:
        with socket.create_connection(("127.0.0.1", AGENT_MCP_PORT), timeout=0.5):
            daemon_reachable = True
    except OSError:
        daemon_reachable = False
        reasons.append(f"daemon not reachable on 127.0.0.1:{AGENT_MCP_PORT}")

    available = available and daemon_reachable
    return {
        "available": available,
        "mode": "agent_mcp_enhanced" if available else "platform_native",
        "port": AGENT_MCP_PORT,
        "home": os.path.expanduser(AGENT_MCP_HOME),
        "reasons": reasons,
        "enhanced_features": {
            "multi_cli_dispatch": available,
            "cross_model_review": available,
            "memory_bank": available,
        } if available else {
            "multi_cli_dispatch": False,
            "cross_model_review": False,
            "memory_bank": False,
        },
    }


def require_agent_mcp() -> dict[str, Any]:
    """Return the availability report, raising if agent-mcp is unavailable."""
    report = detect_agent_mcp()
    if not report["available"]:
        raise AgentMCPUnavailable(AGENT_MCP_UNAVAILABLE)
    return report


def build_spawn_call(
    role: str,
    prompt: str,
    *,
    target_cli: str | None = None,
    model: str | None = None,
    cwd: str = ".",
    permission_mode: str = "plan",
    context_mode: str = "compact",
    summary_chars: int | None = None,
    timeout_seconds: int = 1800,
    cache_ttl: int = 0,
    token_budget: int | None = None,
) -> dict[str, Any]:
    """Build a spawn_agent tool-call payload matching the agent-mcp MCP contract.

    Role defaults come from ROLE_ROUTING; explicit cli/model win over defaults.
    The host agent executes the returned payload via the MCP tool; this module
    only prepares it (no daemon logic here).
    """
    routing = ROLE_ROUTING.get(role, {"role": "strong", "default_cli": "claude",
                                      "default_model": "reasoning"})
    if role not in ROLE_ROUTING:
        raise ValueError(f"unknown role {role!r}; known: {sorted(ROLE_ROUTING)}")

    return {
        "tool": "spawn_agent",
        "arguments": {
            "task_name": role,
            "prompt": prompt,
            "target_cli": target_cli or routing["default_cli"],
            "model": model or routing["default_model"],
            "cwd": cwd,
            "permission_mode": permission_mode,
            "context_mode": context_mode,
            "summary_chars": summary_chars or (600 if routing["role"] == "fast" else 2000),
            "timeout_seconds": timeout_seconds,
            "cache_ttl": cache_ttl,
            "token_budget": token_budget,
        },
        "routing_role": routing["role"],
    }


def build_memory_store_call(content: str, *, kind: str = "research", key: str = "",
                            tags: list[str] | None = None) -> dict[str, Any]:
    """Build a memory_store payload (Memory Bank, 总体实施计划 §26 + v2 方案 §26)."""
    return {
        "tool": "memory_store",
        "arguments": {
            "content": content,
            "kind": kind,
            "key": key,
            "tags": tags or [],
        },
    }


def build_memory_recall_call(query: str, *, kind: str = "research", limit: int = 5) -> dict[str, Any]:
    """Build a memory_recall payload (Memory Bank)."""
    return {
        "tool": "memory_recall",
        "arguments": {
            "query": query,
            "kind": kind,
            "limit": limit,
        },
    }


def cross_model_review(
    draft_verdict: dict[str, Any],
    *,
    independent_model: str = "independent-reasoning",
    target_cli: str = "claude",
) -> dict[str, Any]:
    """Cross-Model Review orchestration (总体实施计划 §25).

    Flow: Primary Analysis -> Draft Verdict -> Independent Review -> Judge ->
    Final Verdict. When agent-mcp is unavailable, degrades to a native
    self-review plan marked AGENT_MCP_UNAVAILABLE (no hard failure).
    """
    report = detect_agent_mcp()
    reviewer_prompt = (
        "你是 EduEvidence 的独立交叉审核者（Independent Reviewer）。"
        "以下是一份 Draft Verdict。请以独立模型视角审查："
        "agreement / disagreements / unsupported_claims / missed_counterevidence / "
        "scope_violations / methodology_issues / confidence_adjustment / "
        "required_revision / final_recommendation。"
        "输出 CrossModelReview JSON（见 schemas/cross-model-review.schema.json）。\n\n"
        f"DRAFT VERDICT:\n{json.dumps(draft_verdict, ensure_ascii=False, indent=2)}"
    )
    if not report["available"]:
        return {
            "status": AGENT_MCP_UNAVAILABLE,
            "degraded_to": "native_self_review",
            "note": "agent-mcp 未安装/不可达：退化为单 Agent 自审（Platform Native Mode），"
                    "不产生独立模型交叉审核。",
            "review_plan": {"reviewer_prompt": reviewer_prompt,
                            "independent_model": independent_model},
        }
    return {
        "status": "READY",
        "spawn_call": build_spawn_call(
            "skeptic", reviewer_prompt, target_cli=target_cli, model=independent_model,
            context_mode="full", summary_chars=2000),
        "flow": ["primary_analysis", "draft_verdict", "independent_review",
                 "judge", "final_verdict"],
        "report": report,
    }


def memory_bank_guide() -> dict[str, str]:
    """Memory Bank fields for long-running teaching research (v2 方案 §26)."""
    return {
        "course_profile": "Course Profile",
        "learner_profile": "Learner Profile",
        "research_questions": "Research Questions",
        "reviewed_sources": "Reviewed Sources",
        "accepted_evidence": "Accepted Evidence",
        "rejected_evidence": "Rejected Evidence",
        "previous_verdict": "Previous Verdict",
        "pilot_design": "Pilot Design",
        "pilot_results": "Pilot Results",
        "open_questions": "Open Questions",
    }


if __name__ == "__main__":
    import sys

    print(json.dumps(detect_agent_mcp(), ensure_ascii=False, indent=2))
    sys.exit(0)
