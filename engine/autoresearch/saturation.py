from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SaturationResult:
    saturated: bool
    low_yield_streak: int
    strategy_diversity_exhausted: bool
    rationale: tuple[str, ...]


def _is_low_yield(row: dict[str, Any]) -> bool:
    gain = row.get("evidence_gain") or {}
    unique = int(gain.get("unique_eligible_evidence", 0) or 0)
    direct = int(gain.get("direct_outcome_findings", 0) or 0)
    delta = float(gain.get("decision_boundary_delta", 0) or 0)
    duplicate_rate = float(gain.get("duplicate_rate", 0) or 0)
    candidate_sources = row.get("candidate_sources") or []
    no_candidates = len(candidate_sources) == 0
    return (
        unique == 0
        and direct == 0
        and abs(delta) < 1e-12
        and (duplicate_rate >= 0.5 or no_candidates)
    )


def detect_saturation(
    iterations: list[dict[str, Any]],
    *,
    min_consecutive: int = 2,
    available_strategy_types: set[str] | None = None,
) -> SaturationResult:
    """Detect bounded secondary-search saturation.

    Strategy diversity is computed across the full history for the gap, while
    the low-yield condition is intentionally a trailing streak. Empty searches
    count as low-yield even when duplicate_rate is zero; otherwise a provider
    returning no candidates could keep the loop alive forever.
    """
    attempted_all = {
        str((row.get("strategy") or {}).get("experiment_type", ""))
        for row in iterations
        if str((row.get("strategy") or {}).get("experiment_type", ""))
    }
    streak = 0
    for row in reversed(iterations):
        if _is_low_yield(row):
            streak += 1
        else:
            break

    if available_strategy_types:
        diversity_exhausted = available_strategy_types.issubset(attempted_all)
    else:
        diversity_exhausted = len(attempted_all) >= 2

    rationale: list[str] = []
    if streak >= min_consecutive:
        rationale.append(
            f"{streak} consecutive iterations produced no unique/direct evidence or decision-boundary change"
        )
    if diversity_exhausted:
        rationale.append("strategy diversity exhausted for the configured search space")
    return SaturationResult(
        streak >= min_consecutive and diversity_exhausted,
        streak,
        diversity_exhausted,
        tuple(rationale),
    )


def transition_to_empirical(
    *,
    dvi_band: str,
    decision_material: bool,
    unresolved: bool,
    saturation: SaturationResult,
    ethics_feasible: bool,
) -> tuple[bool, tuple[str, ...]]:
    checks = [
        (dvi_band.upper() == "HIGH", "gap DVI is HIGH"),
        (decision_material, "gap is material to the decision"),
        (unresolved, "gap remains unresolved"),
        (saturation.saturated, "secondary search is saturated"),
        (ethics_feasible, "empirical study is ethically/operationally feasible"),
    ]
    reasons = tuple(text for ok, text in checks if ok)
    return all(ok for ok, _ in checks), reasons
