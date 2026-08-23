#!/usr/bin/env python3
"""agent_mcp.py — Conditional Agent MCP integration with Mandatory Confirmation Gate.

Agent MCP is **directly installed, never migrated**. EduEvidence only does:

    scan -> recommend -> ask the user -> execute after explicit confirmation

Gate principle (Phase 5-9): Scan first. Recommend second. Ask the user.
Execute only after explicit confirmation.

No hardcoded model names: ROLE_REQUIREMENTS describes role *capability*
requirements only. Concrete CLI/model choices come from the user-approved
mapping stored in agent_mcp_approval.json — anything unverifiable is reported
as `unknown` and never guessed.

When agent-mcp is installed and its daemon is reachable, advanced features
become available:
  - multi-CLI dispatch (fast / strong / independent model routing)
  - Cross-Model Review (an independent model verifies the draft verdict)
  - Memory Bank (memory_store / memory_recall for long-running research)

When unavailable, everything degrades to Platform Native Mode (single-agent
serial execution of the 8-role protocol) with no behavioral break.

Spawning is only reachable through safe_spawn(): it verifies that an explicit
user approval exists, that the approval hash is intact, that the requested
CLI / model / role are exactly the approved ones, and only then builds the
spawn payload. Any failure returns AGENT_MCP_APPROVAL_REQUIRED — business
code MUST NOT call spawn directly.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AGENT_MCP_ENV_FILE = os.environ.get("AGENT_MCP_ENV_FILE", "~/.eduevidence/env")


def _env_file_values(path: str | Path | None = None) -> dict[str, str]:
    """Parse KEY=VALUE lines from ~/.eduevidence/env (best-effort).

    install.sh writes AGENT_MCP_INSTALLED=1 there after installation; it is a
    *fallback* env source — real environment variables always win
    (see _effective_env).
    """
    try:
        text = Path(os.path.expanduser(path or AGENT_MCP_ENV_FILE)).read_text(encoding="utf-8")
    except OSError:
        return {}
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _effective_env(file_values: dict[str, str], key: str, default: str = "") -> str:
    """Resolve one setting: real env var > ~/.eduevidence/env > default."""
    return os.environ.get(key) or file_values.get(key) or default


_ENV_FILE_VALUES = _env_file_values()
AGENT_MCP_PORT = int(_effective_env(_ENV_FILE_VALUES, "AGENT_MCP_PORT", "8765"))
AGENT_MCP_HOME = _effective_env(_ENV_FILE_VALUES, "AGENT_MCP_HOME",
                                os.environ.get("CODEX_HOME", "~/.codex"))
AGENT_MCP_INSTALLED = _effective_env(_ENV_FILE_VALUES, "AGENT_MCP_INSTALLED",
                                     "").lower() in ("1", "true", "yes")

# Failure states per 总体实施计划 §54 + Phase 8 Approval Gate.
AGENT_MCP_UNAVAILABLE = "AGENT_MCP_UNAVAILABLE"
AGENT_MCP_APPROVAL_REQUIRED = "AGENT_MCP_APPROVAL_REQUIRED"

# Role capability requirements shipped with this repo (skill/agents/*.md).
# Capabilities only — NO model names, NO CLI names. `None` means the role has
# no requirement for that dimension (unknown capability is acceptable).
# skeptic requires a *different model family* than the primary analysis;
# that can never be satisfied by spawning the same model in another session.
ROLE_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "education-planner": {
        "reasoning": "high", "speed": None, "cost": None,
        "structured_output": None, "context": None, "tool_use": None,
        "multimodal": None,
    },
    "evidence-retriever": {
        "reasoning": None, "speed": "high", "cost": "low",
        "structured_output": None, "context": None, "tool_use": "strong",
        "multimodal": None,
    },
    "evidence-analyst": {
        "reasoning": "medium+", "speed": None, "cost": None,
        "structured_output": "strong", "context": None, "tool_use": None,
        "multimodal": None,
    },
    "skeptic": {
        "reasoning": "high", "speed": None, "cost": None,
        "structured_output": None, "context": None, "tool_use": None,
        "multimodal": None,
        "independence": "different-model-family",
    },
    "method-reviewer": {
        "reasoning": "high", "speed": None, "cost": None,
        "structured_output": None, "context": "high", "tool_use": None,
        "multimodal": None,
    },
    "evidence-judge": {
        "reasoning": "highest", "speed": None, "cost": None,
        "structured_output": "strong", "context": None, "tool_use": None,
        "multimodal": None,
    },
    "intervention-designer": {
        "reasoning": "high", "speed": None, "cost": None,
        "structured_output": None, "context": None, "tool_use": None,
        "multimodal": None,
    },
    "evaluation-designer": {
        "reasoning": "high", "speed": None, "cost": None,
        "structured_output": None, "context": None, "tool_use": None,
        "multimodal": None,
        "quantitative": "preferred",
    },
}

# Human-readable one-line task per role (for the user-facing recommendation
# table). Display metadata only — not a routing decision.
ROLE_TASKS: dict[str, str] = {
    "education-planner": "Framing：把教学问题转成 EducationResearchFrame",
    "evidence-retriever": "检索支持与反方证据，去重初筛",
    "evidence-analyst": "证据结构化抽取为 Evidence Objects",
    "skeptic": "独立反证：9 项检查，找 null/negative/contradictory 证据",
    "method-reviewer": "方法学审计（样本/测量/结论范围）",
    "evidence-judge": "Tribunal 裁决四态结论",
    "intervention-designer": "干预方案设计（适用性/成本/风险）",
    "evaluation-designer": "评估设计（对照组/指标/定量分析）",
}

# CLI discovery commands (best-effort; CLIs without a working discovery
# command report models: [] — never guessed).
_CLI_MODEL_COMMANDS: dict[str, tuple[list[str], str]] = {
    "opencode": (["opencode", "models"], "slash_lines"),
    "omp": (["omp", "models"], "omp_table"),
    "codex": (["codex", "models"], "slash_lines"),
    "grok": (["grok", "models"], "slash_lines"),
}

# Model-family heuristics for the skeptic independence check (family names
# are coarse identifiers, not capability claims).
_FAMILY_RULES: tuple[tuple[str, str], ...] = (
    ("claude", "anthropic"),
    ("fable", "anthropic"),
    ("gemini", "google"),
    ("gpt-", "openai"),
    ("luna", "openai"),
    ("deepseek", "deepseek"),
    ("dsh", "deepseek"),
    ("ds-flash", "deepseek"),
    ("glm", "zhipu"),
    ("kimi", "moonshot"),
    ("moonshot", "moonshot"),
    ("grok", "xai"),
    ("qwen", "alibaba"),
    ("llama", "meta"),
    ("mimo", "minimax"),
    ("nemotron", "nvidia"),
)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

_REASONING_RANK = {"highest": 5, "high": 4, "medium+": 3, "medium": 2, "low": 1}
_COST_RANK = {"low": 3, "medium": 2, "high": 1}
_QUAL_RANK = {"strong": 3, "medium": 2, "weak": 1}
_CONTEXT_TIEBREAK = {"high": 3, "medium": 2, "low": 1, "unknown": 0}


class AgentMCPUnavailable(RuntimeError):
    """Raised when agent-mcp is not installed or its daemon is not reachable."""


# --------------------------------------------------------------------------
# detect / require — availability probe (tri-state, OPEN-5)
# --------------------------------------------------------------------------

def _daemon_reachable(port: int | None = None) -> bool:
    """Best-effort probe of the agent-mcp daemon on 127.0.0.1:<port>."""
    try:
        with socket.create_connection(("127.0.0.1", AGENT_MCP_PORT if port is None else port),
                                      timeout=0.5):
            return True
    except OSError:
        return False


def detect_agent_mcp() -> dict[str, Any]:
    """Probe availability: env marker + daemon health endpoint.

    Tri-state detection (OPEN-5 — a running daemon must not look like a hard
    failure when the env marker is missing):

      - "available": env declares AGENT_MCP_INSTALLED AND the daemon is reachable
      - "daemon_reachable_undeclared": daemon reachable but env not declared —
        the host is running agent-mcp; set AGENT_MCP_INSTALLED=1 (via
        ~/.eduevidence/env, shell profile, or host MCP injection) to enable it
      - "unavailable": not installed / fully unavailable (env declares but
        daemon down is also reported here, with the daemon reason)

    Backward compatible: available / mode / port / home / reasons /
    enhanced_features keep their prior meaning; state / reason / hint are
    additive. Returns an availability report (never raises).
    """
    declared = AGENT_MCP_INSTALLED
    daemon_reachable = _daemon_reachable()
    reasons: list[str] = []

    if not declared:
        reasons.append("AGENT_MCP_INSTALLED env not set")
    if not daemon_reachable:
        reasons.append(f"daemon not reachable on 127.0.0.1:{AGENT_MCP_PORT}")

    if declared and daemon_reachable:
        state = "available"
    elif daemon_reachable:
        state = "daemon_reachable_undeclared"
    else:
        state = "unavailable"

    available = state == "available"
    if state == "daemon_reachable_undeclared":
        reason = (f"daemon reachable on 127.0.0.1:{AGENT_MCP_PORT} but "
                  "AGENT_MCP_INSTALLED is not declared")
        hint = ("Agent MCP daemon 可达但未声明安装：设置 AGENT_MCP_INSTALLED=1 "
                "（写入 ~/.eduevidence/env、shell profile，或由宿主 MCP 层注入）"
                "即可启用 agent_mcp_enhanced")
    elif available:
        reason = "agent-mcp installed and daemon reachable"
        hint = ""
    else:
        reason = "agent-mcp not available (see reasons)"
        hint = ""

    return {
        "available": available,
        "state": state,
        "mode": "agent_mcp_enhanced" if available else "platform_native",
        "port": AGENT_MCP_PORT,
        "home": os.path.expanduser(AGENT_MCP_HOME),
        "reason": reason,
        "reasons": reasons,
        "hint": hint,
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


# --------------------------------------------------------------------------
# Phase 5.3 — Model Inventory (scan only the user-approved CLI set)
# --------------------------------------------------------------------------

def _run_cli_cmd(argv: list[str], timeout: int = 20) -> str:
    """Run a CLI discovery command, returning combined stdout+stderr."""
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    return (proc.stdout or "") + (proc.stderr or "")


def _parse_slash_lines(text: str) -> list[str]:
    """Parse `opencode models`-style output: one 'provider/model' per line."""
    out: list[str] = []
    for line in text.splitlines():
        line = _ANSI_RE.sub("", line).strip()
        if "/" in line and not line.startswith(("┌", "└", "│", "├", "─")):
            out.append(line)
    return out


def _parse_omp_table(text: str) -> list[dict[str, str]]:
    """Parse `omp models` box table into {model, context, images} records."""
    provider: str | None = None
    records: list[dict[str, str]] = []
    for raw in text.splitlines():
        line = _ANSI_RE.sub("", raw).strip()
        m = re.match(r"^(\S+)\s+\(\d+\)$", line)
        if m:
            provider = m.group(1)
            continue
        if "│" not in line:
            continue
        cells = [c.strip() for c in line.split("│")]
        cells = [c for c in cells if c and not c.startswith(("─", "┌", "└", "├"))]
        if len(cells) < 2 or cells[0] in ("model", "name"):
            continue
        records.append({
            "model": f"{provider}/{cells[0]}" if provider else cells[0],
            "context": cells[1] if len(cells) > 1 else "-",
            "images": cells[-1] if len(cells) > 3 else "-",
        })
    return records


def scan_cli_models(cli: str, *, timeout: int = 20) -> dict[str, Any]:
    """Scan one CLI for models reachable via its own discovery command.

    Returns {"available": bool, "models": [str], "model_details": {model: {...}}}.
    Unverifiable CLIs report models: [] — never guesses.
    """
    entry: dict[str, Any] = {
        "available": shutil.which(cli) is not None,
        "models": [],
        "model_details": {},
    }
    command = _CLI_MODEL_COMMANDS.get(cli)
    if not entry["available"] or command is None:
        return entry
    argv, kind = command
    try:
        text = _run_cli_cmd(argv, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return entry
    if kind == "omp_table":
        for rec in _parse_omp_table(text):
            entry["models"].append(rec["model"])
            entry["model_details"][rec["model"]] = {
                "context": rec["context"], "images": rec["images"]}
    else:
        entry["models"] = _parse_slash_lines(text)
    return entry


def scan_available_models(allowed_clis: list[str], *, timeout: int = 20) -> dict[str, Any]:
    """Scan the user-approved CLI set (never the whole machine)."""
    return {cli: scan_cli_models(cli, timeout=timeout) for cli in allowed_clis}


def write_model_inventory(allowed_clis: list[str], runs_dir: str = "runs",
                          run_id: str | None = None) -> tuple[Path, dict[str, Any]]:
    """Write runs/<run_id>/model_inventory.json (Phase 5.3).

    Shape: {"scanned_at": iso8601, "clis": {cli: {"available": bool,
            "models": [str], "model_details": {...}}}}.
    """
    run_id = run_id or os.environ.get("RUN_ID") or datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path(runs_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    inventory: dict[str, Any] = {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "clis": scan_available_models(allowed_clis),
    }
    path = out_dir / "model_inventory.json"
    path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path, inventory


# --------------------------------------------------------------------------
# Phase 5.4 — Model Capability Profile (verifiable facts only; else unknown)
# --------------------------------------------------------------------------

def _family(model: str) -> str:
    """Coarse model family from the model name (for independence checks)."""
    name = model.split("/")[-1].lower()
    for token, family in _FAMILY_RULES:
        if token in name:
            return family
    return "unknown"


def _context_from_label(context: str) -> str | None:
    """'1M'/'203K'/'-' -> 'high'|'medium'|'low'|None."""
    m = re.match(r"([\d.]+)([KM])", context)
    if not m:
        return None
    tokens = int(float(m.group(1)) * (1000 if m.group(2) == "K" else 1_000_000))
    if tokens >= 200_000:
        return "high"
    if tokens >= 32_000:
        return "medium"
    return "low"


def capability_profile(model: str, inventory: dict[str, Any] | None = None) -> dict[str, Any]:
    """Verified capability profile for one model.

    Every dimension is 'unknown' unless a discovery command provided
    verifiable facts (context window, image input). reasoning/speed/cost/
    structured_output/tool_use are NOT guessed.
    """
    detail: dict[str, Any] = {}
    if inventory:
        for cli_entry in inventory.get("clis", {}).values():
            detail = cli_entry.get("model_details", {}).get(model, {})
            if detail:
                break
    profile: dict[str, Any] = {
        dim: "unknown" for dim in ("reasoning", "speed", "cost",
                                   "structured_output", "context",
                                   "tool_use", "multimodal")
    }
    context = detail.get("context")
    if context:
        level = _context_from_label(context)
        if level:
            profile["context"] = level
    if detail.get("images") in ("yes", "no"):
        profile["multimodal"] = detail["images"]
    profile["family"] = _family(model)
    profile["verified_sources"] = sorted(k for k in detail if detail[k] not in ("", "-"))
    return profile


# --------------------------------------------------------------------------
# Phase 6-7 — Model Recommender (Role Requirements x Capability Profile)
# --------------------------------------------------------------------------

def _score_dimension(dimension: str, requirement: Any, capability: str) -> float:
    """1.0 meets / 0.5 one level below or unknown / 0.0 clearly below."""
    if requirement is None:
        return 1.0
    if capability == "unknown":
        return 0.5
    rank = {"reasoning": _REASONING_RANK, "speed": _REASONING_RANK,
            "context": _REASONING_RANK, "cost": _COST_RANK,
            "structured_output": _QUAL_RANK, "tool_use": _QUAL_RANK,
            "multimodal": _QUAL_RANK}[dimension]
    req_rank = rank.get(requirement, 0)
    cap_rank = rank.get(capability, 0)
    if cap_rank >= req_rank:
        return 1.0
    if cap_rank >= req_rank - 1:
        return 0.5
    return 0.0


def score_role_proposals(role: str, clis: list[str],
                         inventory: dict[str, Any]) -> list[dict[str, Any]]:
    """Score every (cli, model) candidate for one role; best first."""
    reqs = ROLE_REQUIREMENTS[role]
    dims = ("reasoning", "speed", "cost", "structured_output",
            "context", "tool_use", "multimodal")
    proposals: list[dict[str, Any]] = []
    for cli in clis:
        entry = inventory.get("clis", {}).get(cli, {})
        for model in entry.get("models", []):
            cap = capability_profile(model, inventory)
            score = sum(_score_dimension(d, reqs[d], cap[d]) for d in dims) / len(dims)
            notes: list[str] = []
            if cap["context"] != "unknown":
                notes.append(f"verified context {cap['context']}")
            if cap["multimodal"] != "unknown":
                notes.append(f"verified multimodal {cap['multimodal']}")
            if reqs.get("independence"):
                notes.append(f"family {cap['family']}")
            if reqs.get("quantitative") == "preferred":
                notes.append("quantitative output preferred (unverified)")
            proposals.append({
                "role": role, "cli": cli, "model": model, "family": cap["family"],
                "score": round(score, 3), "notes": notes, "capabilities": cap,
            })
    proposals.sort(key=lambda p: (-p["score"],
                                  -_CONTEXT_TIEBREAK[p["capabilities"]["context"]],
                                  p["model"]))
    return proposals


def _cost_class(model: str | None) -> str:
    """Cost class of a model; nothing verifiable -> 'unknown'."""
    return "unknown"


def build_recommendation_table(allowed_clis: list[str],
                               inventory: dict[str, Any]) -> dict[str, Any]:
    """User-facing recommendation table (Phase 6-7).

    One row per role: {role, cli, model, reason, task}. Also summary:
    role_count, concurrency, cross_model_review, memory_bank, cost_class.
    """
    recommendations: list[dict[str, Any]] = []
    for role in ROLE_REQUIREMENTS:
        proposals = score_role_proposals(role, allowed_clis, inventory)
        if not proposals:
            recommendations.append({
                "role": role, "cli": None, "model": None, "family": "unknown",
                "score": None,
                "reason": "no verified models for allowed CLIs; user must "
                          "specify cli+model in the approval",
                "task": ROLE_TASKS[role],
            })
            continue
        best = proposals[0]
        reasons = [f"score {best['score']:.2f} over verified capabilities"]
        reasons.extend(best["notes"])
        recommendations.append({
            "role": role, "cli": best["cli"], "model": best["model"],
            "family": best["family"], "score": best["score"],
            "reason": "; ".join(reasons), "task": ROLE_TASKS[role],
        })

    families = {r["role"]: r.get("family") for r in recommendations}
    skeptic_family = families.get("skeptic")
    judge_family = families.get("evidence-judge")
    cross_model = bool(skeptic_family and judge_family
                       and skeptic_family != judge_family)
    cost_classes = {_cost_class(r["model"]) for r in recommendations if r["model"]}
    cost_class = "Unknown" if not cost_classes or cost_classes == {"unknown"} \
        else "/".join(sorted(cost_classes))

    return {
        "recommendations": recommendations,
        "summary": {
            "role_count": len(recommendations),
            "concurrency": len(recommendations),
            "cross_model_review": cross_model,
            "memory_bank": True,
            "cost_class": cost_class,
            "note": "scores use only verified facts; unknown capabilities "
                    "score 0.5 and never disqualify — the final cli/model "
                    "requires explicit user confirmation (safe_spawn gate).",
        },
    }


# --------------------------------------------------------------------------
# Phase 8 — Approval Gate (agent_mcp_approval.json)
# --------------------------------------------------------------------------

def _role_mapping_hash(roles: dict[str, Any]) -> str:
    """Stable SHA-256 of the canonical role->{cli, model} mapping."""
    payload = json.dumps(roles, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_approval_record(roles: dict[str, Any], allowed_clis: list[str],
                          *, budget: dict[str, Any] | None = None,
                          provider: str | None = None) -> dict[str, Any]:
    """Build the approval record the user confirms.

    roles: {role: {"cli": str, "model": str}} — the exact mapping that will
    be enforced by safe_spawn(). Any later change to this mapping (new CLI,
    replaced model, new role, modified mapping) invalidates the hash and
    requires re-confirmation.
    """
    canonical = json.loads(json.dumps(roles, sort_keys=True))
    return {
        "approved": True,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "allowed_clis": sorted(allowed_clis),
        "role_mapping_hash": _role_mapping_hash(canonical),
        "roles": canonical,
        "budget": budget or {},
        "provider": provider,
        "schema_version": 1,
    }


def write_approval(path: str | Path, roles: dict[str, Any], allowed_clis: list[str],
                   *, budget: dict[str, Any] | None = None,
                   provider: str | None = None) -> dict[str, Any]:
    """Persist the user-approved mapping to agent_mcp_approval.json."""
    record = build_approval_record(roles, allowed_clis, budget=budget, provider=provider)
    Path(path).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    return record


def load_approval(path: str | Path) -> dict[str, Any] | None:
    """Load an approval file; missing/corrupt -> None (gate closed)."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def is_approval_current(approval: dict[str, Any] | None, roles: dict[str, Any],
                        allowed_clis: list[str], *, budget: dict[str, Any] | None = None,
                        provider: str | None = None) -> tuple[bool, list[str]]:
    """True when the approval still matches the current proposal.

    Returns (ok, changes); any change requires re-confirmation: 新增 CLI /
    替换模型 / 新增角色 / 修改映射 / 提高 budget / 新 provider.
    """
    changes: list[str] = []
    if not approval or not approval.get("approved"):
        changes.append("approval missing or not approved")
    else:
        stored = approval.get("roles") or {}
        if approval.get("role_mapping_hash") != _role_mapping_hash(stored):
            changes.append("approval file tampered (role_mapping_hash mismatch)")
        if _role_mapping_hash(roles) != approval.get("role_mapping_hash"):
            changes.append("role mapping changed (new CLI / replaced model / "
                           "new role / modified mapping)")
        if sorted(approval.get("allowed_clis", [])) != sorted(allowed_clis):
            changes.append("allowed_clis changed")
        if budget is not None and approval.get("budget") != budget:
            changes.append("budget changed")
        if provider is not None and approval.get("provider") != provider:
            changes.append("provider changed")
    return (not changes, changes)


def _check_approval(approval: dict[str, Any] | None, role: str, *,
                    target_cli: str | None = None, model: str | None = None,
                    allowed_clis: list[str] | None = None) -> str | None:
    """Gate check: None when allowed, else AGENT_MCP_APPROVAL_REQUIRED.

    Order: approval exists -> hash matches -> CLI allowed -> model approved
    -> role approved.
    """
    if not approval or not approval.get("approved"):
        return AGENT_MCP_APPROVAL_REQUIRED
    stored = approval.get("roles") or {}
    if approval.get("role_mapping_hash") != _role_mapping_hash(stored):
        return AGENT_MCP_APPROVAL_REQUIRED
    mapping = stored.get(role)
    if mapping is None:
        return AGENT_MCP_APPROVAL_REQUIRED
    cli = mapping["cli"] if target_cli is None else target_cli
    mdl = mapping["model"] if model is None else model
    if not cli or not mdl:
        return AGENT_MCP_APPROVAL_REQUIRED
    if allowed_clis is not None and cli not in allowed_clis:
        return AGENT_MCP_APPROVAL_REQUIRED
    if cli != mapping.get("cli") or mdl != mapping.get("model"):
        return AGENT_MCP_APPROVAL_REQUIRED
    return None


# --------------------------------------------------------------------------
# Phase 9 — Spawn Guard: the ONLY spawn entry point
# --------------------------------------------------------------------------

def safe_spawn(role: str, prompt: str, approval: dict[str, Any] | None, *,
               target_cli: str | None = None, model: str | None = None,
               allowed_clis: list[str] | None = None,
               cwd: str = ".", permission_mode: str = "plan",
               context_mode: str = "compact", summary_chars: int | None = None,
               timeout_seconds: int = 1800, cache_ttl: int = 0,
               token_budget: int | None = None) -> dict[str, Any]:
    """UNIFIED spawn entry. Business code MUST NOT call spawn directly.

    Gate order: approval exists -> proposal hash matches -> CLI allowed ->
    model approved -> role approved -> build spawn payload. Any failure
    returns {"status": AGENT_MCP_APPROVAL_REQUIRED, "spawn_call": None}.
    CLI/model default to the approved role mapping; explicit values must
    equal the approved ones.
    """
    failure = _check_approval(approval, role, target_cli=target_cli, model=model,
                              allowed_clis=allowed_clis)
    if failure is not None:
        return {"status": failure, "spawn_call": None}
    mapping = approval["roles"][role]  # type: ignore[index]
    return {
        "status": "READY",
        "spawn_call": build_spawn_call(
            role, prompt, target_cli=mapping["cli"], model=mapping["model"],
            cwd=cwd, permission_mode=permission_mode, context_mode=context_mode,
            summary_chars=summary_chars, timeout_seconds=timeout_seconds,
            cache_ttl=cache_ttl, token_budget=token_budget),
    }


# --------------------------------------------------------------------------
# Payload builders (no hardcoded defaults — cli/model always explicit)
# --------------------------------------------------------------------------

def _routing_class(role: str) -> str:
    """fast / strong / independent class derived from role requirements."""
    reqs = ROLE_REQUIREMENTS.get(role, {})
    if reqs.get("independence"):
        return "independent"
    if reqs.get("speed") == "high":
        return "fast"
    return "strong"


def build_spawn_call(role: str, prompt: str, *, target_cli: str, model: str,
                     cwd: str = ".", permission_mode: str = "plan",
                     context_mode: str = "compact", summary_chars: int | None = None,
                     timeout_seconds: int = 1800, cache_ttl: int = 0,
                     token_budget: int | None = None) -> dict[str, Any]:
    """Build a spawn_agent tool-call payload matching the agent-mcp MCP contract.

    target_cli and model are REQUIRED — there are no hardcoded defaults.
    Approved values come from the user-confirmed mapping via safe_spawn().
    """
    if role not in ROLE_REQUIREMENTS:
        raise ValueError(f"unknown role {role!r}; known: {sorted(ROLE_REQUIREMENTS)}")
    if not target_cli or not model:
        raise ValueError("target_cli and model are required (no hardcoded "
                         "defaults); use safe_spawn() with a user approval")
    routing_role = _routing_class(role)
    if summary_chars is None:
        summary_chars = 600 if routing_role == "fast" else 2000
    return {
        "tool": "spawn_agent",
        "arguments": {
            "task_name": role,
            "prompt": prompt,
            "target_cli": target_cli,
            "model": model,
            "cwd": cwd,
            "permission_mode": permission_mode,
            "context_mode": context_mode,
            "summary_chars": summary_chars,
            "timeout_seconds": timeout_seconds,
            "cache_ttl": cache_ttl,
            "token_budget": token_budget,
        },
        "routing_role": routing_role,
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


def cross_model_review(draft_verdict: dict[str, Any], *, target_cli: str, model: str,
                       approval: dict[str, Any] | None = None,
                       **_: Any) -> dict[str, Any]:
    """Cross-Model Review orchestration (总体实施计划 §25).

    Flow: Primary Analysis -> Draft Verdict -> Independent Review -> Judge ->
    Final Verdict. The independent reviewer runs under the 'skeptic' role with
    the cli/model the user approved for it. Without explicit user approval the
    review is NOT spawned: status AGENT_MCP_APPROVAL_REQUIRED. When agent-mcp
    is unavailable, degrades to a native self-review plan marked
    AGENT_MCP_UNAVAILABLE (no hard failure).
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
                            "independent_model": model},
        }
    if approval is None:
        return {
            "status": AGENT_MCP_APPROVAL_REQUIRED,
            "note": "cross-model review needs explicit user approval "
                    "(safe_spawn gate); nothing was spawned.",
            "review_plan": {"reviewer_prompt": reviewer_prompt,
                            "independent_model": model},
        }
    result = safe_spawn("skeptic", reviewer_prompt, approval,
                        target_cli=target_cli, model=model,
                        context_mode="full", summary_chars=2000)
    if result["status"] != "READY":
        return {
            "status": result["status"],
            "review_plan": {"reviewer_prompt": reviewer_prompt,
                            "independent_model": model},
        }
    return {
        "status": "READY",
        "spawn_call": result["spawn_call"],
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
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Agent MCP detect / inventory / recommend")
    parser.add_argument("--inventory", nargs="*", default=None, metavar="CLI",
                        help="scan these CLIs and write runs/<run_id>/model_inventory.json")
    parser.add_argument("--recommend", nargs="*", default=None, metavar="CLI",
                        help="print the user-facing recommendation table for these CLIs")
    args = parser.parse_args()

    out: dict[str, Any] = {"detect": detect_agent_mcp()}
    if args.inventory is not None:
        path, inventory = write_model_inventory(args.inventory)
        out["model_inventory"] = {"path": str(path),
                                  "clis": {c: {"available": e["available"],
                                               "models": e["models"]}
                                           for c, e in inventory["clis"].items()}}
    if args.recommend is not None:
        _, inventory = write_model_inventory(args.recommend)
        out["recommendation"] = build_recommendation_table(args.recommend, inventory)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0)
