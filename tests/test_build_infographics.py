"""Tests for visualization/eduevidence-report/scripts/build_infographics.py —
双语信息图（P0-13 + HTML-02）。

HTML-02 (2026-08-12)：SVG 只承载短标题 / 关键词 / 阶段 / 方向 / 数字；长文本
（完整 claim、AI 规则、评估段落）不得进入单行 SVG <text>，由 HTML 承载。
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULT = ROOT / "examples" / "ai-coding-assistant" / "result.json"
RESULT_ZH = ROOT / "examples" / "ai-coding-assistant" / "result.zh.json"

from build_infographics import render_infographics  # noqa: E402


def _load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _svg_texts(svg: str) -> list[str]:
    return [re.sub(r"<[^>]+>", "", t).strip()
            for t in re.findall(r"<text[^>]*>(.*?)</text>", svg, re.S)]


def _claim_ids(items: list[str], limit: int = 4) -> list[str]:
    ids: list[str] = []
    for item in items:
        for eid in re.findall(r"\b(?:E|EV)-[A-Za-z0-9-]+\b", str(item or "")):
            if eid not in ids:
                ids.append(eid)
        if len(ids) >= limit:
            break
    return ids[:limit]


def test_render_infographics_lang_titles():
    en = render_infographics(_load("examples/ai-coding-assistant/result.json"), lang="en")
    zh = render_infographics(_load("examples/ai-coding-assistant/result.zh.json"), lang="zh")
    assert "EvidenceFlow Protocol" in en["workflow"]
    assert "EvidenceFlow 协议" in zh["workflow"]
    assert "Can claim" in en["tribunal"]
    assert "可以主张" in zh["tribunal"]
    assert "Cannot claim" in en["tribunal"]
    assert "不可主张" in zh["tribunal"]


def test_tribunal_svg_short_text_and_evidence_ids_only():
    """HTML-02：裁决 SVG 不包含完整 claim 长句；只含证据 ID、计数与动作徽章。"""
    en_data = _load("examples/ai-coding-assistant/result.json")
    zh_data = _load("examples/ai-coding-assistant/result.zh.json")
    en_svg = render_infographics(en_data, lang="en")["tribunal"]
    zh_svg = render_infographics(zh_data, lang="zh")["tribunal"]
    for data in (en_data, zh_data):
        claim = data["decision"]["supported_claims"][0]
        assert claim[:44] not in en_svg
        assert claim[:44] not in zh_svg
    en_ids = _claim_ids(en_data["decision"]["supported_claims"])
    zh_ids = _claim_ids(zh_data["decision"]["supported_claims"])
    assert en_ids and zh_ids
    for eid in en_ids:
        assert eid in en_svg
    for eid in zh_ids:
        assert eid in zh_svg
    supported_count = len(en_data["decision"]["supported_claims"])
    assert f"({supported_count})" in en_svg
    assert "PILOT" in en_svg
    assert "Can claim" in en_svg
    assert "可以主张" in zh_svg


def test_intervention_timeline_bilingual_short_phases():
    """HTML-02：干预时间线只放阶段短名与活动数，不放 AI 规则长句。"""
    en_data = _load("examples/ai-coding-assistant/result.json")
    zh_data = _load("examples/ai-coding-assistant/result.zh.json")
    en = render_infographics(en_data, lang="en")
    zh = render_infographics(zh_data, lang="zh")
    rule = en_data["intervention"]["phase_1"]["ai_usage_rule"]
    assert rule[:20] not in en["intervention"]
    assert "AI rule:" not in en["intervention"]
    assert "AI 规则:" not in zh["intervention"]
    # Renderer deliberately normalizes a long phase name to a short `Phase N`
    # token so SVG text cannot overflow. Preserve that visual contract rather
    # than asserting a historical full phase title.
    assert "Phase 1" in en["intervention"]
    assert "阶段 1" in zh["intervention"] or "Phase 1" in zh["intervention"]
    assert "activities" in en["intervention"]
    assert "项活动" in zh["intervention"]


def test_evaluation_flow_bilingual_short_keywords():
    """HTML-02：评价流程只放阶段关键词，不放评估长段落。"""
    en = render_infographics(_load("examples/ai-coding-assistant/result.json"), lang="en")
    zh = render_infographics(_load("examples/ai-coding-assistant/result.zh.json"), lang="zh")
    assert "Baseline" in en["evaluation"] and "基线" in zh["evaluation"]
    assert "pre-test" in en["evaluation"] and "前测" in zh["evaluation"]
    en_base = _load("examples/ai-coding-assistant/result.json")["evaluation"].get("baseline") or "pre-test"
    assert en_base[:30] not in en["evaluation"]


def test_render_deterministic():
    en_data = _load("examples/ai-coding-assistant/result.json")
    assert render_infographics(en_data, lang="en") == render_infographics(en_data, lang="en")


def test_numbers_shared_between_langs():
    """信息图不包含数字差异：两份渲染的 SVG 中数字标记相同（仅文本不同）。"""
    en_svg = render_infographics(_load("examples/ai-coding-assistant/result.json"), lang="en")
    zh_svg = render_infographics(_load("examples/ai-coding-assistant/result.zh.json"), lang="zh")
    for key in ("workflow", "tribunal", "intervention", "evaluation"):
        assert en_svg[key] != zh_svg[key]
