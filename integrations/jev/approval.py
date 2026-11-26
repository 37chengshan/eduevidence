"""Availability detect + user approval gate (~/.eduevidence/jev_mcp_approval.json)."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import (
    JEV_APPROVAL_PATH,
    JEV_APPROVAL_REQUIRED,
    JEV_UNAVAILABLE,
    MCP_JEV_TOOLS,
    MODE_JEV_MCP,
    NPM_JEV_MCP,
    TIER0_TOOLS,
    THRESHOLDS,
    api_key,
    model_id,
    provider,
    system_one_url,
)


def detect_jev_mcp() -> dict[str, Any]:
    """Probe Jev gateway credentials and (optional) local MCP binary.

    Providers: freejev (FREEJEV_API_KEY + JEV_PROVIDER=freejev; MCP
    https://freejev.org/mcp; request_id never retried) or vercel (default).

    States:
      - available: provider key present and provider is supported
      - mcp_documented: key missing but npx/node present (documented path only)
      - unavailable: neither usable transport
    """
    key = api_key()
    prov = provider()
    reasons: list[str] = []
    has_npx = any(
        os.path.exists(os.path.join(d, "npx"))
        for d in os.environ.get("PATH", "").split(os.pathsep) if d
    )

    if not key:
        reasons.append("AI_GATEWAY_API_KEY not set in env or ~/.eduevidence/env")
    if prov not in ("vercel", "typesafe", "compatible", "openrouter", "cloudflare",
                    "freejev"):
        reasons.append(f"unsupported JEV_PROVIDER={prov!r}")

    if key and prov in ("vercel", "typesafe", "compatible", "openrouter", "cloudflare",
                        "freejev"):
        state = "available"
        available = True
        mode = "jev_gateway"
        hint = ""
    elif has_npx:
        state = "mcp_documented"
        available = False
        mode = "mcp_documented"
        hint = (f"Gateway key missing — register MCP server via `{NPM_JEV_MCP}` "
                "in the host agent, or set AI_GATEWAY_API_KEY + JEV_PROVIDER=vercel "
                "in ~/.eduevidence/env")
    else:
        state = "unavailable"
        available = False
        mode = "none"
        hint = "Install Node 20+ for MCP path, or configure Vercel AI Gateway key"

    return {
        "available": available,
        "state": state,
        "mode": mode,
        "provider": prov if key else None,
        "model": model_id() if key else None,
        "endpoint": system_one_url() if key else None,
        "reason": "; ".join(reasons) or "gateway credentials present",
        "reasons": reasons,
        "hint": hint,
        "tier0_tools": list(TIER0_TOOLS),
        "mcp_alternate": {
            "command": NPM_JEV_MCP,
            "tools": dict(MCP_JEV_TOOLS),
            "env": ["TYPESAFE_API_KEY or AI_GATEWAY_API_KEY", "JEV_PROVIDER"],
        },
        "thresholds": dict(THRESHOLDS),
    }


def require_jev_mcp() -> dict[str, Any]:
    report = detect_jev_mcp()
    if not report["available"]:
        raise RuntimeError(JEV_UNAVAILABLE)
    return report


def _tools_hash(tools: tuple[str, ...] | list[str]) -> str:
    payload = json.dumps(sorted(tools), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_approval_record(
    tools: list[str] | tuple[str, ...] = TIER0_TOOLS,
    *,
    provider_name: str | None = None,
    model: str | None = None,
    mode: int = MODE_JEV_MCP,
) -> dict[str, Any]:
    """Build the approval record the user confirms before any network call."""
    selected = tuple(sorted({str(t) for t in tools if str(t) in TIER0_TOOLS}))
    return {
        "approved": True,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "mode": int(mode),
        "provider": provider_name or provider(),
        "model": model or model_id(),
        "tools": list(selected),
        "tools_hash": _tools_hash(selected),
        "endpoint": system_one_url(),
        "schema_version": 1,
    }


def write_approval(path: str | Path | None = None, **kwargs: Any) -> dict[str, Any]:
    record = build_approval_record(**kwargs)
    out = Path(os.path.expanduser(path or JEV_APPROVAL_PATH))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    return record


def load_approval(path: str | Path | None = None) -> dict[str, Any] | None:
    try:
        return json.loads(
            Path(os.path.expanduser(path or JEV_APPROVAL_PATH)).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def is_approval_current(
    approval: dict[str, Any] | None,
    tools: list[str] | tuple[str, ...] = TIER0_TOOLS,
    *,
    provider_name: str | None = None,
    model: str | None = None,
    mode: int | None = None,
) -> tuple[bool, list[str]]:
    """True when the approval still matches the current proposal."""
    changes: list[str] = []
    if not approval or not approval.get("approved"):
        changes.append("approval missing or not approved")
        return False, changes
    stored = tuple(sorted(approval.get("tools") or []))
    if approval.get("tools_hash") != _tools_hash(stored):
        changes.append("approval file tampered (tools_hash mismatch)")
    wanted = tuple(sorted({str(t) for t in tools if str(t) in TIER0_TOOLS}))
    if wanted != stored:
        changes.append("tool set changed")
    if provider_name is not None and approval.get("provider") != provider_name:
        changes.append("provider changed")
    elif provider_name is None and approval.get("provider") != provider():
        changes.append("provider changed")
    if model is not None and approval.get("model") != model:
        changes.append("model changed")
    elif model is None and approval.get("model") != model_id():
        changes.append("model changed")
    if mode is not None and int(approval.get("mode", -1)) != int(mode):
        changes.append("experimental mode changed")
    disk = load_approval()
    if not disk:
        changes.append("approval file missing on disk")
    elif not disk.get("approved"):
        changes.append("approval on disk is not approved")
    elif disk.get("tools_hash") != approval.get("tools_hash"):
        changes.append("approval file tampered (disk tools_hash mismatch)")
    return (not changes), changes


def _check_approval(approval: dict[str, Any] | None, tool: str) -> str | None:
    """None when allowed, else JEV_APPROVAL_REQUIRED. Fail closed.

    Accepts only records that still match the on-disk approval file.
    In-memory forged dicts are rejected. Provider/endpoint must match live
    config exactly — no vercel bypass.
    """
    if not approval or not approval.get("approved"):
        return JEV_APPROVAL_REQUIRED
    stored = tuple(sorted(approval.get("tools") or []))
    if approval.get("tools_hash") != _tools_hash(stored):
        return JEV_APPROVAL_REQUIRED
    if tool not in TIER0_TOOLS or tool not in stored:
        return JEV_APPROVAL_REQUIRED
    disk = load_approval()
    if not disk or not disk.get("approved"):
        return JEV_APPROVAL_REQUIRED
    if disk.get("tools_hash") != approval.get("tools_hash"):
        return JEV_APPROVAL_REQUIRED
    if tuple(sorted(disk.get("tools") or [])) != stored:
        return JEV_APPROVAL_REQUIRED
    if approval.get("provider") != provider():
        return JEV_APPROVAL_REQUIRED
    if approval.get("endpoint") and approval.get("endpoint") != system_one_url():
        return JEV_APPROVAL_REQUIRED
    return None
