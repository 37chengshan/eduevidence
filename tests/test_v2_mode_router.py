"""Structured ResearchIntent → mode recommendation tests."""

from engine.mode_router import recommend_mode


def _intent(**over):
    base = {
        "decision_target": "teaching_decision",
        "wants_existing_evidence": True,
        "wants_study_design": False,
        "has_user_data": False,
        "wants_data_analysis": False,
        "wants_decision_update": False,
    }
    base.update(over)
    return base


def test_existing_evidence_only_is_evidence_review():
    r = recommend_mode(_intent())
    assert r.mode == "evidence_review"
    assert r.requires_grounding_review is False


def test_wants_study_design_is_full_cycle_with_grounding_review():
    r = recommend_mode(_intent(wants_study_design=True), project_has_grounding=False)
    assert r.mode == "full_research_cycle"
    assert r.requires_grounding_review is True
    assert any("evidence grounding" in reason for reason in r.reasons)


def test_grounded_project_skips_grounding_review():
    r = recommend_mode(_intent(wants_study_design=True), project_has_grounding=True)
    assert r.mode == "full_research_cycle"
    assert r.requires_grounding_review is False


def test_user_data_and_analysis_is_full_cycle():
    r = recommend_mode(_intent(has_user_data=True, wants_data_analysis=True))
    assert r.mode == "full_research_cycle"


def test_decision_update_is_full_cycle():
    r = recommend_mode(_intent(wants_decision_update=True))
    assert r.mode == "full_research_cycle"


def test_explicit_evidence_review_override_wins():
    r = recommend_mode(_intent(), explicit_mode="evidence_review")
    assert r.mode == "evidence_review"
    assert r.reasons == ()


def test_explicit_override_preserves_data_intent_warning():
    r = recommend_mode(_intent(has_user_data=True, wants_data_analysis=True),
                       explicit_mode="evidence_review")
    assert r.mode == "evidence_review"
    assert any("data" in reason.lower() for reason in r.reasons)
