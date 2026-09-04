from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Band(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


_LEVEL = {"low": 1, "medium": 2, "high": 3, "LOW": 1, "MEDIUM": 2, "HIGH": 3}


@dataclass(frozen=True)
class GapPriority:
    gap_id: str
    dvi_band: Band
    cost_band: Band
    decision_material: bool
    drivers: tuple[str, ...]
    next_research_mode: str
    score: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "dvi_band": self.dvi_band.value,
            "cost_band": self.cost_band.value,
            "decision_material": self.decision_material,
            "drivers": list(self.drivers),
            "next_research_mode": self.next_research_mode,
            "score": self.score,
        }


def _v(value: Any, default: int = 2) -> int:
    if isinstance(value, int):
        return max(1, min(3, value))
    return _LEVEL.get(str(value), default)


def _revision_number(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer graph revision")
    try:
        revision = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer graph revision") from exc
    if revision < 0:
        raise ValueError(f"{label} must be >= 0")
    return revision


def _require_revision_bound_decision(
    gap: dict[str, Any], decision: dict[str, Any] | None
) -> None:
    """Fail closed when a DecisionSnapshot and KnowledgeGap are from different revisions.

    DVI may use the current DecisionSnapshot as a decision-sensitivity input. It
    must never combine a stale decision with a newer gap (or vice versa), since
    that could reorder the next research target using an obsolete boundary.
    """
    if not decision:
        return
    if "graph_revision" not in decision:
        raise ValueError(
            "DecisionSnapshot used for DVI must include graph_revision"
        )
    if "derived_from_graph_revision" not in gap:
        raise ValueError(
            f"KnowledgeGap {gap.get('gap_id', '')!r} used for DVI must include "
            "derived_from_graph_revision"
        )
    decision_revision = _revision_number(
        decision.get("graph_revision"), label="DecisionSnapshot.graph_revision"
    )
    gap_revision = _revision_number(
        gap.get("derived_from_graph_revision"),
        label="KnowledgeGap.derived_from_graph_revision",
    )
    if decision_revision != gap_revision:
        raise ValueError(
            "stale DecisionSnapshot for DVI: "
            f"decision revision {decision_revision} != gap revision {gap_revision}"
        )


def _decision_material(gap: dict[str, Any]) -> bool:
    """Return a conservative, separately auditable materiality judgment.

    Materiality is intentionally not derived from the DVI band. An explicit
    boolean on the gap (or extensions.decision_material) wins. Otherwise only
    gap types that can directly block/reverse an education decision are treated
    as material by default.
    """
    explicit = gap.get("decision_material")
    if isinstance(explicit, bool):
        return explicit
    extensions = gap.get("extensions")
    if isinstance(extensions, dict) and isinstance(extensions.get("decision_material"), bool):
        return bool(extensions["decision_material"])
    return str(gap.get("gap_type", "")) in {
        "missing_transfer",
        "missing_retention",
        "unresolved_conflict",
        "weak_causal_identification",
    }


def rank_gap(
    gap: dict[str, Any],
    *,
    decision: dict[str, Any] | None = None,
    expected_evidence_availability: str = "medium",
    research_cost: str = "medium",
    applicability_relevance: str = "medium",
    risk_irreversibility: str = "medium",
) -> GapPriority:
    """Return an explainable ordinal research-priority band.

    This is a conceptual DVI heuristic, not EVPI/EVSI and not a probability.
    Decision materiality is a separate field and must not be inferred from the
    resulting DVI band when deciding whether to bridge to empirical research.
    """
    _require_revision_bound_decision(gap, decision)
    decision = decision or {}
    priority = _v(gap.get("priority", "medium"))
    gap_type = str(gap.get("gap_type", ""))
    material = _decision_material(gap)
    decision_sensitive = 3 if material else priority
    current_uncertainty = 3 if gap_type.startswith("missing_") or gap_type == "unresolved_conflict" else 2
    directness_deficit = 3 if gap_type in {"missing_transfer", "missing_retention", "missing_outcome"} else 2
    applicability = _v(applicability_relevance)
    availability = _v(expected_evidence_availability)
    cost = _v(research_cost)
    risk = _v(risk_irreversibility)
    score = decision_sensitive + current_uncertainty + directness_deficit + applicability + availability + risk - cost
    if decision.get("recommended_action") in {"adopt", "ADOPT"} and gap_type in {"missing_transfer", "missing_retention"}:
        score += 2
    band = Band.HIGH if score >= 13 else Band.MEDIUM if score >= 9 else Band.LOW
    cost_band = Band.HIGH if cost == 3 else Band.MEDIUM if cost == 2 else Band.LOW
    drivers = (
        f"gap_type={gap_type or 'unknown'}",
        f"decision_material={material}",
        f"decision_sensitivity={decision_sensitive}",
        f"current_uncertainty={current_uncertainty}",
        f"directness_deficit={directness_deficit}",
        f"applicability_relevance={applicability}",
        f"expected_evidence_availability={availability}",
        f"risk_irreversibility={risk}",
        f"research_cost={cost}",
    )
    mode = "secondary_evidence_search" if band is not Band.LOW else "defer"
    return GapPriority(
        str(gap.get("gap_id", "")),
        band,
        cost_band,
        material,
        drivers,
        mode,
        score,
    )


def rank_gaps(gaps: list[dict[str, Any]], **kwargs: Any) -> list[GapPriority]:
    return sorted((rank_gap(g, **kwargs) for g in gaps), key=lambda x: (-x.score, x.gap_id))
