"""Release-contract checks for the distributable EduEvidence skill payload."""
from pathlib import Path
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def test_root_skill_uses_current_five_theme_contract():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")

    expected = [
        "Claude Research      [Light]",
        "Academic Paper       [Light]",
        "DataLab              [Light]",
        "DataLab              [Dark]",
        "Presentation / Judge [Dark]",
    ]
    for label in expected:
        assert label in text

    assert "| editorial |" not in text.lower()
    assert "12 个 Section" not in text
    assert "（12 部分）" not in text


def test_skill_installer_copies_every_runtime_directory():
    text = (ROOT / "install.sh").read_text(encoding="utf-8")
    match = re.search(r"SKILL_PAYLOAD=\(([^)]*)\)", text)
    assert match, "install.sh must declare SKILL_PAYLOAD"

    payload = set(match.group(1).split())
    required = {
        "SKILL.md",
        "skill",
        "references",
        "schemas",
        "scripts",
        "retrieval",
        "integrations",
        "visualization",
    }
    assert required <= payload


def test_public_readmes_document_current_themes_and_full_skill_payload():
    for name in ("README.md", "README.en.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        lower = text.lower()

        assert "datalab-dark" in lower
        assert "academic / editorial / datalab" not in lower
        assert "retrieval/" in text
        assert "integrations/" in text
        assert "visualization/" in text


def test_public_docs_do_not_reintroduce_retired_report_contracts():
    reproducibility = (ROOT / "docs" / "reproducibility.md").read_text(encoding="utf-8")
    project_review = (ROOT / "docs" / "PROJECT_REVIEW_2026-08-12.md").read_text(encoding="utf-8")

    assert "12 部分" not in reproducibility
    assert "Claude / Academic / Editorial / Datalab / Presentation" not in project_review


def test_install_script_syntax_and_read_only_entrypoints():
    syntax = subprocess.run(
        ["bash", "-n", str(ROOT / "install.sh")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert syntax.returncode == 0, syntax.stderr

    listed = subprocess.run(
        ["bash", str(ROOT / "install.sh"), "--list-hosts"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert listed.returncode == 0, listed.stderr
    assert "claude" in listed.stdout
    assert "codex" in listed.stdout
    assert "omp" in listed.stdout

    project_python = ROOT / ".venv" / "bin" / "python"
    python_bin = str(project_python if project_python.exists() else Path(sys.executable))
    dry_run = subprocess.run(
        ["bash", str(ROOT / "install.sh"), "--dry-run"],
        cwd=ROOT,
        env={**os.environ, "PYTHON": python_bin},
        text=True,
        capture_output=True,
        check=False,
    )
    assert dry_run.returncode == 0, dry_run.stderr
    assert "[dry-run]" in dry_run.stdout
