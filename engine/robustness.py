"""engine/robustness.py - leave-one-out sensitivity analysis for v4 meta-analysis.

    leave_one_out     re-run a pooling function k times, each time dropping
                      one study, and compare every result against the
                      full-sample pooled effect.
    robustness_label  robust vs fragile: any leave-one-out iteration whose
                      pooled direction flips, or whose 95% CI crosses zero,
                      marks the synthesis fragile.

Pure stdlib, no third-party dependencies.
"""
from __future__ import annotations

import math
from typing import Any, Callable


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _usable(rows: list[dict]) -> list[dict]:
    return [r for r in rows or []
            if _is_number(r.get("d")) and _is_number(r.get("se")) and r["se"] > 0]


def _direction(d: float) -> int:
    """+1 positive, −1 negative, 0 exactly zero."""
    if d > 0:
        return 1
    if d < 0:
        return -1
    return 0


def _ci_crosses_zero(pooled: dict) -> bool:
    return pooled["ci_low"] <= 0.0 <= pooled["ci_high"]


def leave_one_out(rows: list[dict],
                  pooling_fn: Callable[[list[dict]], dict | None]) -> dict | None:
    """Re-run ``pooling_fn`` on every k−1 subset; compare to the full pooled.

    ``direction_flip`` is True when the dropped study reverses the pooled
    direction (full-sample effect is nonzero and the subset moves to the
    opposite sign); ``ci_crosses_zero`` when the subset CI spans zero;
    ``decision_changed`` = either. Returns None when fewer than two usable
    rows exist.
    """
    usable = _usable(rows)
    k = len(usable)
    if k < 2:
        return None
    full = pooling_fn(usable)
    if full is None:
        return None
    full_dir = _direction(full["d"])
    iterations = []
    for i, removed in enumerate(usable):
        subset = usable[:i] + usable[i + 1:]
        pooled = pooling_fn(subset)
        if pooled is None:
            continue
        direction_flip = (full_dir != 0
                          and _direction(pooled["d"]) != 0
                          and _direction(pooled["d"]) != full_dir)
        ci_crosses_zero = _ci_crosses_zero(pooled)
        iterations.append({
            "removed_study_id": removed.get("study_id"),
            "removed_index": i,
            "pooled": pooled,
            "direction_flip": direction_flip,
            "ci_crosses_zero": ci_crosses_zero,
            "decision_changed": direction_flip or ci_crosses_zero,
        })
    return {
        "method": "leave_one_out",
        "k": k,
        "full_pooled": full,
        "iterations": iterations,
        "n_direction_flips": sum(1 for it in iterations if it["direction_flip"]),
        "n_ci_crossings": sum(1 for it in iterations if it["ci_crosses_zero"]),
        "n_decision_changes": sum(1 for it in iterations if it["decision_changed"]),
    }


def robustness_label(results: dict | None) -> str:
    """robust / fragile classification of a leave-one-out result.

    Fragile when any dropped study flips the pooled direction or makes the
    CI cross zero; otherwise robust. None (no analysis possible) is fragile.
    """
    if results is None:
        return "fragile"
    for it in results.get("iterations", []):
        if it.get("direction_flip") or it.get("ci_crosses_zero"):
            return "fragile"
    return "robust"


def _mean_std(values: list[float]) -> tuple[float, float]:
    """Unused helper kept for parity with the textbook SD definition."""
    if not values:
        return 0.0, 0.0
    m = sum(values) / len(values)
    v = sum((x - m) ** 2 for x in values) / (len(values) - 1) if len(values) > 1 else 0.0
    return m, math.sqrt(v)
