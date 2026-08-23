"""Adapter contract tests (P1 gate).

All three visualization adapters must emit the identical envelope shape with
a pinned source_sha256 and locale, CLI output must equal library-function
output (single core path), and error inputs must fail closed with exit code 2.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "visualization" / "eduevidence-report" / "scripts"
RESULT = ROOT / "examples" / "ai-coding-assistant" / "result.json"

ADAPTERS = ("charts", "infographics", "figures")


def _run_adapter(tmp: Path, adapter: str, out_name: str, extra: list[str] | None = None,
                 result_path: Path = RESULT):
    script = {
        "charts": "build_charts.py",
        "infographics": "build_infographics.py",
        "figures": "build_figures.py",
    }[adapter]
    target = tmp / out_name
    cmd = [sys.executable, str(SCRIPTS / script),
           "--result", str(result_path), "--out", str(target)]
    if extra:
        cmd += extra
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(SCRIPTS))
    assert res.returncode == 0, res.stderr
    return json.loads(target.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def envelopes(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("adapter")
    out = {
        "charts": _run_adapter(tmp, "charts", "charts.json"),
        "infographics": _run_adapter(tmp, "infographics", "infographics.json"),
        "figures": _run_adapter(tmp, "figures", "figures.json",
                                extra=["--theme", "okabe_ito"]),
    }
    return out


def test_all_envelopes_have_contract_fields(envelopes):
    for adapter, env in envelopes.items():
        assert env["adapter"] == adapter
        assert env["contract_version"] == "1.0"
        assert env["source_ref"] == "result.json"
        assert len(env["source_sha256"]) == 64
        assert env["locale"] in ("zh", "en")
        assert isinstance(env["data"], dict)


def test_source_hash_pins_result_bytes(envelopes):
    expected = __import__("hashlib").sha256(RESULT.read_bytes()).hexdigest()
    for env in envelopes.values():
        assert env["source_sha256"] == expected


def test_data_content_matches_library_output(envelopes):
    """CLI envelope data must equal the core library functions (no divergence)."""
    sys.path.insert(0, str(SCRIPTS))
    import build_charts as BC
    import build_infographics as BI
    import build_figures as BF

    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert envelopes["charts"]["data"] == BC.build_all(result, lang="zh")
    assert envelopes["infographics"]["data"] == BI.render_infographics(result, lang="zh")
    figure_data = BF.build_figure_data(result)
    figures = BF.render_figures(figure_data, theme="okabe_ito", lang="zh")
    assert envelopes["figures"]["data"]["figure_data"] == figure_data
    assert envelopes["figures"]["data"]["figures"] == figures


def test_envelope_validates_against_schema(envelopes):
    sys.path.insert(0, str(ROOT))
    from validate_schema import validate

    schema_path = SCRIPTS.parent / "schemas" / "adapter-envelope.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    for env in envelopes.values():
        # validate() raises SchemaError on first violation; no exception = valid
        validate(schema, env)


def test_missing_result_fails_closed(tmp_path):
    cmd = [sys.executable, str(SCRIPTS / "build_charts.py"),
           "--result", str(tmp_path / "nope.json"), "--out", str(tmp_path / "x.json")]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(SCRIPTS))
    assert res.returncode == 2
    assert "not found" in res.stderr


def test_non_object_result_fails_closed(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2, 3]", encoding="utf-8")
    cmd = [sys.executable, str(SCRIPTS / "build_charts.py"),
           "--result", str(bad), "--out", str(tmp_path / "x.json")]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(SCRIPTS))
    assert res.returncode == 2
    assert "JSON object" in res.stderr


def test_unwritable_out_fails_closed(tmp_path):
    cmd = [sys.executable, str(SCRIPTS / "build_charts.py"),
           "--result", str(RESULT), "--out", str(tmp_path / "no-dir" / "x.json")]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(SCRIPTS))
    # writable parent is auto-created by the contract helper
    assert res.returncode == 0
    assert (tmp_path / "no-dir" / "x.json").exists()


def test_figures_legacy_out_dir_still_works(tmp_path):
    target = tmp_path / "figures"
    cmd = [sys.executable, str(SCRIPTS / "build_figures.py"),
           "--result", str(RESULT), "--out-dir", str(target),
           "--theme", "okabe_ito"]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(SCRIPTS))
    assert res.returncode == 0, res.stderr
    assert (target / "figure_data.json").exists()


def test_all_repo_fixtures_produce_valid_envelopes(tmp_path):
    """Every repository result.json must flow through the unified contract."""
    fixtures = sorted((ROOT / "examples").glob("*/result.json"))
    assert len(fixtures) >= 3, f"expected >=3 fixtures, got {len(fixtures)}"
    for fixture in fixtures:
        for adapter, extra in (("charts", None), ("infographics", None),
                               ("figures", ["--theme", "okabe_ito"])):
            env = _run_adapter(tmp_path, adapter, f"{fixture.parent.name}.json", extra,
                               result_path=fixture)
            assert env["source_ref"] == "result.json"
            assert env["source_sha256"] == __import__("hashlib").sha256(
                fixture.read_bytes()).hexdigest()


def test_bilingual_envelopes_same_numbers(tmp_path):
    """zh and en envelopes of the same result must carry identical numbers."""
    zh = _run_adapter(tmp_path, "charts", "zh.json")
    en = _run_adapter(tmp_path, "charts", "en.json", extra=["--lang", "en"])
    assert zh["locale"] == "zh" and en["locale"] == "en"
    assert zh["source_sha256"] == en["source_sha256"]
    za = {s["name"]: s["data"] for s in zh["data"]["charts"][0]["option"]["series"]}
    ea = {s["name"]: s["data"] for s in en["data"]["charts"][0]["option"]["series"]}
    for zname, ename in (("正向效应", "Positive effect"), ("负向效应", "Negative effect")):
        assert za[zname] == ea[ename]


def test_empty_result_does_not_crash_adapters(tmp_path):
    """Sparse/empty result must degrade to structured output, never crash."""
    empty = tmp_path / "empty.json"
    empty.write_text("{}", encoding="utf-8")
    for adapter, extra in (("charts", None), ("infographics", None),
                           ("figures", ["--theme", "okabe_ito"])):
        script = {"charts": "build_charts.py", "infographics": "build_infographics.py",
                  "figures": "build_figures.py"}[adapter]
        target = tmp_path / f"empty-{adapter}.json"
        cmd = [sys.executable, str(SCRIPTS / script), "--result", str(empty),
               "--out", str(target)] + (extra or [])
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(SCRIPTS))
        assert res.returncode == 0, f"{adapter}: {res.stderr}"
        env = json.loads(target.read_text(encoding="utf-8"))
        assert env["adapter"] == adapter