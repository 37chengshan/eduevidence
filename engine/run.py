"""RunRecord lifecycle — one execution attempt or mutation inside a Project.

A Run starts at the Project's current graph revision (`graph_revision_before`)
and, on completion, records `graph_revision_after`. Runs live at
`runs/<run_id>/run.json`; a second Run never overwrites the first.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from engine.contracts import validate_record
from engine.ids import new_run_id
from engine.project import ProjectWorkspace
from engine.versions import (
    CONFIDENCE_POLICY_VERSION,
    METHODOLOGY_POLICY_VERSION,
    SOURCE_VALIDATION_POLICY_VERSION,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_path(project: ProjectWorkspace, run_id: str) -> Path:
    return project.runs_dir() / run_id / "run.json"


def _atomic_write_json(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)


def _check(record: dict) -> None:
    errors = validate_record("run", record)
    if errors:
        raise ValueError(f"invalid run record: {errors}")


def start_run(project: ProjectWorkspace, *, purpose: str,
              capabilities: list[str], execution_backend: str) -> dict:
    """Open a new Run at the Project's current revision."""
    run = {
        "run_id": new_run_id(),
        "project_id": project.project_id,
        "purpose": purpose,
        "started_at": _now_iso(),
        "status": "running",
        "graph_revision_before": project.current_revision(),
        "graph_revision_after": None,
        "capabilities": sorted(set(capabilities)),
        "execution_backend": execution_backend,
        "policy_versions": {
            "source_validation": SOURCE_VALIDATION_POLICY_VERSION,
            "methodology": METHODOLOGY_POLICY_VERSION,
            "confidence": CONFIDENCE_POLICY_VERSION,
        },
    }
    _check(run)
    _atomic_write_json(_run_path(project, run["run_id"]), run)
    return run


def finish_run(project: ProjectWorkspace, run_id: str, *,
               status: str, graph_revision_after: int) -> dict:
    """Close a Run with its final status and end revision."""
    path = _run_path(project, run_id)
    if not path.is_file():
        raise FileNotFoundError(f"run {run_id!r} not found in project {project.project_id}")
    run = json.loads(path.read_text(encoding="utf-8"))
    if run["status"] != "running":
        raise ValueError(f"run {run_id} is already {run['status']!r}; cannot finish twice")
    run["status"] = status
    run["graph_revision_after"] = graph_revision_after
    _check(run)
    _atomic_write_json(path, run)
    return run
