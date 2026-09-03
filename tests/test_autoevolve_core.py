from engine.autoevolve import DailyProfile, EvalSnapshot, PlateauTracker, ProtectedManifest, promote


def snap(i, hard=True, sci=1, res=1, rob=1, cost=1, lat=1, comp=1, noise=0.05):
    return EvalSnapshot(i, hard, sci, res, rob, cost, lat, comp, 3, noise)


def test_protected_manifest_rejects_gold_and_schema():
    manifest = ProtectedManifest()
    ok, bad = manifest.validate_changes(
        ["skill/prompts/a.md", "schemas/evidence.schema.json", "benchmarks/holdout/x.json"]
    )
    assert not ok
    assert len(bad) == 2


def test_hard_gate_always_rejects():
    assert promote(snap("b"), snap("c", hard=False))[0] == "REJECT"


def test_science_regression_rejects():
    assert promote(snap("b", sci=1), snap("c", sci=0.9, res=2))[0] == "REJECT"


def test_noise_floor_retests_equal_complexity():
    assert promote(snap("b", res=1), snap("c", res=1.01))[0] == "RETEST"


def test_simplicity_rejects_complex_no_real_gain():
    assert promote(snap("b", res=1, comp=1), snap("c", res=1.01, comp=2))[0] == "REJECT"


def test_material_gain_kept():
    assert promote(snap("b", res=1), snap("c", res=1.2))[0] == "KEEP"


def test_plateau_after_five_nonkeeps():
    assert PlateauTracker().plateau(["REJECT"] * 5)


def test_daily_is_branch_only():
    profile = DailyProfile()
    profile.validate()
    assert profile.promotion == "branch_only"
