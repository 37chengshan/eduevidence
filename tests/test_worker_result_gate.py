import pytest

from engine.orchestration import ExecutionPlanner
from engine.worker_result import require_validated_artifacts_for_judge, validate_worker_output


def task():
    return ExecutionPlanner().plan("M", run_id="RUN-1", base_revision=2).delegated_tasks[0]


def test_worker_cannot_self_attest_validation():
    spec = task()
    result = validate_worker_output(
        spec,
        {
            "task_id": spec.task_id,
            "status": "completed",
            "validated": True,
            "staging_artifacts": [{"artifact_type": "SourceCandidates", "items": []}],
            "summary": "worker says this is valid",
        },
        artifact_validator=lambda artifact: ["source provenance not checked"],
    )
    assert result.validated is False
    assert "source provenance not checked" in result.validation_issues[0]


def test_wrong_task_or_output_type_is_rejected():
    spec = task()
    result = validate_worker_output(
        spec,
        {
            "task_id": "other-task",
            "status": "completed",
            "staging_artifacts": [{"artifact_type": "MethodologyAudit"}],
        },
    )
    assert not result.validated
    assert any("task_id mismatch" in issue for issue in result.validation_issues)
    assert any("not allowed" in issue for issue in result.validation_issues)


def test_judge_fails_closed_on_any_unvalidated_result():
    spec = task()
    valid = validate_worker_output(
        spec,
        {
            "task_id": spec.task_id,
            "status": "completed",
            "staging_artifacts": [{"artifact_type": "SourceCandidates", "items": []}],
        },
        artifact_validator=lambda artifact: [],
    )
    invalid = validate_worker_output(
        spec,
        {
            "task_id": spec.task_id,
            "status": "completed",
            "staging_artifacts": [{"artifact_type": "SourceCandidates", "items": []}],
        },
        artifact_validator=lambda artifact: ["bad provenance"],
    )
    assert valid.validated
    with pytest.raises(PermissionError, match="validated staging artifacts only"):
        require_validated_artifacts_for_judge([valid, invalid])


def test_judge_receives_artifacts_not_worker_summary_prose():
    spec = task()
    result = validate_worker_output(
        spec,
        {
            "task_id": spec.task_id,
            "status": "completed",
            "staging_artifacts": [{"artifact_type": "SourceCandidates", "items": ["SRC-1"]}],
            "summary": "unsupported persuasive prose",
        },
        artifact_validator=lambda artifact: [],
    )
    artifacts = require_validated_artifacts_for_judge([result])
    assert artifacts == [{"artifact_type": "SourceCandidates", "items": ["SRC-1"]}]
    assert all("summary" not in artifact for artifact in artifacts)
