from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from .contracts import (
    IterationStatus,
    ResearchBudget,
    ResearchExperimentType,
    ResearchIteration,
    ResearchStrategy,
)
from .gap_priority import GapPriority, rank_gaps
from .saturation import detect_saturation, transition_to_empirical


@dataclass(frozen=True)
class StepResult:
    iteration: ResearchIteration
    priority: GapPriority
    next_action: str
    rationale: tuple[str, ...]


class EvidenceAutoresearchController:
    """Bounded gap-to-evidence loop with strategy memory."""

    def __init__(self, *, max_iterations: int = 5):
        if not 1 <= max_iterations <= 50:
            raise ValueError("max_iterations must be 1..50")
        self.max_iterations = max_iterations

    def select_gap(self, gaps: list[dict[str, Any]], decision: dict[str, Any] | None = None) -> GapPriority:
        ranked = rank_gaps(
            [
                g for g in gaps
                if str(g.get("status", "open")).lower()
                not in {"resolved", "low_decision_value", "search_saturated", "empirical_needed"}
            ],
            decision=decision,
        )
        if not ranked:
            raise ValueError("no unresolved KnowledgeGap available")
        return ranked[0]

    @staticmethod
    def strategy_types_for(gap: dict[str, Any]) -> tuple[ResearchExperimentType, ...]:
        gap_type = str(gap.get("gap_type", ""))
        if gap_type == "unresolved_conflict":
            return (
                ResearchExperimentType.COUNTER_EVIDENCE_RETRIEVAL,
                ResearchExperimentType.CITATION_CHAINING,
                ResearchExperimentType.TARGETED_RETRIEVAL,
                ResearchExperimentType.TEMPORAL_REFRESH,
            )
        if gap_type in {"population_gap", "context_gap"}:
            return (
                ResearchExperimentType.APPLICABILITY_RETRIEVAL,
                ResearchExperimentType.TARGETED_RETRIEVAL,
                ResearchExperimentType.CITATION_CHAINING,
                ResearchExperimentType.TEMPORAL_REFRESH,
            )
        return (
            ResearchExperimentType.TARGETED_RETRIEVAL,
            ResearchExperimentType.CITATION_CHAINING,
            ResearchExperimentType.TEMPORAL_REFRESH,
            ResearchExperimentType.SOURCE_RECOVERY,
        )

    def build_strategy(
        self,
        priority: GapPriority,
        gap: dict[str, Any],
        history: list[dict[str, Any]] | None = None,
    ) -> ResearchStrategy:
        history = history or []
        attempted = {
            str((row.get("strategy") or {}).get("experiment_type", ""))
            for row in history
            if row.get("gap_id") == priority.gap_id
        }
        choices = self.strategy_types_for(gap)
        experiment_type = next(
            (choice for choice in choices if choice.value not in attempted),
            choices[-1],
        )
        gap_type = str(gap.get("gap_type", ""))
        hypothesis = (
            f"{experiment_type.value} for {gap_type or 'gap'} will find "
            f"decision-relevant evidence that materially improves directness "
            f"or resolves {priority.gap_id}."
        )
        return ResearchStrategy(
            f"STRAT-{priority.gap_id}-{experiment_type.value.lower()}",
            experiment_type,
            hypothesis,
            "decision_relevant_evidence",
            ResearchBudget(),
        )

    def step(
        self,
        *,
        project_id: str,
        base_graph_revision: int,
        gaps: list[dict[str, Any]],
        decision: dict[str, Any] | None,
        history: list[dict[str, Any]],
        executor: Callable[[ResearchStrategy, dict[str, Any]], dict[str, Any]],
        graph_commit: Callable[[list[str]], int | None] | None = None,
        decision_snapshot_id: str | None = None,
        ethics_feasible: bool = False,
    ) -> StepResult:
        priority = self.select_gap(gaps, decision)
        gap = next(g for g in gaps if str(g.get("gap_id")) == priority.gap_id)
        strategy = self.build_strategy(priority, gap, history)
        iteration = ResearchIteration(
            f"RIT-{len(history) + 1:04d}", project_id, base_graph_revision, priority.gap_id, strategy
        )
        outcome = executor(strategy, gap)
        valid = list(dict.fromkeys(outcome.get("validated_evidence_ids") or []))
        iteration.validated_evidence_ids = valid
        iteration.candidate_sources = list(outcome.get("candidate_sources") or [])
        iteration.search_attempts = list(outcome.get("search_attempts") or [])
        iteration.negative_search_ids = list(outcome.get("negative_search_ids") or [])
        iteration.evidence_gain = dict(outcome.get("evidence_gain") or {})

        if valid:
            if graph_commit is None:
                raise ValueError("validated evidence requires single-writer graph_commit callback")
            committed_revision = graph_commit(valid)
            if committed_revision is not None and committed_revision > base_graph_revision:
                iteration.new_graph_revision = committed_revision
                iteration.decision_snapshot_id = decision_snapshot_id
                iteration.complete(IterationStatus.COMPLETED_GAIN)
                return StepResult(
                    iteration,
                    priority,
                    "re_adjudicate",
                    ("validated evidence appended; re-adjudication required before another research iteration",),
                )
            iteration.evidence_gain = {
                **iteration.evidence_gain,
                "duplicate_only": True,
                "unique_eligible_evidence": 0,
            }

        iteration.complete(IterationStatus.COMPLETED_NO_GAIN)
        combined = history + [iteration.as_dict()]
        gap_history = [row for row in combined if row.get("gap_id") == priority.gap_id]
        available = {item.value for item in self.strategy_types_for(gap)}
        saturation = detect_saturation(gap_history, available_strategy_types=available)
        empirical, reasons = transition_to_empirical(
            dvi_band=priority.dvi_band.value,
            decision_material=priority.decision_material,
            unresolved=True,
            saturation=saturation,
            ethics_feasible=ethics_feasible,
        )
        if empirical:
            iteration.status = IterationStatus.EMPIRICAL_NEEDED
            return StepResult(iteration, priority, "empirical_evidence_needed", reasons)
        if saturation.saturated:
            iteration.status = IterationStatus.SEARCH_SATURATED
            return StepResult(iteration, priority, "stop_search_saturated", saturation.rationale)
        return StepResult(
            iteration,
            priority,
            "next_iteration",
            ("no new validated evidence in this bounded iteration",),
        )
