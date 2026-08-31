import json

from engine.evidencecore import load_domain, validate_frame
from engine.research_service import ResearchService

def test_policy_project_manifest_is_portable(tmp_path):
    service = ResearchService(tmp_path)
    project = service.create_project(question="Should phones be banned in high schools?",
                                     title="phone ban policy", domain="policy")
    assert project.manifest()["domain"] == "policy"


def test_policy_frame_rejects_learner_course_fields(tmp_path):
    policy = load_domain("policy")
    assert "frame_schema" in policy
    leaked = {
        "question": "Should phones be banned in high schools?",
        "decision_object": "adopt",
        "intervention": {"policy_name": "classroom_phone_ban", "policy_type": "mandate"},
        "population": {"target_group": "public_high_school_students"},
        "outcomes": {"primary": ["policy_effectiveness"]},
        "learner": {"grade_level": 9},
        "course": "math",
    }
    errors = validate_frame("policy", leaked)
    assert errors, "education learner/course fields must be rejected by the policy frame"


def test_policy_frame_accepts_canonical_shape():
    valid = {
        "question": "Should phones be banned in public high schools?",
        "decision_object": "adopt",
        "intervention": {"policy_name": "classroom_phone_ban", "policy_type": "mandate",
                         "jurisdiction": "public_high_schools"},
        "population": {"target_group": "public_high_school_students"},
        "outcomes": {"primary": ["policy_effectiveness"]},
    }
    assert validate_frame("policy", valid) == []
