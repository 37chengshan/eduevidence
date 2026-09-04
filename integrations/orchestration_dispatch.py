"""TaskSpec-aware dispatch and acceptance adapter for Agent MCP.

Agent MCP remains the only implementation of CLI/model approval and spawn
payload construction. EduEvidence adds two scientific contract gates around
it:

1. every delegated worker must carry a dispatch-ready TaskSpec;
2. every returned worker payload must be reconstructed and validated in the
   main process before any artifact can enter Judge context.

Workers are staging-only. Raw host output is never a Judge input.
"""
from __future__ import annotations

from typing import Any, Callable

from engine.orchestration import ExecutionMode, TaskSpec
from engine.worker_result import (
    ArtifactValidator,
    WorkerResult,
    require_validated_artifacts_for_judge,
    validate_worker_output,
)
from integrations.agent_mcp import safe_spawn


TASKSPEC_REQUIRED = "TASKSPEC_REQUIRED"
TASKSPEC_INVALID = "TASKSPEC_INVALID"
WORKER_OUTPUT_REJECTED = "WORKER_OUTPUT_REJECTED"
HostExecutor = Callable[[dict[str, Any]], dict[str, Any]]


def dispatch_task(
    task: TaskSpec,
    prompt: str,
    approval: dict[str, Any] | None,
    *,
    target_cli: str | None = None,
    model: str | None = None,
    allowed_clis: list[str] | None = None,
    cwd: str = ".",
    permission_mode: str = "plan",
    context_mode: str = "compact",
    summary_chars: int | None = None,
) -> dict[str, Any]:
    """Validate a dispatch-ready TaskSpec, then pass it through safe_spawn()."""
    if not isinstance(task, TaskSpec):
        return {
            "status": TASKSPEC_REQUIRED,
            "spawn_call": None,
            "reason": "subagent dispatch requires a TaskSpec",
        }
    try:
        task.validate_for_dispatch()
    except ValueError as exc:
        return {
            "status": TASKSPEC_INVALID,
            "spawn_call": None,
            "reason": str(exc),
        }
    if task.execution_mode is not ExecutionMode.DELEGATED:
        return {
            "status": TASKSPEC_INVALID,
            "spawn_call": None,
            "reason": "only delegated TaskSpecs may be sent to Agent MCP",
        }

    worker_prompt = f"{task.to_prompt_contract()}\n\nWORKER INSTRUCTIONS:\n{prompt.strip()}"
    result = safe_spawn(
        task.role,
        worker_prompt,
        approval,
        target_cli=target_cli,
        model=model,
        allowed_clis=allowed_clis,
        cwd=cwd,
        permission_mode=permission_mode,
        context_mode=context_mode,
        summary_chars=summary_chars,
        timeout_seconds=task.timeout_seconds,
        token_budget=task.token_budget,
    )
    if result.get("status") == "READY":
        result["task_id"] = task.task_id
        result["run_id"] = task.run_id
        result["base_revision"] = task.base_revision
        result["stage"] = task.stage
        result["evidence_axis"] = task.evidence_axis
        result["allowed_capabilities"] = list(task.allowed_capabilities)
        result["expected_staging_outputs"] = list(task.expected_outputs)
        result["output_contract"] = dict(task.output_contract)
    return result


def accept_worker_output(
    task: TaskSpec,
    raw_output: dict[str, Any],
    *,
    artifact_validator: ArtifactValidator | None = None,
) -> WorkerResult:
    """Main-process acceptance boundary for host/Agent-MCP worker output.

    Worker self-attestation is ignored by `validate_worker_output`. Callers must
    retain the originating TaskSpec and validate against that exact contract.
    """
    return validate_worker_output(
        task,
        raw_output,
        artifact_validator=artifact_validator,
    )


def execute_dispatched_task(
    task: TaskSpec,
    dispatch_result: dict[str, Any],
    host_executor: HostExecutor,
    *,
    artifact_validator: ArtifactValidator | None = None,
) -> WorkerResult:
    """Execute one READY spawn call and immediately pass through acceptance.

    This is the conformant host adapter. It intentionally does not expose a
    helper that returns raw worker artifacts after execution.
    """
    if dispatch_result.get("status") != "READY":
        raise PermissionError("cannot execute a dispatch result that is not READY")
    if dispatch_result.get("task_id") != task.task_id:
        raise ValueError("dispatch result task_id does not match TaskSpec")
    spawn_call = dispatch_result.get("spawn_call")
    if not isinstance(spawn_call, dict):
        raise ValueError("READY dispatch result must contain one spawn_call object")
    raw = host_executor(dict(spawn_call))
    if not isinstance(raw, dict):
        raise ValueError("host executor must return one worker output object")
    return accept_worker_output(
        task,
        raw,
        artifact_validator=artifact_validator,
    )


def judge_artifacts(
    results: list[WorkerResult] | tuple[WorkerResult, ...],
) -> list[dict[str, Any]]:
    """Return Judge inputs only when every worker result passed acceptance."""
    return require_validated_artifacts_for_judge(results)
