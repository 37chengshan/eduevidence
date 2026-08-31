"""Build a transparent, self-describing judge evidence pack from real artifacts."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.project import ProjectWorkspace


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def export_judge_pack(project: ProjectWorkspace, output_dir: Path) -> dict[str, Any]:
    """Copy available project evidence without inventing unavailable claims.

    The manifest lists every required judge-pack category and explicitly marks
    missing inputs. This makes the pack suitable for review while keeping its
    limits auditable.
    """
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = {
        "project_manifest": project.path / "project.json",
        "graph": project.path / "graph",
        "runs": project.path / "runs",
        "decisions": project.path / "decisions",
        "projections": project.path / "projections",
        "reports": project.path / "reports",
        "pilots": project.path / "pilots",
    }
    copied: list[dict[str, str]] = []
    missing: list[str] = []
    for name, source in candidates.items():
        target = output_dir / name
        if source.is_file():
            shutil.copy2(source, target)
            copied.append({"name": name, "path": target.name, "sha256": _sha256(target)})
        elif source.is_dir() and any(source.rglob("*")):
            shutil.copytree(source, target, dirs_exist_ok=True)
            for item in sorted(path for path in target.rglob("*") if path.is_file()):
                copied.append({"name": name, "path": str(item.relative_to(output_dir)), "sha256": _sha256(item)})
        else:
            missing.append(name)
    manifest = {
        "format": "eduevidence-judge-pack/2026.09",
        "project_id": project.project_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "copied_files": copied,
        "missing_categories": missing,
        "limitations": [
            "Only immutable/project-scoped artifacts available at export time are included.",
            "Benchmark, blinded-review and usability evidence must be supplied from completed study artifacts; they are never synthesized by this export.",
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
