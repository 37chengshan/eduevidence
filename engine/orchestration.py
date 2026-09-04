"""Canonical orchestration primitives for EduEvidence.

Protocol stage, scientific role, capability, worker/subagent, and model/CLI are
separate concepts. A RoleSpec describes scientific responsibility; a TaskSpec
is one bounded execution contract; an ExecutionPlan states sequencing and
parallel groups. Runtime model/CLI selection remains an adapter concern.

Scientific rule: workers produce staging artifacts only. Canonical project
state is committed by the single-writer lead path after validation.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable


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

DEFAULT_FORBIDDEN_WORKER_ACTIONS = (
    "canonical_state_write",
    "decision_promotion",
    "recursive_worker_spawn",
    "evaluator_mutation",
)


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
    """One bounded scientific task; delegation requires full runtime context."""

    task_id: str
    stage: str
    role: str
    objective: str
    evidence_axis: str
    run_id: str | None = None
    base_revision: int | None = None
    role_profile: str | None = None
    reason_for_delegation: str | None = None
    inputs: tuple[str, ...] = ()  # legacy alias kept during migration
    input_artifacts: tuple[str, ...] = ()
    allowed_capabilities: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = DEFAULT_FORBIDDEN_WORKER_ACTIONS
    scope: dict[str, Any] = field(default_factory=dict)
    budget: dict[str, Any] = field(default_factory=dict)
    expected_outputs: tuple[str, ...] = ()
    output_contract: dict[str, Any] = field(default_factory=dict)
    termination: dict[str, Any] = field(default_factory=dict)
    execution_mode: ExecutionMode = ExecutionMode.LOCAL
    independent: bool = False
    read_only: bool = True
    timeout_seconds: int = 1800
    token_budget: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

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
        if self.role_profile not in (None, self.role):
            raise ValueError("role_profile must identify the same scientific role")
        if not self.objective.strip():
            raise ValueError("objective must be non-empty")
        if not self.evidence_axis.strip():
            raise ValueError("evidence_axis must be non-empty")
        if self.base_revision is not None and self.base_revision < 0:
            raise ValueError("base_revision must be >= 0")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.token_budget is not None and self.token_budget <= 0:
            raise ValueError("token_budget must be positive when provided")
        unknown_caps = set(self.allowed_capabilities) - set(spec.capabilities)
        if unknown_caps:
            raise ValueError(
                f"task grants capabilities outside role {self.role!r}: {sorted(unknown_caps)}"
            )
        forbidden = CANONICAL_STATE_ARTIFACTS.intersection(self.expected_outputs)
        if self.execution_mode is ExecutionMode.DELEGATED:
            if not self.read_only:
                raise ValueError("delegated workers must be read-only against canonical state")
            if forbidden:
                raise ValueError(
                    "delegated workers may only return staging artifacts; canonical outputs forbidden: "
                    f"{sorted(forbidden)}"
                )
            if "canonical_state_write" not in self.forbidden_actions:
                raise ValueError("delegated TaskSpec must explicitly forbid canonical_state_write")
            if spec.independence_required and not self.independent:
                raise ValueError(f"role {self.role!r} requires independent delegated execution")

    def validate_for_dispatch(self) -> None:
        self.validate()
        if self.execution_mode is not ExecutionMode.DELEGATED:
            raise ValueError("only delegated TaskSpecs may be dispatched")
        if not self.run_id or not self.run_id.strip():
            raise ValueError("delegated TaskSpec requires run_id")
        if self.base_revision is None:
            raise ValueError("delegated TaskSpec requires base_revision")
        if not self.reason_for_delegation or not self.reason_for_delegation.strip():
            raise ValueError("delegated TaskSpec requires reason_for_delegation")
        if not self.allowed_capabilities:
            raise ValueError("delegated TaskSpec requires explicit allowed_capabilities")
        if not self.output_contract:
            raise ValueError("delegated TaskSpec requires output_contract")
        if not self.termination:
            raise ValueError("delegated TaskSpec requires termination contract")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["execution_mode"] = self.execution_mode.value
        return value

    def to_prompt_contract(self) -> str:
        """Produce a stable, explicit worker envelope."""
        self.validate_for_dispatch()
        return (
            f"TASK_ID: {self.task_id}\n"
            f"RUN_ID: {self.run_id}\n"
            f"BASE_GRAPH_REVISION: {self.base_revision}\n"
            f"STAGE: {self.stage}\n"
            f"SCIENTIFIC_ROLE: {self.role}\n"
            f"EVIDENCE_AXIS: {self.evidence_axis}\n"
            f"OBJECTIVE: {self.objective}\n"
            f"REASON_FOR_DELEGATION: {self.reason_for_delegation}\n"
            f"ALLOWED_CAPABILITIES: {', '.join(self.allowed_capabilities)}\n"
            f"FORBIDDEN_ACTIONS: {', '.join(self.forbidden_actions)}\n"
            f"INPUT_ARTIFACTS: {', '.join(self.input_artifacts or self.inputs) if (self.input_artifacts or self.inputs) else 'none'}\n"
            f"SCOPE_JSON: {json.dumps(self.scope, ensure_ascii=False, sort_keys=True)}\n"
            f"BUDGET_JSON: {json.dumps(self.budget, ensure_ascii=False, sort_keys=True)}\n"
            f"OUTPUT_CONTRACT_JSON: {json.dumps(self.output_contract, ensure_ascii=False, sort_keys=True)}\n"
            f"TERMINATION_JSON: {json.dumps(self.termination, ensure_ascii=False, sort_keys=True)}\n"
            "CANONICAL_STATE_WRITE: FORBIDDEN\n"
            "Return only the requested staging artifact(s)."
        )


@dataclass(frozen=True)
class ExecutionPlan:
    complexity: Complexity
    tasks: tuple[TaskSpec, ...]
    max_parallel_workers: int
    parallel_groups: tuple[tuple[str, ...], ...] = ()
    plan_id: str | None = None

    @property
    def delegated_tasks(self) -> tuple[TaskSpec, ...]:
        return tuple(t for t in self.tasks if t.execution_mode is ExecutionMode.DELEGATED)

    def validate(self) -> None:
        if self.max_parallel_workers < 0:
            raise ValueError("max_parallel_workers cannot be negative")
        if self.max_parallel_workers > 6:
            raise ValueError("bounded worker pool exceeds hard limit of 6")
        ids: set[str] = set()
        by_id: dict[str, TaskSpec] = {}
        for task in self.tasks:
            task.validate()
            if task.task_id in ids:
                raise ValueError(f"duplicate task id: {task.task_id}")
            ids.add(task.task_id)
            by_id[task.task_id] = task
        if self.delegated_tasks and self.max_parallel_workers < 1:
            raise ValueError("delegated plan requires max_parallel_workers >= 1")

        grouped: list[str] = []
        for group in self.parallel_groups:
            if not group:
                raise ValueError("parallel groups may not be empty")
            if len(group) > self.max_parallel_workers:
                raise ValueError("parallel group exceeds max_parallel_workers")
            for task_id in group:
                task = by_id.get(task_id)
                if task is None:
                    raise ValueError(f"parallel group references unknown task {task_id}")
                if task.execution_mode is not ExecutionMode.DELEGATED:
                    raise ValueError(f"parallel group may contain delegated tasks only: {task_id}")
                grouped.append(task_id)
        delegated_ids = [task.task_id for task in self.delegated_tasks]
        if sorted(grouped) != sorted(delegated_ids):
            raise ValueError("every delegated task must appear exactly once in parallel_groups")

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "complexity": self.complexity.value,
            "tasks": [task.to_dict() for task in self.tasks],
            "max_parallel_workers": self.max_parallel_workers,
            "parallel_groups": [list(group) for group in self.parallel_groups],
        }


class ExecutionPlanner:
    """Deterministic policy planner; it never chooses a concrete model/CLI."""

    def plan(
        self,
        complexity: str | Complexity,
        *,
        run_id: str | None = None,
        base_revision: int | None = None,
        plan_id: str | None = None,
    ) -> ExecutionPlan:
        level = complexity if isinstance(complexity, Complexity) else Complexity(complexity.upper())
        if level is Complexity.S:
            plan = ExecutionPlan(
                level,
                self._serial_tasks(run_id, base_revision),
                max_parallel_workers=0,
                parallel_groups=(),
                plan_id=plan_id,
            )
        elif level is Complexity.M:
            tasks = self._medium_tasks(run_id, base_revision)
            plan = ExecutionPlan(
                level,
                tasks,
                max_parallel_workers=2,
                parallel_groups=(("retrieve-direct", "retrieve-counter"), ("challenge",)),
                plan_id=plan_id,
            )
        else:
            tasks = self._deep_tasks(run_id, base_revision)
            plan = ExecutionPlan(
                level,
                tasks,
                max_parallel_workers=4,
                parallel_groups=(
                    (
                        "retrieve-direct",
                        "retrieve-transfer",
                        "retrieve-counter",
                        "retrieve-applicability",
                    ),
                    ("challenge", "audit"),
                ),
                plan_id=plan_id,
            )
        plan.validate()
        return plan

    @staticmethod
    def _base(
        task_id: str,
        stage: str,
        role: str,
        objective: str,
        axis: str,
        *,
        run_id: str | None,
        base_revision: int | None,
        delegated: bool = False,
        independent: bool = False,
        outputs: Iterable[str] = (),
    ) -> TaskSpec:
        role_spec = ROLE_REGISTRY[role]
        timeout_seconds = 1800
        token_budget = None
        outputs = tuple(outputs)
        return TaskSpec(
            task_id=task_id,
            stage=stage,
            role=role,
            role_profile=role,
            objective=objective,
            evidence_axis=axis,
            run_id=run_id,
            base_revision=base_revision,
            reason_for_delegation=(
                f"independent bounded {axis} work benefits from delegated context"
                if delegated
                else None
            ),
            allowed_capabilities=role_spec.capabilities,
            forbidden_actions=DEFAULT_FORBIDDEN_WORKER_ACTIONS,
            scope={"evidence_axis": axis},
            budget={"timeout_seconds": timeout_seconds, "token_budget": token_budget},
            expected_outputs=outputs,
            output_contract={
                "artifact_types": list(outputs),
                "canonical_state": False,
                "validation_owner": "lead-orchestrator",
            },
            termination={
                "max_seconds": timeout_seconds,
                "conditions": ["output_contract_satisfied", "budget_exhausted", "tool_failure"],
            },
            execution_mode=ExecutionMode.DELEGATED if delegated else ExecutionMode.LOCAL,
            independent=independent,
            read_only=True,
            timeout_seconds=timeout_seconds,
            token_budget=token_budget,
        )

    def _serial_tasks(self, run_id, base_revision) -> tuple[TaskSpec, ...]:
        return (
            self._base("frame", "frame", "education-planner", "Structure the research question.", "frame", run_id=run_id, base_revision=base_revision),
            self._base("retrieve", "retrieve", "evidence-retriever", "Acquire bounded evidence.", "direct+counter", run_id=run_id, base_revision=base_revision),
            self._base("extract", "extract", "evidence-analyst", "Extract structured findings.", "all-eligible", run_id=run_id, base_revision=base_revision),
            self._base("challenge", "challenge", "skeptic", "Challenge the provisional interpretation.", "counter-evidence", run_id=run_id, base_revision=base_revision),
            self._base("audit", "audit", "method-reviewer", "Audit methodology and outcome validity.", "methodology", run_id=run_id, base_revision=base_revision),
            self._base("judge", "adjudicate", "evidence-judge", "Emit an evidence-bounded decision.", "decision", run_id=run_id, base_revision=base_revision),
        )

    def _medium_tasks(self, run_id, base_revision) -> tuple[TaskSpec, ...]:
        return (
            self._base("frame", "frame", "education-planner", "Structure the research question.", "frame", run_id=run_id, base_revision=base_revision),
            self._base("retrieve-direct", "retrieve", "evidence-retriever", "Retrieve direct decision-relevant evidence.", "direct-causal", run_id=run_id, base_revision=base_revision, delegated=True, outputs=("SourceCandidates",)),
            self._base("retrieve-counter", "retrieve", "evidence-retriever", "Retrieve null, negative and contradictory evidence.", "counter-risk", run_id=run_id, base_revision=base_revision, delegated=True, outputs=("SourceCandidates",)),
            self._base("extract", "extract", "evidence-analyst", "Merge validated sources and extract findings.", "all-eligible", run_id=run_id, base_revision=base_revision),
            self._base("challenge", "challenge", "skeptic", "Independently test the provisional interpretation.", "counter-evidence", run_id=run_id, base_revision=base_revision, delegated=True, independent=True, outputs=("SkepticFindings",)),
            self._base("audit", "audit", "method-reviewer", "Audit methodology and construct validity.", "methodology", run_id=run_id, base_revision=base_revision),
            self._base("judge", "adjudicate", "evidence-judge", "Emit an evidence-bounded decision.", "decision", run_id=run_id, base_revision=base_revision),
        )

    def _deep_tasks(self, run_id, base_revision) -> tuple[TaskSpec, ...]:
        return (
            self._base("frame", "frame", "education-planner", "Structure the research question.", "frame", run_id=run_id, base_revision=base_revision),
            self._base("retrieve-direct", "retrieve", "evidence-retriever", "Retrieve direct causal evidence.", "direct-causal", run_id=run_id, base_revision=base_revision, delegated=True, outputs=("SourceCandidates",)),
            self._base("retrieve-transfer", "retrieve", "evidence-retriever", "Retrieve retention and independent-transfer evidence.", "transfer-retention", run_id=run_id, base_revision=base_revision, delegated=True, outputs=("SourceCandidates",)),
            self._base("retrieve-counter", "retrieve", "evidence-retriever", "Retrieve null, negative, risk and contradiction evidence.", "counter-risk", run_id=run_id, base_revision=base_revision, delegated=True, outputs=("SourceCandidates",)),
            self._base("retrieve-applicability", "retrieve", "evidence-retriever", "Retrieve subgroup, context and freshness evidence.", "applicability-freshness", run_id=run_id, base_revision=base_revision, delegated=True, outputs=("SourceCandidates",)),
            self._base("extract", "extract", "evidence-analyst", "Deterministically merge and extract validated findings.", "all-eligible", run_id=run_id, base_revision=base_revision),
            self._base("challenge", "challenge", "skeptic", "Independently challenge the merged interpretation.", "counter-evidence", run_id=run_id, base_revision=base_revision, delegated=True, independent=True, outputs=("SkepticFindings",)),
            self._base("audit", "audit", "method-reviewer", "Independently audit methodology and outcome validity.", "methodology", run_id=run_id, base_revision=base_revision, delegated=True, independent=True, outputs=("MethodologyAudit",)),
            self._base("judge", "adjudicate", "evidence-judge", "Emit an evidence-bounded decision after all gates.", "decision", run_id=run_id, base_revision=base_revision),
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
