"""TaskSpec-aware dispatch adapter for Agent MCP.

This module is deliberately thin: Agent MCP remains the only implementation
of CLI/model approval and spawn payload construction. EduEvidence adds one
scientific planning gate in front of it: every delegated worker must carry a
validated TaskSpec and may only return staging artifacts.
"""
from __future__ import annotations

from typing import Any

from engine.orchestration import ExecutionMode, TaskSpec
from integrations.agent_mcp import safe_spawn


TASKSPEC_REQUIRED = "TASKSPEC_REQUIRED"
TASKSPEC_INVALID = "TASKSPEC_INVALID"


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
    """Validate a delegated TaskSpec, then pass it through safe_spawn().

    This function does not select a CLI/model and does not weaken the existing
    Agent MCP approval gate. It only binds a scientific task contract to the
    spawn request.
    """
    if not isinstance(task, TaskSpec):
        return {
            "status": TASKSPEC_REQUIRED,
            "spawn_call": None,
            "reason": "subagent dispatch requires a TaskSpec",
        }
    try:
        task.validate()
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
        result["stage"] = task.stage
        result["evidence_axis"] = task.evidence_axis
        result["expected_staging_outputs"] = list(task.expected_outputs)
    return result
