"""Tests for the v4 evidence synthesis layer: effect-size meta-analysis
(engine/meta_analysis.py), publication bias (engine/bias.py), robustness
(engine/robustness.py) and the output contract
(schemas/v4/meta-analysis.schema.json).

Reference values are hand-computed from the textbook definitions
(Borenstein et al. 2009, "Introduction to Meta-Analysis"; DerSimonian &
Laird 1986; Egger 1997; Rosenthal 1979) and cross-checked against an
independent inline restatement of the formulas.
"""
import json
import math
from pathlib import Path

import pytest

from engine.bias import egger_regression, fail_safe_n
from engine.meta_analysis import (collect_effect_sizes, fixed_effect_pooling,
                                  forest_data, random_effect_pooling,
                                  run_meta_analysis)
from engine.robustness import leave_one_out, robustness_label
from validate_schema import SchemaError, validate

ROOT = Path(__file__).resolve().parent.parent
META_SCHEMA = json.loads(
    (ROOT / "schemas" / "v4" / "meta-analysis.schema.json").read_text("utf-8"))

_Z = 1.959963984540054  # 95% two-tailed normal quantile (1.96)

# ---------------------------------------------------------------------------
# Fixtures: the four hand-verification studies (d, se chosen so that the
# inverse-variance weights are clean: 25, 16, 6.25, 4).
# ---------------------------------------------------------------------------

FOUR_STUDIES = [
    {"study_id": "S-A", "outcome_id": "OUT-1", "d": 0.6, "se": 0.2, "n": 100},
    {"study_id": "S-B", "outcome_id": "OUT-1", "d": 0.4, "se": 0.25, "n": 64},
    {"study_id": "S-C", "outcome_id": "OUT-1", "d": 1.2, "se": 0.4, "n": 25},
    {"study_id": "S-D", "outcome_id": "OUT-1", "d": -0.2, "se": 0.5, "n": 16},
]


def _reference_fixed(rows):
    """Independent restatement of inverse-variance fixed-effect pooling."""
    w = [1.0 / r["se"] ** 2 for r in rows]
    sw = sum(w)
    d = sum(wi * r["d"] for wi, r in zip(w, rows)) / sw
    se = 1.0 / math.sqrt(sw)
    return {"d": d, "se": se, "sum_w": sw,
            "ci_low": d - _Z * se, "ci_high": d + _Z * se, "weights": w}


def _reference_random(rows):
    """Independent restatement of DerSimonian-Laird random-effects pooling."""
    fx = _reference_fixed(rows)
    w = fx["weights"]
    sw = fx["sum_w"]
    df = len(rows) - 1
    Q = sum(wi * (r["d"] - fx["d"]) ** 2 for wi, r in zip(w, rows))
    C = sw - sum(wi * wi for wi in w) / sw
    tau2 = max(0.0, (Q - df) / C) if (Q > df and C > 0) else 0.0
    I2 = 100.0 * (Q - df) / Q if Q > 0 else 0.0
    rw = [1.0 / (r["se"] ** 2 + tau2) for r in rows]
    srw = sum(rw)
    d = sum(wi * r["d"] for wi, r in zip(rw, rows)) / srw
    se = 1.0 / math.sqrt(srw)
    return {"d": d, "se": se, "tau2": tau2, "Q": Q, "df": df, "I2": I2,
            "ci_low": d - _Z * se, "ci_high": d + _Z * se}


# ---------------------------------------------------------------------------
# 1. Extraction
# ---------------------------------------------------------------------------

def test_collect_effect_sizes_extracts_se_from_field_ci_and_sample_size():
    evidence = [
        # explicit se field
        {"study_id": "S-A", "outcome_id": "OUT-1", "sample_size": 100,
         "effect_estimate": {"metric": "d", "value": 0.6, "se": 0.2}},
        # se derived from a symmetric 95% CI: (0.89 - (-0.09)) / (2 * 1.96)
        {"study_id": "S-B", "outcome_id": "OUT-1", "sample_size": 64,
         "effect_estimate": {"metric": "d", "value": 0.4,
                             "ci_low": -0.09, "ci_high": 0.89}},
        # se approximated from total n: sqrt(4/n + d^2/(2n))
        {"study_id": "S-C", "outcome_id": "OUT-1", "sample_size": 25,
         "effect_estimate": {"metric": "d", "value": 1.2}},
        # outcome_type fallback when outcome_id absent
        {"study_id": "S-D", "outcome_type": "retention", "sample_size": 16,
         "effect_estimate": {"metric": "d", "value": -0.2}},
    ]
    rows = collect_effect_sizes(evidence)
    assert [r["study_id"] for r in rows] == ["S-A", "S-B", "S-C", "S-D"]
    assert all(r["not_extractable"] is False for r in rows)
    assert rows[0]["se"] == pytest.approx(0.2, abs=1e-12)
    assert rows[1]["se"] == pytest.approx(0.25000459389308044, abs=1e-9)
    assert rows[2]["se"] == pytest.approx(0.43451121964800865, abs=1e-9)
    assert rows[3]["se"] == pytest.approx(0.5012484413940855, abs=1e-9)
    assert rows[3]["outcome_id"] == "retention"
    assert rows[0]["n"] == 100


def test_collect_effect_sizes_marks_not_extractable():
    evidence = [
        {"study_id": "S-E", "outcome_id": "OUT-1", "sample_size": 40,
         "effect_estimate": {"metric": "g", "value": None, "raw_text": "ns"}},
        {"study_id": "S-F", "outcome_id": "OUT-1", "sample_size": 40,
         "effect_estimate": {"metric": "d", "value": 0.3},
         "quality_dimensions": {"D3_measurement_validity": 0}},
        {"study_id": "S-G", "outcome_id": "OUT-1",
         "effect_estimate": {"metric": "d", "value": 0.2}},
    ]
    rows = collect_effect_sizes(evidence)
    assert rows[0]["not_extractable"] is True
    assert rows[0]["reason"] == "missing_effect_value"
    assert rows[1]["not_extractable"] is True
    assert rows[1]["reason"] == "invalid_measurement_quality"
    assert rows[2]["not_extractable"] is True
    assert rows[2]["reason"] == "missing_precision"  # no se / ci / n


# ---------------------------------------------------------------------------
# 2. Pooling — hand-verified against Borenstein (2009)
# ---------------------------------------------------------------------------

def test_fixed_effect_pooling_hand_verified():
    pooled = fixed_effect_pooling(FOUR_STUDIES)
    assert pooled is not None
    ref = _reference_fixed(FOUR_STUDIES)
    # hand-computed: w = [25, 16, 6.25, 4], sum_w = 51.25
    # d = (15 + 6.4 + 7.5 - 0.8) / 51.25 = 28.1 / 51.25
    assert pooled["k"] == 4
    assert pooled["weights"] == pytest.approx([25.0, 16.0, 6.25, 4.0])
    assert pooled["sum_w"] == pytest.approx(51.25, abs=1e-9)
    assert pooled["d"] == pytest.approx(0.548292682927, abs=1e-9)
    assert pooled["se"] == pytest.approx(0.139686059154, abs=1e-9)
    assert pooled["ci_low"] == pytest.approx(0.2745130378, abs=1e-9)
    assert pooled["ci_high"] == pytest.approx(0.8220723280, abs=1e-9)
    # cross-check against the independent restatement
    assert pooled["d"] == pytest.approx(ref["d"], abs=1e-12)
    assert pooled["se"] == pytest.approx(ref["se"], abs=1e-12)


def test_random_effect_pooling_dl_hand_verified():
    pooled = random_effect_pooling(FOUR_STUDIES)
    assert pooled is not None
    ref = _reference_random(FOUR_STUDIES)
    # hand-computed: Q = 5.31297561, df = 3, C = 32.98536585
    # tau2 = (Q - 3) / C = 2.31297561 / 32.98536585
    # I2 = 100 * (Q - 3) / Q
    assert pooled["Q"] == pytest.approx(5.312975609756, abs=1e-9)
    assert pooled["df"] == 3
    assert pooled["tau2"] == pytest.approx(0.070121265898, abs=1e-9)
    assert pooled["I2"] == pytest.approx(43.534466928642, abs=1e-9)
    assert pooled["d"] == pytest.approx(0.541894741739, abs=1e-9)
    assert pooled["se"] == pytest.approx(0.203740294451, abs=1e-9)
    assert pooled["ci_low"] == pytest.approx(0.1425711024, abs=1e-9)
    assert pooled["ci_high"] == pytest.approx(0.9412183811, abs=1e-9)
    # random-effects CI is wider than fixed-effects CI
    assert (pooled["ci_high"] - pooled["ci_low"]) > (
        fixed_effect_pooling(FOUR_STUDIES)["ci_high"]
        - fixed_effect_pooling(FOUR_STUDIES)["ci_low"])
    assert pooled["d"] == pytest.approx(ref["d"], abs=1e-12)
    assert pooled["tau2"] == pytest.approx(ref["tau2"], abs=1e-12)


def test_homogeneous_studies_yield_zero_heterogeneity():
    rows = [
        {"study_id": "H1", "outcome_id": "O", "d": 0.5, "se": 0.2},
        {"study_id": "H2", "outcome_id": "O", "d": 0.5, "se": 0.3},
        {"study_id": "H3", "outcome_id": "O", "d": 0.5, "se": 0.4},
    ]
    pooled = random_effect_pooling(rows)
    assert pooled["Q"] == pytest.approx(0.0, abs=1e-12)
    assert pooled["I2"] == pytest.approx(0.0, abs=1e-12)
    assert pooled["tau2"] == pytest.approx(0.0, abs=1e-12)
    assert pooled["d"] == pytest.approx(0.5, abs=1e-12)
    assert pooled["d"] == pytest.approx(fixed_effect_pooling(rows)["d"], abs=1e-12)


# ---------------------------------------------------------------------------
# 3. Publication bias
# ---------------------------------------------------------------------------

def test_egger_symmetric_data_intercept_zero():
    # constant effect across precisions -> SND = 0.1 * precision, intercept 0
    rows = [
        {"study_id": "E1", "d": 0.1, "se": 0.2},
        {"study_id": "E2", "d": 0.1, "se": 0.4},
        {"study_id": "E3", "d": 0.1, "se": 0.8},
    ]
    res = egger_regression(rows)
    assert res["applicable"] is True
    assert res["intercept"] == pytest.approx(0.0, abs=1e-12)
    assert res["slope"] == pytest.approx(0.1, abs=1e-12)
    assert res["p_value"] == pytest.approx(1.0, abs=1e-12)
    assert res["bias_detected"] is False


def test_egger_asymmetric_data_detects_bias():
    # small (imprecise) studies show larger effects -> negative intercept
    rows_3 = [
        {"study_id": "A1", "d": 0.5, "se": 0.2},
        {"study_id": "A2", "d": 0.3, "se": 0.4},
        {"study_id": "A3", "d": 0.1, "se": 0.8},
    ]
    res = egger_regression(rows_3)
    assert res["intercept"] == pytest.approx(-0.75, abs=1e-9)
    assert res["t"] == pytest.approx(-4.58257569495584, abs=1e-9)
    assert res["p_value"] == pytest.approx(0.136778, abs=1e-5)  # df=1, weak power

    rows_5 = [
        {"study_id": "a", "d": 0.6, "se": 0.2},
        {"study_id": "b", "d": 0.4, "se": 0.3},
        {"study_id": "c", "d": 0.3, "se": 0.4},
        {"study_id": "d", "d": 0.15, "se": 0.6},
        {"study_id": "e", "d": 0.1, "se": 0.9},
    ]
    res5 = egger_regression(rows_5)
    assert res5["intercept"] == pytest.approx(-0.966749, abs=1e-5)
    assert res5["significant"] is True
    assert res5["bias_detected"] is True
    assert res5["p_value"] < 0.05


def test_egger_needs_three_studies():
    res = egger_regression([{"study_id": "a", "d": 0.1, "se": 0.2},
                            {"study_id": "b", "d": 0.2, "se": 0.3}])
    assert res["applicable"] is False
    assert res["reason"] == "need >= 3 studies"


def test_fail_safe_n_rosenthal():
    res = fail_safe_n(FOUR_STUDIES)
    # z = [3.0, 1.6, 3.0, -0.4], sum_z = 7.2
    # N_fs = 7.2^2 / 2.7055 - 4 = 15.1607
    assert res["sum_z"] == pytest.approx(7.2, abs=1e-12)
    assert res["n_fail_safe"] == pytest.approx(15.160661, abs=1e-5)
    assert res["tolerates_5"] is True

    weak = [
        {"study_id": "W1", "d": 0.05, "se": 0.2},
        {"study_id": "W2", "d": 0.1, "se": 0.3},
        {"study_id": "W3", "d": 0.05, "se": 0.5},
    ]
    res_w = fail_safe_n(weak)
    assert res_w["n_fail_safe"] == pytest.approx(0.0, abs=1e-12)
    assert res_w["tolerates_5"] is False


# ---------------------------------------------------------------------------
# 4. Robustness (leave-one-out)
# ---------------------------------------------------------------------------

FLIP_STUDIES = [
    {"study_id": "X1", "outcome_id": "O", "d": 0.4, "se": 0.2},
    {"study_id": "X2", "outcome_id": "O", "d": 0.2, "se": 0.25},
    {"study_id": "X3", "outcome_id": "O", "d": 0.1, "se": 0.3},
    {"study_id": "X4", "outcome_id": "O", "d": -0.8, "se": 0.35},
]

ROBUST_STUDIES = [
    {"study_id": "R1", "outcome_id": "O", "d": 0.6, "se": 0.2},
    {"study_id": "R2", "outcome_id": "O", "d": 0.5, "se": 0.25},
    {"study_id": "R3", "outcome_id": "O", "d": 0.7, "se": 0.3},
    {"study_id": "R4", "outcome_id": "O", "d": 0.6, "se": 0.35},
]


def test_leave_one_out_detects_direction_flip():
    res = leave_one_out(FLIP_STUDIES, fixed_effect_pooling)
    assert res["full_pooled"]["d"] > 0  # pooled is positive with all studies
    by_study = {it["removed_study_id"]: it for it in res["iterations"]}
    assert by_study["X1"]["direction_flip"] is True   # strong + study removed
    assert by_study["X1"]["pooled"]["d"] < 0
    assert by_study["X4"]["direction_flip"] is False  # negative study removed
    assert res["n_direction_flips"] == 1
    assert res["n_ci_crossings"] == 3
    assert res["n_decision_changes"] == 3
    assert robustness_label(res) == "fragile"


def test_leave_one_out_robust_and_label():
    res = leave_one_out(ROBUST_STUDIES, fixed_effect_pooling)
    assert res["n_direction_flips"] == 0
    assert res["n_ci_crossings"] == 0
    assert res["n_decision_changes"] == 0
    assert robustness_label(res) == "robust"
    # every subset stays positive with a CI above zero
    for it in res["iterations"]:
        assert it["pooled"]["ci_low"] > 0
    # no analysis possible is treated as fragile
    assert robustness_label(None) == "fragile"


# ---------------------------------------------------------------------------
# 5. Forest plot data
# ---------------------------------------------------------------------------

def test_forest_data_structure():
    pooled = random_effect_pooling(FOUR_STUDIES)
    fd = forest_data(FOUR_STUDIES, pooled)
    assert fd["k"] == 4
    assert [s["study_id"] for s in fd["studies"]] == ["S-A", "S-B", "S-C", "S-D"]
    for s in fd["studies"]:
        assert s["ci_low"] < s["d"] < s["ci_high"]
        assert s["weight"] > 0
    assert sum(s["weight_pct"] for s in fd["studies"]) == pytest.approx(100.0)
    assert fd["pooled"]["d"] == pytest.approx(pooled["d"], abs=1e-12)
    assert fd["pooled"]["ci_low"] == pytest.approx(pooled["ci_low"], abs=1e-12)
    assert fd["pooled"]["weight_pct"] == 100.0
    # fixed-effect weights come from the pooled model
    fd_fx = forest_data(FOUR_STUDIES, fixed_effect_pooling(FOUR_STUDIES))
    assert [s["weight"] for s in fd_fx["studies"]] == pytest.approx(
        [25.0, 16.0, 6.25, 4.0])


# ---------------------------------------------------------------------------
# 6. Full pipeline + schema contract
# ---------------------------------------------------------------------------

def _evidence_for_meta_analysis():
    return [
        {"evidence_id": "E1", "study_id": "S-A", "outcome_id": "OUT-ret",
         "sample_size": 100,
         "effect_estimate": {"metric": "d", "value": 0.6, "se": 0.2}},
        {"evidence_id": "E2", "study_id": "S-B", "outcome_id": "OUT-ret",
         "sample_size": 64,
         "effect_estimate": {"metric": "d", "value": 0.4,
                             "ci_low": -0.09, "ci_high": 0.89}},
        {"evidence_id": "E3", "study_id": "S-C", "outcome_id": "OUT-ret",
         "sample_size": 25,
         "effect_estimate": {"metric": "d", "value": 1.2}},
        {"evidence_id": "E4", "study_id": "S-D", "outcome_id": "OUT-ret",
         "sample_size": 16,
         "effect_estimate": {"metric": "d", "value": -0.2}},
        {"evidence_id": "E5", "study_id": "S-E", "outcome_id": "OUT-ret",
         "sample_size": 40,
         "effect_estimate": {"metric": "g", "value": None, "raw_text": "ns"}},
    ]


def test_run_meta_analysis_matches_schema_contract():
    ma = run_meta_analysis(_evidence_for_meta_analysis(),
                           outcome_id="OUT-ret")
    validate(ma, META_SCHEMA)  # must not raise
    assert ma["meta_analysis_id"].startswith("MA-")
    assert ma["k"] == 4
    assert ma["label"] in ("robust", "fragile")
    assert ma["pooled_fixed"]["method"] == "fixed_effect"
    assert ma["pooled_random"]["method"] == "random_effect"
    assert set(("Q", "df", "I2", "tau2")) <= set(ma)
    assert ma["egger"]["applicable"] is True
    assert ma["fail_safe_n"]["method"] == "rosenthal"
    assert ma["leave_one_out"]["method"] == "leave_one_out"
    assert len(ma["studies"]) == 4
    assert [r["study_id"] for r in ma["not_extractable"]] == ["S-E"]
    assert ma["not_extractable"][0]["reason"] == "missing_effect_value"

    # the schema rejects tampering
    bad = dict(ma)
    bad["label"] = "weird"
    with pytest.raises(SchemaError):
        validate(bad, META_SCHEMA)


def test_run_meta_analysis_refuses_fewer_than_two_studies():
    with pytest.raises(ValueError, match=">= 2 poolable"):
        run_meta_analysis([{"study_id": "X", "outcome_id": "O",
                            "effect_estimate": {"value": 0.5, "se": 0.2}}])


# ---------------------------------------------------------------------------
# 7. Defensive behaviour
# ---------------------------------------------------------------------------

def test_empty_and_degenerate_inputs():
    assert fixed_effect_pooling([]) is None
    assert random_effect_pooling([]) is None
    assert forest_data([], None) is None
    bad = [{"study_id": "x", "outcome_id": "O", "d": None, "se": None}]
    assert fixed_effect_pooling(bad) is None
    # k = 1 pooling degenerates to the single study
    one = fixed_effect_pooling([{"study_id": "Z", "outcome_id": "O",
                                 "d": 0.3, "se": 0.2}])
    assert one["d"] == pytest.approx(0.3, abs=1e-12)
    assert one["se"] == pytest.approx(0.2, abs=1e-12)
    one_r = random_effect_pooling([{"study_id": "Z", "outcome_id": "O",
                                    "d": 0.3, "se": 0.2}])
    assert one_r["tau2"] == 0.0
    assert leave_one_out([{"study_id": "Z", "outcome_id": "O",
                           "d": 0.3, "se": 0.2}], fixed_effect_pooling) is None


def test_i2_clamped_when_q_below_df_near_homogeneous():
    # P0-1 regression: near-homogeneous data (Q < df, ~40% of real meta-analyses)
    # must clamp I2 to 0.0 instead of producing a huge negative that violates
    # the v4 schema (I2 minimum 0).
    rows = [
        {"study_id": f"STU-{i}", "outcome_id": "OUT-x", "d": 0.50, "se": 0.20, "n": 50}
        for i in range(5)
    ]
    out = random_effect_pooling(rows)
    assert out["I2"] == 0.0, out
    assert 0.0 <= out["I2"] <= 100.0
    # and the full pipeline output must validate against its own schema
    full = run_meta_analysis(rows)
    import json as _json
    from validate_schema import Validator, SchemaError
    schema = _json.loads(Path(__file__).resolve().parent.parent.joinpath(
        'schemas/v4/meta-analysis.schema.json').read_text(encoding='utf-8'))
    Validator(schema).validate(full, schema, '$')


def test_i2_clamped_when_q_below_df_near_homogeneous():
    # P0-1 regression: near-homogeneous data (Q < df, ~40% of real meta-analyses)
    # must clamp I2 to 0.0 instead of producing a huge negative that violates
    # the v4 schema (I2 minimum 0).
    rows = [
        {"study_id": f"STU-{i}", "outcome_id": "OUT-x", "d": 0.50, "se": 0.20, "n": 50}
        for i in range(5)
    ]
    out = random_effect_pooling(rows)
    assert out["I2"] == 0.0, out
    assert 0.0 <= out["I2"] <= 100.0
    # near-homogeneous but not identical: Q > 0 and Q < df must also clamp
    near = [
        {"study_id": "N1", "outcome_id": "O", "d": 0.500, "se": 0.20},
        {"study_id": "N2", "outcome_id": "O", "d": 0.501, "se": 0.20},
        {"study_id": "N3", "outcome_id": "O", "d": 0.499, "se": 0.20},
    ]
    near_out = random_effect_pooling(near)
    assert 0.0 <= near_out["I2"] <= 100.0, near_out
    # and the full pipeline output must validate against its own schema
    evidence = [
        {"evidence_id": f"E-{i}", "study_id": f"STU-{i}", "outcome_id": "OUT-x",
         "sample_size": 50, "effect_estimate": {"value": 0.50, "raw_text": "d=0.5"}}
        for i in range(5)
    ]
    full = run_meta_analysis(evidence)
    import json as _json
    from validate_schema import Validator, SchemaError
    schema = _json.loads(Path(__file__).resolve().parent.parent.joinpath(
        'schemas/v4/meta-analysis.schema.json').read_text(encoding='utf-8'))
    Validator(schema).validate(full, schema, '$')


def test_run_meta_analysis_rejects_unknown_pooling():
    evidence = [
        {"evidence_id": "E-1", "study_id": "STU-1", "outcome_id": "OUT-x",
         "sample_size": 50, "effect_estimate": {"value": 0.5, "raw_text": "d=0.5"}},
        {"evidence_id": "E-2", "study_id": "STU-2", "outcome_id": "OUT-x",
         "sample_size": 50, "effect_estimate": {"value": 0.3, "raw_text": "d=0.3"}},
    ]
    with pytest.raises(ValueError, match="pooling"):
        run_meta_analysis(evidence, pooling="bogus")


def test_meta_analysis_schema_rejects_tampered_output():
    evidence = [
        {"evidence_id": "E-1", "study_id": "STU-1", "outcome_id": "OUT-x",
         "sample_size": 50, "effect_estimate": {"value": 0.5, "raw_text": "d=0.5"}},
        {"evidence_id": "E-2", "study_id": "STU-2", "outcome_id": "OUT-x",
         "sample_size": 50, "effect_estimate": {"value": 0.3, "raw_text": "d=0.3"}},
    ]
    full = run_meta_analysis(evidence)
    full["tampered_field"] = True
    import json as _json
    from validate_schema import Validator, SchemaError
    schema = _json.loads(Path(__file__).resolve().parent.parent.joinpath(
        'schemas/v4/meta-analysis.schema.json').read_text(encoding='utf-8'))
    with pytest.raises(SchemaError):
        Validator(schema).validate(full, schema, '$')
