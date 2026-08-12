"""Strict-mode tests for scripts/validate_schema.py and compute_confidence.py.

Covers P0-02 (validator must actually enforce $ref / const / format: uri /
format: date-time / pattern), P1-01 (additionalProperties: false on all 12
schemas), P1-02 (methodology required fields), P1-03 (source_locator + fetch
provenance), and P0-05 (deterministic compute_confidence pipeline).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from validate_schema import SchemaError, Validator, validate

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = ROOT / "schemas"
SCHEMA_FILES = sorted(SCHEMAS_DIR.glob("*.schema.json"))

#: Minimal valid object per schema (all required fields satisfied).
VALID_SAMPLES = {
    "education-frame.schema.json": {
        "question": "Should first-year students use AI coding assistants?",
        "decision_target": "evidence_review",
    },
    "source.schema.json": {
        "source_id": "S-2023-kazemitabaar",
        "title": "A study",
        "canonical_url": "https://doi.org/10.1145/3544548.3580919",
        "authority_level": "tier1_paper_doi",
    },
    "evidence.schema.json": {
        "evidence_id": "E-001",
        "source_id": "S-2023-kazemitabaar",
        "claim": "test claim",
        "outcome_type": "retention",
        "direction": "support",
        "source_location": "https://doi.org/10.1145/3544548.3580919",
    },
    "methodology.schema.json": {
        "target": "overall",
        "verdict": "PASS",
        "audit_items": {"control_group": {"status": "met"}},
        "task_vs_learning_guard": {"equates_task_with_learning": False},
        "limitations": [],
        "suggestions": [],
    },
    "verdict.schema.json": {
        "decision_question": "Should we adopt?",
        "recommended_action": "pilot",
        "confidence": "Moderate",
    },
    "intervention.schema.json": {
        "decision": "pilot",
        "target_learners": "first-year CS students",
        "pilot_duration": "8_weeks",
        "stop_conditions": [],
    },
    "evaluation.schema.json": {
        "research_question": "Does the pilot improve transfer?",
        "groups": {"treatment": "A", "comparison": "B"},
        "analysis_plan": "ANCOVA",
    },
    "chart-spec.schema.json": {
        "chart_id": "outcome-evidence-overview",
        "purpose": "interactive_analysis",
        "engine": "echarts",
        "data_ref": "outcomes",
    },
    "report-spec.schema.json": {
        "title": "EduEvidence Report",
        "theme": "claude",
        "sections": [],
    },
    "report-result.schema.json": {
        "meta": {"skill": "eduevidence"},
        "research_frame": {},
        "decision": {},
        "evidence": [],
    },
    "fetch-result.schema.json": {
        "original_url": "https://dl.acm.org/doi/10.1145/3544548.3580919",
        "fetch_status": "FETCH_VALID",
    },
    "cross-model-review.schema.json": {
        "agreement": "high",
        "final_recommendation": "approve with revisions",
    },
    "agent-mcp-approval.schema.json": {
        "approved": True,
        "approved_at": "2026-08-12T10:00:00+00:00",
        "allowed_clis": ["codex", "claude"],
        "role_mapping_hash": "abc123abc123abc123abc123abc123abc123abc123abc123abc123abc123abcd",
        "roles": {"skeptic": {"cli": "codex", "model": "claude-opus-4-6"}},
    },
}


def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- P1-01/1-02
@pytest.mark.parametrize("schema_file", SCHEMA_FILES)
def test_all_schemas_are_strict(schema_file):
    """Every schema must reject misspelled/unknown top-level fields."""
    schema = load_schema(schema_file.name)
    assert schema.get("additionalProperties") is False, f"{schema_file.name}: additionalProperties must be false"
    valid = VALID_SAMPLES[schema_file.name]
    validate(valid, schema)  # minimal valid object passes
    bad = dict(valid)
    bad["typo_field"] = "misspelled"
    with pytest.raises(SchemaError, match="unexpected property"):
        validate(bad, schema)


def test_schema_count_is_thirteen():
    assert len(SCHEMA_FILES) == 13


def test_extensions_container_allowed():
    """The unified extensions container stays open (P1-01 escape hatch)."""
    schema = load_schema("evidence.schema.json")
    evidence = dict(VALID_SAMPLES["evidence.schema.json"])
    evidence["extensions"] = {"custom_note": "anything"}
    validate(evidence, schema)


def test_methodology_requires_audit_and_guards():
    schema = load_schema("methodology.schema.json")
    base = dict(VALID_SAMPLES["methodology.schema.json"])
    for missing in ("audit_items", "task_vs_learning_guard", "limitations", "suggestions"):
        bad = {k: v for k, v in base.items() if k != missing}
        with pytest.raises(SchemaError, match="missing required field"):
            validate(bad, schema)


# ---------------------------------------------------------------- const
def test_meta_skill_const_rejects_other_skills():
    """meta.skill must be exactly 'eduevidence' (P0-02 acceptance)."""
    schema = load_schema("report-result.schema.json")
    result = dict(VALID_SAMPLES["report-result.schema.json"])
    result["meta"] = {"skill": "some-other-skill"}
    with pytest.raises(SchemaError, match="const"):
        validate(result, schema)


def test_meta_skill_const_accepts_eduevidence():
    schema = load_schema("report-result.schema.json")
    validate(VALID_SAMPLES["report-result.schema.json"], schema)


# ---------------------------------------------------------------- format
@pytest.mark.parametrize("bad_uri", [
    "not a url",
    "example.com/no-scheme",
    "https://exa mple.com/space",
    "",
])
def test_invalid_uri_fails(bad_uri):
    schema = load_schema("fetch-result.schema.json")
    bad = dict(VALID_SAMPLES["fetch-result.schema.json"])
    bad["original_url"] = bad_uri
    with pytest.raises(SchemaError, match="format: uri"):
        validate(bad, schema)


def test_valid_uri_passes():
    schema = load_schema("fetch-result.schema.json")
    good = dict(VALID_SAMPLES["fetch-result.schema.json"])
    good["original_url"] = "https://doi.org/10.1145/3544548.3580919"
    good["resolved_url"] = "http://dl.acm.org/doi/10.1145/3544548.3580919"
    validate(good, schema)


@pytest.mark.parametrize("bad_dt", [
    "2026-08-12",            # date only, no time
    "not-a-date",
    "2026-08-12T06:41:04",   # no timezone offset
    "2026-13-40T10:00:00Z",  # impossible calendar values
])
def test_invalid_datetime_fails(bad_dt):
    schema = load_schema("fetch-result.schema.json")
    bad = dict(VALID_SAMPLES["fetch-result.schema.json"])
    bad["fetched_at"] = bad_dt
    with pytest.raises(SchemaError, match="format: date-time"):
        validate(bad, schema)


@pytest.mark.parametrize("good_dt", [
    "2026-08-12T06:41:04.660833+00:00",
    "2026-08-12T06:41:04Z",
    "2026-08-12 06:41:04+08:00",
])
def test_valid_datetime_passes(good_dt):
    schema = load_schema("fetch-result.schema.json")
    good = dict(VALID_SAMPLES["fetch-result.schema.json"])
    good["fetched_at"] = good_dt
    validate(good, schema)


# ---------------------------------------------------------------- $ref
def test_ref_local_definitions_valid():
    """source.fetch resolves against #/definitions/fetchProvenance."""
    schema = load_schema("source.schema.json")
    good = dict(VALID_SAMPLES["source.schema.json"])
    good["fetch"] = {
        "fetch_status": "FETCH_VALID",
        "original_url": "https://doi.org/10.1073/pnas.2422633122",
        "fetched_at": "2026-08-12T06:41:04Z",
    }
    validate(good, schema)


def test_ref_local_definitions_invalid_status_fails():
    """Invalid value inside a $ref'd definition must fail (P0-02 acceptance)."""
    schema = load_schema("source.schema.json")
    bad = dict(VALID_SAMPLES["source.schema.json"])
    bad["fetch"] = {"fetch_status": "FETCH_MAYBE"}
    with pytest.raises(SchemaError, match="enum"):
        validate(bad, schema)


def test_ref_local_definitions_missing_required_fails():
    schema = load_schema("source.schema.json")
    bad = dict(VALID_SAMPLES["source.schema.json"])
    bad["fetch"] = {"original_url": "https://doi.org/x"}  # no fetch_status
    with pytest.raises(SchemaError, match="missing required field"):
        validate(bad, schema)


def test_ref_local_definitions_unknown_field_fails():
    """Misspelled field inside a $ref'd definition must fail (P0-02 acceptance)."""
    schema = load_schema("source.schema.json")
    bad = dict(VALID_SAMPLES["source.schema.json"])
    bad["fetch"] = {"fetch_status": "FETCH_VALID", "statuz": "ok"}
    with pytest.raises(SchemaError, match="unexpected property"):
        validate(bad, schema)


def test_ref_relative_file_valid():
    """report-spec.schema.json charts $ref chart-spec.schema.json (file ref)."""
    schema = load_schema("report-spec.schema.json")
    spec = dict(VALID_SAMPLES["report-spec.schema.json"])
    spec["charts"] = [dict(VALID_SAMPLES["chart-spec.schema.json"])]
    Validator(schema, base_dir=SCHEMAS_DIR).validate(spec, schema)


def test_ref_relative_file_invalid_fails():
    schema = load_schema("report-spec.schema.json")
    spec = dict(VALID_SAMPLES["report-spec.schema.json"])
    spec["charts"] = [{"chart_id": "c1"}]  # missing required chart fields
    with pytest.raises(SchemaError, match="required"):
        Validator(schema, base_dir=SCHEMAS_DIR).validate(spec, schema)


def test_unresolvable_ref_fails():
    schema = load_schema("source.schema.json")
    schema = {"type": "object", "properties": {"x": {"$ref": "#/definitions/nope"}}}
    with pytest.raises(SchemaError, match="unresolvable"):
        validate({"x": 1}, schema)


# ---------------------------------------------------------------- pattern
def test_claim_id_pattern():
    schema = load_schema("report-result.schema.json")
    result = dict(VALID_SAMPLES["report-result.schema.json"])
    result["claims"] = [{"claim_id": "C-001", "claim": "c", "evidence_ids": []}]
    validate(result, schema)
    result["claims"] = [{"claim_id": "X-1", "claim": "c"}]
    with pytest.raises(SchemaError, match="pattern"):
        validate(result, schema)


# ---------------------------------------------------------------- P1-03
def test_source_locator_fields():
    schema = load_schema("source.schema.json")
    good = dict(VALID_SAMPLES["source.schema.json"])
    good["source_locator"] = {
        "type": "page",
        "page": 12,
        "section": "Results",
        "paragraph": 3,
        "quote_hash": "abc123",
    }
    validate(good, schema)


def test_source_locator_rejects_unknown_field():
    schema = load_schema("source.schema.json")
    bad = dict(VALID_SAMPLES["source.schema.json"])
    bad["source_locator"] = {"type": "page", "line_number": 99}
    with pytest.raises(SchemaError, match="unexpected property"):
        validate(bad, schema)


# ---------------------------------------------------------------- P0-05
def _make_evidence(study_id, sample_id, direction="support", quality=8.0,
                   status="SUPPORTED"):
    return {
        "evidence_id": f"E-{study_id}-{sample_id}",
        "source_id": f"S-{study_id}",
        "claim": "claim",
        "outcome_type": "retention",
        "direction": direction,
        "relation_to_claim": direction,
        "study_id": study_id,
        "sample_id": sample_id,
        "quality_score": quality,
        "quality_dimensions": {"D5_directness": 2},
        "status": status,
        "source_location": "https://example.com/doi",
    }


def test_compute_confidence_weights_independent_studies():
    from compute_confidence import compute_confidence
    same_study = [_make_evidence("S1", "S1-a"), _make_evidence("S1", "S1-b")]
    diff_study = [_make_evidence("S1", "S1-a"), _make_evidence("S2", "S2-a")]
    c_same = compute_confidence(same_study)
    c_diff = compute_confidence(diff_study)
    assert c_same["independent_studies"] == 1
    assert c_same["independent_samples"] == 2
    assert c_diff["independent_studies"] == 2
    assert c_diff["independent_samples"] == 2
    # 独立研究越多，count term 越高 → 分数越高
    assert (c_diff["confidence_breakdown"]["count_term"]
            > c_same["confidence_breakdown"]["count_term"])


def test_compute_confidence_is_deterministic():
    from compute_confidence import compute_confidence
    evs = [_make_evidence("S1", "S1-a"), _make_evidence("S2", "S2-a", "contradict")]
    assert compute_confidence(evs) == compute_confidence(evs)


def test_compute_confidence_empty_is_insufficient():
    from compute_confidence import compute_confidence
    result = compute_confidence([])
    assert result["confidence"] == "Insufficient"
    assert result["confidence_policy_version"]


def test_compute_confidence_cli_overrides_model_values(tmp_path):
    """CLI: deterministic confidence replaces model confidence in final verdict."""
    evidence_path = tmp_path / "evidence.jsonl"
    evidence_path.write_text(
        "\n".join(json.dumps(_make_evidence(s, f"{s}-a")) for s in ("S1", "S2"))
        + "\n", encoding="utf-8")
    raw = {"decision_question": "q", "recommended_action": "pilot",
           "confidence": "Insufficient", "confidence_breakdown": {"score": 0.01}}
    verdict_path = tmp_path / "raw_verdict.json"
    verdict_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    out_path = tmp_path / "final_verdict.json"

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/compute_confidence.py"),
         "--verdict", str(verdict_path), "--evidence", str(evidence_path),
         "--out", str(out_path)],
        capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode == 0, proc.stderr
    final = json.loads(out_path.read_text(encoding="utf-8"))
    from compute_confidence import compute_confidence
    evs = [json.loads(line) for line in evidence_path.read_text(encoding="utf-8").splitlines()]
    expected = compute_confidence(evs)
    assert final["confidence"] == expected["confidence"]  # 模型值被确定性计算覆盖
    assert final["confidence"] == "High"                  # 与下方证据强度一致
    assert final["confidence_score"] == pytest.approx(expected["confidence_breakdown"]["score"])
    assert final["confidence_policy_version"] == expected["confidence_policy_version"]
    assert final["independent_studies"] == 2
    assert final["independent_samples"] == 2
    assert final["raw_model_confidence"] == "Insufficient"  # 原始值保留审计
    assert "score" in final["confidence_breakdown"]
