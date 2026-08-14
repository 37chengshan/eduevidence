"""engine/meta_analysis.py - v4 quantitative effect-size synthesis (meta-analysis).

Hand-written effect-size pooling over extracted study rows, following the
textbook definitions of Borenstein, Hedges, Higgins & Rothstein (2009),
"Introduction to Meta-Analysis" (Wiley):

    fixed effect   inverse-variance weighting:  M  =  Σ(w·d) / Σw,
                                                 SE = 1 / √Σw,  w = 1/se²
    random effects DerSimonian & Laird (1986) moment estimate of τ² from
                   Cochran's Q, then weighting with w* = 1/(v + τ²)
    heterogeneity  Q = Σ w·(d − M_fixed)²,  df = k − 1,
                   I² = 100·(Q − df)/Q,  τ² = max(0, (Q − df)/C),
                   C = Σw − Σw²/Σw

Pure stdlib (math only), no third-party dependencies. Defensive against empty
input, missing precision, and zero variance: pooling functions return None
when no usable row exists; studies without a numeric effect value or without
derivable precision are marked ``not_extractable`` by :func:`collect_effect_sizes`.

Output contract: schemas/v4/meta-analysis.schema.json.
"""
from __future__ import annotations

import math
import secrets
from datetime import datetime, timezone
from typing import Any

_Z_975 = 1.959963984540054  # two-tailed 95% normal quantile


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _two_tailed_p(z: float) -> float:
    """Two-tailed p under the standard normal: 2·(1 − Φ(|z|))."""
    return 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))


# ---------------------------------------------------------------------------
# 1. Extraction
# ---------------------------------------------------------------------------

def _effect_estimate_dict(evidence: dict) -> dict:
    ee = evidence.get("effect_estimate")
    if isinstance(ee, dict):
        return ee
    if _is_number(ee):
        return {"value": ee}
    return {}


def _derive_se(ee: dict, d: float, sample_size: Any) -> float | None:
    """Precision of a Cohen's d, in priority order.

    1. explicit ``se`` field on the effect estimate;
    2. symmetric 95% CI: se = (ci_high − ci_low) / (2·1.96);
    3. large-sample approximation from total n (equal group sizes):
       se = √(4/n + d²/(2n))   (Borenstein 2009, ch. 4, eq. 4.14/4.18).
    """
    if _is_number(ee.get("se")) and ee["se"] > 0:
        return float(ee["se"])
    low, high = ee.get("ci_low"), ee.get("ci_high")
    if _is_number(low) and _is_number(high) and high > low:
        return (float(high) - float(low)) / (2.0 * _Z_975)
    if _is_number(sample_size) and sample_size > 0:
        n = float(sample_size)
        return math.sqrt(4.0 / n + (d * d) / (2.0 * n))
    return None


def collect_effect_sizes(evidence_list: list[dict]) -> list[dict]:
    """Extract per-study Cohen's-d rows from evidence objects.

    Reads ``effect_estimate`` (value / se / ci_low / ci_high), ``sample_size``
    and ``quality_dimensions`` (a D3_measurement_validity of 0 invalidates the
    numeric estimate). Returns rows ``{study_id, outcome_id, d, se, n}``;
    entries whose effect size cannot be extracted are returned with
    ``d/se/n = None`` plus ``not_extractable: True`` and a ``reason``.
    """
    if not evidence_list:
        return []
    rows: list[dict] = []
    for evidence in evidence_list:
        if not isinstance(evidence, dict):
            continue
        study_id = evidence.get("study_id") or "unknown"
        outcome_id = (evidence.get("outcome_id") or evidence.get("outcome_type")
                      or evidence.get("claim_id") or "unknown")
        sample_size = evidence.get("sample_size")
        base = {"study_id": study_id, "outcome_id": outcome_id,
                "d": None, "se": None,
                "n": (int(sample_size) if _is_number(sample_size) else None)}

        ee = _effect_estimate_dict(evidence)
        d = ee.get("value")
        if not _is_number(d):
            base.update({"not_extractable": True,
                         "reason": "missing_effect_value"})
            rows.append(base)
            continue

        qd = evidence.get("quality_dimensions")
        if isinstance(qd, dict) and qd.get("D3_measurement_validity") == 0:
            base.update({"not_extractable": True,
                         "reason": "invalid_measurement_quality"})
            rows.append(base)
            continue

        d = float(d)
        se = _derive_se(ee, d, sample_size)
        if se is None:
            base.update({"not_extractable": True,
                         "reason": "missing_precision"})
            rows.append(base)
            continue
        base.update({"d": d, "se": se,
                     "n": int(sample_size) if _is_number(sample_size) else None,
                     "not_extractable": False, "reason": None})
        rows.append(base)
    return rows


# ---------------------------------------------------------------------------
# 2. Pooling
# ---------------------------------------------------------------------------

def _usable(rows: list[dict]) -> list[dict]:
    """Rows with finite, positive precision and a finite effect value."""
    clean: list[dict] = []
    for row in rows or []:
        d, se = row.get("d"), row.get("se")
        if _is_number(d) and _is_number(se) and se > 0 and math.isfinite(float(d)) \
                and math.isfinite(float(se)) and float(se) < 1e100:
            clean.append(row)
    return clean


def fixed_effect_pooling(rows: list[dict]) -> dict | None:
    """Inverse-variance fixed-effect pooling (Borenstein 2009, ch. 15-16).

    Returns ``None`` when no usable row exists (empty input / all precision
    missing). Output carries per-study inverse-variance ``weights`` for forest
    plots plus a two-tailed normal test of the pooled effect (``z``/``p_value``).
    """
    usable = _usable(rows)
    if not usable:
        return None
    # precision form avoids se**2 overflow for extreme se (review P2)
    weights = [p * p for p in (1.0 / float(r["se"]) for r in usable)]
    sum_w = sum(weights)
    if sum_w <= 0 or not math.isfinite(sum_w):
        return None
    d = sum(w * float(r["d"]) for w, r in zip(weights, usable)) / sum_w
    se = 1.0 / math.sqrt(sum_w)
    ci_low, ci_high = d - _Z_975 * se, d + _Z_975 * se
    return {
        "method": "fixed_effect",
        "k": len(usable),
        "d": d,
        "se": se,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "z": d / se,
        "p_value": _two_tailed_p(d / se),
        "weights": weights,
        "sum_w": sum_w,
    }


def random_effect_pooling(rows: list[dict]) -> dict | None:
    """DerSimonian-Laird random-effects pooling (Borenstein 2009, ch. 16.2).

    τ² is the DL moment estimate from Cochran's Q (floored at 0); I² is the
    fraction of total variance attributable to between-study heterogeneity.
    Returns ``None`` when no usable row exists; with k = 1, τ² is undefined
    (no heterogeneity evidence) so τ² = 0 and the single study dominates.
    """
    usable = _usable(rows)
    if not usable:
        return None
    k = len(usable)
    fixed = fixed_effect_pooling(usable)
    assert fixed is not None
    d_fixed = fixed["d"]
    # precision form avoids se**2 overflow for extreme se (review P2)
    weights = [p * p for p in (1.0 / float(r["se"]) for r in usable)]
    sum_w = sum(weights)
    Q = sum(w * (float(r["d"]) - d_fixed) ** 2 for w, r in zip(weights, usable))
    df = k - 1

    sum_w2 = sum(w * w for w in weights)
    denom_c = sum_w - (sum_w2 / sum_w) if sum_w > 0 else 0.0
    tau2 = (Q - df) / denom_c if (Q > df and denom_c > 0) else 0.0
    tau2 = max(0.0, tau2)
    # I2 must stay in [0, 100]: with near-homogeneous data Q < df is common
    # (P(Q < df) ~ 40% for real k-1 df), so clamp before dividing (P0-1).
    I2 = 100.0 * max(0.0, Q - df) / Q if Q > 0 else 0.0

    re_weights = [1.0 / ((float(r["se"]) ** 2) + tau2) for r in usable]
    sum_w_star = sum(re_weights)
    if sum_w_star <= 0 or not math.isfinite(sum_w_star):
        return None
    d = sum(w * float(r["d"]) for w, r in zip(re_weights, usable)) / sum_w_star
    se = 1.0 / math.sqrt(sum_w_star)
    return {
        "method": "random_effect",
        "k": k,
        "d": d,
        "se": se,
        "ci_low": d - _Z_975 * se,
        "ci_high": d + _Z_975 * se,
        "z": d / se,
        "p_value": _two_tailed_p(d / se),
        "tau2": tau2,
        "Q": Q,
        "df": df,
        "I2": I2,
        "weights": re_weights,
        "sum_w": sum_w_star,
    }


# ---------------------------------------------------------------------------
# 3. Forest plot data
# ---------------------------------------------------------------------------

def forest_data(rows: list[dict], pooled: dict | None) -> dict | None:
    """Forest-plot data (ECharts/SVG friendly): per-study effect + CI + weight.

    Study weights come from the pooling model when available (``pooled``
    carries ``weights``), otherwise inverse variance 1/se²; ``weight_pct`` is
    the share of each study within the pooled diamond. Returns None when there
    is nothing to plot.
    """
    usable = _usable(rows)
    if not usable or pooled is None:
        return None
    weights = pooled.get("weights")
    if not weights or len(weights) != len(usable):
        # precision form avoids se**2 overflow for extreme se (review P2)
        weights = [p * p for p in (1.0 / float(r["se"]) for r in usable)]
    sum_w = sum(weights)
    if sum_w <= 0:
        return None
    studies = []
    for i, r in enumerate(usable):
        d = float(r["d"])
        se = float(r["se"])
        studies.append({
            "study_id": r.get("study_id"),
            "outcome_id": r.get("outcome_id"),
            "d": d,
            "se": se,
            "ci_low": d - _Z_975 * se,
            "ci_high": d + _Z_975 * se,
            "weight": weights[i],
            "weight_pct": 100.0 * weights[i] / sum_w,
        })
    return {
        "studies": studies,
        "pooled": {
            "d": pooled["d"],
            "se": pooled["se"],
            "ci_low": pooled["ci_low"],
            "ci_high": pooled["ci_high"],
            "weight": sum_w,
            "weight_pct": 100.0,
        },
        "k": len(usable),
    }


# ---------------------------------------------------------------------------
# 4. Full v4 pipeline (schema-shaped composition)
# ---------------------------------------------------------------------------

def _new_ma_id() -> str:
    return f"MA-{secrets.token_hex(4)}"


def run_meta_analysis(evidence_list: list[dict],
                      outcome_id: str = "OUT-meta",
                      pooling: str = "random_effect") -> dict:
    """Compose the full v4 meta-analysis contract from evidence objects.

    Headline pooling for leave-one-out robustness and the final label defaults
    to random effects (the conservative choice under heterogeneity); the fixed
    and random results are both reported. Raises ValueError when fewer than two
    studies are poolable (defensive: refuse to synthesize nonsense).
    """
    from engine.bias import egger_regression, fail_safe_n
    from engine.robustness import leave_one_out, robustness_label

    if pooling not in ("fixed_effect", "random_effect"):
        raise ValueError(f"unknown pooling {pooling!r}")
    rows = collect_effect_sizes(evidence_list)
    usable = _usable(rows)
    if len(usable) < 2:
        raise ValueError(
            f"meta-analysis needs >= 2 poolable studies, got {len(usable)}")
    pooling_fn = (fixed_effect_pooling if pooling == "fixed_effect"
                  else random_effect_pooling)
    pooled_fixed = fixed_effect_pooling(usable)
    pooled_random = random_effect_pooling(usable)
    headline = pooling_fn(usable)
    assert pooled_fixed is not None and pooled_random is not None and headline is not None

    loo = leave_one_out(usable, pooling_fn)
    assert loo is not None
    return {
        "meta_analysis_id": _new_ma_id(),
        "outcome_id": outcome_id,
        "generated_at": _now_iso(),
        "k": len(usable),
        "pooled_fixed": pooled_fixed,
        "pooled_random": pooled_random,
        "Q": pooled_random["Q"],
        "df": pooled_random["df"],
        "I2": pooled_random["I2"],
        "tau2": pooled_random["tau2"],
        "egger": egger_regression(usable),
        "fail_safe_n": fail_safe_n(usable),
        "leave_one_out": loo,
        "label": robustness_label(loo),
        "studies": usable,
        "not_extractable": [r for r in rows if r.get("not_extractable")],
    }
