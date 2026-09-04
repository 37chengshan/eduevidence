"""TaskSpec-aware dispatch adapter for Agent MCP.

Agent MCP remains the only implementation of CLI/model approval and spawn
payload construction. EduEvidence adds a scientific contract gate in front of
it: every delegated worker must carry run/revision context, explicit
capabilities, forbidden actions, scope/budget/output/termination contracts, and
may return staging artifacts only.
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
