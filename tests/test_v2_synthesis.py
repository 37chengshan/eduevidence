"""Claim synthesis tests — independent-study semantics, never Finding votes."""

from engine.graph_store import GraphStore, GraphMutation
from engine.project import ProjectWorkspace
from engine.run import start_run
from engine.synthesis import synthesize_claim, synthesize_project


def _setup(tmp_path):
    ws = ProjectWorkspace.create(tmp_path, question="synthesis?", title="s",
                                 research_mode="evidence_review")
    store = GraphStore.create(ws)
    run = start_run(ws, purpose="s", capabilities=[],
                    execution_backend="sequential_main_agent")
    return store, run


def _commit_bundle(store, run, *, sources, studies, findings, outcomes,
                   claims, links, audits):
    store.commit(run_id=run["run_id"], reason="bundle",
                 mutation=GraphMutation(
                     upserts={"sources": sources, "studies": studies,
                              "findings": findings, "outcomes": outcomes,
                              "claims": claims, "evidence_links": links,
                              "audits": audits}, retire_ids={}))


def _src(sid, status="valid"):
    return {"source_id": sid, "origin": "external", "source_type": "journal_article",
            "canonical_locator": f"https://doi.org/10.0000/{sid}",
            "validation_status": status, "content_hash": None, "extensions": {}}


def _study(sid, key):
    return {"study_id": sid, "source_ids": [f"SRC-{sid}"], "study_design": "RCT",
            "population": "undergrads", "sample_ids": [f"S-{sid}"], "sample_size": 50,
            "intervention": "AI tutor", "comparison": "none",
            "independence_key": key, "identity_status": "resolved", "extensions": {}}


def _finding(fid, study, direction="positive"):
    return {"finding_id": fid, "study_id": study, "finding_type": "quantitative_effect",
            "outcome_id": "OUT-1", "measure": "post", "timepoint": None,
            "effect_direction": direction, "effect_estimate": None,
            "raw_result_text": "x", "source_locator": "p1", "extensions": {}}


def _outcome():
    return {"outcome_id": "OUT-1", "name": "post", "outcome_type": "learning",
            "extensions": {}}


def _claim(cid="CLM-1"):
    return {"claim_id": cid, "text": "AI tutors improve learning",
            "claim_type": "effectiveness", "primary_outcome_ids": ["OUT-1"],
            "scope": "undergrads", "created_in_revision": 1, "status": "active",
            "extensions": {}}


def _link(lid, finding, relation="support", implication="support_adoption",
          directness=2):
    return {"evidence_link_id": lid, "finding_id": finding, "claim_id": "CLM-1",
            "relation_to_claim": relation, "decision_implication": implication,
            "directness": directness, "applicability": {"scope_match": "direct"},
            "reasoning_note": "r", "created_in_revision": 1, "extensions": {}}


def _audit(aid, study, overall="pass"):
    return {"audit_id": aid, "study_id": study, "policy_version": "2026-08-12.v2",
            "design_quality": 2, "sample_quality": 2, "measurement_validity": 2,
            "temporal_strength": 2, "bias_checks": [], "confounders": [],
            "limitations": [], "overall_status": overall,
            "audited_at": "2026-08-12T00:00:00+00:00", "extensions": {}}


def test_five_findings_one_study_counts_as_one_study(tmp_path):
    store, run = _setup(tmp_path)
    _commit_bundle(
        store, run,
        sources=[_src("SRC-STU-A")],
        studies=[_study("STU-A", "key-A")],
        findings=[_finding(f"FND-{i}", "STU-A") for i in range(5)],
        outcomes=[_outcome()],
        claims=[_claim()],
        links=[_link(f"LNK-{i}", f"FND-{i}") for i in range(5)],
        audits=[_audit("AUD-A", "STU-A")])
    syn = synthesize_claim(store, "CLM-1")
    assert syn.status == "supported"
    assert len(syn.study_ids) == 1
    assert len(syn.supporting_link_ids) == 5
    # 5 findings from one study == 1 vote
    assert syn.independent_sample_keys == ("key-A",)


def test_second_independent_contradictory_study_makes_contested(tmp_path):
    store, run = _setup(tmp_path)
    _commit_bundle(
        store, run,
        sources=[_src("SRC-STU-A"), _src("SRC-STU-B")],
        studies=[_study("STU-A", "key-A"), _study("STU-B", "key-B")],
        findings=[_finding("FND-A1", "STU-A", "positive"),
                  _finding("FND-B1", "STU-B", "negative")],
        outcomes=[_outcome()],
        claims=[_claim()],
        links=[_link("LNK-A1", "FND-A1", "support", "support_adoption"),
               _link("LNK-B1", "FND-B1", "contradict", "oppose_adoption")],
        audits=[_audit("AUD-A", "STU-A"), _audit("AUD-B", "STU-B")])
    syn = synthesize_claim(store, "CLM-1")
    assert syn.status == "contested"
    assert len(syn.study_ids) == 2


def test_methodology_fail_study_cannot_support(tmp_path):
    store, run = _setup(tmp_path)
    _commit_bundle(
        store, run,
        sources=[_src("SRC-STU-A")],
        studies=[_study("STU-A", "key-A")],
        findings=[_finding("FND-A1", "STU-A", "positive")],
        outcomes=[_outcome()],
        claims=[_claim()],
        links=[_link("LNK-A1", "FND-A1")],
        audits=[_audit("AUD-A", "STU-A", overall="fail")])
    syn = synthesize_claim(store, "CLM-1")
    assert syn.status == "insufficient"
    assert syn.study_ids == ()


def test_no_direct_studies_is_insufficient(tmp_path):
    store, run = _setup(tmp_path)
    _commit_bundle(
        store, run,
        sources=[_src("SRC-STU-A")],
        studies=[_study("STU-A", "key-A")],
        findings=[_finding("FND-A1", "STU-A", "positive")],
        outcomes=[_outcome()],
        claims=[_claim()],
        links=[_link("LNK-A1", "FND-A1", "neutral", "neutral")],
        audits=[_audit("AUD-A", "STU-A")])
    syn = synthesize_claim(store, "CLM-1")
    assert syn.status == "insufficient"


def test_contradiction_only_is_refuted(tmp_path):
    store, run = _setup(tmp_path)
    _commit_bundle(
        store, run,
        sources=[_src("SRC-STU-A")],
        studies=[_study("STU-A", "key-A")],
        findings=[_finding("FND-A1", "STU-A", "negative")],
        outcomes=[_outcome()],
        claims=[_claim()],
        links=[_link("LNK-A1", "FND-A1", "contradict", "oppose_adoption")],
        audits=[_audit("AUD-A", "STU-A")])
    syn = synthesize_claim(store, "CLM-1")
    assert syn.status == "refuted"


def test_unresolved_study_identity_not_counted(tmp_path):
    store, run = _setup(tmp_path)
    study = _study("STU-A", "key-A")
    study["identity_status"] = "unresolved"
    _commit_bundle(
        store, run,
        sources=[_src("SRC-STU-A")],
        studies=[study],
        findings=[_finding("FND-A1", "STU-A", "positive")],
        outcomes=[_outcome()],
        claims=[_claim()],
        links=[_link("LNK-A1", "FND-A1")],
        audits=[_audit("AUD-A", "STU-A")])
    syn = synthesize_claim(store, "CLM-1")
    assert syn.status == "insufficient"
    assert syn.study_ids == ()


def test_synthesize_project_returns_all_claims(tmp_path):
    store, run = _setup(tmp_path)
    _commit_bundle(
        store, run,
        sources=[_src("SRC-STU-A")],
        studies=[_study("STU-A", "key-A")],
        findings=[_finding("FND-A1", "STU-A", "positive")],
        outcomes=[_outcome()],
        claims=[_claim(), _claim(cid="CLM-2")],
        links=[_link("LNK-A1", "FND-A1"),
               _link("LNK-A2", "FND-A1", "neutral", "neutral")],
        audits=[_audit("AUD-A", "STU-A")])
    syns = synthesize_project(store)
    assert [s.claim_id for s in syns] == ["CLM-1", "CLM-2"]


# ---- Tribunal / DecisionSnapshot (Task 15) --------------------------------

def _tribunal_setup(tmp_path, *, sources, studies, findings, links, audits):
    from engine.tribunal import adjudicate, save_decision_snapshot
    from engine.graph_store import GraphMutation
    ws = ProjectWorkspace.create(tmp_path, question="tribunal?", title="t",
                                 research_mode="evidence_review")
    store = GraphStore.create(ws)
    run = start_run(ws, purpose="t", capabilities=[],
                    execution_backend="sequential_main_agent")
    store.commit(run_id=run["run_id"], reason="bundle",
                 mutation=GraphMutation(
                     upserts={"sources": sources, "studies": studies,
                              "findings": findings, "outcomes": [_outcome()],
                              "claims": [_claim()], "evidence_links": links,
                              "audits": audits}, retire_ids={}))
    return ws, store, adjudicate, save_decision_snapshot


def test_snapshot_has_required_fields(tmp_path):
    ws, store, adjudicate, _ = _tribunal_setup(
        tmp_path,
        sources=[_src("SRC-STU-A")],
        studies=[_study("STU-A", "key-A")],
        findings=[_finding("FND-A1", "STU-A", "positive")],
        links=[_link("LNK-A1", "FND-A1")],
        audits=[_audit("AUD-A", "STU-A")])
    snap = adjudicate(store, project=ws)
    for key in ("decision", "confidence_label", "confidence_score_internal",
                "claim_assessments", "key_evidence_links", "key_risks",
                "applicability_boundary", "missing_evidence",
                "graph_revision", "policy_versions", "created_at"):
        assert key in snap
    assert snap["graph_revision"] == store.active_revision() == 1
    assert snap["decision"] in ("ADOPT", "PILOT", "REJECT", "INSUFFICIENT_EVIDENCE")
    assert snap["confidence_label"] in ("High", "Moderate", "Low", "Insufficient")


def test_snapshot_immutable_after_graph_change(tmp_path):
    ws, store, adjudicate, save = _tribunal_setup(
        tmp_path,
        sources=[_src("SRC-STU-A")],
        studies=[_study("STU-A", "key-A")],
        findings=[_finding("FND-A1", "STU-A", "positive")],
        links=[_link("LNK-A1", "FND-A1")],
        audits=[_audit("AUD-A", "STU-A")])
    snap1 = adjudicate(store, project=ws)
    p1 = save(ws, snap1)
    # graph advances to revision 2
    store.commit(run_id=start_run(ws, purpose="more", capabilities=[],
                                  execution_backend="sequential_main_agent")["run_id"],
                 reason="extra", mutation=GraphMutation(
                     upserts={"outcomes": [{"outcome_id": "OUT-2", "name": "x",
                                            "outcome_type": "learning",
                                            "extensions": {}}]}, retire_ids={}))
    snap2 = adjudicate(store, project=ws)
    assert snap2["graph_revision"] == 2
    # old snapshot file unchanged
    old = __import__("json").loads(p1.read_text())
    assert old["graph_revision"] == 1
    assert old["decision"] == snap1["decision"]


def _weak_audit(aid, study):
    return {"audit_id": aid, "study_id": study, "policy_version": "2026-08-12.v2",
            "design_quality": 0, "sample_quality": 0, "measurement_validity": 0,
            "temporal_strength": 0, "bias_checks": [], "confounders": [],
            "limitations": [], "overall_status": "concern",
            "audited_at": "2026-08-12T00:00:00+00:00", "extensions": {}}


def test_low_confidence_cannot_adopt(tmp_path):
    ws, store, adjudicate, _ = _tribunal_setup(
        tmp_path,
        sources=[_src("SRC-STU-A")],
        studies=[_study("STU-A", "key-A")],
        findings=[_finding("FND-A1", "STU-A", "positive")],
        links=[_link("LNK-A1", "FND-A1", directness=0)],
        audits=[_weak_audit("AUD-A", "STU-A")])
    snap = adjudicate(store, project=ws)
    assert snap["decision"] != "ADOPT"
    assert snap["confidence_label"] in ("Low", "Insufficient")


def test_strong_support_yields_adopt(tmp_path):
    ws, store, adjudicate, _ = _tribunal_setup(
        tmp_path,
        sources=[_src("SRC-STU-A"), _src("SRC-STU-B"), _src("SRC-STU-C"),
                 _src("SRC-STU-D")],
        studies=[_study("STU-A", "kA"), _study("STU-B", "kB"),
                 _study("STU-C", "kC"), _study("STU-D", "kD")],
        findings=[_finding("FND-A1", "STU-A"), _finding("FND-B1", "STU-B"),
                  _finding("FND-C1", "STU-C"), _finding("FND-D1", "STU-D")],
        links=[_link("LNK-A1", "FND-A1"), _link("LNK-B1", "FND-B1"),
               _link("LNK-C1", "FND-C1"), _link("LNK-D1", "FND-D1")],
        audits=[_audit("AUD-A", "STU-A"), _audit("AUD-B", "STU-B"),
                _audit("AUD-C", "STU-C"), _audit("AUD-D", "STU-D")])
    snap = adjudicate(store, project=ws)
    assert snap["decision"] == "ADOPT"
    assert snap["confidence_label"] in ("High", "Moderate")
    assert snap["confidence_score_internal"] > 0


def test_conflict_penalty_applied_only_for_independent_opposition(tmp_path):
    ws, store, adjudicate, _ = _tribunal_setup(
        tmp_path,
        sources=[_src("SRC-STU-A"), _src("SRC-STU-B")],
        studies=[_study("STU-A", "kA"), _study("STU-B", "kB")],
        findings=[_finding("FND-A1", "STU-A", "positive"),
                  _finding("FND-B1", "STU-B", "negative")],
        links=[_link("LNK-A1", "FND-A1", "support", "support_adoption"),
               _link("LNK-B1", "FND-B1", "contradict", "oppose_adoption")],
        audits=[_audit("AUD-A", "STU-A"), _audit("AUD-B", "STU-B")])
    snap = adjudicate(store, project=ws)
    # both directions present -> contested/negative evidence -> REJECT
    assert snap["decision"] == "REJECT"
    components = snap["extensions"]["confidence_components"]
    assert components["decisive_studies"] == 2


def test_negative_only_is_reject(tmp_path):
    ws, store, adjudicate, _ = _tribunal_setup(
        tmp_path,
        sources=[_src("SRC-STU-A")],
        studies=[_study("STU-A", "kA")],
        findings=[_finding("FND-A1", "STU-A", "negative")],
        links=[_link("LNK-A1", "FND-A1", "contradict", "oppose_adoption")],
        audits=[_audit("AUD-A", "STU-A")])
    snap = adjudicate(store, project=ws)
    assert snap["decision"] == "REJECT"
