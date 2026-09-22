"""Depth auto guideline: 单点→S，常规采用→M，高影响/争议/要试点→L，不确定取 M."""
from __future__ import annotations

from typing import Any

from intake.constants import (
    DEPTH_ALIASES,
    DEPTH_CHOICES,
    L_AUTO_SIGNALS,
    M_AUTO_SIGNALS,
    S_AUTO_SIGNALS,
)


def auto_resolve_depth(question: str, hints: dict[str, Any] | None = None) -> tuple[str, str]:
    text = (question or "").lower()
    hints = hints or {}
    blob = " ".join(str(v) for v in hints.values() if isinstance(v, str)).lower()
    hay = f"{text} {blob}"
    strong_l = any(k.lower() in hay for k in L_AUTO_SIGNALS)
    if any(k.lower() in hay for k in S_AUTO_SIGNALS) and not strong_l:
        return "S", "auto: single-point lookup signal → S"
    if strong_l:
        return "L", "auto: high-impact / contested / pilot-or-policy signal → L"
    if any(k.lower() in hay for k in M_AUTO_SIGNALS):
        return "M", "auto: routine adoption / comparison signal → M"
    return "M", "auto: uncertain → M (guideline default)"


def resolve_depth(choice: str | None, question: str,
                  hints: dict[str, Any] | None = None,
                  prefs: dict[str, Any] | None = None) -> tuple[str, str, str]:
    """Return (depth_choice, resolved_depth, rationale)."""
    prefs = prefs or {}
    if choice is not None:
        choice = DEPTH_ALIASES.get(str(choice), str(choice))
    if choice in ("S", "M", "L"):
        return choice, choice, f"explicit choice {choice}"
    if choice == "auto":
        depth, why = auto_resolve_depth(question, hints)
        return "auto", depth, why
    pref = prefs.get("depth_preference") or "auto"
    if pref in ("S", "M", "L"):
        return pref, pref, f"prefs.depth_preference={pref}"
    depth, why = auto_resolve_depth(question, hints)
    return "auto", depth, why


def normalize_depth_choice(raw: str | None) -> str | None:
    if raw is None:
        return None
    mapped = DEPTH_ALIASES.get(str(raw), str(raw))
    return mapped if mapped in DEPTH_CHOICES else raw
