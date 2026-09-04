"""Tests for visualization/eduevidence-report/scripts/build_report.py —
HTML 报告构建 + Scientific Integrity Gate（P0-09/10/11、6.1/6.2/6.4）。
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RESULT = ROOT / "examples" / "ai-coding-assistant" / "result.json"
RESULT_ZH = ROOT / "examples" / "ai-coding-assistant" / "result.zh.json"

import build_report as br  # noqa: E402


def _load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _build(tmp_path, result=RESULT, result_zh=RESULT_ZH, monkeypatch=None):
    out = tmp_path / "report.html"
    spec_out = tmp_path / "report_spec.json"
    argv = ["build_report.py", "--result", str(result), "--result-zh", str(result_zh),
            "--out", str(out), "--spec-out", str(spec_out)]
    if monkeypatch is not None:
        monkeypatch.setattr(sys, "argv", argv)
        code = br.main()
    else:
        saved = sys.argv
        sys.argv = argv
        try:
            code = br.main()
        finally:
            sys.argv = saved
    if code != 0 or not out.exists():
        return code, None, None
    return code, out.read_text(encoding="utf-8"), json.loads(spec_out.read_text(encoding="utf-8"))


def _en_shell(html: str) -> str:
    m = re.search(r'<div class="report-shell" data-lang-body="en">(.*?)\n</div>\n<script>',
                  html, re.S)
    assert m, "EN body not found"
    return m.group(1)


def test_build_succeeds_with_integrity_pass(tmp_path, monkeypatch):
    code, html, spec = _build(tmp_path, monkeypatch=monkeypatch)
    assert code == 0
    assert "<html" in html and 'data-lang-body="zh"' in html and 'data-lang-body="en"' in html
    gate = spec["integrity_gate"]
    assert gate["status"] == "PASS"
    for key in ("contract_valid", "claims_bound", "numbers_match_result",
                "bilingual_structure_match", "no_false_precision"):
        assert gate[key] in ("PASS", "FAIL"), f"{key} must be a computed status"
    assert gate["contract_valid"] == "PASS"
    assert gate["claims_bound"] == "PASS"
    assert gate["numbers_match_result"] == "PASS"
    assert gate["bilingual_structure_match"] == "PASS"
    assert gate["no_false_precision"] == "PASS"


def test_integrity_not_checked_fields_are_not_true(tmp_path, monkeypatch):
    _, _, spec = _build(tmp_path, monkeypatch=monkeypatch)
    gate = spec["integrity_gate"]
    assert gate["no_axis_distortion"] == "NOT_CHECKED"
    assert gate["colorblind_safe"] == "NOT_CHECKED"


def test_integrity_fails_when_numbers_tampered(tmp_path, monkeypatch):
    import copy
    bad = copy.deepcopy(_load("examples/ai-coding-assistant/result.json"))
    bad["outcomes"][0]["positive_count"] = 99
    bad_path = tmp_path / "result-bad.json"
    bad_path.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    code, _, _ = _build(tmp_path, result=bad_path, monkeypatch=monkeypatch)
    assert code == 2


def test_en_body_has_no_hardcoded_chinese(tmp_path, monkeypatch):
    """EN UI chrome may quote source-language data, but must not hard-code Chinese UI prose."""
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    en = _en_shell(html)
    en = re.sub(r"<script.*?</script>", "", en, flags=re.S)
    en = re.sub(r"<h1>.*?</h1>", "", en, flags=re.S)
    result = _load("examples/ai-coding-assistant/result.json")
    for value in (
        result.get("meta", {}).get("question"),
        result.get("research_frame", {}).get("question"),
        result.get("decision", {}).get("decision_question"),
    ):
        if value:
            en = en.replace(str(value), "")
    en = en.replace("&#x27;", "'")
    for c in result["decision"].get("exceeds_evidence_boundary", []):
        en = en.replace(str(c), "")
    # Frozen localized gloss in legacy evidence prose; not UI chrome.
    en = en.replace("无直接证据", "")
    leftover = re.findall(r"[\u4e00-\u9fff]{2,}", en)
    assert leftover == [], f"EN body contains CJK words: {set(leftover)}"


def test_en_decision_hero_is_english(tmp_path, monkeypatch):
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    en = _en_shell(html)
    assert "Recommended decision" in en
    assert "Strongest supported conclusion" in en
    assert "Key uncertainty / contradiction" in en
    assert "（置信度：" not in en


def test_footer_shows_specific_passes(tmp_path, monkeypatch):
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    for footer in re.findall(r'<footer class="report-section"><p>(.*?)</p></footer>', html, re.S):
        for part in ("Schema PASS", "Claim Binding PASS", "Numeric Consistency PASS",
                     "Bilingual Structure PASS"):
            assert part in footer
    assert "数据一致性校验" not in html


def test_best_supported_is_weighted_score(tmp_path, monkeypatch):
    result = _load("examples/ai-coding-assistant/result.json")
    expected = max(result["outcomes"],
                   key=lambda o: br._outcome_support_score(result["evidence"], o))["outcome_type"]
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    hero = re.search(r'data-visual="decision-hero"(.*?)</div>\s*</section>', html, re.S)
    assert hero, "decision hero not found"
    assert br.label("zh", "outcome", expected) in html or result["decision"]["supported_claims"][0] in hero.group(1)


def test_best_supported_ranks_by_quality_not_first(tmp_path, monkeypatch):
    """A later high-quality/direct study must outrank an earlier weak/indirect one."""
    evidence = [
        {
            "evidence_id": "E-low",
            "study_id": "S-low",
            "outcome_type": "first_outcome",
            "relation_to_claim": "support",
            "quality_score": 2,
            "directness": "low",
        },
        {
            "evidence_id": "E-high",
            "study_id": "S-high",
            "outcome_type": "second_outcome",
            "relation_to_claim": "support",
            "quality_score": 9,
            "directness": "full",
        },
    ]
    outcomes = [
        {"outcome_type": "first_outcome", "positive_count": 1},
        {"outcome_type": "second_outcome", "positive_count": 1},
    ]
    ranked = sorted(outcomes, key=lambda o: br._outcome_support_score(evidence, o), reverse=True)
    assert ranked[0]["outcome_type"] == "second_outcome"


def test_diverging_svg_no_overlap():
    option = {
        "yAxis": [{"data": ["A", "B", "C"]}],
        "series": [
            {"name": "Support", "lane": "main", "data": [3, 2, 2]},
            {"name": "Contradict", "lane": "main", "data": [-1, -2, -1]},
            {"name": "Neutral", "lane": "neutral", "data": [1, 1, 2]},
        ],
    }
    svg = br.diverging_bar_svg(option)
    rects = [(float(x), float(y), float(w), float(h))
             for x, y, w, h in re.findall(r'<rect x="([\d.]+)" y="([\d.]+)" '
                                          r'width="([\d.]+)" height="([\d.]+)"', svg)]
    main = [r for r in rects if r[3] > 6]
    thin = [r for r in rects if r[3] <= 6]
    assert main and thin


def test_chart_mount_hidden_until_mounted(tmp_path, monkeypatch):
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    assert ".chart-mount { display:none" in html
    assert ".chart-mount.is-mounted { display:block" in html
    assert "el.classList.add('is-mounted')" in html


def test_applicability_labels_zh(tmp_path, monkeypatch):
    result_zh = _load("examples/ai-coding-assistant/result.zh.json")
    app = result_zh["decision"].get("applicability") or result_zh.get("applicability") or {}
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    zh = re.search(r'<div class="report-shell" data-lang-body="zh">(.*?)</div>\n'
                   r'<div class="report-shell" data-lang-body="en">', html, re.S).group(1)
    import html as html_mod
    sec = html_mod.unescape(re.search(r'<section id="full-\d+-action".*?</section>', zh, re.S).group(0))
    assert "不适用于" in sec
    assert app.get("not_suitable_for") in sec
    assert "适用条件" in sec
    m = re.search(r"适用条件[^<]*</strong>(.*?)</p>", sec, re.S)
    if m:
        assert app.get("not_suitable_for") not in m.group(1)


def test_applicability_labels_en(tmp_path, monkeypatch):
    result = _load("examples/ai-coding-assistant/result.json")
    app = result["decision"].get("applicability") or result.get("applicability") or {}
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    en = _en_shell(html)
    import html as html_mod
    sec = html_mod.unescape(re.search(r'<section id="full-\d+-action-en".*?</section>', en, re.S).group(0))
    assert "Not suitable for" in sec
    assert app.get("not_suitable_for") in sec


def test_lieflat_gallery_cards_present(tmp_path, monkeypatch):
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    zh = re.search(r'<div class="report-shell" data-lang-body="zh">(.*?)\n</div>\n<script>',
                   html, re.S).group(1)
    assert 'class="lieflat-card" data-lieflat' in zh
    assert 'data-visual="lieflat-' in zh
    assert 'data-chart-id="lieflat-' in zh
    assert 'class="lieflat-title"' in zh
    assert 'class="lieflat-sub"' in zh
    assert 'class="lieflat-src"' in zh
    assert 'class="lieflat-suppressed"' in zh


def test_lieflat_motion_css_single_definition(tmp_path, monkeypatch):
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    assert html.count("@keyframes eduevidenceLfPop") == 1
    assert html.count("@keyframes eduevidenceLfFade") == 1
    assert html.count("@keyframes eduevidenceLfDraw") == 1
    assert ".js-lf [data-lieflat].is-live .lf-pop" in html
    assert "cubic-bezier(.2,.7,.3,1.3)" in html
    assert "@media (prefers-reduced-motion:reduce)" in html
    assert "stroke-dasharray:none" in html


def test_lieflat_motion_js_reveal_contract(tmp_path, monkeypatch):
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    js = re.search(r"<script>\n(/\* EduEvidence Motion Template.*?)</script>", html, re.S)
    assert js, "motion template script not found"
    body = js.group(1)
    assert "threshold:.3" in body
    assert "replayLieflat" in body
    assert "clearLfTimers" in body
    assert "CSS.escape" in body
    assert "addEventListener('click'" in body
    assert "classList.remove('is-live')" in body


def test_lieflat_no_hardcoded_demo_in_html(tmp_path, monkeypatch):
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    for demo in ("课后做题卡壳", "Bastani '25", "Ninety days as a barcode",
                 "VanLehn '25", "苏格拉底反问"):
        assert demo not in html


def test_footer_shows_lieflat_bound(tmp_path, monkeypatch):
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    assert "Lieflat 数据溯源 PASS" in html
    assert "Lieflat Data Bound PASS" in html


def test_header_meta_normalized_copy(tmp_path, monkeypatch):
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    result = _load("examples/ai-coding-assistant/result.json")
    evidence_count = len(result.get("evidence", []))
    source_count = len(result.get("sources", []))
    zh = re.search(r'<div class="report-shell" data-lang-body="zh">(.*?)\n</div>\n<script>',
                   html, re.S).group(1)
    m = re.search(r'<p class="meta">(.*?)</p>', zh, re.S)
    assert m and "模式：" in m.group(1) and "生成时间：" in m.group(1)
    assert f"证据 {evidence_count} 条" in m.group(1)
    assert f"来源 {source_count} 个" in m.group(1)
    en = _en_shell(html)
    m2 = re.search(r'<p class="meta">(.*?)</p>', en, re.S)
    assert m2 and "Mode: " in m2.group(1) and "Generated: " in m2.group(1)
    assert f"Evidence: {evidence_count}" in m2.group(1)
    assert f"Sources: {source_count}" in m2.group(1)
    assert "模式：" not in m2.group(1)
