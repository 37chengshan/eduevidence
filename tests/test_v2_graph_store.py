"""Atomicity and integrity tests for the immutable GraphStore.

A commit either fully lands (HEAD + revision dir + project mirror) or leaves
the prior active revision untouched. Orphan revision dirs are ignored by
readers; HEAD/mirror divergence is detectable and repairable.
"""

import json

import pytest

from engine.graph_store import GraphStore, GraphMutation
from engine.project import ProjectWorkspace
from engine.run import start_run, finish_run


def _ws(tmp_path) -> ProjectWorkspace:
    return ProjectWorkspace.create(
        tmp_path, question="Should we allow AI coding assistants?",
        title="AI coding assistant pilot", research_mode="evidence_review")


def _run(ws):
    return start_run(ws, purpose="ingest", capabilities=["literature_search"],
                     execution_backend="sequential_main_agent")


def _src(over=None):
    rec = {
        "source_id": "SRC-aaaaaaaa",
        "origin": "external",
        "source_type": "journal_article",
        "canonical_locator": "https://doi.org/10.0000/example",
        "validation_status": "valid",
        "content_hash": "sha256:abc",
        "extensions": {},
    }
    if over:
        rec.update(over)
    return rec


def _study(over=None):
    rec = {
        "study_id": "STU-aaaaaaaa",
        "source_ids": ["SRC-aaaaaaaa"],
        "study_design": "RCT",
        "population": "first-year CS students",
        "sample_ids": ["S1"],
        "sample_size": 120,
        "intervention": "AI tutor",
        "comparison": "no AI",
        "independence_key": "doi:10.0000/example#study1",
        "identity_status": "resolved",
        "extensions": {},
    }
    if over:
        rec.update(over)
    return rec


def _outcome(over=None):
    rec = {
        "outcome_id": "OUT-aaaaaaaa",
        "name": "independent problem solving",
        "outcome_type": "learning",
        "extensions": {},
    }
    if over:
        rec.update(over)
    return rec


def _finding(over=None):
    rec = {
        "finding_id": "FND-aaaaaaaa",
        "study_id": "STU-aaaaaaaa",
        "finding_type": "quantitative_effect",
        "outcome_id": "OUT-aaaaaaaa",
        "measure": "post-test score",
        "timepoint": "immediate",
        "effect_direction": "positive",
        "effect_estimate": None,
        "raw_result_text": "intervention group scored higher",
        "source_locator": "p.12, Table 3",
        "extensions": {},
    }
    if over:
        rec.update(over)
    return rec


def _claim(over=None):
    rec = {
        "claim_id": "CLM-aaaaaaaa",
        "text": "AI tutors improve independent problem solving",
        "claim_type": "effectiveness",
        "primary_outcome_ids": ["OUT-aaaaaaaa"],
        "scope": "first-year CS, 16-week course",
        "created_in_revision": 1,
        "status": "active",
        "extensions": {},
    }
    if over:
        rec.update(over)
    return rec


def _link(over=None):
    rec = {
        "evidence_link_id": "LNK-aaaaaaaa",
        "finding_id": "FND-aaaaaaaa",
        "claim_id": "CLM-aaaaaaaa",
        "relation_to_claim": "support",
        "decision_implication": "support_adoption",
        "directness": 2,
        "applicability": {"scope_match": "direct"},
        "reasoning_note": "same population and outcome",
        "created_in_revision": 1,
        "extensions": {},
    }
    if over:
        rec.update(over)
    return rec


def _audit(over=None):
    rec = {
        "audit_id": "AUD-aaaaaaaa",
        "study_id": "STU-aaaaaaaa",
        "policy_version": "2026-08-12.v2",
        "design_quality": 2,
        "sample_quality": 1,
        "measurement_validity": 2,
        "temporal_strength": 1,
        "bias_checks": [],
        "confounders": [],
        "limitations": [],
        "overall_status": "pass",
        "audited_at": "2026-08-12T00:00:00+00:00",
        "extensions": {},
    }
    if over:
        rec.update(over)
    return rec


def _valid_bundle():
    """A complete, internally consistent scientific bundle."""
    return GraphMutation(
        upserts={
            "sources": [_src()],
            "studies": [_study()],
            "outcomes": [_outcome()],
            "findings": [_finding()],
            "claims": [_claim()],
            "evidence_links": [_link()],
            "audits": [_audit()],
        },
        retire_ids={},
    )


def _head_revision(ws) -> int:
    return int((ws.path / "graph" / "HEAD").read_text(encoding="utf-8").strip())


def _rev_dir(ws, n: int) -> "object":
    return ws.path / "graph" / "revisions" / f"rev-{n:06d}"


def _rev_manifest(ws, n: int) -> dict:
    return json.loads((_rev_dir(ws, n) / "manifest.json").read_text(encoding="utf-8"))


# ---- cross-entity rejection ---------------------------------------------

def test_finding_referencing_missing_study_rejected(tmp_path):
    ws = _ws(tmp_path)
    store = GraphStore.create(ws)
    run = _run(ws)
    mut = _valid_bundle()
    mut.upserts["studies"] = []  # break the reference
    with pytest.raises(ValueError):
        store.commit(run_id=run["run_id"], reason="broken", mutation=mut)


def test_link_referencing_missing_finding_or_claim_rejected(tmp_path):
    ws, store = _ws(tmp_path), GraphStore.create(_ws(tmp_path))
    run = _run(ws)
    mut = _valid_bundle()
    mut.upserts["findings"] = []
    with pytest.raises(ValueError):
        store.commit(run_id=run["run_id"], reason="broken link", mutation=mut)
    mut2 = _valid_bundle()
    mut2.upserts["claims"] = []
    with pytest.raises(ValueError):
        store.commit(run_id=run["run_id"], reason="broken link", mutation=mut2)


def test_audit_referencing_missing_study_rejected(tmp_path):
    ws, store = _ws(tmp_path), GraphStore.create(_ws(tmp_path))
    run = _run(ws)
    mut = _valid_bundle()
    mut.upserts["studies"] = []
    with pytest.raises(ValueError):
        store.commit(run_id=run["run_id"], reason="broken audit", mutation=mut)


def test_finding_referencing_missing_outcome_rejected(tmp_path):
    ws, store = _ws(tmp_path), GraphStore.create(_ws(tmp_path))
    run = _run(ws)
    mut = _valid_bundle()
    mut.upserts["outcomes"] = []
    with pytest.raises(ValueError):
        store.commit(run_id=run["run_id"], reason="broken outcome", mutation=mut)


# ---- atomicity -----------------------------------------------------------

def test_valid_commit_increments_revision_exactly_once(tmp_path):
    ws = _ws(tmp_path)
    store = GraphStore.create(ws)
    assert ws.current_revision() == 0
    rev = store.commit(run_id=_run(ws)["run_id"], reason="initial ingest",
                       mutation=_valid_bundle())
    assert rev.revision == 1
    assert ws.current_revision() == 1
    assert _head_revision(ws) == 1


def test_failed_commit_leaves_state_untouched(tmp_path):
    ws = _ws(tmp_path)
    store = GraphStore.create(ws)
    before_head = _head_revision(ws)
    before_mirror = ws.current_revision()
    mut = _valid_bundle()
    mut.upserts["studies"] = []  # broken -> must not commit
    with pytest.raises(ValueError):
        store.commit(run_id=_run(ws)["run_id"], reason="broken", mutation=mut)
    assert _head_revision(ws) == before_head
    assert ws.current_revision() == before_mirror
    assert not _rev_dir(ws, 1).exists()
    # no orphan tmp dirs left behind
    leftovers = [p for p in (ws.path / "graph" / "revisions").iterdir()
                 if p.name.startswith(".tmp-")]
    assert leftovers == []


def test_commit_creates_complete_immutable_snapshot(tmp_path):
    ws = _ws(tmp_path)
    store = GraphStore.create(ws)
    store.commit(run_id=_run(ws)["run_id"], reason="initial ingest",
                 mutation=_valid_bundle())
    rev1 = _rev_dir(ws, 1)
    assert (rev1 / "manifest.json").is_file()
    for table in ("sources", "studies", "findings", "outcomes",
                  "claims", "evidence_links", "audits"):
        assert (rev1 / f"{table}.jsonl").is_file()
    # a second commit must not rewrite rev-000001
    store.commit(run_id=_run(ws)["run_id"], reason="second ingest",
                 mutation=_valid_bundle())
    assert _rev_manifest(ws, 1)["revision"] == 1
    assert (rev1 / "sources.jsonl").read_text(encoding="utf-8") != ""


def test_revision_hashes_stable_and_consistent(tmp_path):
    ws = _ws(tmp_path)
    store = GraphStore.create(ws)
    rev1 = store.commit(run_id=_run(ws)["run_id"], reason="initial",
                        mutation=_valid_bundle())
    # re-reading the same snapshot yields the same canonical hash
    assert store.canonical_hash() == rev1.after_hash
    m1 = _rev_manifest(ws, 1)
    assert m1["after_hash"] == rev1.after_hash
    # before hash of first revision is the empty-graph hash
    empty = GraphStore.empty_graph_hash()
    assert m1["before_hash"] == empty


def test_orphan_revision_ignored_by_readers(tmp_path):
    ws = _ws(tmp_path)
    store = GraphStore.create(ws)
    store.commit(run_id=_run(ws)["run_id"], reason="initial",
                 mutation=_valid_bundle())
    # fabricate an orphan rev-000002 not referenced by HEAD
    orphan = _rev_dir(ws, 2)
    orphan.mkdir(parents=True)
    (orphan / "sources.jsonl").write_text(
        json.dumps(_src({"source_id": "SRC-orphan"})) + "\n", encoding="utf-8")
    (orphan / "manifest.json").write_text("{}", encoding="utf-8")
    assert _head_revision(ws) == 1
    assert store.read_table("sources")[0]["source_id"] == "SRC-aaaaaaaa"
    assert store.get("sources", "SRC-orphan") is None


def test_head_mirror_divergence_detected_and_repairable(tmp_path):
    ws = _ws(tmp_path)
    store = GraphStore.create(ws)
    store.commit(run_id=_run(ws)["run_id"], reason="initial",
                 mutation=_valid_bundle())
    # simulate a crash between HEAD write and project mirror write
    ws.update_manifest(graph_revision=0)
    assert _head_revision(ws) == 1
    assert ws.current_revision() == 0
    problems = store.validate()
    assert any("graph_revision" in p and "HEAD" in p for p in problems)
    # repair without rewriting the active revision
    store.repair_head_mirror()
    assert ws.current_revision() == 1
    assert store.validate() == []


# ---- basic reads ---------------------------------------------------------

def test_upsert_replaces_and_retire_removes(tmp_path):
    ws = _ws(tmp_path)
    store = GraphStore.create(ws)
    run = _run(ws)
    store.commit(run_id=run["run_id"], reason="initial", mutation=_valid_bundle())
    src2 = _src({"source_id": "SRC-bbbbbbbb",
                 "canonical_locator": "https://doi.org/10.0000/other"})
    store.commit(
        run_id=run["run_id"], reason="add source",
        mutation=GraphMutation(upserts={"sources": [src2]}, retire_ids={}))
    assert store.get("sources", "SRC-bbbbbbbb")["source_id"] == "SRC-bbbbbbbb"
    store.commit(
        run_id=run["run_id"], reason="retire source",
        mutation=GraphMutation(upserts={}, retire_ids={"sources": ["SRC-bbbbbbbb"]}))
    assert store.get("sources", "SRC-bbbbbbbb") is None
    assert len(store.read_table("sources")) == 1


def test_mirror_write_failure_rolls_back_head(tmp_path, monkeypatch):
    """If project.json mirror update fails after HEAD advanced, HEAD rolls
    back: the caller never sees a failure for a landed commit."""
    ws = _ws(tmp_path)
    store = GraphStore.create(ws)
    run = _run(ws)
    from engine.project import ProjectWorkspace as PW
    original = PW.update_manifest

    def failing_update(self, **changes):
        if changes.get("graph_revision") == 1:
            raise OSError("simulated mirror write failure")
        return original(self, **changes)

    monkeypatch.setattr(PW, "update_manifest", failing_update)
    with pytest.raises(OSError):
        store.commit(run_id=run["run_id"], reason="x", mutation=_valid_bundle())
    # HEAD rolled back; the orphan rev dir is ignored by readers
    assert _head_revision(ws) == 0
    assert store.active_revision() == 0
    # repair path: a later successful commit works from revision 0
    monkeypatch.setattr(PW, "update_manifest", original)
    rev = store.commit(run_id=run["run_id"], reason="retry",
                       mutation=_valid_bundle())
    assert rev.revision == 1
    assert ws.current_revision() == 1
