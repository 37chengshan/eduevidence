"""Jev env / paths / constants (real env > ~/.eduevidence/env > default).

Providers (Mode 1 / 3):
  - freejev: FREEJEV_API_KEY + JEV_PROVIDER=freejev
             Decide: https://freejev.org/api/v1/decide
             MCP (documented only): https://freejev.org/mcp
             request_id is an idempotency key — NEVER retry the same request_id;
             fail-closed escalate this call (new ask => new request_id).
  - vercel (default): AI_GATEWAY_API_KEY or TYPESAFE_API_KEY + JEV_PROVIDER=vercel
             Decide: https://ai-gateway.vercel.sh/typesafe/v1/systemone
             MCP (documented only): npx -y @jkudish/jev-mcp
"""
from __future__ import annotations

import os
from pathlib import Path

JEV_ENV_FILE = os.environ.get("JEV_ENV_FILE", "~/.eduevidence/env")
JEV_APPROVAL_PATH = os.environ.get(
    "JEV_APPROVAL_FILE", "~/.eduevidence/jev_mcp_approval.json")

JEV_UNAVAILABLE = "JEV_UNAVAILABLE"
JEV_APPROVAL_REQUIRED = "JEV_APPROVAL_REQUIRED"
JEV_INVALID_RESPONSE = "JEV_INVALID_RESPONSE"
JEV_PROVIDER_ERROR = "JEV_PROVIDER_ERROR"
ESCALATE_TO_LLM = "ESCALATE_TO_LLM"

MODE_STANDARD = 0
MODE_JEV_MCP = 1
MODE_SEMDECIDE = 2
MODE_HYBRID = 3

TIER0_TOOLS = ("screen", "rerank", "extract", "classify", "verify")

VERCEL_TYPE_SAFE_BASE = "https://ai-gateway.vercel.sh/typesafe"
FREEJEV_DECIDE_URL = "https://freejev.org/api/v1/decide"
FREEJEV_MCP_URL = "https://freejev.org/mcp"
DEFAULT_MODEL = "typesafe-ai/jev"

NPM_JEV_MCP = "npx -y @jkudish/jev-mcp"
MCP_JEV_TOOLS = {
    "screen": "jev_screen",
    "rerank": "jev_rerank",
    "extract": "jev_extract",
    "classify": "jev_classify",
    "verify": "jev_verify",
}

THRESHOLDS = {
    "screen_block_at": 0.75,
    "screen_review_at": 0.25,
    "verify_auto_accept": 0.80,
    "classify_auto_accept": 0.85,
    "classify_minimum_margin": 0.50,
    "extract_auto_accept": 0.80,
    "extract_minimum_margin": 0.40,
    "rerank_auto_accept": 0.70,
}


def _env_file_values(path: str | Path | None = None) -> dict[str, str]:
    """Parse KEY=VALUE lines from ~/.eduevidence/env (best-effort)."""
    try:
        text = Path(os.path.expanduser(path or JEV_ENV_FILE)).read_text(encoding="utf-8")
    except OSError:
        return {}
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("\"'")
    return values


_ENV_FILE_VALUES = _env_file_values()


def _effective_env(key: str, default: str = "") -> str:
    return os.environ.get(key) or _ENV_FILE_VALUES.get(key) or default


def provider() -> str:
    explicit = (_effective_env("JEV_PROVIDER") or "").lower()
    if explicit:
        return explicit
    if _effective_env("FREEJEV_API_KEY") and not (
            _effective_env("AI_GATEWAY_API_KEY")
            or _effective_env("TYPESAFE_API_KEY")):
        return "freejev"
    return "vercel"


def api_key() -> str:
    """Gateway / provider key. Never log or commit this value."""
    return (_effective_env("AI_GATEWAY_API_KEY")
            or _effective_env("TYPESAFE_API_KEY")
            or _effective_env("FREEJEV_API_KEY"))


def model_id() -> str:
    return _effective_env("JEV_MCP_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL


def system_one_url() -> str:
    if provider() == "freejev":
        return FREEJEV_DECIDE_URL
    base = _effective_env("JEV_TYPE_SAFE_BASE", VERCEL_TYPE_SAFE_BASE).rstrip("/")
    return f"{base}/v1/systemone"
