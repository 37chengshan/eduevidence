"""Tribunal direct-learning-evidence gate tests (P0 science gate).

ADOPT requires High confidence + decisive support_adoption Studies whose
findings measure a learning outcome with directness == 2. Task-performance
outcomes, missing outcomes and non-direct links all fail closed to PILOT.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.graph_store import GraphStore, GraphMutation  # noqa: E402
from engine.project import ProjectWorkspace  # noqa: E402
from engine.run import start_run  # noqa: E402
from engine.tribunal import adjudicate  # noqa: E402


def _src(sid):
    return {"source_id": sid, "origin": "external", "source_type": "journal_article",
            "canonical_locator": f"https://doi.org/10.0000/{sid}",
            "validation_status": "valid", "content_hash": None, "extensions": {}}


def _study(sid, key):
    return {"study_id": sid, "source_ids": [f"SRC-{sid}"], "study_design": "RCT",
            "population": "undergrads", "sample_ids": [f"S-{sid}"], "sample_size": 50,
            "intervention": "AI tutor", "comparison": "none",
            "independence_key": key, "identity_status": "resolved", "extensions": {}}


def _finding(fid, study):
    return {"finding_id": fid, "study_id": study, "finding_type": "quantitative_effect",
            "outcome_id": "OUT-1", "measure": "post", "timepoint": None,
            "effect_direction": "positive", "effect_estimate": None,
            "raw_result_text": "x", "source_locator": "p1", "extensions": {}}


def _outcome(outcome_type):
    return {"outcome_id": "OUT-1", "name": "post", "outcome_type": outcome_type,
            "extensions": {}}


def _claim(cid="CLM-1"):
    return {"claim_id": cid, "text": "AI tutors improve learning",
            "claim_type": "effectiveness", "primary_outcome_ids": ["OUT-1"],
            "scope": "undergrads", "created_in_revision": 1, "status": "active",
            "extensions": {}}


def _link(lid, finding, directness=2):
    return {"evidence_link_id": lid, "finding_id": finding, "claim_id": "CLM-1",
            "relation_to_claim": "support", "decision_implication": "support_adoption",
            "directness": directness, "applicability": {"scope_match": "direct"},
            "reasoning_note": "r", "created_in_revision": 1, "extensions": {}}


def _audit(aid, study):
    return {"audit_id": aid, "study_id": study, "policy_version": "2026-08-12.v2",
            "design_quality": 2, "sample_quality": 2, "measurement_validity": 2,
            "temporal_strength": 2, "bias_checks": [], "confounders": [],
            "limitations": [], "overall_status": "pass",
            "audited_at": "2026-08-12T00:00:00+00:00", "extensions": {}}


@pytest.fixture
def strong_graph(tmp_path):
    """Four independent strong supportive studies (High confidence base)."""
    ws = ProjectWorkspace.create(tmp_path, question="q?", title="t",
                                 research_mode="evidence_review")
    store = GraphStore.create(ws)
    run = start_run(ws, purpose="t", capabilities=[],
                    execution_backend="sequential_main_agent")
    sources = [_src(f"SRC-STU-{c}") for c in "ABCD"]
    studies = [_study(f"STU-{c}", f"k{c}") for c in "ABCD"]
    findings = [_finding(f"FND-{c}1", f"STU-{c}") for c in "ABCD"]
    links = [_link(f"LNK-{c}1", f"FND-{c}1") for c in "ABCD"]
    audits = [_audit(f"AUD-{c}", f"STU-{c}") for c in "ABCD"]
    store.commit(run_id=run["run_id"], reason="bundle",
                 mutation=GraphMutation(
                     upserts={"sources": sources, "studies": studies,
                              "findings": findings, "outcomes": [_outcome("learning")],
                              "claims": [_claim()], "evidence_links": links,
                              "audits": audits}, retire_ids={}))
    return store, ws


def test_high_support_with_learning_evidence_adopts(strong_graph):
    store, ws = strong_graph
    snap = adjudicate(store, project=ws)
    assert snap["decision"] == "ADOPT"
    assert snap["extensions"]["confidence_components"]["has_direct_learning_evidence"] is True


def test_task_performance_outcome_downgrades_to_pilot(tmp_path):
    ws = ProjectWorkspace.create(tmp_path, question="q?", title="t",
                                 research_mode="evidence_review")
    store = GraphStore.create(ws)
    run = start_run(ws, purpose="t", capabilities=[],
                    execution_backend="sequential_main_agent")
    sources = [_src(f"SRC-STU-{c}") for c in "ABCD"]
    studies = [_study(f"STU-{c}", f"k{c}") for c in "ABCD"]
    findings = [_finding(f"FND-{c}1", f"STU-{c}") for c in "ABCD"]
    links = [_link(f"LNK-{c}1", f"FND-{c}1") for c in "ABCD"]
    audits = [_audit(f"AUD-{c}", f"STU-{c}") for c in "ABCD"]
    store.commit(run_id=run["run_id"], reason="bundle",
                 mutation=GraphMutation(
                     upserts={"sources": sources, "studies": studies,
                              "findings": findings,
                              "outcomes": [_outcome("task_performance")],
                              "claims": [_claim()], "evidence_links": links,
                              "audits": audits}, retire_ids={}))
    snap = adjudicate(store, project=ws)
    assert snap["decision"] == "PILOT"
    assert snap["extensions"]["confidence_components"]["has_direct_learning_evidence"] is False


def test_indirect_link_downgrades_to_pilot(tmp_path):
    ws = ProjectWorkspace.create(tmp_path, question="q?", title="t",
                                 research_mode="evidence_review")
    store = GraphStore.create(ws)
    run = start_run(ws, purpose="t", capabilities=[],
                    execution_backend="sequential_main_agent")
    sources = [_src(f"SRC-STU-{c}") for c in "ABCD"]
    studies = [_study(f"STU-{c}", f"k{c}") for c in "ABCD"]
    findings = [_finding(f"FND-{c}1", f"STU-{c}") for c in "ABCD"]
    links = [_link(f"LNK-{c}1", f"FND-{c}1", directness=1) for c in "ABCD"]
    audits = [_audit(f"AUD-{c}", f"STU-{c}") for c in "ABCD"]
    store.commit(run_id=run["run_id"], reason="bundle",
                 mutation=GraphMutation(
                     upserts={"sources": sources, "studies": studies,
                              "findings": findings, "outcomes": [_outcome("learning")],
                              "claims": [_claim()], "evidence_links": links,
                              "audits": audits}, retire_ids={}))
    snap = adjudicate(store, project=ws)
    assert snap["decision"] == "PILOT"
    assert snap["extensions"]["confidence_components"]["has_direct_learning_evidence"] is False


def test_process_outcome_fails_closed(tmp_path):
    """Process/risk outcomes are not learning: High + support stays PILOT."""
    ws = ProjectWorkspace.create(tmp_path, question="q?", title="t",
                                 research_mode="evidence_review")
    store = GraphStore.create(ws)
    run = start_run(ws, purpose="t", capabilities=[],
                    execution_backend="sequential_main_agent")
    sources = [_src(f"SRC-STU-{c}") for c in "ABCD"]
    studies = [_study(f"STU-{c}", f"k{c}") for c in "ABCD"]
    findings = [_finding(f"FND-{c}1", f"STU-{c}") for c in "ABCD"]
    links = [_link(f"LNK-{c}1", f"FND-{c}1") for c in "ABCD"]
    audits = [_audit(f"AUD-{c}", f"STU-{c}") for c in "ABCD"]
    store.commit(run_id=run["run_id"], reason="bundle",
                 mutation=GraphMutation(
                     upserts={"sources": sources, "studies": studies,
                              "findings": findings,
                              "outcomes": [_outcome("process")],
                              "claims": [_claim()], "evidence_links": links,
                              "audits": audits}, retire_ids={}))
    snap = adjudicate(store, project=ws)
    assert snap["decision"] == "PILOT"
    assert snap["extensions"]["confidence_components"]["has_direct_learning_evidence"] is False