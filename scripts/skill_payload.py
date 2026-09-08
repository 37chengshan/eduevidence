"""Shared, explicit runtime allowlist for flat Skills, npm installs and wheels."""
from __future__ import annotations

from pathlib import Path
import shutil
import sys

TREES = (
    "agents", "engine", "domains", "skill", "references", "schemas", "scripts",
    "retrieval", "integrations", "visualization/eduevidence-report", "web/studio",
    "assets/readme",
)
FILES = (
    "SKILL.md", "eduevidence_cli.py", "install.sh", "pyproject.toml", "setup.py",
    "LICENSE", "CHANGELOG.md", "README.md", "README.zh-CN.md", "web/index.html",
    "benchmarks/evidence-library.json", "benchmarks/partitions.json",
    "benchmarks/adversarial/cases.jsonl",
)
DOCS = (
    "architecture.md", "demo.md", "demo-storyboard.md", "install-guide.md",
    "reproducibility.md", "release-contract.md", "autoresearch-evolution-plan.md",
    "orchestration-role-model.md", "autoresearch-implementation-status.md",
    "research-studio-guide.zh-CN.md", "demo-workplace-ai.md",
    "release-closeout/README.md", "release-closeout/issues.md",
    "release-closeout/frontend-acceptance.md", "release-closeout/verification.md",
)
EXAMPLES = (
    "ai-coding-assistant-evidence", "workplace-ai-assistant",
)
EXAMPLE_FILES = (
    "result.json", "result.zh.json", "evidence_graph.json", "report_spec.json",
    "EduEvidence_Report.html", "verdict.json", "evidence.jsonl", "sources.jsonl",
    "frame.json", "methodology.json", "intervention.json", "evaluation.json",
)
RETIRED_DEMO_SCRIPTS = {
    "scripts/build_esl_artifacts.py", "scripts/generate_new_projects.py",
    "scripts/enrich_projects_human_and_lieflat.py", "scripts/build_killer_demo.py",
    "scripts/sync_killer_demo_report.py",
}


def payload_files(root: Path):
    """Yield safe relative files; no symlinks, private state or generated caches."""
    paths = set(FILES)
    paths.update(f"docs/{name}" for name in DOCS)
    for tree in TREES:
        paths.update(p.relative_to(root).as_posix() for p in (root / tree).rglob("*") if p.is_file())
    # Ship configuration, never historical results or private Autoevolve sessions.
    paths.update(f"autoevolve/{name}" for name in ("program.md", "config.yaml", "protected.manifest.yaml"))
    for example in EXAMPLES:
        paths.update(f"examples/{example}/{name}" for name in EXAMPLE_FILES)
        paths.update(p.relative_to(root).as_posix() for p in (root / "examples" / example / "reports-5themes").glob("*.html"))
    for relative in sorted(paths):
        if relative in RETIRED_DEMO_SCRIPTS:
            continue
        path = root / relative
        parts = Path(relative).parts
        if any(p.startswith(".") or p in {"__pycache__", "node_modules", "runs", "venv", "test-results"} for p in parts):
            continue
        if path.suffix in {".pyc", ".pyo", ".log"} or any((root.joinpath(*parts[:i])).is_symlink() for i in range(1, len(parts) + 1)):
            continue
        if path.is_file():
            yield relative


def copy_payload(root: Path, destination: Path) -> None:
    required = ("SKILL.md", "agents/openai.yaml", "web/studio/index.html", "eduevidence_cli.py")
    for name in required:
        if not (root / name).is_file():
            raise FileNotFoundError(f"Incomplete Skill runtime: {name}")
    for relative in payload_files(root):
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / relative, output)


if __name__ == "__main__":
    copy_payload(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
