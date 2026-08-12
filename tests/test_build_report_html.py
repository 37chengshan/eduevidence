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
    bad["outcomes"][0]["support_count"] = 99
    bad_path = tmp_path / "result-bad.json"
    bad_path.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    code, _, _ = _build(tmp_path, result=bad_path, monkeypatch=monkeypatch)
    assert code == 2


def test_en_body_has_no_hardcoded_chinese(tmp_path, monkeypatch):
    """6.1：EN 模式除数据自带的 question 文本外，不得出现中文/全角标点。"""
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    en = _en_shell(html)
    en = re.sub(r"<h1>.*?</h1>", "", en, flags=re.S)
    question = _load("examples/ai-coding-assistant/result.json")["meta"]["question"]
    en = en.replace(question, "")
    leftover = re.findall(r"[\u4e00-\u9fff：（）「」]", en)
    assert leftover == [], f"EN body contains hardcoded CJK: {set(leftover)}"


def test_en_summary_tags_are_english(tmp_path, monkeypatch):
    """6.1：summary-tag 与置信度文案随语言。"""
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    en = _en_shell(html)
    assert "summary-tag pos'>Support" in en
    assert "summary-tag neg'>Contradict" in en
    assert "(confidence: " in en
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
    """P0-09：第一屏「证据最充分的结果」= 加权评分最高者，而非第一个。"""
    result = _load("examples/ai-coding-assistant/result.json")
    expected = max(result["outcomes"],
                   key=lambda o: br._outcome_support_score(result["evidence"], o))["outcome_type"]
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    m = re.search(r'kpi-label">[^<]*证据最充分的结果[^<]*</span>'
                  r'<span class="kpi-value">([^<]+)</span>', html)
    assert m, "best-supported KPI not found"
    assert m.group(1) == br.label("zh", "outcome", expected)


def test_best_supported_ranks_by_quality_not_first(tmp_path, monkeypatch):
    """加权评分应让高质量证据的结果排前（构造样例：后出现但质量高 → 胜出）。"""
    result = _load("examples/ai-coding-assistant/result.json")
    evidence = list(result["evidence"])
    # 两个结果各有 1 条支持证据：先出现的质量低，后出现的质量高
    outcomes = [
        {"outcome_type": "knowledge_gain", "support_count": 1, "contradict_count": 0,
         "neutral_count": 0, "evidence_ids": ["E-007"]},
        {"outcome_type": "completion_time", "support_count": 1, "contradict_count": 0,
         "neutral_count": 0, "evidence_ids": ["E-001"]},
    ]
    ranked = sorted(outcomes, key=lambda o: br._outcome_support_score(evidence, o), reverse=True)
    assert ranked[0]["outcome_type"] == "completion_time"  # E-001 质量 9 > E-007 质量 6


def test_diverging_svg_no_overlap(tmp_path, monkeypatch):
    """P0-10：静态 diverging SVG 三系列不互相覆盖：主道左右分向，中性独立细条道。"""
    _, html, _ = _build(tmp_path, monkeypatch=monkeypatch)
    zh = re.search(r'<div class="report-shell" data-lang-body="zh">(.*?)</div>\n'
                   r'<div class="report-shell" data-lang-body="en">', html, re.S).group(1)
    svg = re.search(r'<svg viewBox="0 0 720 300"[^>]*>(.*?)</svg>', zh, re.S).group(0)
    rects = [(float(x), float(y), float(w), float(h))
             for x, y, w, h in re.findall(r'<rect x="([\d.]+)" y="([\d.]+)" '
                                          r'width="([\d.]+)" height="([\d.]+)"', svg)]
    main = [r for r in rects if r[3] > 6]
    thin = [r for r in rects if r[3] <= 6]
    assert main and thin, "diverging chart must have main bars and a neutral thin lane"
    # 同一行主道 bar 不得重叠（中心线两侧允许镜像邻接）
    for i in range(len(main)):
        for j in range(i + 1, len(main)):
            a, b = main[i], main[j]
            if abs(a[1] - b[1]) > 1e-6:
                continue
            if a[0] < b[0] + b[2] - 1e-6 and b[0] < a[0] + a[2] - 1e-6:
                assert abs(a[0] + a[2] - 405) < 1e-6 or abs(b[0] + b[2] - 405) < 1e-6 \
                    or abs(a[0] - 405) < 1e-6 or abs(b[0] - 405) < 1e-6, \
                    f"main bars overlap: {a} vs {b}"
    # 中性道不与主道共享 y 区间
    main_ys = [r[1] for r in main]
    for r in thin:
        assert all(r[1] > y for y in main_ys), f"neutral lane overlaps main lane: {r}"


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
    sec = re.search(r'<section id="zh-08-applicability".*?</section>', zh, re.S).group(0)
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
    sec = re.search(r'<section id="en-08-applicability".*?</section>', en, re.S).group(0)
    assert "Not suitable for" in sec
    assert app.get("not_suitable_for") in sec
