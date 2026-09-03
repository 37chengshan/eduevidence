"""Canonical orchestration primitives for EduEvidence.

This module separates five concepts that were historically easy to conflate:
protocol stage, scientific role, capability, worker/subagent, and model/CLI.
It is intentionally deterministic and dependency-free so Platform Native and
Agent MCP Enhanced modes share the same planning semantics.

Scientific rule: workers may produce staging artifacts, but only the lead
orchestrator/single-writer path may commit canonical project state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class Complexity(str, Enum):
    S = "S"
    M = "M"
    L = "L"


class ExecutionMode(str, Enum):
    LOCAL = "local"
    DELEGATED = "delegated"


CANONICAL_STAGES = (
    "frame",
    "retrieve",
    "extract",
    "challenge",
    "audit",
    "adjudicate",
    "applicability",
    "intervene",
    "evaluate",
)

CANONICAL_STATE_ARTIFACTS = frozenset({
    "EvidenceGraph",
    "GraphRevision",
    "DecisionSnapshot",
    "KnowledgeGap",
    "StudyDesign",
    "PilotRun",
    "AnalysisRun",
})


@dataclass(frozen=True)
class RoleSpec:
    """A scientific responsibility, not an instruction to spawn an agent."""

    name: str
    responsibility: str
    stages: tuple[str, ...]
    capabilities: tuple[str, ...]
    independence_required: bool = False
    critical_path: bool = False

    def __post_init__(self) -> None:
        unknown = set(self.stages) - set(CANONICAL_STAGES)
        if unknown:
            raise ValueError(f"role {self.name!r} references unknown stages: {sorted(unknown)}")


ROLE_REGISTRY: dict[str, RoleSpec] = {
    "education-planner": RoleSpec(
        "education-planner",
        "Own framing completeness, scope, comparison and outcome definition.",
        ("frame",),
        ("research-planning",),
        critical_path=True,
    ),
    "evidence-retriever": RoleSpec(
        "evidence-retriever",
        "Acquire candidate sources and record verifiable provenance without adjudicating them.",
        ("retrieve",),
        ("literature-review", "full-text-fetch", "source-validation"),
    ),
    "evidence-analyst": RoleSpec(
        "evidence-analyst",
        "Extract structured study findings without deciding what the evidence body means.",
        ("extract",),
        ("evidence-extraction",),
    ),
    "skeptic": RoleSpec(
        "skeptic",
        "Own independent counter-evidence and alternative-explanation coverage.",
        ("challenge",),
        ("contradiction-analysis", "counter-retrieval"),
        independence_required=True,
        critical_path=True,
    ),
    "method-reviewer": RoleSpec(
        "method-reviewer",
        "Own study-level methodology appraisal and evidence-quality limitations.",
        ("audit",),
        ("methodology-audit",),
        independence_required=True,
        critical_path=True,
    ),
    "evidence-judge": RoleSpec(
        "evidence-judge",
        "Own the bounded decision after evidence, challenge and audit gates pass.",
        ("adjudicate", "applicability"),
        ("evidence-review", "decision-adjudication", "applicability"),
        critical_path=True,
    ),
    "intervention-designer": RoleSpec(
        "intervention-designer",
        "Turn a grounded decision and KnowledgeGap into a bounded intervention or pilot.",
        ("intervene",),
        ("study-design", "intervention-design"),
    ),
    "evaluation-designer": RoleSpec(
        "evaluation-designer",
        "Define estimable evaluation, retention/transfer measurement and update logic.",
        ("evaluate",),
        ("evaluation-design", "data-analysis"),
    ),
}


@dataclass(frozen=True)
class TaskSpec:
    """One bounded unit of work that may be executed locally or delegated.

    A TaskSpec is required for delegation. It states the scientific role,
    evidence axis, inputs, expected staging outputs and budget. Delegated tasks
    are read-only with respect to canonical project state.
    """

    task_id: str
    stage: str
    role: str
    objective: str
    evidence_axis: str
    inputs: tuple[str, ...] = ()
    expected_outputs: tuple[str, ...] = ()
    execution_mode: ExecutionMode = ExecutionMode.LOCAL
    independent: bool = False
    read_only: bool = True
    timeout_seconds: int = 1800
    token_budget: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must be non-empty")
        if self.stage not in CANONICAL_STAGES:
            raise ValueError(f"unknown protocol stage: {self.stage!r}")
        spec = ROLE_REGISTRY.get(self.role)
        if spec is None:
            raise ValueError(f"unknown scientific role: {self.role!r}")
        if self.stage not in spec.stages:
            raise ValueError(
                f"role {self.role!r} does not own stage {self.stage!r}; owns {spec.stages}"
            )
        if not self.objective.strip():
            raise ValueError("objective must be non-empty")
        if not self.evidence_axis.strip():
            raise ValueError("evidence_axis must be non-empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.token_budget is not None and self.token_budget <= 0:
            raise ValueError("token_budget must be positive when provided")
        if self.execution_mode is ExecutionMode.DELEGATED and not self.read_only:
            raise ValueError("delegated workers must be read-only against canonical state")
        if spec.independence_required and self.execution_mode is ExecutionMode.DELEGATED:
            if not self.independent:
                raise ValueError(f"role {self.role!r} requires independent delegated execution")
        forbidden = CANONICAL_STATE_ARTIFACTS.intersection(self.expected_outputs)
        if self.execution_mode is ExecutionMode.DELEGATED and forbidden:
            raise ValueError(
                "delegated workers may only return staging artifacts; canonical outputs forbidden: "
                f"{sorted(forbidden)}"
            )

    def to_prompt_contract(self) -> str:
        """Produce a stable task envelope for a worker prompt."""
        self.validate()
        return (
            f"TASK_ID: {self.task_id}\n"
            f"STAGE: {self.stage}\n"
            f"SCIENTIFIC_ROLE: {self.role}\n"
            f"EVIDENCE_AXIS: {self.evidence_axis}\n"
            f"OBJECTIVE: {self.objective}\n"
            f"INPUTS: {', '.join(self.inputs) if self.inputs else 'none'}\n"
            f"EXPECTED_STAGING_OUTPUTS: "
            f"{', '.join(self.expected_outputs) if self.expected_outputs else 'none'}\n"
            "CANONICAL_STATE_WRITE: FORBIDDEN\n"
            "Return only the requested staging artifact(s)."
        )


@dataclass(frozen=True)
class ExecutionPlan:
    complexity: Complexity
    tasks: tuple[TaskSpec, ...]
    max_parallel_workers: int

    @property
    def delegated_tasks(self) -> tuple[TaskSpec, ...]:
        return tuple(t for t in self.tasks if t.execution_mode is ExecutionMode.DELEGATED)

    def validate(self) -> None:
        if self.max_parallel_workers < 0:
            raise ValueError("max_parallel_workers cannot be negative")
        ids: set[str] = set()
        for task in self.tasks:
            task.validate()
            if task.task_id in ids:
                raise ValueError(f"duplicate task id: {task.task_id}")
            ids.add(task.task_id)
        if len(self.delegated_tasks) > 0 and self.max_parallel_workers < 1:
            raise ValueError("delegated plan requires max_parallel_workers >= 1")
        if self.max_parallel_workers > 6:
            raise ValueError("bounded worker pool exceeds hard limit of 6")


class ExecutionPlanner:
    """Deterministic planner for whether scientific duties need subagents.

    It never chooses a concrete model or CLI. Agent MCP handles that later,
    after user approval. The planner only decides local vs delegated work and
    the evidence axes that should remain independent.
    """

    def plan(self, complexity: str | Complexity) -> ExecutionPlan:
        level = complexity if isinstance(complexity, Complexity) else Complexity(complexity.upper())
        if level is Complexity.S:
            plan = ExecutionPlan(level, self._serial_tasks(), max_parallel_workers=0)
        elif level is Complexity.M:
            plan = ExecutionPlan(level, self._medium_tasks(), max_parallel_workers=3)
        else:
            plan = ExecutionPlan(level, self._deep_tasks(), max_parallel_workers=4)
        plan.validate()
        return plan

    @staticmethod
    def _base(task_id: str, stage: str, role: str, objective: str, axis: str,
              *, delegated: bool = False, independent: bool = False,
              outputs: Iterable[str] = ()) -> TaskSpec:
        return TaskSpec(
            task_id=task_id,
            stage=stage,
            role=role,
            objective=objective,
            evidence_axis=axis,
            expected_outputs=tuple(outputs),
            execution_mode=ExecutionMode.DELEGATED if delegated else ExecutionMode.LOCAL,
            independent=independent,
            read_only=True,
        )

    def _serial_tasks(self) -> tuple[TaskSpec, ...]:
        return (
            self._base("frame", "frame", "education-planner", "Structure the research question.", "frame"),
            self._base("retrieve", "retrieve", "evidence-retriever", "Acquire bounded evidence.", "direct+counter"),
            self._base("extract", "extract", "evidence-analyst", "Extract structured findings.", "all-eligible"),
            self._base("challenge", "challenge", "skeptic", "Challenge the provisional interpretation.", "counter-evidence"),
            self._base("audit", "audit", "method-reviewer", "Audit methodology and outcome validity.", "methodology"),
            self._base("judge", "adjudicate", "evidence-judge", "Emit an evidence-bounded decision.", "decision"),
        )

    def _medium_tasks(self) -> tuple[TaskSpec, ...]:
        return (
            self._base("frame", "frame", "education-planner", "Structure the research question.", "frame"),
            self._base("retrieve-direct", "retrieve", "evidence-retriever", "Retrieve direct decision-relevant evidence.", "direct-causal", delegated=True, outputs=("SourceCandidates",)),
            self._base("retrieve-counter", "retrieve", "evidence-retriever", "Retrieve null, negative and contradictory evidence.", "counter-risk", delegated=True, outputs=("SourceCandidates",)),
            self._base("extract", "extract", "evidence-analyst", "Merge validated sources and extract findings.", "all-eligible"),
            self._base("challenge", "challenge", "skeptic", "Independently test the provisional interpretation.", "counter-evidence", delegated=True, independent=True, outputs=("SkepticFindings",)),
            self._base("audit", "audit", "method-reviewer", "Audit methodology and construct validity.", "methodology"),
            self._base("judge", "adjudicate", "evidence-judge", "Emit an evidence-bounded decision.", "decision"),
        )

    def _deep_tasks(self) -> tuple[TaskSpec, ...]:
        return (
            self._base("frame", "frame", "education-planner", "Structure the research question.", "frame"),
            self._base("retrieve-direct", "retrieve", "evidence-retriever", "Retrieve direct causal evidence.", "direct-causal", delegated=True, outputs=("SourceCandidates",)),
            self._base("retrieve-transfer", "retrieve", "evidence-retriever", "Retrieve retention and independent-transfer evidence.", "transfer-retention", delegated=True, outputs=("SourceCandidates",)),
            self._base("retrieve-counter", "retrieve", "evidence-retriever", "Retrieve null, negative, risk and contradiction evidence.", "counter-risk", delegated=True, outputs=("SourceCandidates",)),
            self._base("retrieve-applicability", "retrieve", "evidence-retriever", "Retrieve subgroup, context and freshness evidence.", "applicability-freshness", delegated=True, outputs=("SourceCandidates",)),
            self._base("extract", "extract", "evidence-analyst", "Deterministically merge and extract validated findings.", "all-eligible"),
            self._base("challenge", "challenge", "skeptic", "Independently challenge the merged interpretation.", "counter-evidence", delegated=True, independent=True, outputs=("SkepticFindings",)),
            self._base("audit", "audit", "method-reviewer", "Independently audit methodology and outcome validity.", "methodology", delegated=True, independent=True, outputs=("MethodologyAudit",)),
            self._base("judge", "adjudicate", "evidence-judge", "Emit an evidence-bounded decision after all gates.", "decision"),
        )


class CanonicalWriteGuard:
    """Fail-closed single-writer authority for canonical state mutations."""

    def __init__(self, writer_id: str = "lead-orchestrator") -> None:
        if not writer_id.strip():
            raise ValueError("writer_id must be non-empty")
        self.writer_id = writer_id

    def require(self, actor_id: str, artifact_type: str) -> None:
        if artifact_type not in CANONICAL_STATE_ARTIFACTS:
            return
        if actor_id != self.writer_id:
            raise PermissionError(
                f"canonical state {artifact_type} may only be written by {self.writer_id!r}; "
                f"actor {actor_id!r} is staging-only"
            )
