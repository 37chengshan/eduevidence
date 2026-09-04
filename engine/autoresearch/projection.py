from __future__ import annotations
from typing import Any
from .gap_priority import rank_gaps
from .saturation import detect_saturation


def research_loop_projection(
    *,
    decision: dict[str, Any] | None,
    gaps: list[dict[str, Any]],
    iterations: list[dict[str, Any]],
    revision: int,
) -> dict[str, Any]:
    """Projection-only state for Research Studio; never mutates canonical state."""
    ranked = [item.as_dict() for item in rank_gaps(gaps, decision=decision)]
    current = iterations[-1] if iterations else None
    saturation = detect_saturation(iterations)
    return {
        "graph_revision": revision,
        "decision": decision or {},
        "gap_priorities": ranked,
        "current_iteration": current,
        "saturation": {
            "saturated": saturation.saturated,
            "low_yield_streak": saturation.low_yield_streak,
            "strategy_diversity_exhausted": saturation.strategy_diversity_exhausted,
            "rationale": list(saturation.rationale),
        },
        "iteration_count": len(iterations),
    }
