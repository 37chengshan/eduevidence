"""v4 builtin evidence library — generation + schema + preliminary verdict tests.

Verifies:
  1. scripts/build_evidence_library.py generates benchmarks/evidence-library.json
     with >= 100 deduplicated entries (the build runs once per module via an
     autouse fixture, so every test sees a fresh, schema-checked library).
  2. The generated library validates against schemas/v4/evidence-library.schema.json
     (repo zero-dependency Validator from scripts/validate_schema.py).
  3. engine.library_builtin.preliminary_verdict returns pilot/insufficient_evidence
     with preliminary=true for flipped-classroom style questions, and never crashes
     on empty questions (insufficient_evidence, no matches).

benchmarks/annotations and examples/ are read-only: this test only reads them.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from engine.library_builtin import (
    DIRECTIONS,
    load_builtin_library,
    preliminary_verdict,
)

ROOT = Path(__file__).resolve().parent.parent
LIBRARY_JSON = ROOT / "benchmarks" / "evidence-library.json"
SCHEMA_JSON = ROOT / "schemas" / "v4" / "evidence-library.schema.json"
BUILD_SCRIPT = ROOT / "scripts" / "build_evidence_library.py"

MIN_ENTRIES = 100


def _run_build() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BUILD_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


@pytest.fixture(scope="module", autouse=True)
def _built_library():
    """Rebuild the library once per module so tests run against a fresh artifact."""
    result = _run_build()
    assert result.returncode == 0, (
        f"build_evidence_library.py failed ({result.returncode}):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    yield


def _load_library_json() -> dict:
    return json.loads(LIBRARY_JSON.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. generation
# ---------------------------------------------------------------------------
def test_build_script_generates_library_with_100_entries():
    lib = _load_library_json()
    assert lib["library_id"]
    assert lib["version"]
    assert lib["generated_at"]
    assert lib["coverage_note"]
    assert len(lib["entries"]) >= MIN_ENTRIES, (
        f"expected >= {MIN_ENTRIES} entries, got {len(lib['entries'])}"
    )


def test_entries_are_unique_and_deduplicated():
    lib = _load_library_json()
    entry_ids = [e["entry_id"] for e in lib["entries"]]
    assert len(entry_ids) == len(set(entry_ids)), "entry_id must be unique"
    # dedup key (source_id, outcome_token, claim_text) must be unique
    keys = {(e["source_id"], e["outcome_token"], e["claim_text"].strip().lower())
            for e in lib["entries"]}
    assert len(keys) == len(lib["entries"]), (
        "entries must be deduplicated on (source_id, outcome_token, claim_text)"
    )


# ---------------------------------------------------------------------------
# 2. schema validation
# ---------------------------------------------------------------------------
def test_library_validates_against_v4_schema():
    from validate_schema import SchemaError, Validator  # conftest adds scripts/

    schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
    lib = _load_library_json()
    validator = Validator(schema, base_dir=SCHEMA_JSON.parent.parent)
    try:
        validator.validate(lib, schema, "$")
    except SchemaError as exc:
        pytest.fail(f"library failed v4 schema validation: {exc}")


def test_entry_fields_are_well_formed():
    lib = _load_library_json()
    for entry in lib["entries"]:
        assert entry["direction"] in DIRECTIONS
        assert entry["claim_text"].strip()
        assert entry["outcome_token"].strip()
        assert entry["domains"], f"{entry['entry_id']} missing domains"
        assert entry["confidence_markers"], f"{entry['entry_id']} missing markers"
        assert entry["year"] is None or isinstance(entry["year"], int)


# ---------------------------------------------------------------------------
# 3. engine load + preliminary verdict
# ---------------------------------------------------------------------------
def test_load_builtin_library_returns_valid_library():
    lib = load_builtin_library()
    assert len(lib["entries"]) >= MIN_ENTRIES
    assert set(lib.keys()) >= {"library_id", "version", "generated_at",
                               "entries", "coverage_note"}


@pytest.mark.parametrize(
    "question",
    [
        "翻转课堂相比传统课堂讲授是否显著提高学生两周后对课程知识的保持率？",
        "翻转课堂教学方法能否提高学生对课程知识的保持率？",
        "翻转课堂与讲授式教学相比，对知识保持的效果如何？",
    ],
)
def test_flipped_classroom_question_verdict(question):
    result = preliminary_verdict(question)
    assert result["preliminary"] is True
    assert result["library_version"], "library_version must be present"
    assert result["verdict"] in ("pilot", "insufficient_evidence"), (
        f"flipped-classroom question must not be rejected or adopted, "
        f"got {result['verdict']}"
    )
    assert result["coverage"]["matched_entries"] or result["verdict"] == "insufficient_evidence"


@pytest.mark.parametrize("question", ["", "   ", "？？？"])
def test_empty_question_does_not_crash(question):
    result = preliminary_verdict(question)
    assert result["preliminary"] is True
    assert result["verdict"] == "insufficient_evidence"
    assert result["coverage"]["matched_entries"] == []


@pytest.mark.parametrize(
    "question",
    [
        "翻转课堂相比传统课堂讲授是否显著提高学生两周后对课程知识的保持率？",
        "使用AI编程助手（如GitHub Copilot）完成编程作业的大学生，其代码正确率是否显著高于不使用AI助手的对照学生？",
        "在写作课程中使用AI写作助手的学生，脱离工具后独立完成议论文写作的得分是否显著低于不使用AI的学生？",
        "",
    ],
)
def test_preliminary_verdict_never_adopts(question):
    assert preliminary_verdict(question)["verdict"] != "adopt"
