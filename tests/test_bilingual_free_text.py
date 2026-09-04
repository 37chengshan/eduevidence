"""HTML-01：英文 report body 不得残留生成式中文自由文本。

规则：render(lang="en") 使用 result.json，render(lang="zh") 使用 result.zh.json。
原始用户问题可以按 provenance 原样保留；除此以外，英文分析/UI 不得泄漏中文。
"""
import re
import sys
from pathlib import Path

import build_report as br

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "ai-coding-assistant-evidence"

CJK_RUN = re.compile(r"[\u4e00-\u9fff]{4,}")
SOURCE_LANGUAGE_PATHS = {
    "$.meta.question",
    "$.research_frame.question",
    "$.decision.decision_question",
}
# A narrowly scoped human-readable gloss embedded in one legacy English sentence.
# Do not widen this into a generic CJK allowlist.
ALLOWED_INLINE_GLOSSES = ("无直接证据",)


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


def _strip_allowed_source_language(text: str, result: dict) -> str:
    for value in (
        result.get("meta", {}).get("question"),
        result.get("research_frame", {}).get("question"),
        result.get("decision", {}).get("decision_question"),
    ):
        if value:
            text = text.replace(str(value), "")
    for gloss in ALLOWED_INLINE_GLOSSES:
        text = text.replace(gloss, "")
    return text


def test_en_body_has_no_chinese_free_text(tmp_path):
    """EN body may quote the source-language question, but generated prose stays English."""
    import json
    html = _build(tmp_path, DEMO / "result.json", DEMO / "result.zh.json")
    result = json.loads((DEMO / "result.json").read_text(encoding="utf-8"))
    en = _strip_allowed_source_language(_en_shell(html), result)
    leftover = CJK_RUN.findall(en)
    assert leftover == [], f"EN body contains Chinese free text: {set(leftover)}"


def test_en_body_uses_english_data_fields(tmp_path):
    html = _build(tmp_path, DEMO / "result.json", DEMO / "result.zh.json")
    en = _en_shell(html)
    result = __import__("json").loads((DEMO / "result.json").read_text(encoding="utf-8"))
    zh = __import__("json").loads((DEMO / "result.zh.json").read_text(encoding="utf-8"))
    assert result["decision"]["target_population"][:60] in en
    assert result["decision"]["reason_for_disagreement"][:60] in en
    assert result["research_frame"]["learner"]["prior_knowledge"][:40] in en
    assert zh["decision"]["target_population"][:40] not in en
    assert zh["decision"]["reason_for_disagreement"][:40] not in en
    for zh_word in ("可以主张", "目标人群", "证据裁决", "置信度", "先看结论"):
        assert zh_word not in en


def test_zh_body_keeps_chinese_free_text(tmp_path):
    html = _build(tmp_path, DEMO / "result.json", DEMO / "result.zh.json")
    zh_shell = _zh_shell(html)
    zh = __import__("json").loads((DEMO / "result.zh.json").read_text(encoding="utf-8"))
    assert zh["decision"]["target_population"][:40] in zh_shell
    assert "可以主张" in zh_shell


def test_english_data_file_itself_has_no_chinese(tmp_path):
    """Only exact provenance fields and a frozen inline gloss may contain CJK."""
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
            if path in SOURCE_LANGUAGE_PATHS:
                return hits
            if any(seg.endswith(("title_zh", "lead_zh")) for seg in path.split(".")):
                return hits
            cleaned = obj
            for gloss in ALLOWED_INLINE_GLOSSES:
                cleaned = cleaned.replace(gloss, "")
            if CJK_RUN.search(cleaned):
                hits.append((path, obj[:60]))
        return hits

    hits = walk(en)
    assert hits == [], f"result.json contains unexpected Chinese free text: {hits}"
