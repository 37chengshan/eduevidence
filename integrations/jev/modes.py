"""Experimental mode resolution (0|1|2|3)."""
from __future__ import annotations

from .config import (
    MODE_HYBRID,
    MODE_JEV_MCP,
    MODE_SEMDECIDE,
    MODE_STANDARD,
    _effective_env,
)


def resolve_experimental_mode(flag: str | int | bool | None = None) -> int:
    """Map --experimental / env to mode 0..3.

    Accepts 0|1|2|3, True (=1), None (env EDU_EXPERIMENTAL_JEV, else 0).
    """
    if flag is None:
        flag = _effective_env("EDU_EXPERIMENTAL_JEV", "") or _effective_env(
            "EXPERIMENTAL", "")
    if flag is True:
        return MODE_JEV_MCP
    if flag is False or flag is None or flag == "":
        return MODE_STANDARD
    text = str(flag).strip().lower()
    if text in ("0", "standard", "off", "false", "none"):
        return MODE_STANDARD
    if text in ("1", "jev", "jev-mcp", "jev_mcp", "true", "on"):
        return MODE_JEV_MCP
    if text in ("2", "semdecide", "sem"):
        return MODE_SEMDECIDE
    if text in ("3", "hybrid"):
        return MODE_HYBRID
    try:
        value = int(text)
    except ValueError:
        return MODE_STANDARD
    return value if value in (0, 1, 2, 3) else MODE_STANDARD
