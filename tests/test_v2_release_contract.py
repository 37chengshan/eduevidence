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
    # Agent MCP may be mentioned as an option, never as the only backend
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
