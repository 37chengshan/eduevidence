from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    invariants = ROOT / "references" / "scientific-invariants.md"
    if not invariants.is_file():
        fail("missing scientific invariants")
    text = invariants.read_text(encoding="utf-8").lower()
    for phrase in (
        "optimize the research process, never the conclusion.",
        "single writer",
        "append-only",
    ):
        if phrase not in text:
            fail(f"missing invariant: {phrase}")

    registry = ROOT / "skill" / "roles" / "registry.yaml"
    if not registry.is_file():
        fail("missing role registry")
    registry_text = registry.read_text(encoding="utf-8")
    for role in ("evidence-retriever", "skeptic", "method-reviewer", "evidence-judge"):
        if role not in registry_text:
            fail(f"role missing: {role}")

    from engine.orchestration import CanonicalWriteGuard, ExecutionPlanner
    for level, cap in (("S", 0), ("M", 3), ("L", 6)):
        plan = ExecutionPlanner().plan(level)
        if level == "S" and plan.delegated_tasks:
            fail("S must delegate zero tasks")
        if len(plan.delegated_tasks) > cap:
            fail(f"{level} delegated worker plan exceeds policy cap")
        if max((len(group) for group in plan.parallel_groups), default=0) > plan.max_parallel_workers:
            fail(f"{level} execution group exceeds max_parallel_workers")
    try:
        CanonicalWriteGuard().require("worker", "GraphRevision")
        fail("single writer guard did not block worker")
    except PermissionError:
        pass

    schema_dir = ROOT / "schemas" / "vNext"
    required = {
        "research-iteration.schema.json",
        "research-strategy.schema.json",
        "negative-search-record.schema.json",
        "gap-priority.schema.json",
        "task-spec.schema.json",
        "worker-result.schema.json",
        "execution-plan.schema.json",
        "skill-experiment.schema.json",
        "eval-snapshot.schema.json",
        "autoevolve-session.schema.json",
    }
    missing = [name for name in required if not (schema_dir / name).is_file()]
    if missing:
        fail("missing schemas: " + ",".join(sorted(missing)))
    for name in required:
        json.loads((schema_dir / name).read_text(encoding="utf-8"))

    head = os.getenv("GITHUB_HEAD_REF", "") or os.getenv("GITHUB_REF_NAME", "")
    if head.startswith("autoresearch/"):
        base = os.getenv("GITHUB_BASE_REF", "main")
        subprocess.run(
            ["git", "fetch", "origin", base, "--depth=1"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        changed = subprocess.check_output(
            ["git", "diff", "--name-only", f"origin/{base}...HEAD"],
            cwd=ROOT,
            text=True,
        ).splitlines()
        from engine.autoevolve import ProtectedManifest
        ok, bad = ProtectedManifest.from_repo(ROOT).validate_changes(changed)
        if not ok:
            fail("protected mutation on autoresearch branch: " + ",".join(bad))

    print("autoresearch invariants OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
