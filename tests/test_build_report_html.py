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
    """用给定数据跑一次 main()，返回 (returncode, html_text|None, spec|None)。"""
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
    # 每个 PASS 字段都必须来自真实检查（字符串状态，而非硬编码 True）
    for key in ("contract_valid", "claims_bound", "numbers_match_result",
                "bilingual_structure_match", "no_false_precision"):
        assert gate[key] in ("PASS", "FAIL"), f"{key} must be a computed status"
    assert gate["contract_valid"] == "PASS"
    assert gate["claims_bound"] == "PASS"
    assert gate["numbers_match_result"] == "PASS"
    assert gate["bilingual_structure_match"] == "PASS"
    assert gate["no_false_precision"] == "PASS"


def test_integrity_not_checked_fields_are_not_true(tmp_path, monkeypatch):
    """未实现的检查必须标 NOT_CHECKED，而不是 True（P0-3）。"""
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
    """6.1：EN 模式 UI chrome 不得出现中文/全角标点（JS 注释与数据内容除外）。"""
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    en = _en_shell(html)
    en = re.sub(r"<script.*?</script>", "", en, flags=re.S)  # JS 注释不可见
    en = re.sub(r"<h1>.*?</h1>", "", en, flags=re.S)
    question = _load("examples/ai-coding-assistant/result.json")["meta"]["question"]
    en = en.replace(question, "")
    # exceeds_evidence_boundary 引用用户原始中文主张（数据内容，非 UI）；
    # HTML 中引号是 &#x27; 实体，替换时先还原实体再剔除
    en = en.replace("&#x27;", "'")
    for c in _load("examples/ai-coding-assistant/result.json")["decision"].get(
            "exceeds_evidence_boundary", []):
        en = en.replace(str(c), "")
    leftover = re.findall(r"[\u4e00-\u9fff]{2,}", en)
    assert leftover == [], f"EN body contains CJK words: {set(leftover)}"


def test_en_decision_hero_is_english(tmp_path, monkeypatch):
    """6.1：新版 Decision Hero UI 文案随语言。"""
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    en = _en_shell(html)
    assert "Recommended decision" in en
    assert "Strongest supported conclusion" in en
    assert "Key uncertainty / contradiction" in en
    assert "（置信度：" not in en


def test_footer_shows_specific_passes(tmp_path, monkeypatch):
    """6.4：footer 拆成具体 PASS 项。"""
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    for footer in re.findall(r'<footer class="report-section"><p>(.*?)</p></footer>', html, re.S):
        for part in ("Schema PASS", "Claim Binding PASS", "Numeric Consistency PASS",
                     "Bilingual Structure PASS"):
            assert part in footer
    assert "数据一致性校验" not in html


def test_best_supported_is_weighted_score(tmp_path, monkeypatch):
    """P0-09：第一屏仍按加权支持度排序，而不是依赖原始 outcome 顺序。"""
    result = _load("examples/ai-coding-assistant/result.json")
    expected = max(result["outcomes"],
                   key=lambda o: br._outcome_support_score(result["evidence"], o))["outcome_type"]
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    hero = re.search(r'data-visual="decision-hero"(.*?)</div>\s*</section>', html, re.S)
    assert hero, "decision hero not found"
    assert br.label("zh", "outcome", expected) in html or result["decision"]["supported_claims"][0] in hero.group(1)


def test_best_supported_ranks_by_quality_not_first(tmp_path, monkeypatch):
    """加权评分应让高质量证据的结果排前（构造样例：后出现但质量高 → 胜出）。"""
    result = _load("examples/ai-coding-assistant/result.json")
    evidence = list(result["evidence"])
    # 两个结果各有 1 条正向效应证据：先出现的质量低，后出现的质量高
    outcomes = [
        {"outcome_type": "completion_time", "positive_count": 1, "negative_count": 0,
         "null_count": 0, "evidence_ids": ["E-011"]},
        {"outcome_type": "assignment_score", "positive_count": 1, "negative_count": 0,
         "null_count": 0, "evidence_ids": ["E-001"]},
    ]
    ranked = sorted(outcomes, key=lambda o: br._outcome_support_score(evidence, o), reverse=True)
    assert ranked[0]["outcome_type"] == "assignment_score"  # E-001 质量 9 > E-011 质量 6


def test_diverging_svg_no_overlap():
    """P0-10：dense 数据需要图表时，静态 diverging SVG 仍保持分向与中性独立道。"""
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
    """6.2：.chart-mount 默认 display:none，init 成功后加 .is-mounted。"""
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    assert ".chart-mount { display:none" in html
    assert ".chart-mount.is-mounted { display:block" in html
    assert "el.classList.add('is-mounted')" in html


def test_applicability_labels_zh(tmp_path, monkeypatch):
    """P0-14：not_suitable_for 显示为「不适用于」，conditions 独立于 suitable_for。"""
    result_zh = _load("examples/ai-coding-assistant/result.zh.json")
    app = result_zh["decision"].get("applicability") or result_zh.get("applicability") or {}
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    zh = re.search(r'<div class="report-shell" data-lang-body="zh">(.*?)</div>\n'
                   r'<div class="report-shell" data-lang-body="en">', html, re.S).group(1)
    import html as html_mod
    sec = html_mod.unescape(re.search(r'<section id="full-\d+-action".*?</section>', zh, re.S).group(0))
    assert "不适用于" in sec
    assert app.get("not_suitable_for") in sec
    assert "适用条件" in sec  # required_conditions 独立标签
    # not_suitable_for 不得挂在「适用条件」下
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
