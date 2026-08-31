"""Project-scoped durable control plane.

This service is the only write API intended for CLI and console integrations.
It keeps immutable artifact bytes and replayable events in SQLite WAL, while
preserving the existing ProjectWorkspace and graph store implementations.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.project import ProjectWorkspace
from engine.run import finish_run, start_run

RUN_STATUSES = frozenset({
    "queued", "running", "waiting_for_user", "waiting_for_user_data", "waiting_for_executor",
    "waiting_for_tool", "waiting_for_review", "blocked_scientific_gate", "blocked_contract_error",
    "completed", "failed_recoverable", "failed_terminal", "cancelled",
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResearchService:
    def __init__(self, home: Path):
        self.home = Path(home).expanduser().resolve()
        self.home.mkdir(parents=True, exist_ok=True)
        self.db_path = self.home / "research-control.sqlite3"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _init_db(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL, run_id TEXT, type TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS artifacts (artifact_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, run_id TEXT, artifact_type TEXT NOT NULL, sha256 TEXT NOT NULL, path TEXT NOT NULL, created_at TEXT NOT NULL, metadata TEXT NOT NULL);
            """)

    def _event(self, project_id: str, event_type: str, payload: dict[str, Any], run_id: str | None = None) -> int:
        with self._connect() as db:
            cursor = db.execute("INSERT INTO events(project_id,run_id,type,payload,created_at) VALUES(?,?,?,?,?)",
                                (project_id, run_id, event_type, json.dumps(payload, ensure_ascii=False, sort_keys=True), _now()))
            return int(cursor.lastrowid)

    def create_project(self, *, question: str, title: str, research_mode: str = "evidence_review", domain: str = "education") -> ProjectWorkspace:
        project = ProjectWorkspace.create(self.home, question=question, title=title, research_mode=research_mode, domain=domain)
        self._event(project.project_id, "project_created", project.manifest())
        return project

    def start_run(self, project_id: str, *, purpose: str, capabilities: list[str], execution_backend: str = "sequential_main_agent") -> dict:
        project = ProjectWorkspace.open(self.home, project_id)
        run = start_run(project, purpose=purpose, capabilities=capabilities, execution_backend=execution_backend)
        self._event(project_id, "run_started", run, run["run_id"])
        return run

    def submit_artifact(self, project_id: str, *, artifact_type: str, content: bytes, run_id: str | None = None,
                        metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        digest = hashlib.sha256(content).hexdigest()
        artifact_id = f"ART-{digest[:20]}"
        directory = self.home / "artifacts" / digest[:2]
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / digest
        if not path.exists():
            path.write_bytes(content)
        record = {"artifact_id": artifact_id, "project_id": project_id, "run_id": run_id,
                  "artifact_type": artifact_type, "sha256": digest, "path": str(path),
                  "created_at": _now(), "metadata": metadata or {}}
        with self._connect() as db:
            db.execute("INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?,?,?,?,?)",
                       (artifact_id, project_id, run_id, artifact_type, digest, str(path), record["created_at"], json.dumps(record["metadata"], ensure_ascii=False, sort_keys=True)))
        self._event(project_id, "artifact_submitted", record, run_id)
        return record

    def events(self, project_id: str, *, after_seq: int = 0) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM events WHERE project_id=? AND seq>? ORDER BY seq", (project_id, after_seq)).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]

    def projects(self) -> list[dict[str, Any]]:
        directory = self.home / "projects"
        if not directory.is_dir():
            return []
        return [json.loads(manifest.read_text(encoding="utf-8"))
                for manifest in sorted(directory.glob("*/project.json"))]

    def runs(self, project_id: str) -> list[dict[str, Any]]:
        project = ProjectWorkspace.open(self.home, project_id)
        return [json.loads(path.read_text(encoding="utf-8"))
                for path in sorted(project.runs_dir().glob("*/run.json"))]

    def artifacts(self, project_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM artifacts WHERE project_id=? ORDER BY created_at", (project_id,)).fetchall()
        return [{**dict(row), "metadata": json.loads(row["metadata"])} for row in rows]
