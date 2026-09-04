from __future__ import annotations

import hashlib
import os
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


EVAL_SUITE_PATTERNS = (
    "benchmarks/evaluator/**",
    "benchmarks/holdout/**",
    "benchmarks/adversarial/**",
    "benchmarks/annotations/**",
    "benchmarks/partitions.json",
    "benchmarks/questions.jsonl",
    "references/scientific-invariants.md",
)


def _matches(rel: str, pattern: str) -> bool:
    import fnmatch

    return fnmatch.fnmatch(rel, pattern) or (
        pattern.endswith("/**") and rel.startswith(pattern[:-3])
    )


def compute_eval_suite_hash(root: str | Path) -> str:
    """Hash the trusted evaluation suite from repository files.

    The evaluator does not supply this identity. The runner computes it from
    protected evaluator/partition/gold/adversarial inputs before promotion.
    """
    root = Path(root).resolve()
    digest = hashlib.sha256()
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        if any(_matches(rel, pattern) for pattern in EVAL_SUITE_PATTERNS):
            files.append(path)
    if not files:
        raise ValueError("trusted evaluation suite is empty")
    for path in sorted(files):
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


@dataclass(frozen=True)
class AgentIsolation:
    """Runner-owned authority for mutation-agent OS isolation.

    `verified` is true only when the runner itself can construct a supported
    container boundary that mounts the sanitized mutation view and nothing from
    the canonical repository. Evaluator JSON can never set this value.
    """

    mode: str
    verified: bool
    runtime: str | None = None
    image: str | None = None
    reason: str = ""

    @classmethod
    def from_environment(cls) -> "AgentIsolation":
        mode = os.environ.get("EDUEVIDENCE_AUTOEVOLVE_ISOLATION", "none").strip().lower()
        if mode in {"", "none", "off"}:
            return cls("none", False, reason="no OS isolation provider configured")
        if mode != "container":
            return cls(mode, False, reason=f"unsupported isolation mode: {mode}")

        requested = os.environ.get("EDUEVIDENCE_AUTOEVOLVE_CONTAINER_RUNTIME", "").strip()
        runtimes = [requested] if requested else ["docker", "podman"]
        runtime = next((item for item in runtimes if item and shutil.which(item)), None)
        image = os.environ.get("EDUEVIDENCE_AUTOEVOLVE_ISOLATION_IMAGE", "").strip()
        if not runtime:
            return cls("container", False, reason="docker/podman runtime unavailable")
        if not image:
            return cls("container", False, runtime=runtime, reason="isolation image not configured")
        return cls(
            "container",
            True,
            runtime=runtime,
            image=image,
            reason="runner-owned container boundary",
        )

    def wrap_command(
        self,
        command: str,
        view: str | Path,
        env: Mapping[str, str],
    ) -> tuple[str, dict[str, str]]:
        """Return a command/environment suitable for `_run_json`.

        Container mode exposes only the sanitized view at /workspace, disables
        networking, uses a read-only container root, and gives the agent a
        writable tmpfs. Only explicit EDUEVIDENCE_* control variables are
        forwarded; host credentials are not inherited implicitly.
        """
        if not self.verified:
            return command, dict(env)
        assert self.runtime and self.image
        view = Path(view).resolve()
        argv = [
            self.runtime,
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev",
            "--mount",
            f"type=bind,src={view},dst=/workspace,rw",
            "--workdir",
            "/workspace",
        ]
        view_prefix = str(view)
        for key, value in env.items():
            if not key.startswith("EDUEVIDENCE_"):
                continue
            text = str(value)
            if text == view_prefix:
                text = "/workspace"
            elif text.startswith(view_prefix + os.sep):
                rel = Path(text).relative_to(view).as_posix()
                text = f"/workspace/{rel}"
            argv.extend(["--env", f"{key}={text}"])
        argv.extend([self.image, "sh", "-lc", command])
        # The container runtime itself receives only the minimal host settings
        # needed to launch. Model/API credentials are not implicitly forwarded.
        host_env = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "HOME", "TMPDIR"}
        }
        return shlex.join(argv), host_env
