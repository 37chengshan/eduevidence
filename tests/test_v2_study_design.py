"""Evidence-grounded StudyDesign gate tests."""

import json

import pytest

from engine.project import ProjectWorkspace
from engine.study_design import (
    validate_design_grounding, save_study_design, save_analysis_plan,
)


def _design(**over):
    base = {
        "design_id": "DSN-1",
        "gap_ids": ["GAP-1"],
        "research_question": "Does AI tutoring improve retention?",
        "design_type": "rct",
        "population": "first-year CS",
        "sampling_plan": "classroom random assignment",
        "intervention": "AI tutor",
        "comparison": "no AI",
        "outcomes": ["retention"],
        "measures": ["retention test"],
        "timepoints": ["baseline", "1 week"],
        "assignment_strategy": "random",
        "confounder_plan": "block by prior GPA",
        "analysis_requirements": ["pre/post descriptive comparison"],
        "success_criteria": ["retention gain"],
        "stop_conditions": ["adverse effect"],
        "ethics_flags": {
            "human_subjects": True,
            "sensitive_data": False,
            "minors_involved": False,
            "consent_status": "obtained",
            "ethics_review_required": True,
            "deidentification_required": True,
        },
        "preregistration_fields": {},
        "derived_from_graph_revision": 1,
        "created_at": "2026-08-12T00:00:00+00:00",
        "extensions": {},
    }
    base.update(over)
    return base


def _project_with_gap(tmp_path, gap_rev=1):
    ws = ProjectWorkspace.create(tmp_path, question="design?", title="d",
                                 research_mode="full_research_cycle")
    gaps_dir = ws.path / "gaps"
    gaps_dir.mkdir(parents=True, exist_ok=True)
    rec = {
        "gap_id": "GAP-1", "gap_type": "missing_retention",
        "related_claim_ids": ["CLM-1"], "related_outcome_ids": ["OUT-1"],
        "priority": "high", "reasoning": "retention unmeasured",
        "status": "open", "derived_from_graph_revision": gap_rev,
        "extensions": {},
    }
    (gaps_dir / f"gaps-rev-{gap_rev:06d}.jsonl").write_text(
        json.dumps(rec) + "\n", encoding="utf-8")
    # the gap is derived from a committed graph revision
    if gap_rev > 0:
        ws.update_manifest(graph_revision=gap_rev)
    return ws


def test_design_without_gaps_fails(tmp_path):
    ws = _project_with_gap(tmp_path)
    errors = validate_design_grounding(ws, _design(gap_ids=[]))
    assert errors
    assert any("evidence grounding" in e for e in errors)


def test_design_with_unknown_gap_fails(tmp_path):
    ws = _project_with_gap(tmp_path)
    errors = validate_design_grounding(ws, _design(gap_ids=["GAP-999"]))
    assert errors
    assert any("unknown gaps" in e for e in errors)


def test_design_with_stale_gap_revision_fails(tmp_path):
    ws = _project_with_gap(tmp_path, gap_rev=1)
    # advance the project to revision 2; the gap derives from revision 1
    ws.update_manifest(graph_revision=2)
    errors = validate_design_grounding(ws, _design(gap_ids=["GAP-1"]))
    assert errors
    assert any("revision" in e for e in errors)


def test_design_with_valid_gap_passes(tmp_path):
    ws = _project_with_gap(tmp_path)
    errors = validate_design_grounding(ws, _design())
    assert errors == []


def test_design_cross_project_gap_fails(tmp_path):
    ws_a = _project_with_gap(tmp_path / "home", gap_rev=1)
    # design referencing GAP-1 but persisted in a different project dir
    ws_b = ProjectWorkspace.create(tmp_path / "home", question="other?",
                                   title="o", research_mode="evidence_review")
    errors = validate_design_grounding(ws_b, _design(gap_ids=["GAP-1"]))
    assert errors
    assert any("unknown gaps" in e for e in errors)


def test_design_ethics_flags_required_fields(tmp_path):
    ws = _project_with_gap(tmp_path)
    bad = _design()
    del bad["ethics_flags"]["consent_status"]
    errors = validate_design_grounding(ws, bad)
    assert errors
    assert any("consent_status" in e for e in errors)


def test_design_has_no_analysis_plan_id(tmp_path):
    ws = _project_with_gap(tmp_path)
    d = _design()
    assert "analysis_plan_id" not in d
    errors = validate_design_grounding(ws, d)
    assert errors == []


def test_save_study_design_and_analysis_plan(tmp_path):
    ws = _project_with_gap(tmp_path)
    dpath = save_study_design(ws, _design())
    assert dpath.is_file()
    # duplicate save rejected
    with pytest.raises(FileExistsError):
        save_study_design(ws, _design())
    plan = {
        "analysis_plan_id": "APL-1", "design_id": "DSN-1", "dataset_ids": [],
        "primary_analysis": "pre/post descriptive comparison",
        "secondary_analyses": [], "assumption_checks": [],
        "preregistered": True, "created_at": "2026-08-12T00:00:00+00:00",
        "extensions": {},
    }
    ppath = save_analysis_plan(ws, plan)
    assert ppath.is_file()
