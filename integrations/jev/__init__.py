"""integrations.jev — Jev (TypeSafe System One) experimental Tier-0 package.

Experimental only (`--experimental` / mode 1 or 3). Never a scientific gate
replacement. Public API is re-exported here and via integrations/jev_mcp.py.

Providers: freejev (FREEJEV_API_KEY + JEV_PROVIDER=freejev, MCP
https://freejev.org/mcp, request_id never retried) or vercel (default).
Fail-closed: invalid / provider errors escalate to the large model.
"""
from __future__ import annotations

from typing import Any

from .approval import (
    build_approval_record,
    detect_jev_mcp,
    is_approval_current,
    load_approval,
    require_jev_mcp,
    write_approval,
)
from .cli import npx_mcp_guide
from .config import (
    DEFAULT_MODEL,
    ESCALATE_TO_LLM,
    JEV_APPROVAL_PATH,
    JEV_APPROVAL_REQUIRED,
    JEV_ENV_FILE,
    JEV_INVALID_RESPONSE,
    JEV_PROVIDER_ERROR,
    JEV_UNAVAILABLE,
    MCP_JEV_TOOLS,
    MODE_HYBRID,
    MODE_JEV_MCP,
    MODE_SEMDECIDE,
    MODE_STANDARD,
    NPM_JEV_MCP,
    THRESHOLDS,
    TIER0_TOOLS,
    VERCEL_TYPE_SAFE_BASE,
    api_key,
    model_id,
    provider,
    system_one_url,
)
from .gateway import system_one
from .modes import resolve_experimental_mode
from .tools_classify import classify
from .tools_extract import extract
from .tools_rerank import rerank
from .tools_screen import screen
from .tools_verify import verify

# Map capability_id -> wrapper (engine/capabilities.py experimental set).
CAPABILITY_TO_TOOL = {
    "content_screen": screen,
    "semantic_rerank": rerank,
    "field_extract": extract,
    "classify_check": classify,
    "claim_verify": verify,
}


def safe_call(capability_id: str, *args: Any,
              approval: dict[str, Any] | None = None,
              **kwargs: Any) -> dict[str, Any]:
    """Capability-routed Tier-0 call with the approval gate applied."""
    fn = CAPABILITY_TO_TOOL.get(capability_id)
    if fn is None:
        return {"status": JEV_INVALID_RESPONSE,
                "error": f"unknown capability {capability_id!r}",
                "escalate": ESCALATE_TO_LLM}
    kwargs.setdefault("approval", approval)
    return fn(*args, **kwargs)


__all__ = [
    "CAPABILITY_TO_TOOL",
    "DEFAULT_MODEL",
    "ESCALATE_TO_LLM",
    "JEV_APPROVAL_PATH",
    "JEV_APPROVAL_REQUIRED",
    "JEV_ENV_FILE",
    "JEV_INVALID_RESPONSE",
    "JEV_PROVIDER_ERROR",
    "JEV_UNAVAILABLE",
    "MCP_JEV_TOOLS",
    "MODE_HYBRID",
    "MODE_JEV_MCP",
    "MODE_SEMDECIDE",
    "MODE_STANDARD",
    "NPM_JEV_MCP",
    "THRESHOLDS",
    "TIER0_TOOLS",
    "VERCEL_TYPE_SAFE_BASE",
    "api_key",
    "build_approval_record",
    "classify",
    "detect_jev_mcp",
    "extract",
    "is_approval_current",
    "load_approval",
    "model_id",
    "npx_mcp_guide",
    "provider",
    "require_jev_mcp",
    "rerank",
    "resolve_experimental_mode",
    "safe_call",
    "screen",
    "system_one",
    "system_one_url",
    "verify",
    "write_approval",
]
