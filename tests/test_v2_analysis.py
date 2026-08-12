"""AnalysisPlan/AnalysisRun + Native Core descriptive analysis tests."""

import csv

import pytest

from engine.analysis import (
    run_native_descriptive, record_external_analysis,
    capability_unavailable, validate_analysis_plan, AnalysisCapabilityResult,
)
from engine.datasets import ingest_dataset
from engine.project import ProjectWorkspace


def _csv(tmp_path, rows):
    p = tmp_path / "d.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["student", "pre", "post", "group"])
        for r in rows:
            w.writerow(r)
    return p


def _ws(tmp_path):
    return ProjectWorkspace.create(tmp_path, question="analysis?", title="a",
                                   research_mode="full_research_cycle")


def _plan(ws, **over):
    base = {
        "analysis_plan_id": "APL-1", "design_id": "DSN-1",
        "primary_analysis": "pre/post descriptive comparison",
        "secondary_analyses": [], "assumption_checks": [],
        "preregistered": True, "created_at": "2026-08-12T00:00:00+00:00",
        "extensions": {},
    }
    base.update(over)
    return base


def _asset(ws, tmp_path, rows):
    src = _csv(tmp_path, rows)
    return ingest_dataset(ws, design_id="DSN-1", source_path=src,
                          privacy={"classification": "internal",
                                   "deidentification_status": "done",
                                   "consent_metadata": None})


def test_native_descriptive_profile(tmp_path):
    ws = _ws(tmp_path)
    asset = _asset(ws, tmp_path, [
        ["S1", "50", "60", "A"], ["S2", "40", "55", "A"], ["S3", "30", "45", "B"]])
    plan = _plan(ws, dataset_ids=[asset["dataset_id"]])
    run = run_native_descriptive(ws, plan)
    assert run["status"] == "completed"
    out = run["outputs"][asset["dataset_id"]]
    assert out["row_count"] == 3
    assert out["types"] == {"student": "string", "pre": "number",
                            "post": "number", "group": "string"}
    assert out["descriptive_statistics"]["pre"]["mean"] == 40.0
    assert out["descriptive_statistics"]["post"]["max"] == 60
    assert out["group_counts"]["group"] == {"A": 2, "B": 1}


def test_pre_post_descriptive_difference(tmp_path):
    ws = _ws(tmp_path)
    asset = _asset(ws, tmp_path, [
        ["S1", "50", "62", "A"], ["S2", "40", "48", "A"]])
    plan = _plan(ws, dataset_ids=[asset["dataset_id"]],
                 extensions={"pre_post_mapping": {
                     "dataset_id": asset["dataset_id"],
                     "pre_column": "pre", "post_column": "post"}})
    run = run_native_descriptive(ws, plan)
    diff = run["outputs"][asset["dataset_id"]]["pre_post_descriptive_difference"]
    assert diff["pre_mean"] == 45.0
    assert diff["post_mean"] == 55.0
    assert diff["mean_difference"] == 10.0
    assert "no p-value" in diff["note"]


def test_between_group_descriptive_difference(tmp_path):
    ws = _ws(tmp_path)
    asset = _asset(ws, tmp_path, [
        ["S1", "50", "60", "A"], ["S2", "40", "50", "A"], ["S3", "30", "40", "B"]])
    plan = _plan(ws, dataset_ids=[asset["dataset_id"]],
                 extensions={"between_group_mapping": {
                     "dataset_id": asset["dataset_id"],
                     "group_column": "group", "value_column": "post"}})
    run = run_native_descriptive(ws, plan)
    diff = run["outputs"][asset["dataset_id"]]["between_group_descriptive_difference"]
    assert diff["group_means"] == {"A": 55.0, "B": 40.0}
    assert "no p-value" in diff["note"]


def test_multilevel_without_provider_degrades_honestly(tmp_path):
    ws = _ws(tmp_path)
    plan = _plan(ws, dataset_ids=[])
    result = capability_unavailable("multilevel_analysis", plan)
    assert isinstance(result, AnalysisCapabilityResult)
    assert result.status == "ANALYSIS_CAPABILITY_UNAVAILABLE"
    assert result.output == {}
    assert result.warnings
    # no p-values / effect estimates fabricated
    assert "p-value" in result.warnings[0]


def test_external_analysis_recorded_with_provenance(tmp_path):
    ws = _ws(tmp_path)
    asset = _asset(ws, tmp_path, [["S1", "50", "60", "A"]])
    plan = _plan(ws, dataset_ids=[asset["dataset_id"]])
    run = record_external_analysis(
        ws, plan=plan, provider="scp:statistical_analysis",
        software={"name": "R", "version": "4.3", "package": "lme4"},
        outputs={"fit": {"estimate": 0.31, "p_value": 0.02}},
        assumption_checks=[{"check": "normality", "result": "pass"}],
        status="completed")
    assert run["status"] == "completed"
    assert run["extensions"]["provider"] == "scp:statistical_analysis"
    assert run["outputs"]["fit"]["p_value"] == 0.02
    assert run["dataset_ids"] == [asset["dataset_id"]]


def test_privacy_block_fails_run(tmp_path):
    ws = _ws(tmp_path)
    src = _csv(tmp_path, [["S1", "50", "60", "A"]])
    asset = ingest_dataset(ws, design_id="DSN-1", source_path=src,
                           privacy={"classification": "confidential",
                                    "deidentification_status": "not_done",
                                    "consent_metadata": None})
    asset.setdefault("extensions", {})["deidentification_required"] = True
    (ws.path / "datasets" / "raw" / asset["dataset_id"] / "manifest.json").write_text(
        __import__("json").dumps(asset), encoding="utf-8")
    plan = _plan(ws, dataset_ids=[asset["dataset_id"]])
    run = run_native_descriptive(ws, plan)
    assert run["status"] == "failed"
    assert "privacy_block" in run["outputs"]
