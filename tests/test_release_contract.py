"""Release-contract checks for the distributable EduEvidence skill payload."""
from pathlib import Path
import re

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
