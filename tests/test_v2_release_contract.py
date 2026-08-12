from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_v2_migration_must_keep_v1_entrypoints_present():
    assert (ROOT / "SKILL.md").is_file()
    assert (ROOT / "scripts" / "orchestrator.py").is_file()
    assert (ROOT / "visualization" / "eduevidence-report" / "scripts" / "build_report.py").is_file()


def test_v2_engine_is_not_yet_required_by_v1_fixture():
    assert (ROOT / "examples" / "ai-coding-assistant" / "result.json").is_file()
