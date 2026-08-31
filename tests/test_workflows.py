from engine.workflows import PROJECTION_STAGE_ID, SCIENTIFIC_STAGE_IDS, execution_stages, workflow_registry


def test_canonical_protocol_has_applicability_and_no_presentation_stage():
    assert "applicability" in SCIENTIFIC_STAGE_IDS
    assert "present" not in SCIENTIFIC_STAGE_IDS
    assert execution_stages()[-1] == PROJECTION_STAGE_ID


def test_user_workflows_are_few_and_capability_based():
    registry = workflow_registry()
    assert {"evidence_review", "decision_and_pilot", "evaluate_and_update"} <= set(registry)
    assert all(spec.capability_ids for spec in registry.values())
