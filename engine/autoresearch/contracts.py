from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResearchExperimentType(str, Enum):
    TARGETED_RETRIEVAL = "TARGETED_RETRIEVAL"
    COUNTER_EVIDENCE_RETRIEVAL = "COUNTER_EVIDENCE_RETRIEVAL"
    APPLICABILITY_RETRIEVAL = "APPLICABILITY_RETRIEVAL"
    TEMPORAL_REFRESH = "TEMPORAL_REFRESH"
    CITATION_CHAINING = "CITATION_CHAINING"
    SCREENING_PRIORITY = "SCREENING_PRIORITY"
    SOURCE_RECOVERY = "SOURCE_RECOVERY"


class IterationStatus(str, Enum):
    COMPLETED_GAIN = "completed_gain"
    COMPLETED_NO_GAIN = "completed_no_gain"
    SEARCH_SATURATED = "search_saturated"
    EMPIRICAL_NEEDED = "empirical_needed"
    BUDGET_EXHAUSTED = "budget_exhausted"
    TOOL_FAILURE = "tool_failure"
    INVALID = "invalid"


@dataclass(frozen=True)
class ResearchBudget:
    max_queries: int = 6
    max_candidates: int = 30
    max_fulltext_fetches: int = 12

    def validate(self) -> None:
        if min(self.max_queries, self.max_candidates, self.max_fulltext_fetches) < 0:
            raise ValueError("research budget values must be non-negative")


@dataclass(frozen=True)
class ResearchStrategy:
    strategy_id: str
    experiment_type: ResearchExperimentType
    hypothesis: str
    expected_gain: str
    budget: ResearchBudget = field(default_factory=ResearchBudget)

    def validate(self) -> None:
        if not self.strategy_id.strip() or not self.hypothesis.strip() or not self.expected_gain.strip():
            raise ValueError("strategy_id, hypothesis and expected_gain are required")
        self.budget.validate()


@dataclass(frozen=True)
class NegativeSearchRecord:
    negative_search_id: str
    research_iteration_id: str
    gap_id: str
    queries: tuple[str, ...]
    providers: tuple[str, ...]
    candidate_count: int
    fetched_count: int
    eligible_count: int
    exclusion_reasons: dict[str, int] = field(default_factory=dict)
    scope: dict[str, Any] = field(default_factory=dict)
    searched_at: str = field(default_factory=utcnow)
    conclusion: str = "no_eligible_evidence_found_within_search_scope"

    def validate(self) -> None:
        if self.eligible_count != 0:
            raise ValueError("NegativeSearchRecord requires eligible_count == 0")
        if min(self.candidate_count, self.fetched_count, self.eligible_count) < 0:
            raise ValueError("counts must be non-negative")
        if self.fetched_count > self.candidate_count:
            raise ValueError("fetched_count cannot exceed candidate_count")
        if self.conclusion != "no_eligible_evidence_found_within_search_scope":
            raise ValueError("negative search conclusion must remain scope-bounded")


@dataclass
class ResearchIteration:
    iteration_id: str
    project_id: str
    base_graph_revision: int
    gap_id: str
    strategy: ResearchStrategy
    execution_plan_id: str | None = None
    search_attempts: list[dict[str, Any]] = field(default_factory=list)
    candidate_sources: list[str] = field(default_factory=list)
    validated_evidence_ids: list[str] = field(default_factory=list)
    negative_search_ids: list[str] = field(default_factory=list)
    evidence_gain: dict[str, Any] = field(default_factory=dict)
    new_graph_revision: int | None = None
    decision_snapshot_id: str | None = None
    status: IterationStatus | None = None
    started_at: str = field(default_factory=utcnow)
    completed_at: str | None = None

    def validate(self) -> None:
        self.strategy.validate()
        if self.base_graph_revision < 0:
            raise ValueError("base_graph_revision must be >= 0")
        if self.new_graph_revision is not None:
            if not self.validated_evidence_ids:
                raise ValueError("no-gain iteration must not create a GraphRevision")
            if self.new_graph_revision <= self.base_graph_revision:
                raise ValueError("new_graph_revision must advance base revision")
        if self.status == IterationStatus.COMPLETED_NO_GAIN and self.new_graph_revision is not None:
            raise ValueError("completed_no_gain cannot create GraphRevision")

    def complete(self, status: IterationStatus) -> None:
        self.status = status
        self.completed_at = utcnow()
        self.validate()

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["strategy"]["experiment_type"] = self.strategy.experiment_type.value
        out["status"] = self.status.value if self.status else None
        return out
