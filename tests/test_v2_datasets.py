"""Immutable DatasetAsset ingest + privacy gate tests."""

import csv
import json

import pytest

from engine.datasets import (
    ingest_dataset, validate_dataset_asset, derive_csv_profile,
    analysis_blocked_by_privacy,
)
from engine.project import ProjectWorkspace


def _make_csv(tmp_path, rows=10, cols=("id", "score")):
    p = tmp_path / "data.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for i in range(rows):
            w.writerow([i, f"{i / 10:.1f}"] if len(cols) == 2 else [i])
    return p


def _ws(tmp_path):
    return ProjectWorkspace.create(tmp_path, question="dataset?", title="d",
                                   research_mode="full_research_cycle")


def _privacy(**over):
    base = {
        "classification": "confidential",
        "deidentification_status": "not_done",
        "consent_metadata": {"status": "obtained"},
    }
    base.update(over)
    return base


def test_ingest_copies_bytes_once_and_hashes(tmp_path):
    ws = _ws(tmp_path)
    src = _make_csv(tmp_path)
    asset = ingest_dataset(ws, design_id="DSN-1", source_path=src,
                           privacy=_privacy())
    assert asset["dataset_id"].startswith("DAT-")
    dest = ws.path / "datasets" / "raw" / asset["dataset_id"] / "data.csv"
    assert dest.is_file()
    assert dest.read_bytes() == src.read_bytes()
    assert asset["content_hash"]
    assert asset["row_count"] == 10
    assert asset["column_count"] == 2


def test_reingest_same_bytes_dedupes(tmp_path):
    ws = _ws(tmp_path)
    src = _make_csv(tmp_path)
    a1 = ingest_dataset(ws, design_id="DSN-1", source_path=src, privacy=_privacy())
    a2 = ingest_dataset(ws, design_id="DSN-1", source_path=src, privacy=_privacy())
    assert a1["dataset_id"] == a2["dataset_id"]
    raw = ws.path / "datasets" / "raw"
    assert len(list(raw.iterdir())) == 1


def test_raw_never_written_to_library(tmp_path):
    ws = _ws(tmp_path)
    src = _make_csv(tmp_path)
    ingest_dataset(ws, design_id="DSN-1", source_path=src, privacy=_privacy())
    lib = tmp_path / "library"
    assert not lib.exists() or not any(lib.rglob("*.csv"))


def test_missing_privacy_classification_fails_gate(tmp_path):
    ws = _ws(tmp_path)
    src = _make_csv(tmp_path)
    with pytest.raises(ValueError):
        ingest_dataset(ws, design_id="DSN-1", source_path=src,
                       privacy=_privacy(classification=None))


def test_asset_schema_and_project_locality(tmp_path):
    ws = _ws(tmp_path)
    src = _make_csv(tmp_path)
    asset = ingest_dataset(ws, design_id="DSN-1", source_path=src,
                           privacy=_privacy())
    assert validate_dataset_asset(ws, asset) == []
    other = ProjectWorkspace.create(tmp_path, question="other?", title="o",
                                    research_mode="evidence_review")
    assert validate_dataset_asset(other, asset)


def test_deidentification_block(tmp_path):
    ws = _ws(tmp_path)
    src = _make_csv(tmp_path)
    asset = ingest_dataset(ws, design_id="DSN-1", source_path=src,
                           privacy=_privacy(deidentification_status="not_done"))
    # mark deidentification as required via the design's ethics flag path
    asset.setdefault("extensions", {})["deidentification_required"] = True
    reasons = analysis_blocked_by_privacy(asset)
    assert reasons and any("deidentified" in r for r in reasons)
    # done -> no block
    asset["deidentification_status"] = "done"
    assert analysis_blocked_by_privacy(asset) == []


def test_csv_profile_missingness(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("id,score,group\n1,,\n,2.0,A\n3,4.0,\n", encoding="utf-8")
    prof = derive_csv_profile(p)
    assert prof["row_count"] == 3
    assert prof["column_count"] == 3
    assert prof["missingness"] == {"id": 1, "score": 1, "group": 2}


def test_ingest_missing_source_raises(tmp_path):
    ws = _ws(tmp_path)
    with pytest.raises(FileNotFoundError):
        ingest_dataset(ws, design_id="DSN-1", source_path=tmp_path / "nope.csv",
                       privacy=_privacy())
