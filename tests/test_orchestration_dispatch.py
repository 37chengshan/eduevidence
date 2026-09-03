from __future__ import annotations

from engine.orchestration import ExecutionMode, ExecutionPlanner, TaskSpec
import integrations.orchestration_dispatch as dispatch


def test_dispatch_rejects_non_taskspec():
    result = dispatch.dispatch_task("not-a-task", "x", None)  # type: ignore[arg-type]
    assert result["status"] == dispatch.TASKSPEC_REQUIRED
    assert result["spawn_call"] is None


def test_dispatch_rejects_local_task(monkeypatch):
    called = False

    def fake_safe_spawn(*args, **kwargs):
        nonlocal called
        called = True
        return {"status": "READY", "spawn_call": {}}

    monkeypatch.setattr(dispatch, "safe_spawn", fake_safe_spawn)
    task = TaskSpec(
        task_id="local",
        stage="retrieve",
        role="evidence-retriever",
        objective="local retrieval",
        evidence_axis="direct",
        execution_mode=ExecutionMode.LOCAL,
    )
    result = dispatch.dispatch_task(task, "do work", None)
    assert result["status"] == dispatch.TASKSPEC_INVALID
    assert called is False


def test_dispatch_wraps_prompt_and_preserves_existing_approval_gate(monkeypatch):
    seen = {}

    def fake_safe_spawn(role, prompt, approval, **kwargs):
        seen.update({"role": role, "prompt": prompt, "approval": approval, **kwargs})
        return {"status": "READY", "spawn_call": {"tool": "spawn_agent"}}

    monkeypatch.setattr(dispatch, "safe_spawn", fake_safe_spawn)
    task = ExecutionPlanner().plan("M").delegated_tasks[0]
    approval = {"approved": True}
    result = dispatch.dispatch_task(task, "Search the requested evidence axis.", approval)

    assert result["status"] == "READY"
    assert result["task_id"] == task.task_id
    assert result["stage"] == task.stage
    assert result["evidence_axis"] == task.evidence_axis
    assert seen["role"] == task.role
    assert seen["approval"] is approval
    assert "CANONICAL_STATE_WRITE: FORBIDDEN" in seen["prompt"]
    assert f"EVIDENCE_AXIS: {task.evidence_axis}" in seen["prompt"]
    assert "Search the requested evidence axis." in seen["prompt"]
    assert seen["timeout_seconds"] == task.timeout_seconds


def test_dispatch_rejects_canonical_output_before_safe_spawn(monkeypatch):
    called = False

    def fake_safe_spawn(*args, **kwargs):
        nonlocal called
        called = True
        return {"status": "READY", "spawn_call": {}}

    monkeypatch.setattr(dispatch, "safe_spawn", fake_safe_spawn)
    task = TaskSpec(
        task_id="bad",
        stage="retrieve",
        role="evidence-retriever",
        objective="bad task",
        evidence_axis="direct",
        expected_outputs=("DecisionSnapshot",),
        execution_mode=ExecutionMode.DELEGATED,
    )
    result = dispatch.dispatch_task(task, "x", None)
    assert result["status"] == dispatch.TASKSPEC_INVALID
    assert called is False
