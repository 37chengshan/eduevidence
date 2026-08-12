"""Tests for visualization/eduevidence-report/scripts/build_infographics.py —
双语信息图（P0-13）：zh 用 result.zh.json 文本，en 用 result.json 文本。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULT = ROOT / "examples" / "ai-coding-assistant" / "result.json"
RESULT_ZH = ROOT / "examples" / "ai-coding-assistant" / "result.zh.json"

from build_infographics import render_infographics  # noqa: E402


def _load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_render_infographics_lang_titles():
    en = render_infographics(_load("examples/ai-coding-assistant/result.json"), lang="en")
    zh = render_infographics(_load("examples/ai-coding-assistant/result.zh.json"), lang="zh")
    assert "EvidenceFlow Protocol" in en["workflow"]
    assert "EvidenceFlow 协议" in zh["workflow"]
    assert "Can claim" in en["tribunal"]
    assert "可以主张" in zh["tribunal"]
    assert "Cannot claim" in en["tribunal"]
    assert "不可主张" in zh["tribunal"]


def test_tribunal_text_from_correct_language_data():
    """裁决信息图的 claim / reason_for_disagreement 文本必须来自对应语言数据。"""
    en_data = _load("examples/ai-coding-assistant/result.json")
    zh_data = _load("examples/ai-coding-assistant/result.zh.json")
    en_svg = render_infographics(en_data, lang="en")["tribunal"]
    zh_svg = render_infographics(zh_data, lang="zh")["tribunal"]
    en_claim = en_data["decision"]["supported_claims"][0][:44]
    zh_claim = zh_data["decision"]["supported_claims"][0][:44]
    assert en_claim in en_svg
    assert zh_claim in zh_svg
    assert en_data["decision"]["reason_for_disagreement"][:80] in en_svg
    assert zh_data["decision"]["reason_for_disagreement"][:80] in zh_svg


def test_intervention_timeline_bilingual():
    en = render_infographics(_load("examples/ai-coding-assistant/result.json"), lang="en")
    zh = render_infographics(_load("examples/ai-coding-assistant/result.zh.json"), lang="zh")
    assert "AI rule: " in en["intervention"]
    assert "AI 规则: " in zh["intervention"]
    en_phase = _load("examples/ai-coding-assistant/result.json")["intervention"]["phase_1"]["name"]
    zh_phase = _load("examples/ai-coding-assistant/result.zh.json")["intervention"]["phase_1"]["name"]
    assert en_phase in en["intervention"]
    assert zh_phase in zh["intervention"]


def test_evaluation_flow_bilingual():
    en = render_infographics(_load("examples/ai-coding-assistant/result.json"), lang="en")
    zh = render_infographics(_load("examples/ai-coding-assistant/result.zh.json"), lang="zh")
    assert "Baseline" in en["evaluation"] and "基线" in zh["evaluation"]
    # 副标题（数据文本）随语言
    en_base = _load("examples/ai-coding-assistant/result.json")["evaluation"].get("baseline") or "pre-test"
    assert en_base[:30] in en["evaluation"]


def test_render_deterministic():
    en_data = _load("examples/ai-coding-assistant/result.json")
    assert render_infographics(en_data, lang="en") == render_infographics(en_data, lang="en")


def test_numbers_shared_between_langs():
    """信息图不包含数字差异：两份渲染的 SVG 中数字标记相同（仅文本不同）。"""
    en_svg = render_infographics(_load("examples/ai-coding-assistant/result.json"), lang="en")
    zh_svg = render_infographics(_load("examples/ai-coding-assistant/result.zh.json"), lang="zh")
    for key in ("workflow", "tribunal", "intervention", "evaluation"):
        assert en_svg[key] != zh_svg[key]  # 文本确实按语言不同
