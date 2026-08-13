"""Isolation tests for the snapshot-based Shared Research Library.

Research facts may be reused; interpretations are project-contextual. A
library update must never silently change an existing Project's conclusions:
only an explicit import/sync advances the Project graph.
"""

import json

from engine.library import ResearchLibrary
from engine.project import ProjectWorkspace
from engine.run import start_run


def _src(sid="SRC-lib1", locator="https://doi.org/10.0000/lib1", **over):
    rec = {
        "source_id": sid, "origin": "external", "source_type": "journal_article",
        "canonical_locator": locator, "validation_status": "valid",
        "content_hash": None, "extensions": {},
    }
    rec.update(over)
    return rec


def _study(sid="STU-lib1"):
    return {
        "study_id": sid, "source_ids": ["SRC-lib1"], "study_design": "RCT",
        "population": "undergrads", "sample_ids": ["S1"], "sample_size": 100,
        "intervention": "AI tutor", "comparison": "none",
        "independence_key": "doi:10.0000/lib1#study1", "identity_status": "resolved",
        "extensions": {},
    }


def _finding(fid="FND-lib1", **over):
    rec = {
        "finding_id": fid, "study_id": "STU-lib1", "finding_type": "quantitative_effect",
        "outcome_id": "OUT-lib1", "measure": "post score", "timepoint": "immediate",
        "effect_direction": "positive", "effect_estimate": None,
        "raw_result_text": "positive", "source_locator": "p3", "extensions": {},
    }
    rec.update(over)
    return rec


def _audit(aid="AUD-lib1"):
    return {
        "audit_id": aid, "study_id": "STU-lib1", "policy_version": "2026-08-12.v2",
        "design_quality": 2, "sample_quality": 1, "measurement_validity": 2,
        "temporal_strength": 1, "bias_checks": [], "confounders": [],
        "limitations": [], "overall_status": "pass",
        "audited_at": "2026-08-12T00:00:00+00:00", "extensions": {},
    }


def _project(tmp_path):
    return ProjectWorkspace.create(tmp_path, question="library isolation?",
                                   title="lib test", research_mode="evidence_review")


def _run(ws):
    return start_run(ws, purpose="import", capabilities=[],
                     execution_backend="sequential_main_agent")


# ---- basic revision model ------------------------------------------------

def test_open_creates_library_layout(tmp_path):
    lib = ResearchLibrary.open(tmp_path)
    assert lib.active_revision() == 0
    assert (tmp_path / "library" / "revisions").is_dir()
    assert (tmp_path / "library" / "HEAD").is_file()


def test_add_verified_bundle_creates_immutable_revision(tmp_path):
    lib = ResearchLibrary.open(tmp_path)
    rev = lib.add_verified_bundle(
        sources=[_src()], studies=[_study()],
        findings=[_finding()], audits=[_audit()])
    assert rev == 1
    assert lib.active_revision() == 1
    rev_dir = tmp_path / "library" / "revisions" / "rev-000001"
    for table in ("sources", "studies", "findings", "audits"):
        assert (rev_dir / f"{table}.jsonl").is_file()
    assert (rev_dir / "manifest.json").is_file()


def test_find_source_by_locator(tmp_path):
    lib = ResearchLibrary.open(tmp_path)
    lib.add_verified_bundle(sources=[_src()], studies=[], findings=[], audits=[])
    assert lib.find_source("https://doi.org/10.0000/lib1")["source_id"] == "SRC-lib1"
    assert lib.find_source("https://doi.org/10.0000/nope") is None


def test_library_rejects_invalid_entity(tmp_path):
    lib = ResearchLibrary.open(tmp_path)
    try:
        lib.add_verified_bundle(
            sources=[_src(validation_status="bogus")], studies=[],
            findings=[], audits=[])
        assert False, "expected ValueError"
    except ValueError:
        pass
    assert lib.active_revision() == 0


# ---- snapshot isolation --------------------------------------------------

def test_import_snapshot_into_project(tmp_path):
    lib = ResearchLibrary.open(tmp_path)
    lib.add_verified_bundle(sources=[_src()], studies=[_study()],
                            findings=[_finding()], audits=[_audit()])
    ws = _project(tmp_path)
    rev = lib.import_snapshot(project=ws, source_ids=["SRC-lib1"],
                              run_id=_run(ws)["run_id"])
    assert rev.revision == 1
    assert ws.current_revision() == 1
    store = rev  # GraphRevision returned; read via GraphStore below
    from engine.graph_store import GraphStore
    store = GraphStore.create(ws)
    assert len(store.read_table("sources")) == 1
    assert len(store.read_table("studies")) == 1
    assert len(store.read_table("findings")) == 1
    assert len(store.read_table("audits")) == 1
    # imported facts carry origin metadata binding them to library rev 1
    src = store.read_table("sources")[0]
    assert src["extensions"]["origin"]["library_revision"] == 1
    assert src["extensions"]["origin"]["library_entity_id"] == "SRC-lib1"


def test_library_update_does_not_change_imported_project(tmp_path):
    lib = ResearchLibrary.open(tmp_path)
    lib.add_verified_bundle(sources=[_src()], studies=[_study()],
                            findings=[_finding()], audits=[_audit()])
    ws = _project(tmp_path)
    lib.import_snapshot(project=ws, source_ids=["SRC-lib1"], run_id=_run(ws)["run_id"])
    from engine.graph_store import GraphStore
    before_hash = GraphStore.create(ws).canonical_hash()

    # library advances to revision 2 with a changed finding
    lib.add_verified_bundle(
        sources=[_src()],
        studies=[_study()],
        findings=[_finding(effect_direction="negative")],
        audits=[_audit()])
    assert lib.active_revision() == 2

    # the Project graph is untouched until an explicit import/sync
    assert GraphStore.create(ws).canonical_hash() == before_hash
    assert ws.current_revision() == 1

    # diff reports the changed facts (the finding changed direction)
    diff = lib.diff_project_snapshot(project=ws, source_ids=["SRC-lib1"])
    assert diff["changed"] == ["FND-lib1"]
    assert diff["added"] == []
    assert diff["removed"] == []

    # explicit sync advances the project and changes its hash
    lib.import_snapshot(project=ws, source_ids=["SRC-lib1"], run_id=_run(ws)["run_id"])
    assert ws.current_revision() == 2
    assert GraphStore.create(ws).canonical_hash() != before_hash
    fnd = [f for f in GraphStore.create(ws).read_table("findings")][0]
    assert fnd["effect_direction"] == "negative"
    assert fnd["extensions"]["origin"]["library_revision"] == 2


def test_import_unknown_source_raises(tmp_path):
    lib = ResearchLibrary.open(tmp_path)
    lib.add_verified_bundle(sources=[_src()], studies=[], findings=[], audits=[])
    ws = _project(tmp_path)
    try:
        lib.import_snapshot(project=ws, source_ids=["SRC-missing"],
                            run_id=_run(ws)["run_id"])
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "SRC-missing" in str(exc)
    assert ws.current_revision() == 0


def test_library_never_writes_project_files(tmp_path):
    lib = ResearchLibrary.open(tmp_path)
    lib.add_verified_bundle(sources=[_src()], studies=[_study()],
                            findings=[_finding()], audits=[_audit()])
    ws = _project(tmp_path)
    lib.import_snapshot(project=ws, source_ids=["SRC-lib1"], run_id=_run(ws)["run_id"])
    # the library revision contains the entities; the project holds its own copy
    lib_rev_dir = tmp_path / "library" / "revisions" / "rev-000001"
    proj_rev_dir = ws.path / "graph" / "revisions" / "rev-000001"
    assert (lib_rev_dir / "findings.jsonl").is_file()
    assert (proj_rev_dir / "findings.jsonl").is_file()
    assert json.loads((proj_rev_dir / "findings.jsonl").read_text().strip())["extensions"]["origin"]


def test_import_multi_source_study_transitively_imports_all_sources(tmp_path):
    """A Study citing SRC-A+SRC-B imported with source_ids=[SRC-A] must pull
    SRC-B transitively instead of failing cross-entity validation."""
    lib = ResearchLibrary.open(tmp_path)
    lib.add_verified_bundle(
        sources=[_src("SRC-lib1", "https://doi.org/10.0000/lib1"),
                 _src("SRC-lib2", "https://doi.org/10.0000/lib2")],
        studies=[_study()], findings=[], audits=[])
    # rewrite the study to cite both sources
    from engine.graph_store import GraphStore
    ws = _project(tmp_path)
    lib.import_snapshot(project=ws, source_ids=["SRC-lib1"],
                        run_id=_run(ws)["run_id"])
    store = GraphStore.create(ws)
    # study STU-lib1 cites only SRC-lib1 in this fixture; simulate the
    # multi-source case directly in the library revision via a second study
    lib2 = ResearchLibrary.open(tmp_path)
    ws2 = _project(tmp_path)
    # add a study citing both
    lib2.add_verified_bundle(
        sources=[_src("SRC-lib1", "https://doi.org/10.0000/lib1"),
                 _src("SRC-lib2", "https://doi.org/10.0000/lib2")],
        studies=[{"study_id": "STU-multi", "source_ids": ["SRC-lib1", "SRC-lib2"],
                  "study_design": "RCT", "population": "u", "sample_ids": ["S1"],
                  "sample_size": 50, "intervention": "AI", "comparison": "none",
                  "independence_key": "k-multi", "identity_status": "resolved",
                  "extensions": {}}],
        findings=[], audits=[])
    lib2.import_snapshot(project=ws2, source_ids=["SRC-lib1"],
                         run_id=_run(ws2)["run_id"])
    store2 = GraphStore.create(ws2)
    src_ids = {s["source_id"] for s in store2.read_table("sources")}
    assert {"SRC-lib1", "SRC-lib2"} <= src_ids
    assert any(s["study_id"] == "STU-multi" for s in store2.read_table("studies"))
    assert store2.validate() == []
