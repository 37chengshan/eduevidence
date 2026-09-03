from __future__ import annotations
from typing import Any
from .core import PlateauTracker


def skill_evolution_projection(
    *,
    baseline: dict[str, Any] | None,
    best: dict[str, Any] | None,
    experiments: list[dict[str, Any]],
    protected_integrity: bool = True,
) -> dict[str, Any]:
    """Projection-only developer state; never mutates repository or user projects."""
    statuses = [str(item.get("status", "")) for item in experiments]
    return {
        "baseline": baseline,
        "best": best,
        "experiments": experiments,
        "experiment_count": len(experiments),
        "plateau": PlateauTracker().plateau(statuses),
        "protected_integrity": protected_integrity,
        "promotion": "branch_only",
    }
