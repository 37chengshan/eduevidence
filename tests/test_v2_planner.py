"""Capability registry + task-DAG planner tests."""

import pytest

from engine.capabilities import capability_registry
from engine.planner import build_research_plan, PlanStep

EV_REVIEW_STEPS = (
    "research_framing", "literature_search", "counter_evidence_search",
    "source_fetch", "source_validation", "study_extraction",
    "finding_extraction", "methodology_appraisal", "claim_linking",
    "evidence_synthesis", "tribunal", "applicability_analysis",
    "knowledge_gap_detection", "report_projection", "report_rendering",
)


def test_registry_contains_all_capabilities():
    reg = capability_registry()
    for cid in EV_REVIEW_STEPS:
        assert cid in reg
    for cid in ("study_design", "measurement_design", "data_validation",
                "data_analysis", "intervention_design", "evaluation_design"):
        assert cid in reg


def test_evidence_review_plan_has_full_pipeline():
    plan = build_research_plan(mode="evidence_review",
                               decision_target="evidence_review",
                               depth="standard", has_grounding=True,
                               has_dataset=False)
    ids = [s.capability_id for s in plan]
    assert ids == list(EV_REVIEW_STEPS)
    # no wait step in a pure evidence review
    assert all(s.kind == "capability" for s in plan)


def test_full_cycle_plan_includes_design_after_grounding():
    plan = build_research_plan(mode="full_research_cycle",
                               decision_target="teaching_pilot",
                               depth="deep", has_grounding=True,
                               has_dataset=True)
    ids = [s.capability_id for s in plan if s.capability_id]
    assert "study_design" in ids
    assert "measurement_design" in ids
    assert "data_validation" in ids
    assert "data_analysis" in ids
    # design depends on knowledge gaps
    study_design = next(s for s in plan if s.capability_id == "study_design")
    assert study_design.depends_on == ("knowledge_gap_detection",)


def test_full_cycle_without_dataset_waits_for_user_data():
    plan = build_research_plan(mode="full_research_cycle",
                               decision_target="research_cycle",
                               depth="deep", has_grounding=True,
                               has_dataset=False)
    waits = [s for s in plan if s.kind == "wait"]
    assert len(waits) == 1
    assert waits[0].wait_state == "waiting_for_user_data"
    assert waits[0].capability_id is None
    # the wait comes after design; analysis steps are NOT emitted
    ids = [s.capability_id for s in plan if s.capability_id]
    assert "data_analysis" not in ids
    wait = waits[0]
    assert wait.depends_on == ("measurement_design",)


def test_intervention_evaluation_target_dependent():
    plan = build_research_plan(mode="evidence_review",
                               decision_target="evidence_review",
                               depth="standard", has_grounding=True,
                               has_dataset=False)
    ids = [s.capability_id for s in plan if s.capability_id]
    assert "intervention_design" not in ids
    assert "evaluation_design" not in ids

    plan2 = build_research_plan(mode="evidence_review",
                                decision_target="teaching_pilot",
                                depth="standard", has_grounding=True,
                                has_dataset=False)
    ids2 = [s.capability_id for s in plan2 if s.capability_id]
    assert "intervention_design" in ids2
    assert "evaluation_design" in ids2


def test_plan_steps_have_schema_bound_contracts():
    plan = build_research_plan(mode="evidence_review",
                               decision_target="evidence_review",
                               depth="standard", has_grounding=True,
                               has_dataset=False)
    finding = next(s for s in plan if s.capability_id == "finding_extraction")
    assert finding.output_contract == "finding"
    synthesis = next(s for s in plan if s.capability_id == "evidence_synthesis")
    assert synthesis.gate and "independent" in synthesis.gate.lower()


def test_plan_independent_of_agent_names():
    plan = build_research_plan(mode="evidence_review",
                               decision_target="evidence_review",
                               depth="standard", has_grounding=True,
                               has_dataset=False)
    blob = str(plan)
    for forbidden in ("claude", "gpt", "opencodex", "deepseek", "model=",
                      "agent=", "spawn_agent"):
        assert forbidden not in blob.lower()


# ---- schema-bound briefs (Task 12) ---------------------------------------

def test_finding_brief_contains_schema_derived_details(tmp_path):
    from pathlib import Path
    from engine.briefs import build_task_brief
    from engine.project import ProjectWorkspace
    plan = build_research_plan(mode="evidence_review",
                               decision_target="evidence_review",
                               depth="standard", has_grounding=True,
                               has_dataset=False)
    finding_step = next(s for s in plan if s.capability_id == "finding_extraction")
    ws = ProjectWorkspace.create(tmp_path, question="briefs?", title="t",
                                 research_mode="evidence_review")
    brief = build_task_brief(
        finding_step, project=ws,
        input_payload={"study_ids": ["STU-aaaaaaaa"]},
        output_path=tmp_path / "out" / "finding.jsonl")
    assert "finding.schema.json" in brief
    assert "finding_type" in brief
    assert "quantitative_effect" in brief and "qualitative_theme" in brief
    assert "positive" in brief and "not_applicable" in brief
    assert "STU-aaaaaaaa" in brief
    assert "relation_to_claim" in brief and "does NOT belong" in brief
    assert "validate_record" in brief


def test_wait_step_rejects_brief_generation(tmp_path):
    from engine.briefs import build_task_brief
    from engine.project import ProjectWorkspace
    from engine.planner import PlanStep
    plan = build_research_plan(mode="full_research_cycle",
                               decision_target="research_cycle",
                               depth="deep", has_grounding=True,
                               has_dataset=False)
    wait = next(s for s in plan if s.kind == "wait")
    assert isinstance(wait, PlanStep)
    ws = ProjectWorkspace.create(tmp_path, question="wait?", title="t",
                                 research_mode="full_research_cycle")
    try:
        build_task_brief(wait, project=ws, input_payload={},
                         output_path=tmp_path / "x.json")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "wait" in str(exc).lower()


def test_required_fields_are_schema_derived_not_hardcoded():
    # add a required field to the finding schema -> brief must reflect it
    import json
    from engine.briefs import build_task_brief
    from engine.contracts import schema_path
    from engine.planner import PlanStep
    from engine.project import ProjectWorkspace
    from pathlib import Path
    import tempfile

    import engine.contracts as contracts
    contracts._cache.clear()
    sch_path = schema_path("finding")
    original = sch_path.read_text(encoding="utf-8")
    sch = json.loads(original)
    sch["required"].append("hypothetical_new_field")
    sch["properties"]["hypothetical_new_field"] = {"type": "string"}
    sch_path.write_text(json.dumps(sch), encoding="utf-8")
    try:
        ws = ProjectWorkspace.create(Path(tempfile.mkdtemp()), question="q",
                                     title="t", research_mode="evidence_review")
        step = PlanStep(step_id="s1", kind="capability",
                        capability_id="finding_extraction", wait_state=None,
                        depends_on=(), input_refs=("study",),
                        output_contract="finding", gate=None)
        brief = build_task_brief(step, project=ws, input_payload={},
                                 output_path=Path("/tmp/out.json"))
        assert "hypothetical_new_field" in brief
        assert "REQUIRED" in brief
    finally:
        sch_path.write_text(original, encoding="utf-8")
        contracts._cache.clear()
