"""Tests for scripts/claim_audit.py — Citation Audit (plan section 11)."""
import pytest

from claim_audit import audit_claims


def _evidence(eid, direction="support", outcome="retention", source="S-1", location="https://x"):
    return {
        "evidence_id": eid,
        "source_id": source,
        "source_location": location,
        "direction": direction,
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
                 "direction": "support", "outcome_type": "retention"}]
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


def test_unsupported_when_evidence_contradicts():
    evidence = [_evidence("E-1", direction="contradict")]
    claims = [{"claim": "c1", "evidence_ids": ["E-1"]}]
    results = audit_claims(claims, evidence)
    assert results[0]["status"] == "UNSUPPORTED"
