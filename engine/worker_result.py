"""Validation boundary between delegated workers and canonical reasoning.

A worker may return candidate staging artifacts and prose, but it cannot mark
its own output trustworthy. The lead/main process reconstructs WorkerResult,
checks it against the originating TaskSpec and artifact validators, and only
then may validated artifacts enter a Judge context.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from engine.orchestration import CANONICAL_STATE_ARTIFACTS, TaskSpec


ArtifactValidator = Callable[[dict[str, Any]], list[str]]


@dataclass(frozen=True)
class WorkerResult:
    task_id: str
    status: str
    staging_artifacts: tuple[dict[str, Any], ...]
    validated: bool
    validation_issues: tuple[str, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "staging_artifacts": [dict(item) for item in self.staging_artifacts],
            "validated": self.validated,
            "validation_issues": list(self.validation_issues),
            "metrics": dict(self.metrics),
            "summary": self.summary,
        }


def validate_worker_output(
    task: TaskSpec,
    raw: dict[str, Any],
    *,
    artifact_validator: ArtifactValidator | None = None,
) -> WorkerResult:
    """Validate untrusted worker output in the lead process.

    Any worker-supplied `validated` field is deliberately ignored.
    """
    task.validate_for_dispatch()
    issues: list[str] = []
    if not isinstance(raw, dict):
        raise ValueError("worker output must be an object")
    if raw.get("task_id") != task.task_id:
        issues.append("task_id mismatch")
    status = str(raw.get("status", "failed"))
    if status not in {"completed", "failed", "blocked"}:
        issues.append(f"invalid worker status: {status}")
        status = "failed"
    artifacts = raw.get("staging_artifacts", [])
    if not isinstance(artifacts, list) or any(not isinstance(item, dict) for item in artifacts):
        issues.append("staging_artifacts must be a list of objects")
        artifacts = []

    expected = set(task.expected_outputs)
    for index, artifact in enumerate(artifacts):
        artifact_type = str(artifact.get("artifact_type", ""))
        if not artifact_type:
            issues.append(f"artifact[{index}] missing artifact_type")
            continue
        if artifact_type in CANONICAL_STATE_ARTIFACTS:
            issues.append(f"artifact[{index}] attempts canonical output {artifact_type}")
        if expected and artifact_type not in expected:
            issues.append(
                f"artifact[{index}] type {artifact_type} not allowed by TaskSpec output contract"
            )
        if artifact_validator is not None:
            issues.extend(
                f"artifact[{index}]: {problem}"
                for problem in artifact_validator(artifact)
            )

    validated = status == "completed" and not issues
    return WorkerResult(
        task_id=task.task_id,
        status=status,
        staging_artifacts=tuple(dict(item) for item in artifacts),
        validated=validated,
        validation_issues=tuple(issues),
        metrics=dict(raw.get("metrics") or {}),
        summary=str(raw.get("summary", "")),
    )


def require_validated_artifacts_for_judge(
    results: list[WorkerResult] | tuple[WorkerResult, ...],
) -> list[dict[str, Any]]:
    """Fail closed if a Judge context contains any unvalidated worker result."""
    invalid = [result.task_id for result in results if not result.validated]
    if invalid:
        raise PermissionError(
            "Judge may consume validated staging artifacts only; rejected task results: "
            + ",".join(invalid)
        )
    artifacts: list[dict[str, Any]] = []
    for result in results:
        artifacts.extend(dict(item) for item in result.staging_artifacts)
    return artifacts
