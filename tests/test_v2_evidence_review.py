"""Graph-oriented evidence review mutation tests."""

import pytest

from engine.evidence_review import (
    ingest_validated_sources, ingest_extracted_studies_findings,
    ingest_methodology_audits, ingest_claims_links,
)
from engine.graph_store import GraphStore, GraphMutation
from engine.project import ProjectWorkspace
from engine.run import start_run


def _setup(tmp_path):
    ws = ProjectWorkspace.create(tmp_path, question="evidence review?",
                                 title="er", research_mode="evidence_review")
    store = GraphStore.create(ws)
    run = start_run(ws, purpose="review", capabilities=[],
                    execution_backend="sequential_main_agent")
    return ws, store, run


def _src(sid="SRC-1", status="valid"):
    return {
        "source_id": sid, "origin": "external", "source_type": "journal_article",
        "canonical_locator": f"https://doi.org/10.0000/{sid}", "validation_status": status,
        "content_hash": None, "extensions": {},
    }


def _study(sid="STU-1"):
    return {
        "study_id": sid, "source_ids": ["SRC-1"], "study_design": "RCT",
        "population": "undergrads", "sample_ids": ["S1"], "sample_size": 50,
        "intervention": "AI tutor", "comparison": "none",
        "independence_key": "doi:10.0000/SRC-1#s1", "identity_status": "resolved",
        "extensions": {},
    }


def _finding(fid="FND-1", direction="positive", study="STU-1"):
    return {
        "finding_id": fid, "study_id": study, "finding_type": "quantitative_effect",
        "outcome_id": "OUT-1", "measure": "post score", "timepoint": "immediate",
        "effect_direction": direction, "effect_estimate": None,
        "raw_result_text": "observed", "source_locator": "p1", "extensions": {},
    }


def _audit(aid="AUD-1", study="STU-1"):
    return {
        "audit_id": aid, "study_id": study, "policy_version": "2026-08-12.v2",
        "design_quality": 2, "sample_quality": 2, "measurement_validity": 2,
        "temporal_strength": 2, "bias_checks": [], "confounders": [],
        "limitations": [], "overall_status": "pass",
        "audited_at": "2026-08-12T00:00:00+00:00", "extensions": {},
    }


def _claim(cid="CLM-1"):
    return {
        "claim_id": cid, "text": "AI tutors improve learning", "claim_type": "effectiveness",
        "primary_outcome_ids": ["OUT-1"], "scope": "undergrads",
        "created_in_revision": 1, "status": "active", "extensions": {},
    }


def _link(lid="LNK-1", fid="FND-1", cid="CLM-1", relation="support",
          implication="support_adoption"):
    return {
        "evidence_link_id": lid, "finding_id": fid, "claim_id": cid,
        "relation_to_claim": relation, "decision_implication": implication,
        "directness": 2, "applicability": {"scope_match": "direct"},
        "reasoning_note": "r", "created_in_revision": 1, "extensions": {},
    }


def _outcome(oid="OUT-1"):
    return {
        "outcome_id": oid, "name": "post score", "outcome_type": "learning",
        "extensions": {},
    }


def test_invalid_source_status_cannot_enter_graph(tmp_path):
    _, store, run = _setup(tmp_path)
    with pytest.raises(ValueError):
        ingest_validated_sources(store, run_id=run["run_id"],
                                 sources=[_src(status="failed")])
    assert store.read_table("sources") == []


def test_accepted_partial_source_may_enter(tmp_path):
    _, store, run = _setup(tmp_path)
    ingest_validated_sources(store, run_id=run["run_id"],
                             sources=[_src(status="accepted_partial")])
    assert len(store.read_table("sources")) == 1


def test_finding_without_source_provenance_rejected(tmp_path):
    _, store, run = _setup(tmp_path)
    # no sources at all -> study provenance absent
    with pytest.raises(ValueError):
        ingest_extracted_studies_findings(
            store, run_id=run["run_id"], studies=[_study()], findings=[_finding()])
    assert store.read_table("studies") == []


def test_finding_without_study_rejected(tmp_path):
    _, store, run = _setup(tmp_path)
    ingest_validated_sources(store, run_id=run["run_id"], sources=[_src()])
    with pytest.raises(ValueError):
        ingest_extracted_studies_findings(
            store, run_id=run["run_id"], studies=[], findings=[_finding()])


def test_negative_finding_supported_by_claim_keeps_direction(tmp_path):
    _, store, run = _setup(tmp_path)
    ingest_validated_sources(store, run_id=run["run_id"], sources=[_src()])
    store.commit(run_id=run["run_id"], reason="outcome",
                 mutation=GraphMutation(upserts={"outcomes": [_outcome()]},
                                        retire_ids={}))
    ingest_extracted_studies_findings(
        store, run_id=run["run_id"], studies=[_study()],
        findings=[_finding(direction="negative")])
    ingest_claims_links(store, run_id=run["run_id"], claims=[_claim()],
                        links=[_link(relation="support",
                                     implication="support_adoption")])
    from engine.semantics import finding_effect
    fnd = store.get("findings", "FND-1")
    assert finding_effect(fnd) == "negative"
    link = store.get("evidence_links", "LNK-1")
    assert link["relation_to_claim"] == "support"


def test_counter_evidence_finding_preserved(tmp_path):
    _, store, run = _setup(tmp_path)
    ingest_validated_sources(store, run_id=run["run_id"], sources=[_src()])
    store.commit(run_id=run["run_id"], reason="outcome",
                 mutation=GraphMutation(upserts={"outcomes": [_outcome()]},
                                        retire_ids={}))
    ingest_extracted_studies_findings(
        store, run_id=run["run_id"], studies=[_study()],
        findings=[_finding(fid="FND-neg", direction="negative")])
    # counter-evidence link with oppose implication must survive ingest
    ingest_claims_links(store, run_id=run["run_id"], claims=[_claim()],
                        links=[_link(lid="LNK-neg", fid="FND-neg",
                                     relation="contradict",
                                     implication="oppose_adoption")])
    links = store.read_table("evidence_links")
    assert len(links) == 1
    assert links[0]["decision_implication"] == "oppose_adoption"


def test_audit_requires_existing_study(tmp_path):
    _, store, run = _setup(tmp_path)
    with pytest.raises(ValueError):
        ingest_methodology_audits(store, run_id=run["run_id"], audits=[_audit()])
