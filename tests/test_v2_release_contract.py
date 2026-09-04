"""Skill contract tests — EduEvidence is a Skill-delivered Research Engine.

The public Skill/docs must describe the Research Engine architecture (not a
standalone server/app), keep Agent MCP optional, and freeze the grounding
rule: no new study design without evidence grounding.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_PHRASES = (
    "EduEvidence Research Engine",
    "Evidence Review",
    "Full Research Cycle",
    "Project Workspace",
    "Evidence Graph",
    "Shared Research Library",
    "No new study design without evidence grounding",
)


def _skill_text() -> str:
    return (ROOT / "SKILL.md").read_text(encoding="utf-8")


def test_skill_mentions_research_engine_architecture():
    text = _skill_text()
    for phrase in REQUIRED_PHRASES:
        assert phrase.lower() in text.lower(), f"SKILL.md missing: {phrase!r}"


def test_skill_does_not_present_engine_as_standalone_server():
    text = _skill_text()
    for forbidden in ("standalone server", "web server", "daemon required",
                      "Agent MCP is mandatory", "Agent MCP is required"):
        assert forbidden not in text.lower(), f"SKILL.md must not claim: {forbidden!r}"


def test_skill_keeps_agent_mcp_optional():
    text = _skill_text()
    assert "Agent MCP" in text
    assert "Native" in text or "native" in text


def test_readme_mentions_research_engine():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Research Engine" in readme
    assert "Evidence Review" in readme
    assert "Full Research Cycle" in readme


def test_skill_startup_flow_uses_project_state_not_chat_memory():
    text = _skill_text()
    assert "Project" in text
    assert "Run" in text
    assert "research_mode" in text or "Research Mode" in text


# ---- packaging (Task 26) --------------------------------------------------

def test_skill_payload_includes_engine():
    install = (ROOT / "install.sh").read_text(encoding="utf-8")
    line = next(l for l in install.splitlines() if l.startswith("SKILL_PAYLOAD="))
    for item in ("SKILL.md", "engine", "skill", "references", "schemas",
                 "scripts", "retrieval", "integrations", "visualization"):
        assert item in line, f"install.sh payload missing {item!r}"


def test_wheel_metadata_includes_engine_package():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.setuptools.packages.find]" in pyproject
    for package_glob in ("engine*", "scripts*", "retrieval*", "integrations*"):
        assert f'"{package_glob}"' in pyproject


def test_copied_payload_imports_engine_without_source_repo(tmp_path):
    """A copied Skill payload must import engine modules standalone."""
    import shutil, subprocess, sys
    payload = tmp_path / "payload"
    payload.mkdir()
    for item in ("engine", "scripts"):
        shutil.copytree(ROOT / item, payload / item)
    shutil.copytree(ROOT / "schemas", payload / "schemas")
    probe = (
        "import sys; sys.path.insert(0, %r)\n"
        "import engine.project, engine.graph_store, engine.projections\n"
        "print('engine-import-ok')\n" % str(payload)
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True,
        cwd=str(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "engine-import-ok" in result.stdout
