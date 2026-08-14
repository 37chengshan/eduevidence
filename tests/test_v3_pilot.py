"""Tests for engine/pilot.py - Decision-to-Outcome Loop (v3)."""
import json
from pathlib import Path

import pytest

from engine.graph_store import GraphStore
from engine.pilot import (
    OUTCOME_TAXONOMY, import_outcomes, link_analysis, redecide, register_pilot,
)
from engine.project import ProjectWorkspace
from engine.tribunal import adjudicate, save_decision_snapshot

ROOT = Path(__file__).resolve().parent.parent
TAXONOMY_SAMPLE = sorted(OUTCOME_TAXONOMY)[:4]


@pytest.fixture
def project(tmp_path):
    p = ProjectWorkspace.create(
        tmp_path, question="pilot test question",
        title="pilot test project", research_mode="evidence_review")
    return p


@pytest.fixture
def decision(project):
    """Seed a minimal graph revision with a claim + decision snapshot."""
    store = GraphStore.create(project)
    from engine.graph_store import GraphMutation
    from engine.ids import new_local_id

    src = {"source_id": "SRC-seed", "origin": "external", "source_type": "paper",
           "canonical_locator": "https://doi.org/10.1/seed", "validation_status": "valid",
           "content_hash": None, "extensions": {}}
    study = {"study_id": "STU-seed", "source_ids": ["SRC-seed"],
             "study_design": "rct", "population": "students",
             "sample_ids": ["S1"], "independence_key": "seed-1",
             "identity_status": "resolved", "extensions": {}}
    outcome = {"outcome_id": "OUT-retention", "name": "retention",
               "outcome_type": "learning", "extensions": {}}
    claim = {"claim_id": "CLM-1", "text": "AI tutor improves retention",
             "claim_type": "causal_effect", "primary_outcome_ids": ["OUT-retention"],
             "scope": "course-level", "created_in_revision": 1,
             "status": "active", "extensions": {}}
    finding = {"finding_id": "FND-seed", "study_id": "STU-seed",
               "finding_type": "quantitative_effect", "outcome_id": "OUT-retention",
               "measure": "effect size", "timepoint": None, "effect_direction": "positive",
               "effect_estimate": {"metric": "effect size", "value": 0.4, "raw_text": "d=0.4"},
               "raw_result_text": "d=0.4",
               "source_locator": "https://doi.org/10.1/seed", "extensions": {}}
    link = {"evidence_link_id": "LNK-seed", "finding_id": "FND-seed", "claim_id": "CLM-1",
            "relation_to_claim": "support", "decision_implication": "support_adoption",
            "directness": 2, "applicability": {"scope_match": "direct"},
            "reasoning_note": "seed", "created_in_revision": 1, "extensions": {}}
    from engine.ids import new_run_id

    store.commit(run_id=new_run_id(existing={"seed"}), reason="seed graph",
                 mutation=GraphMutation(upserts={
                     "sources": [src], "studies": [study], "outcomes": [outcome],
                     "claims": [claim], "findings": [finding],
                     "evidence_links": [link]}))
    store.repair_head_mirror()
    snap = adjudicate(store, project=project)
    path = save_decision_snapshot(project, snap)
    return snap


def _csv(tmp_path, cols, rows):
    p = tmp_path / "outcomes.csv"
    p.write_text("\n".join([",".join(cols)] + [",".join(r) for r in rows]) + "\n",
                 encoding="utf-8")
    return p


def test_register_pilot_requires_real_decision(project):
    with pytest.raises(ValueError, match="decision snapshot"):
        register_pilot(project, decision_snapshot_id="DEC-nope", title="t",
                       start_date="2026-09-01T00:00:00+00:00",
                       end_date="2026-12-01T00:00:00+00:00",
                       conditions=["c"], sample_size=30, design_id="DSN-1",
                       anon_policy={"no_pii_columns": True, "note": ""},
                       outcome_columns=["retention"])


def test_register_pilot_blocks_unknown_outcomes_and_pii(project, decision):
    with pytest.raises(ValueError, match="outside Outcome Taxonomy"):
        register_pilot(project, decision_snapshot_id=decision["decision_snapshot_id"],
                       title="t", start_date="2026-09-01T00:00:00+00:00",
                       end_date="2026-12-01T00:00:00+00:00", conditions=["c"],
                       sample_size=30, design_id="DSN-1",
                       anon_policy={"no_pii_columns": True, "note": ""},
                       outcome_columns=["made_up_outcome"])
    with pytest.raises(ValueError, match="no_pii_columns"):
        register_pilot(project, decision_snapshot_id=decision["decision_snapshot_id"],
                       title="t", start_date="2026-09-01T00:00:00+00:00",
                       end_date="2026-12-01T00:00:00+00:00", conditions=["c"],
                       sample_size=30, design_id="DSN-1",
                       anon_policy={"no_pii_columns": False, "note": ""},
                       outcome_columns=["retention"])


def test_full_pilot_loop(project, decision, tmp_path):
    pilot = register_pilot(
        project, decision_snapshot_id=decision["decision_snapshot_id"],
        title="retention pilot", start_date="2026-09-01T00:00:00+00:00",
        end_date="2026-12-01T00:00:00+00:00", conditions=["tutor with guardrails"],
        sample_size=30, design_id="DSN-1",
        anon_policy={"no_pii_columns": True, "note": "anonymized cohort"},
        outcome_columns=["retention"])
    assert pilot["status"] == "registered"
    assert pilot["pilot_id"].startswith("PIL-")

    csv = _csv(tmp_path, ["student_id", "retention"], [["s1", "0.8"], ["s2", "0.9"]])
    # PII gate: a student-id column must be refused
    with pytest.raises(ValueError, match="PII columns"):
        import_outcomes(project, pilot["pilot_id"], source_path=csv,
                        privacy={"classification": "confidential"})

    csv = _csv(tmp_path, ["retention"], [["0.8"], ["0.9"], ["0.7"]])
    asset = import_outcomes(project, pilot["pilot_id"], source_path=csv,
                            privacy={"classification": "internal",
                                     "deidentification_status": "done"})
    assert asset["dataset_id"].startswith("DAT-")
    pilot = json.loads((project.path / "pilots" / f"{pilot['pilot_id']}.json").read_text(encoding="utf-8"))
    assert pilot["status"] == "data_imported"

    # link_analysis requires a real analysis run; create a stub file first
    (project.path / "analyses").mkdir(exist_ok=True)
    (project.path / "analyses" / "ANL-1.json").write_text(
        json.dumps({"analysis_run_id": "ANL-1", "plan": {}, "result": {}}), encoding="utf-8")
    pilot = link_analysis(project, pilot["pilot_id"], analysis_run_id="ANL-1")
    assert pilot["status"] == "analyzed"

    result = redecide(
        project, pilot["pilot_id"], claim_id="CLM-1", outcome_token="retention",
        measure="mean retention", effect_direction="positive",
        raw_result_text="pilot mean 0.80 (n=30)",
        relation_to_claim="support", effect_estimate={"value": 0.8})
    assert result["revision"] >= 2
    assert result["diff"]["to_decision_snapshot_id"] == result["snapshot"]["decision_snapshot_id"]
    assert result["snapshot"]["graph_revision"] == result["revision"]

    pilot = json.loads((project.path / "pilots" / f"{pilot['pilot_id']}.json").read_text(encoding="utf-8"))
    assert pilot["status"] == "adjudicated"
    assert pilot["redecide"]["new_decision_snapshot_id"] == result["snapshot"]["decision_snapshot_id"]

    store = GraphStore(project)
    assert store.active_revision() == result["revision"]
    assert store.validate() == []


def test_redecide_rejects_unknown_claim(project, decision, tmp_path):
    pilot = register_pilot(
        project, decision_snapshot_id=decision["decision_snapshot_id"], title="t",
        start_date="2026-09-01T00:00:00+00:00", end_date="2026-12-01T00:00:00+00:00",
        conditions=["c"], sample_size=10, design_id="DSN-1",
        anon_policy={"no_pii_columns": True, "note": ""},
        outcome_columns=["retention"])
    # a registered (data-less) pilot must refuse re-adjudication entirely
    with pytest.raises(ValueError, match="before re-adjudication"):
        redecide(project, pilot["pilot_id"], claim_id="CLM-1",
                 outcome_token="retention", measure="m", effect_direction="positive",
                 raw_result_text="x", relation_to_claim="support")
    # after data import, an unknown claim must be rejected by the graph
    csv = _csv(tmp_path, ["retention"], [["0.8"], ["0.9"]])
    import_outcomes(project, pilot["pilot_id"], source_path=csv,
                    privacy={"classification": "internal",
                             "deidentification_status": "done"})
    with pytest.raises(ValueError, match="not found in project graph"):
        redecide(project, pilot["pilot_id"], claim_id="CLM-zzz",
                 outcome_token="retention", measure="m", effect_direction="positive",
                 raw_result_text="x", relation_to_claim="support")
