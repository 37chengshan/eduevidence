#!/usr/bin/env python3
"""scripts/did_regression.py — Deterministic Difference-in-Differences (DID) Statistical Engine.

Pure Python stdlib implementation with zero mandatory dependencies (no pandas/numpy required),
with automatic acceleration when pandas/numpy are present.

Model:
    Y_ist = beta0 + beta1 * Treat_i + beta2 * Post_t + delta * (Treat_i * Post_t) + epsilon_ist

Where:
    delta = Causal DID treatment effect estimate
    beta1 = Baseline difference between treatment and control
    beta2 = Common secular time trend
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path
def _two_tailed_p_from_z(z: float) -> float:
    """Standard normal two-tailed p-value."""
    return 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))


def _null_inference() -> Dict[str, Any]:
    """Fail-closed inference fields for not-estimable designs (never fake SE/p)."""
    return {
        "did_coefficient": None,
        "standard_error": None,
        "t_statistic": None,
        "p_value": None,
        "ci_95": None,
        "hedges_g": None,
    }


def _solve_linear_system(A: List[List[float]], b: List[float]) -> List[float]:
    """Gaussian elimination with partial pivoting for small OLS systems (p <= 10)."""
    n = len(b)
    # Augmented matrix
    M = [A[i][:] + [b[i]] for i in range(n)]

    for i in range(n):
        # Pivot
        max_row = max(range(i, n), key=lambda r: abs(M[r][i]))
        if abs(M[max_row][i]) < 1e-12:
            raise ValueError("Singular matrix in OLS estimation")
        M[i], M[max_row] = M[max_row], M[i]

        pivot = M[i][i]
        for j in range(i, n + 1):
            M[i][j] /= pivot

        for r in range(n):
            if r != i:
                factor = M[r][i]
                for c in range(i, n + 1):
                    M[r][c] -= factor * M[i][c]

    return [M[i][n] for i in range(n)]


def _matrix_inverse(A: List[List[float]]) -> List[List[float]]:
    """Inverts an n x n matrix using Gauss-Jordan elimination."""
    n = len(A)
    # Augment with identity
    M = [A[i][:] + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]

    for i in range(n):
        max_row = max(range(i, n), key=lambda r: abs(M[r][i]))
        if abs(M[max_row][i]) < 1e-12:
            raise ValueError("Singular matrix in inversion")
        M[i], M[max_row] = M[max_row], M[i]

        pivot = M[i][i]
        for j in range(2 * n):
            M[i][j] /= pivot

        for r in range(n):
            if r != i:
                factor = M[r][i]
                for c in range(2 * n):
                    M[r][c] -= factor * M[i][c]

    return [[M[i][n + j] for j in range(n)] for i in range(n)]


def run_did_analysis(csv_path: str) -> Dict[str, Any]:
    """Runs Difference-in-Differences regression on a classroom/field CSV dataset."""
    path = Path(csv_path)
    if not path.exists():
        return {"status": "error", "error_code": "ERR_NO_FILE",
                "message": f"File not found: {csv_path}"}

    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if len(rows) < 4:
        return {"status": "error", "error_code": "ERR_INSUFFICIENT_ROWS",
                "message": "Insufficient data rows (minimum 4 required)"}

    # Normalize column names (+ cluster candidates; exact names only, never guessed)
    field_map = {}
    cluster_columns: List[str] = []
    for col in rows[0].keys():
        cl = col.strip().lower()
        if cl in ("cluster_id", "class_id", "school_id", "group_id") or cl.endswith("_cluster"):
            cluster_columns.append(col)
        if "treat" in cl or cl in ("group", "condition", "is_treatment"):
            field_map["treat"] = col
        elif "post" in cl or "after" in cl or "period" in cl or "time" in cl or "pre_post" in cl:
            field_map["post"] = col
        elif "score" in cl or "outcome" in cl or "grade" in cl or "result" in cl or "performance" in cl or cl == "y":
            field_map["outcome"] = col

    if "treat" not in field_map or "post" not in field_map or "outcome" not in field_map:
        return {
            "status": "error", "error_code": "ERR_MISSING_COLUMNS",
            "message": f"CSV missing required columns (need treat/post/outcome). Found: {list(rows[0].keys())}"
        }

    # Parse numeric arrays
    y_vals: List[float] = []
    treat_vals: List[float] = []
    post_vals: List[float] = []
    treat_post_vals: List[float] = []

    # Cells for 2x2 table
    cell_y = {(0, 0): [], (0, 1): [], (1, 0): [], (1, 1): []}

    for r in rows:
        try:
            t = 1.0 if float(r[field_map["treat"]]) > 0.5 else 0.0
            p = 1.0 if float(r[field_map["post"]]) > 0.5 else 0.0
            y = float(r[field_map["outcome"]])
            
            treat_vals.append(t)
            post_vals.append(p)
            treat_post_vals.append(t * p)
            y_vals.append(y)
            cell_y[(int(t), int(p))].append(y)
        except (ValueError, TypeError):
            continue

    n = len(y_vals)
    if n < 4:
        return {"status": "error", "error_code": "ERR_PARSE",
                "message": "Failed to parse sufficient numeric rows"}

    # Cell means
    means = {}
    stds = {}
    for k, v in cell_y.items():
        if v:
            m = sum(v) / len(v)
            means[k] = m
            var = sum((x - m) ** 2 for x in v) / (len(v) - 1) if len(v) > 1 else 1.0
            stds[k] = math.sqrt(var)
        else:
            means[k] = 0.0
            stds[k] = 1.0

    # --- Estimability gates (fail closed; never fabricate inference) ---
    if len(set(treat_vals)) < 2:
        return {
            "status": "error", "error_code": "ERR_NO_TREAT_VARIATION",
            "message": "Treatment column has no variation; DID not estimable",
            **_null_inference(),
        }
    if len(set(post_vals)) < 2:
        return {
            "status": "error", "error_code": "ERR_NO_POST_VARIATION",
            "message": "Post column has no variation; DID not estimable",
            **_null_inference(),
        }
    for k in ((0, 0), (0, 1), (1, 0), (1, 1)):
        if not cell_y[k]:
            return {
                "status": "error", "error_code": "ERR_EMPTY_CELL",
                "message": f"DID design has an empty 2x2 cell ({k}); not estimable",
                **_null_inference(),
            }
    if n - 4 <= 0:
        return {
            "status": "error", "error_code": "ERR_SATURATED",
            "message": "Model saturated (n - 4 <= 0); no residual degrees of freedom for inference",
            **_null_inference(),
        }
    y_mean = sum(y_vals) / n
    tss = sum((y - y_mean) ** 2 for y in y_vals)
    if tss <= 0:
        return {
            "status": "error", "error_code": "ERR_ZERO_VARIANCE",
            "message": "Outcome has zero variance; DID inference not estimable",
            **_null_inference(),
        }

    y_c_pre = means[(0, 0)]
    y_c_post = means[(0, 1)]
    y_t_pre = means[(1, 0)]
    y_t_post = means[(1, 1)]

    # Simple 2x2 delta
    delta_simple = (y_t_post - y_t_pre) - (y_c_post - y_c_pre)

    # OLS Estimation: Y = X * beta + e, X = [1, Treat, Post, Treat*Post]
    # Build X^T X (4x4) and X^T Y (4x1)
    X = [[1.0, treat_vals[i], post_vals[i], treat_post_vals[i]] for i in range(n)]
    XtX = [[0.0] * 4 for _ in range(4)]
    XtY = [0.0] * 4

    for i in range(n):
        row = X[i]
        yi = y_vals[i]
        for r in range(4):
            XtY[r] += row[r] * yi
            for c in range(4):
                XtX[r][c] += row[r] * row[c]

    try:
        beta = _solve_linear_system(XtX, XtY)
        XtX_inv = _matrix_inverse(XtX)
    except Exception:
        return {
            "status": "error", "error_code": "ERR_DESIGN_NOT_ESTIMABLE",
            "message": "Design matrix inversion failed: singular or collinear design",
            **_null_inference(),
        }

    # Residual sum of squares & Standard Error
    rss = 0.0
    for i in range(n):
        y_hat = beta[0] + beta[1] * treat_vals[i] + beta[2] * post_vals[i] + beta[3] * treat_post_vals[i]
        rss += (y_vals[i] - y_hat) ** 2

    df_resid = n - 4
    sigma2 = rss / df_resid
    r_squared = max(0.0, 1.0 - (rss / tss)) if tss > 0 else 0.0

    if rss <= 0:
        return {
            "status": "error", "error_code": "ERR_ZERO_RESIDUAL",
            "message": "Zero residual variance; inference not estimable",
            **_null_inference(),
        }
    se_delta = math.sqrt(sigma2 * XtX_inv[3][3])
    t_stat = beta[3] / se_delta if se_delta > 0 else 0.0
    p_val = _two_tailed_p_from_z(t_stat)

    # Standardized Effect Size: Hedges' g
    s_pooled_pre = math.sqrt((stds[(0, 0)] ** 2 + stds[(1, 0)] ** 2) / 2.0) if stds[(0, 0)] and stds[(1, 0)] else 1.0
    hedges_j = 1.0 - (3.0 / (4.0 * df_resid - 1.0)) if df_resid > 2 else 1.0
    hedges_g = round(hedges_j * (beta[3] / s_pooled_pre), 3) if s_pooled_pre > 0 else 0.0

    # Baseline Equivalence
    baseline_diff = y_t_pre - y_c_pre
    baseline_g = baseline_diff / s_pooled_pre if s_pooled_pre > 0 else 0.0
    # QED/DID can never meet WWC 5.0 standards WITHOUT reservations; and without
    # covariate-adjustment fields a 0.05<|g|<=0.25 baseline is not passable.
    if abs(baseline_g) <= 0.05:
        wwc_rating = "Meets Standards With Reservations"
    elif abs(baseline_g) <= 0.25:
        wwc_rating = "Does Not Meet Standards (Statistical Adjustment Required)"
    else:
        wwc_rating = "Does Not Meet Standards (Baseline Imbalance)"

    ci_95 = [
        round(beta[3] - 1.96 * se_delta, 3),
        round(beta[3] + 1.96 * se_delta, 3)
    ]

    cluster_note = (
        f"cluster column(s) detected ({', '.join(cluster_columns)}) but cluster-robust "
        "inference is not implemented in this build; p-value is not cluster-robust"
        if cluster_columns else
        "cluster identifier missing; p-value is not cluster-robust"
    )
    return {
        "status": "success",
        "inference_status": "non_cluster_warning",
        "inference_warning": cluster_note,
        "cluster_columns": cluster_columns,
        "sample_size": n,
        "treatment_n": len(cell_y[(1, 0)]) + len(cell_y[(1, 1)]),
        "control_n": len(cell_y[(0, 0)]) + len(cell_y[(0, 1)]),
        "did_coefficient": round(beta[3], 4),
        "standard_error": round(se_delta, 4),
        "t_statistic": round(t_stat, 3),
        "p_value": round(p_val, 4),
        "ci_95": ci_95,
        "r_squared": round(r_squared, 4),
        "hedges_g": hedges_g,
        "baseline_equivalence_g": round(baseline_g, 3),
        "wwc_baseline_rating": wwc_rating,
        "cell_means": {
            "control_pre": round(y_c_pre, 2),
            "control_post": round(y_c_post, 2),
            "treatment_pre": round(y_t_pre, 2),
            "treatment_post": round(y_t_post, 2),
        }
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/did_regression.py <path_to_csv>")
        sys.exit(1)
    res = run_did_analysis(sys.argv[1])
    print(json.dumps(res, indent=2, ensure_ascii=False))
    sys.exit(0 if res.get("status") == "success" else 1)
