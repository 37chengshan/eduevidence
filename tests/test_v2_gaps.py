"""Knowledge Gap derivation tests.

A gap is derived from graph coverage vs the research frame — a task-
performance Finding never covers a retention or transfer gap.
"""

import json

from engine.gaps import derive_gaps, save_gaps
from engine.graph_store import GraphStore, GraphMutation
from engine.project import ProjectWorkspace
from engine.run import start_run


def _setup(tmp_path):
    ws = ProjectWorkspace.create(tmp_path, question="gaps?", title="g",
                                 research_mode="evidence_review")
    store = GraphStore.create(ws)
    run = start_run(ws, purpose="g", capabilities=[],
                    execution_backend="sequential_main_agent")
    return ws, store, run


def _bundle(store, run):
    store.commit(run_id=run["run_id"], reason="bundle",
                 mutation=GraphMutation(
                     upserts={
                         "sources": [{"source_id": "SRC-1", "origin": "external",
                                      "source_type": "t",
                                      "canonical_locator": "https://doi.org/10.0000/1",
                                      "validation_status": "valid",
                                      "content_hash": None, "extensions": {}}],
                         "studies": [{"study_id": "STU-1", "source_ids": ["SRC-1"],
                                      "study_design": "RCT", "population": "u",
                                      "sample_ids": ["S1"], "sample_size": 30,
                                      "intervention": "AI", "comparison": "none",
                                      "independence_key": "k1",
                                      "identity_status": "resolved",
                                      "extensions": {}}],
                         "outcomes": [{"outcome_id": "OUT-1", "name": "task completion",
                                       "outcome_type": "task_performance",
                                       "extensions": {}}],
                         "findings": [{"finding_id": "FND-1", "study_id": "STU-1",
                                       "finding_type": "quantitative_effect",
                                       "outcome_id": "OUT-1", "measure": "completion",
                                       "timepoint": "immediate",
                                       "effect_direction": "positive",
                                       "effect_estimate": None,
                                       "raw_result_text": "x", "source_locator": "p1",
                                       "extensions": {}}],
                     }, retire_ids={}))


def test_frame_retention_transfer_gaps_detected(tmp_path):
    ws, store, run = _setup(tmp_path)
    _bundle(store, run)
    frame = {
        "requested_outcomes": [
            {"name": "independent problem solving", "outcome_type": "learning"},
            {"name": "retention at 1 week", "outcome_type": "retention"},
            {"name": "transfer to no-AI", "outcome_type": "transfer"},
        ],
        "target_population": "first-year CS",
    }
    gaps = derive_gaps(store=store, frame=frame)
    types = {g["gap_type"] for g in gaps}
    assert "missing_retention" in types
    assert "missing_transfer" in types
    # the task-performance Finding does not cover retention/transfer
    ret_gap = next(g for g in gaps if g["gap_type"] == "missing_retention")
    assert "no retention-type measurement" in ret_gap["reasoning"].lower()
    assert all(g["derived_from_graph_revision"] == 1 for g in gaps)


def test_gaps_are_schema_valid(tmp_path):
    ws, store, run = _setup(tmp_path)
    _bundle(store, run)
    from engine.contracts import validate_record
    gaps = derive_gaps(store=store, frame={"requested_outcomes": ["retention at 1 week"]})
    for g in gaps:
        assert validate_record("knowledge-gap", g) == []
        assert g["gap_id"].startswith("GAP-")
        assert g["status"] == "open"
        # frame-level gaps carry no claim binding: related ids stay empty
        assert g["related_outcome_ids"] == []


def test_task_performance_only_flag_no_false_learning_claim(tmp_path):
    ws, store, run = _setup(tmp_path)
    _bundle(store, run)
    frame = {"requested_outcomes": [{"name": "post score", "outcome_type": "learning"},
                                    {"name": "completion", "outcome_type": "task_performance"}]}
    gaps = derive_gaps(store=store, frame=frame)
    types = {g["gap_type"] for g in gaps}
    # learning requested but only task performance covered -> missing_outcome
    assert "missing_outcome" in types
    # no gap claims the task-performance finding covers learning
    assert not any("covers learning" in g["reasoning"].lower() for g in gaps)


def test_save_gaps_roundtrip(tmp_path):
    ws, store, run = _setup(tmp_path)
    _bundle(store, run)
    gaps = derive_gaps(store=store, frame={"requested_outcomes": ["retention"]})
    path = save_gaps(ws, graph_revision=1, gaps=gaps)
    assert path.is_file()
    assert path.name == "gaps-rev-000001.jsonl"
    loaded = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(loaded) == len(gaps)
    assert loaded[0]["derived_from_graph_revision"] == 1


def test_contradiction_gap_from_synthesis(tmp_path):
    ws, store, run = _setup(tmp_path)
    store.commit(run_id=run["run_id"], reason="bundle",
                 mutation=GraphMutation(
                     upserts={
                         "sources": [{"source_id": "SRC-1", "origin": "external",
                                      "source_type": "t",
                                      "canonical_locator": "https://doi.org/10.0000/1",
                                      "validation_status": "valid",
                                      "content_hash": None, "extensions": {}},
                                     {"source_id": "SRC-2", "origin": "external",
                                      "source_type": "t",
                                      "canonical_locator": "https://doi.org/10.0000/2",
                                      "validation_status": "valid",
                                      "content_hash": None, "extensions": {}}],
                         "studies": [{"study_id": "STU-A", "source_ids": ["SRC-1"],
                                      "study_design": "RCT", "population": "u",
                                      "sample_ids": ["S1"], "sample_size": 30,
                                      "intervention": "AI", "comparison": "none",
                                      "independence_key": "kA",
                                      "identity_status": "resolved",
                                      "extensions": {}},
                                     {"study_id": "STU-B", "source_ids": ["SRC-2"],
                                      "study_design": "RCT", "population": "u",
                                      "sample_ids": ["S2"], "sample_size": 30,
                                      "intervention": "AI", "comparison": "none",
                                      "independence_key": "kB",
                                      "identity_status": "resolved",
                                      "extensions": {}}],
                         "outcomes": [{"outcome_id": "OUT-1", "name": "post",
                                       "outcome_type": "learning", "extensions": {}}],
                         "findings": [{"finding_id": "FND-A", "study_id": "STU-A",
                                       "finding_type": "quantitative_effect",
                                       "outcome_id": "OUT-1", "measure": "post",
                                       "timepoint": None, "effect_direction": "positive",
                                       "effect_estimate": None, "raw_result_text": "x",
                                       "source_locator": "p1", "extensions": {}},
                                      {"finding_id": "FND-B", "study_id": "STU-B",
                                       "finding_type": "quantitative_effect",
                                       "outcome_id": "OUT-1", "measure": "post",
                                       "timepoint": None, "effect_direction": "negative",
                                       "effect_estimate": None, "raw_result_text": "x",
                                       "source_locator": "p2", "extensions": {}}],
                         "claims": [{"claim_id": "CLM-1", "text": "AI helps",
                                     "claim_type": "effectiveness",
                                     "primary_outcome_ids": ["OUT-1"], "scope": "u",
                                     "created_in_revision": 1, "status": "active",
                                     "extensions": {}}],
                         "evidence_links": [{"evidence_link_id": "LNK-A",
                                             "finding_id": "FND-A", "claim_id": "CLM-1",
                                             "relation_to_claim": "support",
                                             "decision_implication": "support_adoption",
                                             "directness": 2,
                                             "applicability": {"scope_match": "direct"},
                                             "reasoning_note": "r",
                                             "created_in_revision": 1,
                                             "extensions": {}},
                                            {"evidence_link_id": "LNK-B",
                                             "finding_id": "FND-B", "claim_id": "CLM-1",
                                             "relation_to_claim": "contradict",
                                             "decision_implication": "oppose_adoption",
                                             "directness": 2,
                                             "applicability": {"scope_match": "direct"},
                                             "reasoning_note": "r",
                                             "created_in_revision": 1,
                                             "extensions": {}}],
                         "audits": [{"audit_id": "AUD-A", "study_id": "STU-A",
                                     "policy_version": "2026-08-12.v2",
                                     "design_quality": 2, "sample_quality": 2,
                                     "measurement_validity": 2, "temporal_strength": 2,
                                     "bias_checks": [], "confounders": [],
                                     "limitations": [], "overall_status": "pass",
                                     "audited_at": "2026-08-12T00:00:00+00:00",
                                     "extensions": {}},
                                    {"audit_id": "AUD-B", "study_id": "STU-B",
                                     "policy_version": "2026-08-12.v2",
                                     "design_quality": 2, "sample_quality": 2,
                                     "measurement_validity": 2, "temporal_strength": 2,
                                     "bias_checks": [], "confounders": [],
                                     "limitations": [], "overall_status": "pass",
                                     "audited_at": "2026-08-12T00:00:00+00:00",
                                     "extensions": {}}],
                     }, retire_ids={}))
    from engine.synthesis import synthesize_project
    syntheses = synthesize_project(store)
    gaps = derive_gaps(store=store, syntheses=syntheses, frame={})
    types = {g["gap_type"] for g in gaps}
    assert "unresolved_conflict" in types
