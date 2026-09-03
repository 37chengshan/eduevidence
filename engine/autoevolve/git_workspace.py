from __future__ import annotations
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


def _run(repo: Path, *args: str, capture: bool = False) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, capture_output=capture
    )
    return completed.stdout.rstrip("\n") if capture else ""


def safe_tag(tag: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", tag).strip("-")
    if not clean or clean in {".", ".."}:
        raise ValueError("invalid run tag")
    return clean[:80]


@dataclass(frozen=True)
class GitWorkspace:
    repo: Path
    path: Path
    branch: str

    @classmethod
    def create(cls, repo: str | Path, tag: str):
        repo = Path(repo).resolve()
        tag = safe_tag(tag)
        branch = f"autoresearch/{tag}"
        current = _run(repo, "branch", "--show-current", capture=True)
        if current.startswith("autoresearch/"):
            raise ValueError("create the session from a non-autoresearch base branch")
        path = repo / ".autoevolve-worktrees" / tag
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(path)
        _run(repo, "worktree", "add", "-b", branch, str(path), "HEAD")
        return cls(repo, path, branch)

    def changed_files(self) -> list[str]:
        output = _run(self.path, "status", "--porcelain", capture=True)
        return [line[3:] for line in output.splitlines() if line.strip()]

    def restore(self) -> None:
        output = _run(self.path, "status", "--porcelain", capture=True)
        untracked = [line[3:] for line in output.splitlines() if line.startswith("?? ")]
        _run(self.path, "restore", "--staged", "--worktree", ".")
        for relative in untracked:
            target = (self.path / relative).resolve()
            if self.path not in target.parents and target != self.path:
                raise ValueError("unsafe untracked path")
            if target.is_file() or target.is_symlink():
                target.unlink(missing_ok=True)
            elif target.is_dir():
                import shutil
                shutil.rmtree(target)

    def commit(self, message: str) -> str:
        _run(self.path, "add", "-A")
        _run(self.path, "commit", "-m", message)
        return _run(self.path, "rev-parse", "HEAD", capture=True)
