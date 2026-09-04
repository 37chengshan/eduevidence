"""Sanitized mutation view for Skill Autoresearch agents.

This prevents accidental holdout/gold exposure by default: the mutation agent
sees a tracked-file copy without .git and without evaluator/holdout/adversarial
benchmark material. `benchmarks/questions.jsonl` and gold annotations are
filtered to DEV ids only. It is context isolation, not an OS security sandbox;
a promotion evaluator must independently attest stronger holdout isolation.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tracked_files(worktree: Path) -> list[str]:
    output = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=worktree, text=False
    )
    return [item.decode("utf-8") for item in output.split(b"\0") if item]


def _dev_ids(worktree: Path) -> set[str]:
    path = worktree / "benchmarks" / "partitions.json"
    if not path.is_file():
        return set()
    value = json.loads(path.read_text(encoding="utf-8"))
    return {str(item) for item in value.get("dev", [])}


def _copy_filtered_benchmark(source: Path, dest: Path, rel: str, dev_ids: set[str]) -> bool:
    if rel == "benchmarks/partitions.json":
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        return True
    if rel == "benchmarks/questions.jsonl":
        rows = []
        for line in source.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("id") in dev_ids:
                rows.append(json.dumps(row, ensure_ascii=False))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
        return True
    if rel.startswith("benchmarks/annotations/gold-"):
        qid = Path(rel).stem.removeprefix("gold-")
        if qid in dev_ids:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            return True
    if rel.startswith("benchmarks/dev/"):
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        return True
    return False


@dataclass
class AgentMutationView:
    path: Path
    baseline_hashes: dict[str, str]

    @classmethod
    def create(
        cls,
        worktree: str | Path,
        *,
        session_context: dict[str, Any] | None = None,
    ) -> "AgentMutationView":
        worktree = Path(worktree).resolve()
        root = Path(tempfile.mkdtemp(prefix="eduevidence-autoevolve-agent-"))
        dev_ids = _dev_ids(worktree)
        for rel in _tracked_files(worktree):
            source = worktree / rel
            if not source.is_file() or source.is_symlink():
                continue
            dest = root / rel
            if rel.startswith("benchmarks/"):
                _copy_filtered_benchmark(source, dest, rel, dev_ids)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
        if session_context is not None:
            context_path = root / "autoevolve" / "session-context.json"
            context_path.parent.mkdir(parents=True, exist_ok=True)
            context_path.write_text(
                json.dumps(session_context, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        baseline = {
            path.relative_to(root).as_posix(): _sha(path)
            for path in root.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        return cls(root, baseline)

    def changed_files(self) -> list[str]:
        current = {
            path.relative_to(self.path).as_posix(): _sha(path)
            for path in self.path.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        changed = {
            rel
            for rel in set(self.baseline_hashes) | set(current)
            if self.baseline_hashes.get(rel) != current.get(rel)
        }
        # Any symlink created by the agent is an invalid attempted mutation.
        changed.update(
            path.relative_to(self.path).as_posix()
            for path in self.path.rglob("*")
            if path.is_symlink()
        )
        return sorted(changed)

    def sync_to(self, worktree: str | Path, changed: list[str]) -> None:
        worktree = Path(worktree).resolve()
        for rel in changed:
            source = self.path / rel
            target = (worktree / rel).resolve()
            if worktree not in target.parents and target != worktree:
                raise ValueError(f"unsafe mutation path: {rel}")
            if source.is_symlink():
                raise ValueError(f"symlink mutations are forbidden: {rel}")
            if source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            elif target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()

    def cleanup(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)
