"""Full Research Cycle end-to-end tests: analysis → one graph revision → decision history."""

import json

from engine.graph_store import GraphStore, GraphMutation
from engine.project import ProjectWorkspace
from engine.run import start_run
from engine.tribunal import adjudicate, save_decision_snapshot, decision_diff
from engine.update import commit_project_study


def _ws(tmp_path):
    ws = ProjectWorkspace.create(tmp_path, question="full cycle?", title="fc",
                                 research_mode="full_research_cycle")
    return ws


def _base_graph(store, run):
    """Revision 1: one external source + study + finding + claim + link + audit."""
    store.commit(run_id=run["run_id"], reason="external evidence",
                 mutation=GraphMutation(
                     upserts={
                         "sources": [{"source_id": "SRC-ext", "origin": "external",
                                      "source_type": "journal_article",
                                      "canonical_locator": "https://doi.org/10.0000/ext",
                                      "validation_status": "valid",
                                      "content_hash": None, "extensions": {}}],
                         "studies": [{"study_id": "STU-ext", "source_ids": ["SRC-ext"],
                                      "study_design": "RCT", "population": "u",
                                      "sample_ids": ["S1"], "sample_size": 60,
                                      "intervention": "AI", "comparison": "none",
                                      "independence_key": "k-ext",
                                      "identity_status": "resolved",
                                      "extensions": {}}],
                         "outcomes": [{"outcome_id": "OUT-1", "name": "post",
                                       "outcome_type": "learning", "extensions": {}}],
                         "findings": [{"finding_id": "FND-ext", "study_id": "STU-ext",
                                       "finding_type": "quantitative_effect",
                                       "outcome_id": "OUT-1", "measure": "post",
                                       "timepoint": None, "effect_direction": "positive",
                                       "effect_estimate": None, "raw_result_text": "x",
                                       "source_locator": "p1", "extensions": {}}],
                         "claims": [{"claim_id": "CLM-1", "text": "AI helps",
                                     "claim_type": "effectiveness",
                                     "primary_outcome_ids": ["OUT-1"], "scope": "u",
                                     "created_in_revision": 1, "status": "active",
                                     "extensions": {}}],
                         "evidence_links": [{"evidence_link_id": "LNK-ext",
                                             "finding_id": "FND-ext", "claim_id": "CLM-1",
                                             "relation_to_claim": "support",
                                             "decision_implication": "support_adoption",
                                             "directness": 2,
                                             "applicability": {"scope_match": "direct"},
                                             "reasoning_note": "r",
                                             "created_in_revision": 1,
                                             "extensions": {}}],
                         "audits": [{"audit_id": "AUD-ext", "study_id": "STU-ext",
                                     "policy_version": "2026-08-12.v2",
                                     "design_quality": 2, "sample_quality": 1,
                                     "measurement_validity": 2, "temporal_strength": 1,
                                     "bias_checks": [], "confounders": [],
                                     "limitations": [], "overall_status": "concern",
                                     "audited_at": "2026-08-12T00:00:00+00:00",
                                     "extensions": {}}],
                     }, retire_ids={}))


def _local_bundle(ws):
    """Schema-valid local study inputs for commit_project_study."""
    design = {
        "design_id": "DSN-1", "gap_ids": ["GAP-1"],
        "research_question": "retention?", "design_type": "rct",
        "population": "u", "sampling_plan": "random",
        "intervention": "AI", "comparison": "none",
        "outcomes": ["retention"], "measures": ["retention test"],
        "timepoints": ["1 week"], "assignment_strategy": "random",
        "confounder_plan": "", "analysis_requirements": ["descriptive"],
        "success_criteria": [], "stop_conditions": [],
        "ethics_flags": {"human_subjects": True, "sensitive_data": False,
                         "minors_involved": False, "consent_status": "obtained",
                         "ethics_review_required": True,
                         "deidentification_required": False},
        "preregistration_fields": {}, "derived_from_graph_revision": 1,
        "created_at": "2026-08-12T00:00:00+00:00", "extensions": {},
    }
    dataset = {
        "dataset_id": "DAT-1", "project_id": ws.project_id, "design_id": "DSN-1",
        "source_type": "csv", "path": "/tmp/x.csv", "content_hash": "sha256:abc",
        "schema_summary": {}, "row_count": 126, "column_count": 4,
        "variable_dictionary": None, "privacy_classification": "internal",
        "consent_metadata": None, "deidentification_status": "done",
        "created_at": "2026-08-12T00:00:00+00:00", "extensions": {},
    }
    analysis_run = {
        "analysis_run_id": "ANL-1", "analysis_plan_id": "APL-1",
        "dataset_ids": ["DAT-1"], "status": "validated",
        "outputs": {"descriptive": {}}, "assumption_checks": [],
        "created_at": "2026-08-12T00:00:00+00:00", "extensions": {},
    }
    study = {
        "study_id": "STU-local", "source_ids": ["SRC-DAT-1"],
        "study_design": "rct", "population": "u", "sample_ids": ["S-local"],
        "sample_size": 126, "intervention": "AI", "comparison": "none",
        "independence_key": "local:retention-2026", "identity_status": "resolved",
        "extensions": {},
    }
    findings = [
        {"finding_id": "FND-local-1", "study_id": "STU-local",
         "finding_type": "quantitative_effect", "outcome_id": "OUT-1",
         "measure": "retention test", "timepoint": "1 week",
         "effect_direction": "positive", "effect_estimate": None,
         "raw_result_text": "local retention gain", "source_locator": "local",
         "extensions": {}},
        {"finding_id": "FND-local-2", "study_id": "STU-local",
         "finding_type": "process_finding", "outcome_id": "OUT-1",
         "measure": "engagement", "timepoint": None,
         "effect_direction": "positive", "effect_estimate": None,
         "raw_result_text": "engagement up", "source_locator": "local",
         "extensions": {}},
    ]
    audit = {
        "audit_id": "AUD-local", "study_id": "STU-local",
        "policy_version": "2026-08-12.v2", "design_quality": 2,
        "sample_quality": 2, "measurement_validity": 2, "temporal_strength": 2,
        "bias_checks": [], "confounders": [], "limitations": [],
        "overall_status": "pass", "audited_at": "2026-08-12T00:00:00+00:00",
        "extensions": {},
    }
    claims = [{"claim_id": "CLM-1", "text": "AI helps",
               "claim_type": "effectiveness", "primary_outcome_ids": ["OUT-1"],
               "scope": "u", "created_in_revision": 1, "status": "active",
               "extensions": {}}]
    links = [
        {"evidence_link_id": "LNK-local-1", "finding_id": "FND-local-1",
         "claim_id": "CLM-1", "relation_to_claim": "support",
         "decision_implication": "support_adoption", "directness": 2,
         "applicability": {"scope_match": "direct"}, "reasoning_note": "r",
         "created_in_revision": 2, "extensions": {}},
        {"evidence_link_id": "LNK-local-2", "finding_id": "FND-local-2",
         "claim_id": "CLM-1", "relation_to_claim": "support",
         "decision_implication": "support_adoption", "directness": 1,
         "applicability": {"scope_match": "partial"}, "reasoning_note": "r",
         "created_in_revision": 2, "extensions": {}},
    ]
    return design, dataset, analysis_run, study, findings, audit, claims, links


def test_full_cycle_commits_one_revision(tmp_path):
    ws = _ws(tmp_path)
    store = GraphStore.create(ws)
    run = start_run(ws, purpose="base", capabilities=[],
                    execution_backend="sequential_main_agent")
    _base_graph(store, run)
    assert store.active_revision() == 1

    design, dataset, analysis_run, study, findings, audit, claims, links = _local_bundle(ws)
    run2 = start_run(ws, purpose="local study", capabilities=[],
                     execution_backend="sequential_main_agent")
    rev = commit_project_study(
        store=store, run_id=run2["run_id"], design=design, dataset_asset=dataset,
        analysis_run=analysis_run, study=study, findings=findings,
        methodology_audit=audit, claims=claims, links=links)
    assert rev.revision == 2  # ONE revision, not per-finding
    assert store.active_revision() == 2

    # one project-local source with portable locator
    srcs = store.read_table("sources")
    local_srcs = [s for s in srcs if s["origin"] == "project"]
    assert len(local_srcs) == 1
    assert local_srcs[0]["canonical_locator"].startswith("project://")
    # one new study + two findings sharing it
    studies = store.read_table("studies")
    assert len(studies) == 2
    local_fnds = [f for f in store.read_table("findings") if f["study_id"] == "STU-local"]
    assert len(local_fnds) == 2
    # audit exists, links reference existing claims
    assert any(a["study_id"] == "STU-local" for a in store.read_table("audits"))
    assert store.validate() == []


def test_unvalidated_analysis_returns_analysis_invalid(tmp_path):
    ws = _ws(tmp_path)
    store = GraphStore.create(ws)
    run = start_run(ws, purpose="base", capabilities=[],
                    execution_backend="sequential_main_agent")
    _base_graph(store, run)
    design, dataset, analysis_run, study, findings, audit, claims, links = _local_bundle(ws)
    analysis_run["status"] = "completed"  # not validated
    try:
        commit_project_study(store=store, run_id=run["run_id"], design=design,
                             dataset_asset=dataset, analysis_run=analysis_run,
                             study=study, findings=findings,
                             methodology_audit=audit, claims=claims, links=links)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "ANALYSIS_INVALID" in str(exc)
    assert store.active_revision() == 1  # graph unchanged


def test_decision_history_and_diff(tmp_path):
    ws = _ws(tmp_path)
    store = GraphStore.create(ws)
    run = start_run(ws, purpose="base", capabilities=[],
                    execution_backend="sequential_main_agent")
    _base_graph(store, run)
    snap1 = adjudicate(store, project=ws)
    p1 = save_decision_snapshot(ws, snap1)

    design, dataset, analysis_run, study, findings, audit, claims, links = _local_bundle(ws)
    run2 = start_run(ws, purpose="local", capabilities=[],
                     execution_backend="sequential_main_agent")
    commit_project_study(store=store, run_id=run2["run_id"], design=design,
                         dataset_asset=dataset, analysis_run=analysis_run,
                         study=study, findings=findings, methodology_audit=audit,
                         claims=claims, links=links)
    snap2 = adjudicate(store, project=ws)
    p2 = save_decision_snapshot(ws, snap2)

    assert snap1["graph_revision"] == 1
    assert snap2["graph_revision"] == 2
    # old snapshot file immutable
    assert json.loads(p1.read_text())["graph_revision"] == 1

    diff = decision_diff(snap1, snap2,
                         previous_gaps=({"gap_id": "GAP-1"},),
                         current_gaps=())
    assert diff["from_decision_snapshot_id"] == snap1["decision_snapshot_id"]
    assert diff["to_decision_snapshot_id"] == snap2["decision_snapshot_id"]
    assert diff["from_graph_revision"] == 1
    assert diff["to_graph_revision"] == 2
    assert "LNK-local-1" in diff["new_key_evidence_links"]
    # resolved gaps computed from input gaps, not claimed by the diff itself
    assert diff["resolved_gaps"] == ["GAP-1"]
    assert diff["new_gaps"] == []
