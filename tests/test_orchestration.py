from __future__ import annotations

import pytest

from engine.orchestration import (
    CANONICAL_STATE_ARTIFACTS,
    CanonicalWriteGuard,
    Complexity,
    ExecutionMode,
    ExecutionPlanner,
    ROLE_REGISTRY,
    TaskSpec,
)


def test_role_registry_is_scientific_responsibility_not_runtime_mapping():
    assert set(ROLE_REGISTRY) == {
        "education-planner",
        "evidence-retriever",
        "evidence-analyst",
        "skeptic",
        "method-reviewer",
        "evidence-judge",
        "intervention-designer",
        "evaluation-designer",
    }
    assert ROLE_REGISTRY["skeptic"].independence_required is True
    assert ROLE_REGISTRY["method-reviewer"].independence_required is True
    assert "counter-retrieval" in ROLE_REGISTRY["skeptic"].capabilities


def test_s_plan_is_serial_and_spawns_nothing():
    plan = ExecutionPlanner().plan("S")
    assert plan.complexity is Complexity.S
    assert plan.max_parallel_workers == 0
    assert plan.delegated_tasks == ()


def test_m_plan_delegates_bounded_independent_work():
    plan = ExecutionPlanner().plan("M")
    delegated = plan.delegated_tasks
    assert plan.max_parallel_workers == 3
    assert {t.task_id for t in delegated} == {
        "retrieve-direct",
        "retrieve-counter",
        "challenge",
    }
    skeptic = next(t for t in delegated if t.role == "skeptic")
    assert skeptic.independent is True
    assert skeptic.read_only is True


def test_l_plan_parallelizes_by_evidence_axis_not_provider():
    plan = ExecutionPlanner().plan("L")
    retrieval_axes = {
        t.evidence_axis
        for t in plan.delegated_tasks
        if t.role == "evidence-retriever"
    }
    assert retrieval_axes == {
        "direct-causal",
        "transfer-retention",
        "counter-risk",
        "applicability-freshness",
    }
    assert plan.max_parallel_workers == 4
    assert plan.max_parallel_workers <= 6


def test_delegated_task_cannot_claim_canonical_state_output():
    task = TaskSpec(
        task_id="bad",
        stage="retrieve",
        role="evidence-retriever",
        objective="Try to write graph state.",
        evidence_axis="direct",
        expected_outputs=("GraphRevision",),
        execution_mode=ExecutionMode.DELEGATED,
    )
    with pytest.raises(ValueError, match="canonical outputs forbidden"):
        task.validate()


def test_independent_role_requires_independent_delegated_execution():
    task = TaskSpec(
        task_id="skeptic-bad",
        stage="challenge",
        role="skeptic",
        objective="Challenge the claim.",
        evidence_axis="counter",
        expected_outputs=("SkepticFindings",),
        execution_mode=ExecutionMode.DELEGATED,
        independent=False,
    )
    with pytest.raises(ValueError, match="requires independent"):
        task.validate()


def test_prompt_contract_explicitly_forbids_canonical_writes():
    task = ExecutionPlanner().plan("M").delegated_tasks[0]
    prompt = task.to_prompt_contract()
    assert "CANONICAL_STATE_WRITE: FORBIDDEN" in prompt
    assert f"SCIENTIFIC_ROLE: {task.role}" in prompt
    assert f"EVIDENCE_AXIS: {task.evidence_axis}" in prompt


def test_single_writer_guard_allows_staging_but_blocks_canonical_mutation():
    guard = CanonicalWriteGuard("lead")
    guard.require("worker-1", "SourceCandidates")
    for artifact in CANONICAL_STATE_ARTIFACTS:
        with pytest.raises(PermissionError):
            guard.require("worker-1", artifact)
        guard.require("lead", artifact)
