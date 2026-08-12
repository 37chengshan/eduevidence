"""Tests for scripts/claim_audit.py — Citation Audit (plan section 11)."""
import pytest

from claim_audit import audit_claims


def _evidence(eid, relation="support", effect="positive", outcome="retention",
              source="S-1", location="https://x", claim_id="C-001"):
    return {
        "evidence_id": eid,
        "source_id": source,
        "source_location": location,
        "relation_to_claim": relation,
        "effect_direction": effect,
        "claim_id": claim_id,
        "outcome_type": outcome,
        "applicability": {"scope": "university"},
    }


def test_supported_when_all_bind():
    evidence = [_evidence("E-1")]
    claims = [{"claim": "c1", "evidence_ids": ["E-1"], "outcome_type": "retention"}]
    results = audit_claims(claims, evidence)
    assert results[0]["status"] == "SUPPORTED"
    assert results[0]["issues"] == []


def test_unsupported_no_evidence():
    evidence = []
    claims = [{"claim": "c1", "evidence_ids": []}]
    results = audit_claims(claims, evidence)
    assert results[0]["status"] == "UNSUPPORTED"


def test_unsupported_missing_evidence_id():
    evidence = [_evidence("E-1")]
    claims = [{"claim": "c1", "evidence_ids": ["E-99"]}]
    results = audit_claims(claims, evidence)
    assert results[0]["status"] == "UNSUPPORTED"
    assert any("not found" in i for i in results[0]["issues"])


def test_unsupported_missing_source_location():
    evidence = [{"evidence_id": "E-1", "source_id": "S-1", "source_location": "",
                 "relation_to_claim": "support", "effect_direction": "positive",
                 "outcome_type": "retention"}]
    claims = [{"claim": "c1", "evidence_ids": ["E-1"]}]
    results = audit_claims(claims, evidence)
    assert results[0]["status"] == "UNSUPPORTED"


def test_downgrade_on_scope_exceed():
    evidence = [_evidence("E-1")]
    claims = [{"claim": "c1", "evidence_ids": ["E-1"], "scope": "worldwide"}]
    results = audit_claims(claims, evidence)
    assert results[0]["status"] == "DOWNGRADE_CONFIDENCE"


def test_downgrade_on_outcome_mismatch():
    evidence = [_evidence("E-1", outcome="retention")]
    claims = [{"claim": "c1", "evidence_ids": ["E-1"], "outcome_type": "transfer"}]
    results = audit_claims(claims, evidence)
    assert results[0]["status"] == "DOWNGRADE_CONFIDENCE"


def test_contradict_when_evidence_contradicts():
    evidence = [_evidence("E-1", relation="contradict")]
    claims = [{"claim": "c1", "evidence_ids": ["E-1"]}]
    results = audit_claims(claims, evidence)
    assert results[0]["status"] == "CONTRADICT"


# ---------------------------------------------------------------------------
# B-1 semantic cases: citation relation judged ONLY by relation_to_claim —
# never by effect_direction or the legacy direction field.
# ---------------------------------------------------------------------------

def test_semantic_case1_negative_claim_negative_effect_support():
    """negative claim + negative effect + relation_to_claim=support -> SUPPORTED.

    无护栏 AI 损害独立考试表现 <- 独立考试 -17% (support, negative)
    """
    evidence = [_evidence("E-1", relation="support", effect="negative")]
    claims = [{"claim": "无护栏 AI 损害独立考试表现", "evidence_ids": ["E-1"]}]
    results = audit_claims(claims, evidence)
    assert results[0]["status"] == "SUPPORTED"
    assert results[0]["issues"] == []


def test_semantic_case2_positive_claim_negative_effect_contradict():
    """positive claim + negative effect + relation_to_claim=contradict -> CONTRADICT.

    AI 提升成绩 <- 独立考试 -17% (contradict, negative)
    """
    evidence = [_evidence("E-1", relation="contradict", effect="negative")]
    claims = [{"claim": "AI 提升独立考试成绩", "evidence_ids": ["E-1"]}]
    results = audit_claims(claims, evidence)
    assert results[0]["status"] == "CONTRADICT"
    assert any("contradicts claim" in i for i in results[0]["issues"])


def test_semantic_case3_null_claim_null_effect_support():
    """null claim + null effect + relation_to_claim=support -> SUPPORTED.

    保留差异未达显著 <- 无显著差异 (support, null)
    """
    evidence = [_evidence("E-1", relation="support", effect="null")]
    claims = [{"claim": "一周后保留差异未达统计显著", "evidence_ids": ["E-1"]}]
    results = audit_claims(claims, evidence)
    assert results[0]["status"] == "SUPPORTED"
    assert results[0]["issues"] == []
