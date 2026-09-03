from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SaturationResult:
    saturated: bool
    low_yield_streak: int
    strategy_diversity_exhausted: bool
    rationale: tuple[str, ...]


def detect_saturation(
    iterations: list[dict[str, Any]],
    *,
    min_consecutive: int = 2,
    available_strategy_types: set[str] | None = None,
) -> SaturationResult:
    streak = 0
    rationale: list[str] = []
    attempted: set[str] = set()
    for row in reversed(iterations):
        strat = row.get("strategy", {})
        attempted.add(str(strat.get("experiment_type", "")))
        gain = row.get("evidence_gain") or {}
        unique = int(gain.get("unique_eligible_evidence", 0) or 0)
        direct = int(gain.get("direct_outcome_findings", 0) or 0)
        delta = float(gain.get("decision_boundary_delta", 0) or 0)
        duplicate_rate = float(gain.get("duplicate_rate", 0) or 0)
        low = unique == 0 and direct == 0 and abs(delta) < 1e-12 and duplicate_rate >= 0.5
        if low:
            streak += 1
        else:
            break
    if available_strategy_types:
        diversity_exhausted = available_strategy_types.issubset(attempted)
    else:
        diversity_exhausted = len({x for x in attempted if x}) >= 2
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
    reasons: list[str] = []
    checks = [
        (dvi_band.upper() == "HIGH", "gap DVI is HIGH"),
        (decision_material, "gap is material to the decision"),
        (unresolved, "gap remains unresolved"),
        (saturation.saturated, "secondary search is saturated"),
        (ethics_feasible, "empirical study is ethically/operationally feasible"),
    ]
    for ok, text in checks:
        if ok:
            reasons.append(text)
    return all(ok for ok, _ in checks), tuple(reasons)
