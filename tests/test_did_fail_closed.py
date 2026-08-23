"""DID fail-closed contract tests (P0 science gate).

run_did_analysis must NEVER fabricate inference: not-estimable designs return
status=error with a stable error_code and every inference field null; normal
DID runs carry inference_status=non_cluster_warning and a QED-correct WWC
rating (never "Meets Standards Without Reservations").
"""
import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from did_regression import run_did_analysis  # noqa: E402

INFERENCE_FIELDS = (
    "did_coefficient", "standard_error", "t_statistic", "p_value", "ci_95", "hedges_g",
)


def _write_csv(tmp_path: Path, rows: list) -> str:
    p = tmp_path / "did.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    return str(p)


@pytest.fixture
def normal_csv(tmp_path):
    rows = [["treat", "post", "score"]]
    rows += [[1, 1, 88 + i / 10] for i in range(20)]
    rows += [[1, 0, 70 + i / 10] for i in range(20)]
    rows += [[0, 1, 76 + i / 10] for i in range(20)]
    rows += [[0, 0, 72 + i / 10] for i in range(20)]
    return _write_csv(tmp_path, rows)


def test_collinear_design_fails_closed(tmp_path):
    rows = [["treat", "post", "score"],
            [1, 1, 90.0], [1, 1, 88.0], [0, 0, 70.0], [0, 0, 72.0]]
    res = run_did_analysis(_write_csv(tmp_path, rows))
    assert res["status"] == "error"
    assert res["error_code"] in ("ERR_EMPTY_CELL", "ERR_DESIGN_NOT_ESTIMABLE")
    for field in INFERENCE_FIELDS:
        assert res[field] is None, f"{field} must be null on error"


def test_saturated_model_fails_closed(tmp_path):
    rows = [["treat", "post", "score"],
            [1, 1, 90.0], [1, 0, 70.0], [0, 1, 80.0], [0, 0, 75.0]]
    res = run_did_analysis(_write_csv(tmp_path, rows))
    assert res["status"] == "error"
    assert res["error_code"] == "ERR_SATURATED"
    assert res["standard_error"] is None
    assert res["p_value"] is None


def test_zero_variance_outcome_fails_closed(tmp_path):
    rows = [["treat", "post", "score"]] + [[1, 1, 50.0], [1, 0, 50.0],
                                           [0, 1, 50.0], [0, 0, 50.0]] * 5
    res = run_did_analysis(_write_csv(tmp_path, rows))
    assert res["status"] == "error"
    assert res["error_code"] == "ERR_ZERO_VARIANCE"
    assert res["did_coefficient"] is None


def test_empty_cell_fails_closed(tmp_path):
    rows = [["treat", "post", "score"],
            [1, 1, 90.0], [1, 1, 88.0], [0, 0, 70.0], [0, 0, 72.0], [0, 1, 80.0]]
    res = run_did_analysis(_write_csv(tmp_path, rows))
    assert res["status"] == "error"
    assert res["error_code"] == "ERR_EMPTY_CELL"


def test_no_treat_variation_fails_closed(tmp_path):
    rows = [["treat", "post", "score"]] + [[0, 1, 80 + i] for i in range(5)] \
        + [[0, 0, 70 + i] for i in range(5)]
    res = run_did_analysis(_write_csv(tmp_path, rows))
    assert res["status"] == "error"
    assert res["error_code"] == "ERR_NO_TREAT_VARIATION"


def test_normal_did_has_non_cluster_warning(normal_csv):
    res = run_did_analysis(normal_csv)
    assert res["status"] == "success"
    assert res["inference_status"] == "non_cluster_warning"
    assert "not cluster-robust" in res["inference_warning"]
    assert res["did_coefficient"] is not None


def test_qed_never_without_reservations(normal_csv):
    res = run_did_analysis(normal_csv)
    assert res["status"] == "success"
    assert "Meets Standards Without Reservations" not in res["wwc_baseline_rating"]


def test_cluster_column_detected_but_not_claimed(tmp_path):
    rows = [["treat", "post", "score", "class_id"]]
    rows += [[1, 1, 88 + i / 10, (i % 4) + 1] for i in range(20)]
    rows += [[1, 0, 70 + i / 10, (i % 4) + 1] for i in range(20)]
    rows += [[0, 1, 76 + i / 10, (i % 4) + 1] for i in range(20)]
    rows += [[0, 0, 72 + i / 10, (i % 4) + 1] for i in range(20)]
    res = run_did_analysis(_write_csv(tmp_path, rows))
    assert res["status"] == "success"
    assert res["cluster_columns"] == ["class_id"]
    # Must NOT claim cluster-robust inference in this build
    assert res["inference_status"] == "non_cluster_warning"
    assert "cluster-robust" in res["inference_warning"]


def test_error_fields_do_not_collapse_to_zero(tmp_path):
    """Downstream contract: error inference fields must stay null, never 0."""
    rows = [["treat", "post", "score"],
            [1, 1, 90.0], [1, 0, 70.0], [0, 1, 80.0], [0, 0, 75.0]]
    res = run_did_analysis(_write_csv(tmp_path, rows))
    assert res["status"] == "error"
    for field in INFERENCE_FIELDS:
        val = res[field]
        assert val is None or val is False, f"{field} must not be falsy-collapsed to 0"