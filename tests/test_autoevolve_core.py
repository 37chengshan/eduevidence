from engine.autoevolve import DailyProfile, EvalSnapshot, PlateauTracker, ProtectedManifest, promote


def snap(
    i,
    hard=True,
    sci=1,
    res=1,
    rob=1,
    cost=1,
    lat=1,
    comp=1,
    noise=0.05,
    repeats=3,
    promotion_gates=True,
    suite="suite-v1",
):
    return EvalSnapshot(
        i,
        hard,
        sci,
        res,
        rob,
        cost,
        lat,
        comp,
        repeats,
        noise,
        promotion_gates,
        promotion_gates,
        promotion_gates,
        promotion_gates,
        suite,
    )


def test_protected_manifest_rejects_gold_and_schema():
    manifest = ProtectedManifest()
    ok, bad = manifest.validate_changes(
        ["skill/prompts/a.md", "schemas/evidence.schema.json", "benchmarks/holdout/x.json"]
    )
    assert not ok
    assert len(bad) == 2


def test_safe_mutation_scope_rejects_controlled_and_unknown_paths():
    manifest = ProtectedManifest()
    ok, bad = manifest.validate_mutation_scope(
        ["skill/workflows/a.md", "engine/orchestration.py", "random.txt"],
        mutation_tiers=("safe",),
        allow_controlled=False,
    )
    assert not ok
    assert bad == ["engine/orchestration.py", "random.txt"]


def test_hard_gate_always_rejects():
    assert promote(snap("b"), snap("c", hard=False))[0] == "REJECT"


def test_science_regression_rejects():
    assert promote(snap("b", sci=1), snap("c", sci=0.9, res=2))[0] == "REJECT"


def test_noise_floor_retests_equal_complexity():
    assert promote(snap("b", res=1), snap("c", res=1.01))[0] == "RETEST"


def test_insufficient_repeats_retests():
    assert promote(snap("b", repeats=1), snap("c", res=1.2, repeats=1))[0] == "RETEST"


def test_simplicity_rejects_complex_no_real_gain():
    assert promote(snap("b", res=1, comp=1), snap("c", res=1.01, comp=2))[0] == "REJECT"


def test_material_gain_kept_when_all_promotion_evidence_is_present():
    assert promote(snap("b", res=1), snap("c", res=1.2))[0] == "KEEP"


def test_material_gain_without_holdout_is_not_auto_kept():
    status, reason = promote(
        snap("b", res=1, promotion_gates=False),
        snap("c", res=1.2, promotion_gates=False),
    )
    assert status == "HUMAN_REVIEW"
    assert "HOLDOUT" in reason


def test_eval_suite_mismatch_is_not_auto_kept():
    status, reason = promote(snap("b", suite="A"), snap("c", res=1.2, suite="B"))
    assert status == "HUMAN_REVIEW"
    assert "suite" in reason


def test_material_gain_with_cost_regression_requires_human_review():
    status, reason = promote(snap("b", cost=1), snap("c", res=1.2, cost=2))
    assert status == "HUMAN_REVIEW"
    assert "cost" in reason


def test_equivalent_quality_simpler_candidate_can_win():
    assert promote(snap("b", comp=2), snap("c", res=1.01, comp=1))[0] == "KEEP"


def test_plateau_after_five_nonkeeps():
    assert PlateauTracker().plateau(["REJECT"] * 5)


def test_daily_is_branch_only():
    profile = DailyProfile()
    profile.validate()
    assert profile.promotion == "branch_only"
