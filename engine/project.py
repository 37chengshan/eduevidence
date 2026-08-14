"""ProjectWorkspace lifecycle — the durable unit of V2 research.

A Project owns a versioned Evidence Graph plus gap/design/dataset/analysis/
decision/projection/report/run areas. Run is one execution attempt *inside*
a Project; Project is long-lived. `project.json` is written atomically and
always mirrors `graph/HEAD` in `graph_revision`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from engine.contracts import validate_record
from engine.ids import new_project_id
from engine.versions import ENGINE_VERSION, GRAPH_SCHEMA_VERSION

_SUBDIRS = (
    "graph/revisions",
    "gaps",
    "study-designs",
    "datasets/raw",
    "datasets/processed",
    "datasets/manifests",
    "analyses",
    "decisions",
    "projections",
    "reports",
    "runs",
    "pilots",
)

_MANIFEST_NAME = "project.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, record: dict) -> None:
    """Write JSON via tmp file + rename so readers never see partial state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)


def _default_decision_target(research_mode: str) -> str:
    return "research_cycle" if research_mode == "full_research_cycle" else "teaching_decision"


@dataclass(frozen=True)
class ProjectWorkspace:
    home: Path
    project_id: str
    path: Path

    @classmethod
    def create(cls, home: Path, *, question: str, title: str,
               research_mode: str) -> "ProjectWorkspace":
        home = Path(home).expanduser().resolve()
        project_id = new_project_id(question)
        path = home / "projects" / project_id
        for sub in _SUBDIRS:
            (path / sub).mkdir(parents=True, exist_ok=True)
        now = _now_iso()
        manifest = {
            "project_id": project_id,
            "title": title,
            "domain": "education",
            "question": question,
            "research_mode": research_mode,
            "decision_target": _default_decision_target(research_mode),
            "created_at": now,
            "updated_at": now,
            "engine_version": ENGINE_VERSION,
            "schema_version": GRAPH_SCHEMA_VERSION,
            "graph_revision": 0,
            "status": "active",
        }
        errors = validate_record("project", manifest)
        if errors:
            raise ValueError(f"invalid project manifest: {errors}")
        _atomic_write_json(path / _MANIFEST_NAME, manifest)
        return cls(home=home, project_id=project_id, path=path)

    @classmethod
    def open(cls, home: Path, project_id: str) -> "ProjectWorkspace":
        home = Path(home).expanduser().resolve()
        path = home / "projects" / project_id
        if not (path / _MANIFEST_NAME).is_file():
            raise FileNotFoundError(f"project {project_id!r} not found under {home}")
        return cls(home=home, project_id=project_id, path=path)

    def manifest(self) -> dict:
        return json.loads((self.path / _MANIFEST_NAME).read_text(encoding="utf-8"))

    def update_manifest(self, **changes) -> dict:
        """Apply changes, bump updated_at, write atomically; return the new manifest."""
        manifest = self.manifest()
        manifest.update(changes)
        manifest["updated_at"] = _now_iso()
        errors = validate_record("project", manifest)
        if errors:
            raise ValueError(f"invalid project manifest after update: {errors}")
        _atomic_write_json(self.path / _MANIFEST_NAME, manifest)
        return manifest

    def current_revision(self) -> int:
        return int(self.manifest()["graph_revision"])

    def runs_dir(self) -> Path:
        return self.path / "runs"
