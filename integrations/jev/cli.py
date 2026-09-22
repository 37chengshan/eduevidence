"""CLI: --experimental / --approve / --mcp-guide (npx @jkudish/jev-mcp path)."""
from __future__ import annotations

import argparse
import json
from typing import Any

from .approval import detect_jev_mcp, write_approval
from .config import (
    MCP_JEV_TOOLS,
    MODE_HYBRID,
    MODE_JEV_MCP,
    MODE_STANDARD,
    NPM_JEV_MCP,
    TIER0_TOOLS,
)
from .modes import resolve_experimental_mode


def npx_mcp_guide() -> dict[str, Any]:
    """Documented alternate: host-registered @jkudish/jev-mcp MCP server."""
    return {
        "command": NPM_JEV_MCP,
        "requires": ["Node.js >= 20", "TYPESAFE_API_KEY or AI_GATEWAY_API_KEY"],
        "env": {
            "AI_GATEWAY_API_KEY": "set in ~/.eduevidence/env — never commit",
            "JEV_PROVIDER": "vercel | freejev",
            "TYPESAFE_API_KEY": "optional direct TypeSafe key",
            "FREEJEV_API_KEY": "FreeJev key when JEV_PROVIDER=freejev",
        },
        "freejev": {
            "mcp": "https://freejev.org/mcp",
            "decide": "https://freejev.org/api/v1/decide",
            "request_id": "idempotency key — never retry the same request_id",
        },
        "client_snippets": {
            "claude_code": "claude mcp add jev -- npx -y @jkudish/jev-mcp",
            "generic_json": {
                "mcpServers": {
                    "jev": {
                        "command": "npx",
                        "args": ["-y", "@jkudish/jev-mcp"],
                        "env": {"TYPESAFE_API_KEY": "<from ~/.eduevidence/env>"},
                    }
                }
            },
        },
        "tools": dict(MCP_JEV_TOOLS),
        "note": "MCP path is host-side; this module only documents it and does "
                "not spawn or migrate jev-mcp implementation.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Jev experimental detect / approve / Tier-0 probe")
    parser.add_argument("--experimental", nargs="?", const="1", default=None,
                        metavar="MODE",
                        help="enable experimental mode 0|1|2|3 (default 1) and "
                             "print the resolved plan")
    parser.add_argument("--approve", action="store_true",
                        help="write ~/.eduevidence/jev_mcp_approval.json for "
                             "the current provider/model/tools")
    parser.add_argument("--mcp-guide", action="store_true",
                        help="print the documented npx @jkudish/jev-mcp path")
    args = parser.parse_args(argv)

    out: dict[str, Any] = {"detect": detect_jev_mcp()}
    mode = resolve_experimental_mode(args.experimental)
    if args.experimental is not None:
        out["experimental"] = {
            "mode": mode,
            "mode_name": {0: "standard", 1: "jev-mcp", 2: "semdecide",
                          3: "hybrid"}.get(mode, str(mode)),
            "enabled": mode != MODE_STANDARD,
            "tier0_tools": list(TIER0_TOOLS) if mode in (MODE_JEV_MCP, MODE_HYBRID) else [],
            "fail_closed": "uncertain / invalid / provider errors escalate to large model",
        }
    if args.approve:
        out["approval"] = write_approval()
    if args.mcp_guide:
        out["mcp_alternate"] = npx_mcp_guide()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0
