"""HTML-01：英文 report body 不得残留大段中文自由文本。

规则（审查计划 §12.2）：render(lang="en") 必须使用 result.json（英文数据），
render(lang="zh") 使用 result.zh.json。除论文标题 / 原文引用 / 专有名词外，
英文 report body 不应出现大段中文自由文本。
"""
import re
import sys
from pathlib import Path

import build_report as br

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "ai-coding-assistant"

CJK_RUN = re.compile(r"[\u4e00-\u9fff]{4,}")


def _build(tmp_path, result, result_zh, theme="claude"):
    out = tmp_path / "report.html"
    spec_out = tmp_path / "report_spec.json"
    argv = [
        "build_report.py",
        "--result", str(result),
        "--result-zh", str(result_zh),
        "--out", str(out),
        "--spec-out", str(spec_out),
        "--theme", theme,
    ]
    import pytest
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(sys, "argv", argv)
    try:
        code = br.main()
    finally:
        monkeypatch.undo()
    assert code == 0
    return out.read_text(encoding="utf-8")


def _en_shell(html: str) -> str:
    m = re.search(r'<div class="report-shell" data-lang-body="en">(.*?)\n</div>\n<script>',
                  html, re.S)
    assert m, "EN report shell not found"
    return m.group(1)


def _zh_shell(html: str) -> str:
    m = re.search(r'<div class="report-shell" data-lang-body="zh">(.*?)\n</div>\n<script>',
                  html, re.S)
    assert m, "ZH report shell not found"
    return m.group(1)


def test_en_body_has_no_chinese_free_text(tmp_path):
    """6.1/HTML-01：EN body 无 ≥4 字连续中文（数据 + UI 双层均干净）。"""
    html = _build(tmp_path, DEMO / "result.json", DEMO / "result.zh.json")
    en = _en_shell(html)
    leftover = CJK_RUN.findall(en)
    assert leftover == [], f"EN body contains Chinese free text: {set(leftover)}"


def test_en_body_uses_english_data_fields(tmp_path):
    """EN body 自由文本来自 result.json（英文），不是 zh 内容换英文标签。"""
    html = _build(tmp_path, DEMO / "result.json", DEMO / "result.zh.json")
    en = _en_shell(html)
    result = __import__("json").loads((DEMO / "result.json").read_text(encoding="utf-8"))
    zh = __import__("json").loads((DEMO / "result.zh.json").read_text(encoding="utf-8"))
    # 英文数据的关键自由文本出现
    assert result["decision"]["target_population"][:60] in en
    assert result["decision"]["reason_for_disagreement"][:60] in en
    assert result["research_frame"]["learner"]["prior_knowledge"][:40] in en
    # 中文平行数据的对应文本不得出现在 EN body
    assert zh["decision"]["target_population"][:40] not in en
    assert zh["decision"]["reason_for_disagreement"][:40] not in en
    # 中文 UI 词不得出现在 EN body
    for zh_word in ("可以主张", "目标人群", "证据裁决", "置信度", "先看结论"):
        assert zh_word not in en


def test_zh_body_keeps_chinese_free_text(tmp_path):
    """对照：ZH body 仍使用 result.zh.json 的中文自由文本。"""
    html = _build(tmp_path, DEMO / "result.json", DEMO / "result.zh.json")
    zh_shell = _zh_shell(html)
    zh = __import__("json").loads((DEMO / "result.zh.json").read_text(encoding="utf-8"))
    assert zh["decision"]["target_population"][:40] in zh_shell
    assert "可以主张" in zh_shell


def test_english_data_file_itself_has_no_chinese(tmp_path):
    """result.json 数据源本身无中文自由文本（除双语章节标题 title_zh/lead_zh）。"""
    import json
    en = json.loads((DEMO / "result.json").read_text(encoding="utf-8"))

    def walk(obj, path="$"):
        hits = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                hits += walk(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                hits += walk(v, f"{path}[{i}]")
        elif isinstance(obj, str) and CJK_RUN.search(obj):
            if not any(seg.endswith(("title_zh", "lead_zh")) for seg in path.split(".")):
                hits.append((path, obj[:60]))
        return hits

    hits = walk(en)
    assert hits == [], f"result.json contains Chinese free text: {hits}"
