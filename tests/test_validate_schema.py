"""Tests for scripts/validate_schema.py — schema validation engine."""
import json
import sys
from pathlib import Path

import pytest

from validate_schema import SchemaError, validate

ROOT = Path(__file__).resolve().parent.parent


def load_schema(name: str) -> dict:
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


def test_valid_evidence_passes():
    schema = load_schema("evidence.schema.json")
    evidence = {
        "evidence_id": "E-001",
        "source_id": "S-2023-test",
        "claim": "test claim",
        "outcome_type": "retention",
        "direction": "support",
        "source_location": "https://example.com/doi",
    }
    validate(evidence, schema)  # should not raise


def test_missing_required_field_fails():
    schema = load_schema("evidence.schema.json")
    evidence = {
        "evidence_id": "E-001",
        "claim": "no source_id here",
        "outcome_type": "retention",
        "direction": "support",
        "source_location": "https://example.com/doi",
    }
    with pytest.raises(SchemaError, match="source_id"):
        validate(evidence, schema)


def test_bad_enum_fails():
    schema = load_schema("evidence.schema.json")
    evidence = {
        "evidence_id": "E-001",
        "source_id": "S-1",
        "claim": "x",
        "outcome_type": "retention",
        "direction": "maybe",  # not in support|contradict|neutral
        "source_location": "https://example.com",
    }
    with pytest.raises(SchemaError, match="enum"):
        validate(evidence, schema)


def test_quality_dimension_range():
    schema = load_schema("evidence.schema.json")
    evidence = {
        "evidence_id": "E-001",
        "source_id": "S-1",
        "claim": "x",
        "outcome_type": "retention",
        "direction": "support",
        "source_location": "https://example.com",
        "quality_dimensions": {"D1_study_design": 5},  # > 2
    }
    with pytest.raises(SchemaError, match="maximum"):
        validate(evidence, schema)


def test_frame_requires_question():
    schema = load_schema("education-frame.schema.json")
    frame = {"decision_target": "evidence_review"}  # missing question
    with pytest.raises(SchemaError, match="question"):
        validate(frame, schema)


def test_verdict_enum_action():
    schema = load_schema("verdict.schema.json")
    verdict = {
        "decision_question": "q",
        "recommended_action": "maybe",
        "confidence": "High",
    }
    with pytest.raises(SchemaError, match="enum"):
        validate(verdict, schema)


def test_methodology_additional_properties_schema_enforced():
    """schema-valued additionalProperties (methodology audit_items) must be validated."""
    schema = load_schema("methodology.schema.json")
    bad_audit = {"target": "S-1", "verdict": "PASS",
                 "audit_items": {"control_group": {"status": "approved"}},  # invalid status
                 "task_vs_learning_guard": {}, "limitations": [], "suggestions": []}
    with pytest.raises(SchemaError, match="enum"):
        validate(bad_audit, schema)


def test_methodology_valid_audit_passes():
    schema = load_schema("methodology.schema.json")
    good = {"target": "S-1", "verdict": "PASS",
            "audit_items": {"control_group": {"status": "met", "note": "ok"}},
            "task_vs_learning_guard": {"equates_task_with_learning": False},
            "limitations": ["l"], "suggestions": ["s"]}
    validate(good, schema)  # should not raise


def test_repo_schemas_are_valid_json():
    for schema_file in sorted((ROOT / "schemas").glob("*.schema.json")):
        json.loads(schema_file.read_text(encoding="utf-8"))


def test_example_packs_pass_their_schemas():
    """End-to-end: every example pack record passes its matching schema."""
    from validate_schema import load_records, validate

    cases = [
        ("education-frame.schema.json", "examples/ai-coding-assistant/frame.json"),
        ("evidence.schema.json", "examples/ai-coding-assistant/evidence.jsonl"),
        ("verdict.schema.json", "examples/ai-coding-assistant/verdict.json"),
        ("education-frame.schema.json", "examples/ai-writing-assistant/frame.json"),
        ("evidence.schema.json", "examples/ai-writing-assistant/evidence.jsonl"),
        ("verdict.schema.json", "examples/ai-writing-assistant/verdict.json"),
        ("education-frame.schema.json", "examples/ai-tutor/frame.json"),
        ("evidence.schema.json", "examples/ai-tutor/evidence.jsonl"),
        ("verdict.schema.json", "examples/ai-tutor/verdict.json"),
    ]
    for schema_name, data_rel in cases:
        schema = load_schema(schema_name)
        records = load_records(ROOT / data_rel)
        for record in records:
            validate(record, schema)
