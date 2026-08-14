"""Tests for engine/meta_synthesis.py - cross-project library synthesis (v3)."""
import json
from pathlib import Path

import pytest

from engine.library import ResearchLibrary
from engine.meta_synthesis import save_synthesis, synthesize_library

ROOT = Path(__file__).resolve().parent.parent


def _audit(study_id, status="pass"):
    return {"audit_id": f"AUD-{study_id[-1]}", "study_id": study_id,
            "policy_version": "2026-08-12.v2", "overall_status": status,
            "audited_at": "2026-08-13T00:00:00+00:00",
            "design_quality": 2, "sample_quality": 2, "measurement_validity": 2,
            "temporal_strength": 1, "bias_checks": [], "confounders": [],
            "limitations": [], "extensions": {}}


def _seed_library(tmp_path):
    lib = ResearchLibrary.open(tmp_path)
    sources = [{"source_id": "SRC-a", "origin": "external", "source_type": "paper",
                "canonical_locator": "https://doi.org/10.1/a", "validation_status": "valid",
                "content_hash": None, "extensions": {}},
               {"source_id": "SRC-b", "origin": "external", "source_type": "paper",
                "canonical_locator": "https://doi.org/10.1/b", "validation_status": "valid",
                "content_hash": None, "extensions": {}}]
    studies = [
        {"study_id": "STU-a", "source_ids": ["SRC-a"], "study_design": "rct",
         "population": "s1", "sample_ids": ["S1"], "independence_key": "proj1",
         "identity_status": "resolved", "extensions": {}},
        {"study_id": "STU-b", "source_ids": ["SRC-b"], "study_design": "quasi_experimental",
         "population": "s2", "sample_ids": ["S2"], "independence_key": "proj2",
         "identity_status": "resolved", "extensions": {}},
    ]
    findings = [
        {"finding_id": "FND-a1", "study_id": "STU-a", "finding_type": "quantitative_effect",
         "outcome_id": "OUT-retention", "measure": "d", "timepoint": None,
         "effect_direction": "positive", "effect_estimate": {"metric": "d", "value": 0.5, "raw_text": "d=0.5"},
         "raw_result_text": "d=0.5", "source_locator": "https://doi.org/10.1/a", "extensions": {}},
        {"finding_id": "FND-b1", "study_id": "STU-b", "finding_type": "quantitative_effect",
         "outcome_id": "OUT-retention", "measure": "d", "timepoint": None,
         "effect_direction": "null", "effect_estimate": {"metric": "d", "value": 0.02, "raw_text": "ns"},
         "raw_result_text": "ns", "source_locator": "https://doi.org/10.1/b", "extensions": {}},
        {"finding_id": "FND-b2", "study_id": "STU-b", "finding_type": "quantitative_effect",
         "outcome_id": "OUT-ai_dependency", "measure": "d", "timepoint": None,
         "effect_direction": "negative", "effect_estimate": {"metric": "d", "value": -0.3, "raw_text": "d=-0.3"},
         "raw_result_text": "d=-0.3", "source_locator": "https://doi.org/10.1/b", "extensions": {}},
    ]
    audits = [_audit("STU-a"), _audit("STU-b")]
    lib.add_verified_bundle(sources=sources, studies=studies,
                            findings=findings, audits=audits)
    return lib


def test_synthesis_aggregates_outcomes_and_studies(tmp_path):
    lib = _seed_library(tmp_path)
    syn = synthesize_library(lib)
    assert syn["library_revision"] == 1
    assert syn["independent_studies"] == 2
    assert syn["source_count"] == 2
    by_token = {o["outcome_token"]: o for o in syn["outcomes"]}
    assert by_token["retention"]["positive_findings"] == ["FND-a1"]
    assert by_token["retention"]["null_findings"] == ["FND-b1"]
    assert by_token["ai_dependency"]["negative_findings"] == ["FND-b2"]
    assert set(by_token["retention"]["study_keys"]) == {"proj1", "proj2"}


def test_synthesis_skips_failed_audit_studies(tmp_path):
    lib = _seed_library(tmp_path)
    # fail STU-a's audit by appending a newer failed audit
    lib.add_verified_bundle(sources=[], studies=[], findings=[],
                            audits=[_audit("STU-a", status="fail")])
    syn = synthesize_library(lib)
    by_token = {o["outcome_token"]: o for o in syn["outcomes"]}
    assert by_token["retention"]["positive_findings"] == []
    assert syn["independent_studies"] == 1


def test_save_synthesis_roundtrip(tmp_path):
    lib = _seed_library(tmp_path)
    syn = synthesize_library(lib)
    out = save_synthesis(syn, tmp_path / "syntheses")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["synthesis_id"] == syn["synthesis_id"]
    assert data["synthesis_id"].startswith("SYN-")
