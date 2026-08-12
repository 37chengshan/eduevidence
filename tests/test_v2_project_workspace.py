from pathlib import Path

import os

import pytest

from engine.paths import resolve_home
from engine.ids import new_project_id, new_run_id, new_local_id


def test_explicit_home_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("EDUEVIDENCE_HOME", "/ignored")
    assert resolve_home(tmp_path) == tmp_path.resolve()


def test_env_home_is_used_when_explicit_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("EDUEVIDENCE_HOME", str(tmp_path))
    assert resolve_home() == tmp_path.resolve()


def test_default_home_is_eduevidence_dir(monkeypatch):
    monkeypatch.delenv("EDUEVIDENCE_HOME", raising=False)
    assert resolve_home().name == ".eduevidence"


def test_project_id_is_unique_even_for_same_question():
    from datetime import datetime, timezone
    now = datetime(2026, 8, 12, 14, 0, tzinfo=timezone.utc)
    a = new_project_id("Should we use flipped classroom?", now=now, existing=set())
    b = new_project_id("  Should we use flipped classroom?  ", now=now, existing={a})
    assert a.startswith("PRJ-")
    assert b.startswith("PRJ-")
    assert a != b


def test_project_id_stable_prefix_and_creation_identity():
    from datetime import datetime, timezone
    now = datetime(2026, 8, 12, 14, 0, tzinfo=timezone.utc)
    pid = new_project_id("flipped classroom", now=now)
    # creation identity embeds UTC creation time, not a question hash
    assert "20260812" in pid


def test_run_id_unique_and_prefixed():
    from datetime import datetime, timezone
    now = datetime(2026, 8, 12, 14, 0, tzinfo=timezone.utc)
    a = new_run_id(now=now)
    b = new_run_id(now=now)
    assert a.startswith("RUN-")
    assert a != b


def test_local_id_respects_existing_and_prefix():
    existing = {"STU-aaaa1111"}
    a = new_local_id("STU", existing=existing)
    b = new_local_id("STU", existing=existing | {a})
    assert a.startswith("STU-")
    assert a not in existing
    assert a != b


def test_local_id_rejects_unknown_prefixes():
    # prefixes are frozen in the design; unknown ones are a programming error
    with pytest.raises(ValueError):
        new_local_id("XXX", existing=set())


# ---- project workspace lifecycle ----------------------------------------

def _created_ws(tmp_path):
    from engine.project import ProjectWorkspace
    return ProjectWorkspace.create(
        tmp_path, question="Should we allow AI coding assistants?",
        title="AI coding assistant pilot", research_mode="evidence_review")


def test_create_makes_exact_directory_layout(tmp_path):
    ws = _created_ws(tmp_path)
    all_dirs = {str(p.relative_to(ws.path)) for p in ws.path.rglob("*") if p.is_dir()}
    # leaf directories (parents like datasets/ and graph/ are implied)
    leaves = {d for d in all_dirs if not any(
        (ws.path / d / sub).is_dir() for sub in os.listdir(ws.path / d)
    )}
    assert leaves == {
        "analyses", "datasets/manifests", "datasets/processed", "datasets/raw",
        "decisions", "gaps", "graph/revisions", "projections", "reports",
        "runs", "study-designs",
    }


def test_create_writes_project_manifest(tmp_path):
    ws = _created_ws(tmp_path)
    m = ws.manifest()
    assert m["project_id"] == ws.project_id
    assert m["research_mode"] == "evidence_review"
    assert m["graph_revision"] == 0
    assert m["status"] == "active"


def test_open_missing_project_raises(tmp_path):
    from engine.project import ProjectWorkspace
    with pytest.raises(FileNotFoundError):
        ProjectWorkspace.open(tmp_path, "PRJ-does-not-exist")


def test_open_existing_project_roundtrips(tmp_path):
    from engine.project import ProjectWorkspace
    ws = _created_ws(tmp_path)
    ws2 = ProjectWorkspace.open(tmp_path, ws.project_id)
    assert ws2.path == ws.path
    assert ws2.manifest()["question"] == ws.manifest()["question"]


def test_manifest_requires_contract_valid(tmp_path):
    from engine.contracts import validate_record
    ws = _created_ws(tmp_path)
    assert validate_record("project", ws.manifest()) == []


def test_update_manifest_mirrors_graph_revision(tmp_path):
    ws = _created_ws(tmp_path)
    m = ws.update_manifest(graph_revision=1)
    assert m["graph_revision"] == 1
    assert ws.current_revision() == 1


# ---- run history ---------------------------------------------------------

def test_runs_are_isolated_per_project(tmp_path):
    from engine.project import ProjectWorkspace
    from engine.run import start_run, finish_run
    ws = _created_ws(tmp_path)
    run1 = start_run(ws, purpose="first pass", capabilities=["literature_search"],
                     execution_backend="host_native_subagents")
    run2 = start_run(ws, purpose="second pass", capabilities=["web_fetch"],
                     execution_backend="host_native_subagents")
    assert run1["run_id"] != run2["run_id"]
    assert (ws.path / "runs" / run1["run_id"] / "run.json").is_file()
    assert (ws.path / "runs" / run2["run_id"] / "run.json").is_file()
    # second run must not overwrite the first
    from engine.contracts import validate_record
    assert validate_record("run", run1) == []
    assert validate_record("run", run2) == []


def test_run_starts_at_current_revision_and_finishes_with_after(tmp_path):
    from engine.project import ProjectWorkspace
    from engine.run import start_run, finish_run
    ws = _created_ws(tmp_path)
    run = start_run(ws, purpose="pass", capabilities=["literature_search"],
                    execution_backend="sequential_main_agent")
    assert run["graph_revision_before"] == 0
    assert run["graph_revision_after"] is None
    assert run["status"] == "running"
    finished = finish_run(ws, run["run_id"], status="completed", graph_revision_after=1)
    assert finished["graph_revision_after"] == 1
    assert finished["status"] == "completed"


def test_finish_unknown_run_raises(tmp_path):
    from engine.project import ProjectWorkspace
    from engine.run import finish_run
    ws = _created_ws(tmp_path)
    with pytest.raises(FileNotFoundError):
        finish_run(ws, "RUN-nope", status="completed", graph_revision_after=1)


def test_run_records_isolated_across_projects(tmp_path):
    from engine.project import ProjectWorkspace
    from engine.run import start_run
    a = _created_ws(tmp_path)
    b = ProjectWorkspace.create(
        tmp_path, question="Peer assessment?", title="Peer grading",
        research_mode="evidence_review")
    ra = start_run(a, purpose="a", capabilities=[], execution_backend="sequential_main_agent")
    rb = start_run(b, purpose="b", capabilities=[], execution_backend="sequential_main_agent")
    assert ra["project_id"] == a.project_id
    assert rb["project_id"] == b.project_id
    assert not (a.path / "runs" / rb["run_id"]).exists()
