"""V2 CLI tests — thin dispatch into engine modules, temp EDUEVIDENCE_HOME."""

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from orchestrator import main  # noqa: E402


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("EDUEVIDENCE_HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    return tmp_path / "home"


def _run(args, home):
    from engine.paths import resolve_home
    return main([*args, "--home", str(resolve_home())])


def test_project_create_and_status(home, capsys):
    code = _run(["project", "create", "--question", "Should we use AI tutors?",
                 "--title", "t", "--mode", "evidence_review"], home)
    assert code == 0
    pid = capsys.readouterr().out.strip()
    assert pid.startswith("PRJ-")
    code = _run(["project", "status", "--project", pid], home)
    assert code == 0
    out = capsys.readouterr().out
    assert "graph_revision: 0" in out


def test_project_list(home, capsys):
    _run(["project", "create", "--question", "flipped classroom?"], home)
    code = _run(["project", "list"], home)
    assert code == 0
    assert "PRJ-" in capsys.readouterr().out


def test_graph_validate_empty_ok(home, capsys):
    code = _run(["project", "create", "--question", "x"], home)
    assert code == 0
    pid = capsys.readouterr().out.strip()
    code = _run(["graph", "validate", "--project", pid], home)
    assert code == 0
    assert "graph valid" in capsys.readouterr().out


def test_research_plan(home, capsys):
    code = _run(["project", "create", "--question", "x"], home)
    assert code == 0
    pid = capsys.readouterr().out.strip()
    code = _run(["research", "plan", "--project", pid], home)
    assert code == 0
    out = capsys.readouterr().out
    assert "mode: evidence_review" in out
    assert "research_framing" in out
    assert "report_rendering" in out


def test_migrate_v1_creates_project_without_editing_pack(home, tmp_path, capsys):
    pack = tmp_path / "pack"
    shutil.copytree(Path(__file__).resolve().parent.parent / "examples" / "ai-coding-assistant",
                    pack)
    before = (pack / "result.json").read_bytes()
    code = _run(["migrate-v1", "--pack", str(pack)], home)
    assert code == 0
    out = capsys.readouterr().out
    assert "PRJ-" in out and "rev 1" in out
    assert (pack / "result.json").read_bytes() == before


def test_v1_list_command_still_works(home, capsys):
    code = main(["list", "--runs-dir", str(home / "runs")])
    assert code == 0


def test_v1_run_command_still_parses(home, capsys, tmp_path):
    code = main(["run", "--question", "q?", "--runs-dir", str(tmp_path / "runs")])
    assert code == 0
