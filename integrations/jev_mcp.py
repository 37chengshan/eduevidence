#!/usr/bin/env python3
"""jev_mcp.py — thin re-export of integrations.jev (package split).

Public API unchanged. Implementation lives in integrations/jev/.
Providers: freejev (FREEJEV_API_KEY + JEV_PROVIDER=freejev; MCP
https://freejev.org/mcp; request_id never retried) or vercel (default).
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from integrations.jev import *  # noqa: F401,F403
from integrations.jev import __all__  # noqa: F401

if __name__ == "__main__":
    from integrations.jev.cli import main
    raise SystemExit(main())
