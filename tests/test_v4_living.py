"""Tests for engine/living.py - Living Evidence (v4).

Covers subscription creation (bad-snapshot rejection), incremental evidence
refresh (graph revision bump, drift report generation with a sensible
suggested_action), the no-change/confirmed path, and idempotency (content-hash
dedupe: re-injecting the same evidence never re-enters the graph).

Graph write patterns mirror tests/test_v3_pilot.py's seed (GraphStore.create /
commit / GraphMutation / claim-binding contract fields).
"""
import json
from pathlib import Path

import pytest

from engine.graph_store import GraphMutation, GraphStore
from engine.ids import new_run_id
from engine.living import (
    create_subscription, refresh, set_subscription_status,
)
from engine.project import ProjectWorkspace
from engine.tribunal import adjudicate, save_decision_snapshot
from scripts.validate_schema import SchemaError, validate as validate_schema

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def project(tmp_path):
    p = ProjectWorkspace.create(
        tmp_path, question="does an AI tutor improve retention?",
        title="living evidence project", research_mode="evidence_review")
    return p


@pytest.fixture
def decision(project):
    """Baseline graph (revision 1) + DecisionSnapshot -> High/ADOPT.

    One audited supporting RCT: confidence High, decision ADOPT.
    """
    store = GraphStore.create(project)
    src = {"source_id": "SRC-base", "origin": "external", "source_type": "paper",
           "canonical_locator": "https://doi.org/10.1/base",
           "validation_status": "valid", "content_hash": None, "extensions": {}}
    study = {"study_id": "STU-base", "source_ids": ["SRC-base"],
             "study_design": "rct", "population": "students",
             "sample_ids": ["S1"], "independence_key": "base-1",
             "identity_status": "resolved", "extensions": {}}
    outcome = {"outcome_id": "OUT-retention", "name": "retention",
               "outcome_type": "learning", "extensions": {}}
    claim = {"claim_id": "CLM-1", "text": "AI tutor improves retention",
             "claim_type": "causal_effect", "primary_outcome_ids": ["OUT-retention"],
             "scope": "course-level", "created_in_revision": 1,
             "status": "active", "extensions": {}}
    finding = {"finding_id": "FND-base", "study_id": "STU-base",
               "finding_type": "quantitative_effect", "outcome_id": "OUT-retention",
               "measure": "effect size", "timepoint": None,
               "effect_direction": "positive",
               "effect_estimate": {"metric": "effect size", "value": 0.4,
                                   "raw_text": "d=0.4"},
               "raw_result_text": "d=0.4",
               "source_locator": "https://doi.org/10.1/base", "extensions": {}}
    link = {"evidence_link_id": "LNK-base", "finding_id": "FND-base",
            "claim_id": "CLM-1", "relation_to_claim": "support",
            "decision_implication": "support_adoption", "directness": 2,
            "applicability": {"scope_match": "direct"},
            "reasoning_note": "baseline", "created_in_revision": 1,
            "extensions": {}}
    audit = {"audit_id": "AUD-base", "study_id": "STU-base",
             "policy_version": "2026-08-12.v3",
             "design_quality": 2, "sample_quality": 2,
             "measurement_validity": 2, "temporal_strength": 2,
             "bias_checks": [], "confounders": [], "limitations": [],
             "overall_status": "pass",
             "audited_at": "2026-01-01T00:00:00+00:00", "extensions": {}}
    store.commit(run_id=new_run_id(existing={"base"}), reason="baseline graph",
                 mutation=GraphMutation(upserts={
                     "sources": [src], "studies": [study], "outcomes": [outcome],
                     "claims": [claim], "findings": [finding],
                     "evidence_links": [link], "audits": [audit]}))
    store.repair_head_mirror()
    snap = adjudicate(store, project=project)
    save_decision_snapshot(project, snap)
    return snap


# ---- evidence record helpers -------------------------------------------

def _new_evidence(direction="contradict", tag="new1"):
    """One living-evidence record bound to the existing CLM-1 claim."""
    positive = direction == "support"
    return {
        "source": {"source_id": f"SRC-{tag}", "origin": "external",
                   "source_type": "paper",
                   "canonical_locator": f"https://doi.org/10.1/{tag}",
                   "validation_status": "valid", "content_hash": None,
                   "extensions": {}},
        "study": {"study_id": f"STU-{tag}", "source_ids": [f"SRC-{tag}"],
                  "study_design": "rct", "population": "students",
                  "sample_ids": [f"S-{tag}"], "independence_key": tag,
                  "identity_status": "resolved", "extensions": {}},
        "outcome": {"name": "retention", "outcome_type": "learning",
                    "extensions": {}},
        "finding": {"finding_id": f"FND-{tag}", "finding_type": "quantitative_effect",
                    "outcome_id": "OUT-retention", "measure": "effect size",
                    "effect_direction": "positive" if positive else "negative",
                    "effect_estimate": {"metric": "effect size",
                                        "value": 0.4 if positive else -0.2,
                                        "raw_text": "d=0.4" if positive else "d=-0.2"},
                    "raw_result_text": "d=0.4" if positive else "d=-0.2",
                    "source_locator": f"https://doi.org/10.1/{tag}",
                    "extensions": {}},
        "evidence_link": {"evidence_link_id": f"LNK-{tag}", "claim_id": "CLM-1",
                          "relation_to_claim": "support" if positive else "contradict",
                          "reasoning_note": f"new {direction}ing RCT",
                          "applicability": {"scope_match": "direct"}},
        "audit": {"audit_id": f"AUD-{tag}", "study_id": f"STU-{tag}",
                  "policy_version": "2026-08-12.v3",
                  "design_quality": 2, "sample_quality": 2,
                  "measurement_validity": 2, "temporal_strength": 2,
                  "bias_checks": [], "confounders": [], "limitations": [],
                  "overall_status": "pass",
                  "audited_at": "2026-02-01T00:00:00+00:00", "extensions": {}},
    }


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---- subscription creation ---------------------------------------------

def test_create_subscription_rejects_bad_snapshot(project):
    with pytest.raises(ValueError, match="decision snapshot"):
        create_subscription(project, "DEC-nope", ["ai tutor"])
    with pytest.raises(ValueError, match="decision snapshot"):
        create_subscription(project, "not-a-decision", ["ai tutor"])


def test_create_subscription_writes_valid_record(project, decision):
    sub = create_subscription(project, decision["decision_snapshot_id"],
                              ["AI tutor", "retention", "ai tutor"])
    assert sub["subscription_id"].startswith("SUB-")
    assert sub["decision_snapshot_id"] == decision["decision_snapshot_id"]
    assert sub["question"] == "does an AI tutor improve retention?"
    # query_terms are trimmed + deduplicated
    assert sub["query_terms"] == ["AI tutor", "retention"]
    assert sub["status"] == "active"
    assert sub["extensions"]["last_snapshot_id"] == decision["decision_snapshot_id"]

    path = project.path / "living" / "subscriptions" / f"{sub['subscription_id']}.json"
    assert path.is_file()
    validate_schema(_load_json(path),
                    json.loads((ROOT / "schemas/v4/living-subscription.schema.json")
                               .read_text(encoding="utf-8")))


def test_create_subscription_rejects_empty_query_terms(project, decision):
    with pytest.raises(ValueError, match="query_terms"):
        create_subscription(project, decision["decision_snapshot_id"], [])


# ---- refresh: new evidence ---------------------------------------------

def test_refresh_new_evidence_increments_revision_and_reports_changed(
        project, decision):
    sub = create_subscription(project, decision["decision_snapshot_id"],
                              ["AI tutor", "retention"])
    store = GraphStore(project)
    assert store.active_revision() == 1

    # a contradicting RCT flips the decision ADOPT -> REJECT
    result = refresh(project, sub["subscription_id"],
                     new_evidence=[_new_evidence("contradict", "new1")])

    assert result["evidence_committed"] is True
    assert result["graph_revision"] == 2
    assert store.active_revision() == 2
    assert store.validate() == []

    # drift report written and schema-valid
    assert result["drift_report_path"].endswith(
        f"living/drift/{result['drift']['drift_id']}.json")
    drift = result["drift"]
    assert drift["drift_id"].startswith("DRF-")
    assert drift["subscription_id"] == sub["subscription_id"]
    assert drift["from_revision"] == 1
    assert drift["to_revision"] == 2
    assert drift["new_evidence_ids"] == ["FND-new1"]
    assert drift["suggested_action"] == "changed"
    assert "ADOPT" in drift["summary"] and "REJECT" in drift["summary"]
    assert drift["extensions"]["diff"]["action_changed"] is True
    assert drift["extensions"]["diff"]["to_decision_snapshot_id"] ==         result["snapshot"]["decision_snapshot_id"]
    validate_schema(drift, json.loads(
        (ROOT / "schemas/v4/drift-report.schema.json").read_text(encoding="utf-8")))

    # new snapshot persisted and bound to the refreshed revision
    assert result["snapshot"]["decision"] == "REJECT"
    assert result["snapshot"]["graph_revision"] == 2
    assert (project.path / "decisions" /
            f"{result['snapshot']['decision_snapshot_id']}.json").is_file()

    # subscription tracks the new snapshot + ingested hash
    sub2 = _load_json(project.path / "living" / "subscriptions" /
                      f"{sub['subscription_id']}.json")
    assert sub2["extensions"]["last_snapshot_id"] ==         result["snapshot"]["decision_snapshot_id"]
    assert sub2["extensions"]["to_graph_revision"] == 2
    assert len(sub2["extensions"]["ingested_evidence_hashes"]) == 1


def test_refresh_new_supporting_evidence_reports_needs_review(project, decision):
    sub = create_subscription(project, decision["decision_snapshot_id"], ["retention"])
    # another supporting RCT keeps ADOPT; evidence is new -> needs_review
    result = refresh(project, sub["subscription_id"],
                     new_evidence=[_new_evidence("support", "new2")])
    assert result["evidence_committed"] is True
    assert result["graph_revision"] == 2
    assert result["snapshot"]["decision"] == "ADOPT"
    assert result["drift"]["suggested_action"] == "needs_review"
    assert result["drift"]["new_evidence_ids"] == ["FND-new2"]
    assert result["drift"]["extensions"]["diff"]["action_changed"] is False


def test_refresh_rejects_unknown_claim(project, decision):
    sub = create_subscription(project, decision["decision_snapshot_id"], ["retention"])
    bad = _new_evidence("support", "bad")
    bad["evidence_link"]["claim_id"] = "CLM-zzz"
    with pytest.raises(ValueError, match="claim .* not found in project graph"):
        refresh(project, sub["subscription_id"], new_evidence=[bad])
    # graph untouched
    assert GraphStore(project).active_revision() == 1


# ---- refresh: no change / idempotency ----------------------------------

def test_refresh_empty_evidence_confirmed(project, decision):
    sub = create_subscription(project, decision["decision_snapshot_id"], ["retention"])
    result = refresh(project, sub["subscription_id"], new_evidence=[])
    assert result["evidence_committed"] is False
    assert result["graph_revision"] == 1
    assert result["drift"]["suggested_action"] == "confirmed"
    assert result["drift"]["new_evidence_ids"] == []
    assert result["drift"]["from_revision"] == result["drift"]["to_revision"] == 1
    assert result["snapshot"] is None


def test_refresh_idempotent_duplicate_evidence(project, decision):
    sub = create_subscription(project, decision["decision_snapshot_id"], ["retention"])
    packet = _new_evidence("contradict", "dup")

    first = refresh(project, sub["subscription_id"], new_evidence=[packet])
    assert first["evidence_committed"] is True
    assert first["graph_revision"] == 2

    # same evidence again: content-hash dedupe, no graph change
    second = refresh(project, sub["subscription_id"], new_evidence=[packet])
    assert second["evidence_committed"] is False
    assert second["graph_revision"] == 2
    assert second["drift"]["suggested_action"] == "confirmed"
    assert second["drift"]["new_evidence_ids"] == []
    assert "dedupe" in second["drift"]["summary"]
    assert len(second["drift"]["extensions"]["skipped_duplicate_hashes"]) == 1
    assert GraphStore(project).active_revision() == 2

    # only one finding/link ever entered the graph
    store = GraphStore(project)
    findings = store.read_table("findings")
    links = store.read_table("evidence_links")
    assert [f["finding_id"] for f in findings].count("FND-dup") == 1
    assert [l["evidence_link_id"] for l in links].count("LNK-dup") == 1


def test_refresh_same_batch_duplicates_committed_once(project, decision):
    sub = create_subscription(project, decision["decision_snapshot_id"], ["retention"])
    packet = _new_evidence("support", "batch")
    # the same record listed twice in one refresh must enter the graph once
    result = refresh(project, sub["subscription_id"],
                     new_evidence=[packet, dict(packet)])
    assert result["evidence_committed"] is True
    assert result["graph_revision"] == 2
    findings = GraphStore(project).read_table("findings")
    assert [f["finding_id"] for f in findings].count("FND-batch") == 1


# ---- refresh: retriever adapter ----------------------------------------

def test_refresh_via_retriever_adapter(project, decision):
    sub = create_subscription(project, decision["decision_snapshot_id"], ["retention"])
    calls = []

    def retriever(subscription):
        calls.append(subscription["subscription_id"])
        return [_new_evidence("support", "retr")]

    result = refresh(project, sub["subscription_id"], retriever=retriever)
    assert calls == [sub["subscription_id"]]
    assert result["evidence_committed"] is True
    assert result["graph_revision"] == 2
    assert result["drift"]["suggested_action"] == "needs_review"
    assert result["drift"]["new_evidence_ids"] == ["FND-retr"]


def test_refresh_requires_evidence_source(project, decision):
    sub = create_subscription(project, decision["decision_snapshot_id"], ["retention"])
    with pytest.raises(ValueError, match="evidence source"):
        refresh(project, sub["subscription_id"])
    with pytest.raises(ValueError, match="exactly one"):
        refresh(project, sub["subscription_id"], new_evidence=[],
                retriever=lambda s: [])


# ---- subscription status gating ----------------------------------------

def test_refresh_rejects_paused_subscription(project, decision):
    sub = create_subscription(project, decision["decision_snapshot_id"], ["retention"])
    set_subscription_status(project, sub["subscription_id"], "paused")
    with pytest.raises(ValueError, match="paused"):
        refresh(project, sub["subscription_id"],
                new_evidence=[_new_evidence("support", "pz")])
    assert GraphStore(project).active_revision() == 1


def test_refresh_missing_subscription(project, decision):
    # malformed id -> ValueError (shape validated before existence)
    with pytest.raises(ValueError, match="invalid subscription id"):
        refresh(project, "SUB-missing", new_evidence=[])
    # well-formed but absent id -> FileNotFoundError
    with pytest.raises(FileNotFoundError, match="subscription not found"):
        refresh(project, "SUB-00000000", new_evidence=[])


def test_set_subscription_status_rejects_invalid(project, decision):
    from engine.living import create_subscription, set_subscription_status
    sub = create_subscription(project, decision_snapshot_id=decision["decision_snapshot_id"],
                              query_terms=["retention"])
    with pytest.raises(ValueError, match="active|paused"):
        set_subscription_status(project, sub["subscription_id"], "frozen")
    ok = set_subscription_status(project, sub["subscription_id"], "paused")
    assert ok["status"] == "paused"


def test_refresh_retriever_exception_is_propagated(project, decision):
    from engine.living import create_subscription, refresh
    sub = create_subscription(project, decision_snapshot_id=decision["decision_snapshot_id"],
                              query_terms=["retention"])

    def boom(subscription):
        raise RuntimeError("retriever backend down")

    with pytest.raises(RuntimeError, match="retriever backend down"):
        refresh(project, sub["subscription_id"], retriever=boom)
