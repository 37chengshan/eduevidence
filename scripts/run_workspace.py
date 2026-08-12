#!/usr/bin/env python3
"""run_workspace.py — Run Workspace & Run Manifest (Phase 12-13).

A run is an isolated directory under ``<runs_dir>/<run_id>/`` holding every
artifact the EvidenceFlow Protocol touches, so a run can be audited, resumed
and reproduced without any external state:

    run_manifest.json      run identity + policy versions (Phase 13)
    state.json             stage progress machine (Phase 32 resume)
    capability_plan.json   required vs available capabilities
    resource_plan.json     token budgets / concurrency / timeouts
    execution_plan.json    stage list with artifacts + schema gates
    model_inventory.json   model routing per role
    agent_mcp_approval.json  Mode B availability + user approval
    frame.json             Education Research Frame
    sources.jsonl          Source Objects (registry, post-dedupe)
    fetch/                 fetched content provenance (raw + validation)
    evidence.jsonl         Claim-level Evidence Objects
    skeptic.json           counter-evidence / null-result / confounder list
    methodology.json       Methodology Audit
    raw_verdict.json       model verdict (pre-gate)
    final_verdict.json     deterministic verdict (post-gate, Phase 15)
    intervention.json      Teaching Intervention Plan
    evaluation.json        Evaluation Plan
    result.json / result.zh.json   bilingual result pack
    report_spec.json       report contract consumed by the render layer
    report.html            rendered bilingual report
    trace.jsonl            append-only run event log
    task-briefs/           per-stage prompts written when a stage waits for
                           an external agent

Manifest fields (Phase 13): run_id, skill_version, git_commit, started_at,
question, execution_mode, scp_available, agent_mcp_available,
agent_mcp_approved, resource_policy_version, confidence_policy_version.

Usage (importable; also a small CLI for workspace maintenance):

    python scripts/run_workspace.py --runs-dir runs create --run-id 20260812-103000
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_VERSION = "1.0.0"
RESOURCE_POLICY_VERSION = "2026-08-12.v1"

#: Ordered EvidenceFlow stages the orchestrator routes through.
STAGES = [
    "frame", "retrieve", "extract", "challenge", "audit",
    "adjudicate", "intervene", "evaluate", "present",
]

#: Every artifact a run workspace owns (dirs end with '/').
WORKSPACE_FILES: list[str] = [
    "run_manifest.json", "state.json",
    "capability_plan.json", "resource_plan.json", "execution_plan.json",
    "model_inventory.json", "agent_mcp_approval.json",
    "frame.json", "sources.jsonl", "fetch/", "evidence.jsonl", "skeptic.json",
    "methodology.json", "raw_verdict.json", "final_verdict.json",
    "intervention.json", "evaluation.json", "result.json", "result.zh.json",
    "report_spec.json", "report.html", "trace.jsonl",
]

EMPTY_SEED: dict[str, str] = {
    "capability_plan.json": "{}",
    "resource_plan.json": "{}",
    "execution_plan.json": "{}",
    "model_inventory.json": "{}",
    "agent_mcp_approval.json": "{}",
    "frame.json": "{}",
    "sources.jsonl": "",
    "evidence.jsonl": "",
    "skeptic.json": "{}",
    "methodology.json": "{}",
    "raw_verdict.json": "{}",
    "final_verdict.json": "{}",
    "intervention.json": "{}",
    "evaluation.json": "{}",
    "result.json": "{}",
    "result.zh.json": "{}",
    "report_spec.json": "{}",
    "report.html": "",
}


def utc_now() -> str:
    """RFC 3339 UTC timestamp for manifest/state/trace."""
    return datetime.now(timezone.utc).isoformat()


def git_commit(root: Path | None = None) -> str:
    """Short HEAD commit of the repository (best-effort, 'unknown' off-repo)."""
    root = root or Path.cwd()
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def detect_scp() -> bool:
    """Scholar-Copilot availability marker (env override, default off)."""
    return os.environ.get("EDUEVIDENCE_SCP_AVAILABLE", "").lower() in ("1", "true", "yes")


def next_run_id(runs_dir: Path, *, now: datetime | None = None) -> str:
    """Timestamp run id, uniquified with a -N suffix on collision."""
    now = now or datetime.now(timezone.utc)
    base = now.strftime("%Y%m%d-%H%M%S")
    candidate = base
    suffix = 2
    while (runs_dir / candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


# ----------------------------------------------------------------- JSON I/O


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def save_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


# --------------------------------------------------------------- workspace


def build_manifest(
    run_id: str,
    question: str,
    *,
    execution_mode: str,
    agent_mcp_available: bool,
    agent_mcp_approved: bool,
    scp_available: bool | None = None,
    root: Path | None = None,
    started_at: str | None = None,
) -> dict[str, Any]:
    """Phase 13 run manifest with every contract field."""
    return {
        "run_id": run_id,
        "skill_version": SKILL_VERSION,
        "git_commit": git_commit(root),
        "started_at": started_at or utc_now(),
        "question": question,
        "execution_mode": execution_mode,
        "scp_available": detect_scp() if scp_available is None else scp_available,
        "agent_mcp_available": agent_mcp_available,
        "agent_mcp_approved": agent_mcp_approved,
        "resource_policy_version": RESOURCE_POLICY_VERSION,
        "confidence_policy_version": "2026-08-12.v1",
    }


class RunWorkspace:
    """Filesystem + state access for one run under ``<runs_dir>/<run_id>``."""

    def __init__(self, runs_dir: Path, run_id: str):
        self.runs_dir = Path(runs_dir)
        self.run_id = run_id
        self.path = self.runs_dir / run_id

    # -- lifecycle ----------------------------------------------------------

    def exists(self) -> bool:
        return (self.path / "run_manifest.json").is_file()

    def create(self) -> "RunWorkspace":
        """Materialize the full workspace skeleton (empty seeds + state)."""
        self.path.mkdir(parents=True, exist_ok=True)
        for name, content in EMPTY_SEED.items():
            target = self.path / name
            if not target.exists():
                target.write_text(content, encoding="utf-8")
        (self.path / "fetch").mkdir(exist_ok=True)
        (self.path / "task-briefs").mkdir(exist_ok=True)
        if not (self.path / "trace.jsonl").exists():
            self.path.joinpath("trace.jsonl").write_text("", encoding="utf-8")
        if not (self.path / "state.json").exists():
            self.save_state({"run_id": self.run_id, "question": "",
                             "depth": "M", "status": "running",
                             "current_stage": STAGES[0],
                             "stages": {s: {"status": "pending"} for s in STAGES}})
        if not self.manifest_path.exists():
            self.save_manifest(build_manifest(
                self.run_id, "", execution_mode="platform_native",
                agent_mcp_available=False, agent_mcp_approved=False))
        self.trace("workspace_created", stage=None, detail=f"run workspace {self.run_id}")
        return self

    # -- manifest ------------------------------------------------------------

    @property
    def manifest_path(self) -> Path:
        return self.path / "run_manifest.json"

    def load_manifest(self) -> dict[str, Any]:
        return load_json(self.manifest_path)

    def save_manifest(self, manifest: dict[str, Any]) -> None:
        save_json(self.manifest_path, manifest)

    # -- state (Phase 32 resume) ----------------------------------------------

    @property
    def state_path(self) -> Path:
        return self.path / "state.json"

    def load_state(self) -> dict[str, Any]:
        state = load_json(self.state_path)
        state.setdefault("stages", {s: {"status": "pending"} for s in STAGES})
        return state

    def save_state(self, updates: dict[str, Any] | None = None) -> dict[str, Any]:
        """Persist state; returns the merged state. Threads one writer at a time."""
        lock = self.path / ".state.lock"
        for _ in range(50):
            try:
                with lock.open("x", encoding="utf-8"):
                    break
            except FileExistsError:
                pass
            import time
            time.sleep(0.02)
        try:
            state = self.load_state()
            if updates:
                state.update(updates)
            state["updated_at"] = utc_now()
            save_json(self.state_path, state)
            return state
        finally:
            try:
                lock.unlink()
            except OSError:
                pass

    def stage_status(self, stage: str) -> str:
        return self.load_state().get("stages", {}).get(stage, {}).get("status", "pending")

    def mark_stage(self, stage: str, status: str, *, detail: str = "", artifacts: list[str] | None = None) -> None:
        """Update one stage's row in state.json."""
        state = self.load_state()
        row = state["stages"].setdefault(stage, {"status": "pending"})
        row["status"] = status
        if detail:
            row["detail"] = detail
        if artifacts:
            row["artifacts"] = artifacts
        self.save_state({"stages": state["stages"]})

    # -- trace -----------------------------------------------------------------

    def trace(self, event: str, *, stage: str | None = None, detail: str = "") -> None:
        record = {"ts": utc_now(), "event": event, "stage": stage, "detail": detail}
        append_jsonl(self.path / "trace.jsonl", record)

    # -- external-agent briefs --------------------------------------------------

    def brief_path(self, stage: str) -> Path:
        return self.path / "task-briefs" / f"{stage}.md"

    def write_brief(self, stage: str, question: str, prompt: str) -> Path:
        """Write the handoff brief the orchestrator leaves for an external agent."""
        path = self.brief_path(stage)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = (f"# Run {self.run_id} — stage: {stage}\n\n"
                   f"## Question\n{question}\n\n## Task\n{prompt}\n\n"
                   f"## Output\nWrite the stage artifact into this run workspace "
                   f"(see execution_plan.json for the artifact path and schema gate).\n")
        path.write_text(content, encoding="utf-8")
        self.trace("brief_written", stage=stage, detail=str(path))
        return path


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="EduEvidence run workspace maintenance")
    parser.add_argument("--runs-dir", default="runs")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="create a workspace skeleton")
    create.add_argument("--run-id", required=True)
    create.add_argument("--question", default="")
    args = parser.parse_args()

    if args.command == "create":
        ws = RunWorkspace(Path(args.runs_dir), args.run_id)
        ws.create()
        print(f"workspace created: {ws.path}")
        return 0
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(main())
