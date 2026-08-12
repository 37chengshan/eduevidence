"""Semantic-separation tests for the V2 evidence graph contracts.

The three core semantics must never be conflated:
  - Finding.effect_direction        = what the study actually observed
  - EvidenceLink.relation_to_claim  = does this result support the Claim?
  - EvidenceLink.decision_implication = what it means for the current decision
"""

from engine.contracts import validate_record


def _source(**over):
    base = {
        "source_id": "SRC-aaaaaaaa",
        "origin": "external",
        "source_type": "journal_article",
        "canonical_locator": "https://doi.org/10.0000/example",
        "validation_status": "valid",
        "content_hash": "sha256:abc",
        "extensions": {},
    }
    base.update(over)
    return base


def _study(**over):
    base = {
        "study_id": "STU-aaaaaaaa",
        "source_ids": ["SRC-aaaaaaaa"],
        "study_design": "RCT",
        "population": "first-year CS students",
        "sample_ids": ["S1"],
        "sample_size": 120,
        "intervention": "AI tutor",
        "comparison": "no AI",
        "independence_key": "doi:10.0000/example#study1",
        "identity_status": "resolved",
        "extensions": {},
    }
    base.update(over)
    return base


def _finding(**over):
    base = {
        "finding_id": "FND-aaaaaaaa",
        "study_id": "STU-aaaaaaaa",
        "finding_type": "quantitative_effect",
        "outcome_id": "OUT-aaaaaaaa",
        "measure": "post-test score",
        "timepoint": "immediate",
        "effect_direction": "positive",
        "effect_estimate": {
            "metric": "mean difference",
            "value": 0.31,
            "unit": "sd",
            "ci_low": 0.1,
            "ci_high": 0.5,
            "p_value": 0.003,
            "raw_text": "d = 0.31, 95% CI [0.10, 0.50]",
        },
        "raw_result_text": "intervention group scored higher",
        "source_locator": "p.12, Table 3",
        "extensions": {},
    }
    base.update(over)
    return base


def _outcome(**over):
    base = {
        "outcome_id": "OUT-aaaaaaaa",
        "name": "independent problem solving",
        "outcome_type": "learning",
        "extensions": {},
    }
    base.update(over)
    return base


def _claim(**over):
    base = {
        "claim_id": "CLM-aaaaaaaa",
        "text": "AI tutors improve independent problem solving",
        "claim_type": "effectiveness",
        "primary_outcome_ids": ["OUT-aaaaaaaa"],
        "scope": "first-year CS, 16-week course",
        "created_in_revision": 1,
        "status": "active",
        "extensions": {},
    }
    base.update(over)
    return base


def _link(**over):
    base = {
        "evidence_link_id": "LNK-aaaaaaaa",
        "finding_id": "FND-aaaaaaaa",
        "claim_id": "CLM-aaaaaaaa",
        "relation_to_claim": "support",
        "decision_implication": "support_adoption",
        "directness": 2,
        "applicability": {"scope_match": "direct"},
        "reasoning_note": "same population and outcome",
        "created_in_revision": 1,
        "extensions": {},
    }
    base.update(over)
    return base


def _audit(**over):
    base = {
        "audit_id": "AUD-aaaaaaaa",
        "study_id": "STU-aaaaaaaa",
        "policy_version": "2026-08-12.v2",
        "design_quality": 2,
        "sample_quality": 1,
        "measurement_validity": 2,
        "temporal_strength": 1,
        "bias_checks": ["blinding"],
        "confounders": [],
        "limitations": ["single site"],
        "overall_status": "pass",
        "audited_at": "2026-08-12T00:00:00+00:00",
        "extensions": {},
    }
    base.update(over)
    return base


# ---- entity schemas are strict ------------------------------------------

def test_source_valid():
    assert validate_record("source", _source()) == []


def test_source_rejects_bad_validation_status():
    assert validate_record("source", _source(validation_status="maybe")) != []


def test_source_rejects_relative_locator():
    assert validate_record("source", _source(canonical_locator="papers/foo.pdf")) != []


def test_source_accepts_project_uri_locator():
    rec = _source(canonical_locator="project://PRJ-1/datasets/DAT-1")
    assert validate_record("source", rec) == []


def test_study_valid():
    assert validate_record("study", _study()) == []


def test_study_rejects_missing_sample_ids():
    rec = _study()
    del rec["sample_ids"]
    assert validate_record("study", rec) != []


def test_study_rejects_unknown_identity_status():
    assert validate_record("study", _study(identity_status="guessed")) != []


def test_finding_valid():
    assert validate_record("finding", _finding()) == []


def test_finding_rejects_invalid_effect_direction():
    assert validate_record("finding", _finding(effect_direction="support")) != []


def test_qualitative_finding_accepts_not_applicable():
    rec = _finding(finding_type="qualitative_theme", effect_direction="not_applicable")
    assert validate_record("finding", rec) == []


def test_finding_accepts_null_effect_estimate():
    rec = _finding(effect_estimate=None)
    assert validate_record("finding", rec) == []


def test_finding_rejects_effect_estimate_without_raw_text():
    rec = _finding(effect_estimate={"metric": "d", "value": 0.3})
    assert validate_record("finding", rec) != []


def test_outcome_valid_and_typed():
    assert validate_record("outcome", _outcome()) == []
    assert validate_record("outcome", _outcome(outcome_type="risk")) == []
    assert validate_record("outcome", _outcome(outcome_type="not_a_type")) != []


def test_claim_valid():
    assert validate_record("claim", _claim()) == []


def test_claim_rejects_zero_created_in_revision():
    assert validate_record("claim", _claim(created_in_revision=0)) != []


def test_link_valid():
    assert validate_record("evidence-link", _link()) == []


def test_link_rejects_unknown_relation():
    assert validate_record("evidence-link", _link(relation_to_claim="proves")) != []


def test_link_rejects_unknown_implication():
    assert validate_record("evidence-link", _link(decision_implication="adopt")) != []


def test_link_directness_bounded():
    assert validate_record("evidence-link", _link(directness=3)) != []
    assert validate_record("evidence-link", _link(directness=-1)) != []


def test_link_applicability_scope_match_enum():
    assert validate_record("evidence-link",
                           _link(applicability={"scope_match": "partial"})) == []
    assert validate_record("evidence-link",
                           _link(applicability={"scope_match": "none"})) != []


def test_audit_valid():
    assert validate_record("methodology-audit", _audit()) == []


def test_audit_quality_scales_bounded():
    assert validate_record("methodology-audit", _audit(design_quality=3)) != []
    assert validate_record("methodology-audit", _audit(overall_status="great")) != []
