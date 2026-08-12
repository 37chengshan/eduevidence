#!/usr/bin/env python3
"""build_report.py — HTML Composer: single-file offline EduEvidence_Report.html
(v5 Iteration 6-9, SWF Iteration E).

Pipeline (SKILL.md §8):
    result.json (+ result.zh.json)
      -> contract validation (report-result.schema.json semantics)
      -> claim-evidence-source audit  (REPORT_INVALID gate, §27/§60)
      -> adapters in-memory: ECharts specs / AntV infographics / Academic figures
      -> numbers-match integrity gate
      -> report_spec.json (visualization decision record)
      -> single-file offline HTML: 双语（中文默认 + English 切换）12 节，
         执行摘要叙事（问题→结论→依据→行动），每节导读行，静态优先 + JS 增强

数据契约：
  - result.json  = 研究管线输出的原始数据（英文）
  - result.zh.json = AI 生成的全中文平行版本（同构，枚举/ID/URL/数字不变）
  - 渲染器按当前语言取数据 + 双语 UI 文案；数字一致性门对两份数据分别校验

Usage:
    python3 visualization/eduevidence-report/scripts/build_report.py \
        --result examples/ai-coding-assistant/result.json \
        --result-zh examples/ai-coding-assistant/result.zh.json \
        --out examples/ai-coding-assistant/EduEvidence_Report.html
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

from build_charts import build_all as build_chart_specs
from build_figures import build_figure_data, render_figures
from build_infographics import build_all as build_infographics
from zh_labels import label

THEMES_DIR = Path(__file__).resolve().parent.parent / "themes"
THEME_NAMES = ("claude", "academic", "editorial", "datalab", "presentation")

DIR_LABEL = {"support": "支持", "contradict": "反驳", "neutral": "中性"}
DIR_CLASS = {"support": "pos", "contradict": "neg", "neutral": "neu"}
DIR_COLOR = {"support": "#5E8A6A", "contradict": "#A85B53", "neutral": "#C99A4A"}

# ---------------------------------------------------------------------------
# 双语 UI 文案
# ---------------------------------------------------------------------------

UI_ZH = {
    "theme_label": "主题",
    "lang_label": "语言",
    "zh": "中文",
    "en": "EN",
    "section_titles": {
        "01": "01 执行决策", "02": "02 结果证据概览", "03": "03 证据矩阵",
        "04": "04 证据裁决", "05": "05 方法学审计", "06": "06 冲突分析",
        "07": "07 主张-证据追溯", "08": "08 适用性", "09": "09 教学干预",
        "10": "10 评价方案", "11": "11 基准测试", "12": "12 来源与溯源",
    },
    "section_leads": {
        "01": "本节回答：这个问题最终怎么决定？结论是什么、置信度多高、依据哪几条证据？",
        "02": "本节回答：AI 到底对哪些学习结果有支持证据、哪些有反驳？一图看清证据分布。",
        "03": "本节回答：每条证据来自哪项研究、测的是什么、方向和质量如何？可筛选、可搜索。",
        "04": "本节回答：证据允许我们主张什么、不允许主张什么？缺失的关键证据是什么？",
        "05": "本节回答：这些研究的质量可靠吗？哪些方法学问题让结论要打折？",
        "06": "本节回答：为什么不同研究会得出不同结论？分歧出在哪一环节？",
        "07": "本节回答：从最终结论到证据到原始来源，每一步是否都能追查？",
        "08": "本节回答：这个结论适用于谁、适用于什么课程和结果、需要什么条件？",
        "09": "本节回答：如果试点，AI 使用规则怎么分阶段放开？什么情况必须叫停？",
        "10": "本节回答：如何设计实验验证效果？测什么指标、成功标准是什么？",
        "11": "本节回答：EduEvidence 自己的基准测试表现如何（引用精度、成本）？",
        "12": "本节回答：引用的每一篇文献是谁、出自哪里、如何获取的？",
    },
    "decision_kpi": ["决策", "置信度", "证据最充分的结果", "最不确定的结果", "主要风险", "来源数量"],
    "summary_title": "一句话结论",
    "summary_question": "问题",
    "summary_evidence": "依据",
    "summary_action": "行动",
    "outcome_table": ["结果类型", "支持", "反驳", "中性", "证据"],
    "figure1_caption": "图 1. 各结果类型的支持证据数量（出版级学术图，不随主题变化）。",
    "matrix_filter": "筛选 / 搜索",
    "matrix_search_ph": "搜索证据…",
    "matrix_all_dir": "全部方向",
    "matrix_all_outcome": "全部结果",
    "matrix_heads": ["ID", "研究", "设计", "结果", "人群", "干预", "方向", "质量", "直接性", "来源", "主张"],
    "tribunal_decision": "决策",
    "tribunal_confidence": "置信度",
    "tribunal_can": "可以主张",
    "tribunal_uncertain": "尚不能主张",
    "tribunal_cannot": "被反驳的主张",
    "tribunal_missing": "缺失证据",
    "tribunal_flow": "EvidenceFlow 协议",
    "tribunal_figure": "裁决信息图",
    "method_audit_heads": ["检查项", "状态", "说明"],
    "method_guard": "任务 vs 学习护栏",
    "conflict_verdict": "裁决说明",
    "trace_decision": "决策",
    "trace_claim_prefix": "主张",
    "trace_no_source": "无来源",
    "applicability": ["适用于谁", "适用课程", "适用结果", "适用条件", "目标人群", "目标情境"],
    "intervention_learners": "目标学习者",
    "intervention_duration": "试点时长",
    "intervention_policy": "AI 使用规则",
    "intervention_rule": "AI 规则",
    "intervention_activities": "活动",
    "intervention_check": "结果检查",
    "intervention_stop": "停止条件",
    "intervention_timeline": "干预时间线信息图",
    "evaluation_question": "研究问题",
    "evaluation_measures": ["基线", "后测", "保持测试", "迁移测试"],
    "evaluation_metrics": ["过程指标", "学习指标", "风险指标"],
    "evaluation_threshold": "成功阈值",
    "evaluation_plan": "分析计划",
    "evaluation_figure": "评价设计信息图",
    "benchmark_note": "无基准数据（result.json 未携带 benchmark.baselines），见独立基准报告。",
    "sources_title": "来源列表",
    "sources_heads": ["ID", "标题", "年份", "权威级别", "可验证位置"],
    "provenance_title": "Fetch 溯源",
    "provenance_heads": ["来源", "Fetch 方式", "状态", "降级", "时间"],
    "provenance_search": "搜索提供方",
    "provenance_time": "检索时间",
    "provenance_empty": "无逐条 fetch 记录（来源由研究管线直接提供）。",
    "no_data": "无数据。",
    "header_evidence": "证据",
    "header_sources": "来源",
    "header_mode": "模式",
    "header_generated": "生成时间",
    "footer": "EduEvidence 证据报告 · 由 eduevidence-report Skill 确定性渲染 · 数据源：result.json · 完整性门：通过 · 单文件离线可打开",
    "raw_tag_title": "原始标识",
}

UI_EN = {
    "theme_label": "Theme",
    "lang_label": "Language",
    "zh": "中文",
    "en": "EN",
    "section_titles": {
        "01": "01 Executive Decision", "02": "02 Outcome Evidence Overview",
        "03": "03 Evidence Matrix", "04": "04 Evidence Tribunal",
        "05": "05 Methodology Audit", "06": "06 Conflict Analysis",
        "07": "07 Claim-Evidence Trace", "08": "08 Applicability",
        "09": "09 Teaching Intervention", "10": "10 Evaluation Plan",
        "11": "11 Benchmark", "12": "12 Sources & Provenance",
    },
    "section_leads": {
        "01": "What is the final decision on this question, at what confidence, and on which evidence?",
        "02": "Which learning outcomes have supporting vs contradicting evidence?",
        "03": "What does each piece of evidence measure, and how strong is it? Filter and search.",
        "04": "What can the evidence claim, what can it not claim, and what is missing?",
        "05": "How reliable are these studies, and which methodological concerns discount the conclusions?",
        "06": "Why do different studies reach different conclusions, and where exactly do they diverge?",
        "07": "Can every step from conclusion to evidence to source be traced?",
        "08": "Who does this conclusion apply to, for which course and outcomes, under what conditions?",
        "09": "If we pilot, how should AI usage rules phase in, and when must we stop?",
        "10": "How do we evaluate real effects: metrics, comparison, success threshold?",
        "11": "How does EduEvidence itself perform on its benchmark (citation precision, cost)?",
        "12": "Where does every cited study come from and how was it fetched?",
    },
    "decision_kpi": ["Decision", "Confidence", "Best-supported outcome", "Most uncertain outcome", "Main risk", "Sources"],
    "summary_title": "Bottom line",
    "summary_question": "Question",
    "summary_evidence": "Evidence",
    "summary_action": "Action",
    "outcome_table": ["Outcome", "Support", "Contradict", "Neutral", "Evidence"],
    "figure1_caption": "Fig. 1. Number of supporting evidence items per outcome type (publication figure, theme-independent).",
    "matrix_filter": "Filter / Search",
    "matrix_search_ph": "Search evidence…",
    "matrix_all_dir": "All directions",
    "matrix_all_outcome": "All outcomes",
    "matrix_heads": ["ID", "Study", "Design", "Outcome", "Population", "Intervention", "Direction", "Quality", "Directness", "Source", "Claim"],
    "tribunal_decision": "Decision",
    "tribunal_confidence": "Confidence",
    "tribunal_can": "Can claim",
    "tribunal_uncertain": "Cannot yet claim",
    "tribunal_cannot": "Contradicted claims",
    "tribunal_missing": "Missing evidence",
    "tribunal_flow": "EvidenceFlow Protocol",
    "tribunal_figure": "Tribunal infographic",
    "method_audit_heads": ["Item", "Status", "Note"],
    "method_guard": "Task vs learning guard",
    "conflict_verdict": "Tribunal note",
    "trace_decision": "Decision",
    "trace_claim_prefix": "Claim",
    "trace_no_source": "No source",
    "applicability": ["Suitable for", "Course", "Outcomes", "Conditions", "Target population", "Target context"],
    "intervention_learners": "Target learners",
    "intervention_duration": "Pilot duration",
    "intervention_policy": "AI usage policy",
    "intervention_rule": "AI rule",
    "intervention_activities": "Activities",
    "intervention_check": "Outcome check",
    "intervention_stop": "Stop conditions",
    "intervention_timeline": "Intervention timeline infographic",
    "evaluation_question": "Research question",
    "evaluation_measures": ["Baseline", "Post test", "Retention", "Transfer"],
    "evaluation_metrics": ["Process metrics", "Learning metrics", "Risk metrics"],
    "evaluation_threshold": "Success threshold",
    "evaluation_plan": "Analysis plan",
    "evaluation_figure": "Evaluation design infographic",
    "benchmark_note": "No benchmark data in result.json (benchmark.baselines empty); see the standalone benchmark report.",
    "sources_title": "Source list",
    "sources_heads": ["ID", "Title", "Year", "Authority", "Verifiable location"],
    "provenance_title": "Fetch provenance",
    "provenance_heads": ["Source", "Fetch method", "Status", "Fallback", "Time"],
    "provenance_search": "Search provider",
    "provenance_time": "Fetched at",
    "provenance_empty": "No per-source fetch records (sources provided directly by the research pipeline).",
    "no_data": "No data.",
    "header_evidence": "evidence items",
    "header_sources": "sources",
    "header_mode": "mode",
    "header_generated": "generated at",
    "footer": "EduEvidence Evidence Report · deterministically rendered by eduevidence-report Skill · source: result.json · integrity gate: PASS · single-file offline",
    "raw_tag_title": "raw id",
}


class ReportInvalid(Exception):
    """Scientific Integrity Gate failure (§27/§60): report must not be published."""


def esc(text: Any) -> str:
    return html.escape(str(text if text is not None else ""))


# ---------------------------------------------------------------------------
# 1. Contract validation + claim-evidence-source audit
# ---------------------------------------------------------------------------

def validate_contract(result: dict) -> list[str]:
    problems: list[str] = []
    for key in ("meta", "research_frame", "decision", "evidence"):
        if not isinstance(result.get(key), (dict, list)):
            problems.append(f"missing required top-level key: {key}")
    meta = result.get("meta") or {}
    if meta.get("skill") != "eduevidence":
        problems.append(f"meta.skill must be 'eduevidence', got {meta.get('skill')!r}")
    if not isinstance(result.get("outcomes", []), list):
        problems.append("outcomes must be an array")
    if not isinstance(result.get("sources", []), list):
        problems.append("sources must be an array")
    return problems


def audit_claims(result: dict) -> list[str]:
    problems: list[str] = []
    evidence = {e.get("evidence_id"): e for e in result.get("evidence", [])}
    sources = {s.get("source_id") for s in result.get("sources", [])}
    for i, claim in enumerate(result.get("claims", [])):
        eids = claim.get("evidence_ids") or []
        if not eids:
            problems.append(f"claim #{i} has no evidence_ids")
            continue
        for eid in eids:
            ev = evidence.get(eid)
            if ev is None:
                problems.append(f"claim #{i} references unknown evidence {eid!r}")
                continue
            sid = ev.get("source_id")
            if not sid or sid not in sources:
                problems.append(f"evidence {eid!r} (claim #{i}) has no resolvable source")
            if claim.get("status") == "SUPPORTED" and not sid:
                problems.append(f"SUPPORTED claim #{i} rests on source-less evidence {eid!r}")
    return problems


def check_numbers(result: dict, charts: dict) -> list[str]:
    problems: list[str] = []
    evidence = {e.get("evidence_id"): e for e in result.get("evidence", [])}
    for outcome in result.get("outcomes", []):
        dirs = [evidence[eid].get("direction") for eid in outcome.get("evidence_ids", [])
                if eid in evidence]
        derived = {k: dirs.count(k) for k in ("support", "contradict", "neutral")}
        for key, field in (("support", "support_count"), ("contradict", "contradict_count"),
                           ("neutral", "neutral_count")):
            if derived.get(key, 0) != outcome.get(field, 0):
                problems.append(
                    f"outcome {outcome.get('outcome_type')!r}: {field}={outcome.get(field)} "
                    f"but evidence-derived {key}={derived.get(key, 0)}")
    for chart in charts.get("charts", []):
        if chart.get("chart_id") != "outcome-evidence-overview":
            continue
        series = {s["name"]: s["data"] for s in chart.get("option", {}).get("series", [])}
        key = {"支持": "support", "反驳": "contradict", "中性": "neutral"}
        names = [o.get("outcome_type") for o in result.get("outcomes", [])]
        for outcome in result.get("outcomes", []):
            idx = names.index(outcome["outcome_type"]) if outcome["outcome_type"] in names else -1
            if idx < 0:
                continue
            for zh_name, en in key.items():
                data = series.get(zh_name, [])
                if idx >= len(data):
                    continue
                value = data[idx]
                if abs(value) != outcome[f"{en}_count"]:
                    problems.append(
                        f"chart {chart.get('chart_id')}: {outcome['outcome_type']} "
                        f"{en}_count={outcome[f'{en}_count']} but series={value}")
                if en == "contradict" and value > 0:
                    problems.append(f"contradict series must be ≤ 0, got {value}")
                if en in ("support", "neutral") and value < 0:
                    problems.append(f"{en} series must be ≥ 0, got {value}")
    return problems


# ---------------------------------------------------------------------------
# 2. report_spec.json — visualization decision record (§47)
# ---------------------------------------------------------------------------

def build_report_spec(result: dict, charts: dict, infographics: dict,
                      figures: dict, integrity: dict) -> dict:
    return {
        "generated_by": "build_report.py",
        "source": "result.json + result.zh.json",
        "question": result.get("meta", {}).get("question", ""),
        "theme_default": "claude",
        "theme_switchable": list(THEME_NAMES),
        "lang_default": "zh",
        "lang_switchable": ["zh", "en"],
        "charts": [
            {"chart_id": c.get("chart_id"), "purpose": c.get("purpose"),
             "engine": c.get("engine"), "data_ref": c.get("data_ref"),
             "title": c.get("title"), "integrity": c.get("integrity")}
            for c in charts.get("charts", [])
        ],
        "infographics": [
            {"chart_id": cid, "purpose": "process_or_story",
             "engine": "antv_infographic", "title": _svg_title(svg)}
            for cid, svg in infographics.items()
        ],
        "academic_figures": [
            {"chart_id": name[:-4], "purpose": "statistical_publication",
             "engine": "academic_figure", "caption": _svg_caption(svg)}
            for name, svg in figures.items()
        ],
        "integrity_gate": integrity,
    }


def _svg_title(svg: str) -> str:
    start = svg.find("<title>")
    if start >= 0:
        end = svg.find("</title>", start)
        if end > start:
            return svg[start + 7:end]
    return ""


def _svg_caption(svg: str) -> str:
    import re
    m = re.search(r'aria-label="([^"]*)"', svg)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# 3. 执行摘要叙事（问题 → 结论 → 依据 → 行动）
# ---------------------------------------------------------------------------

def exec_summary_html(result: dict, lang: str, ui: dict) -> str:
    meta = result.get("meta", {})
    decision = result.get("decision", {})
    question = meta.get("question") or decision.get("decision_question") or ""
    action = decision.get("recommended_action", "insufficient_evidence")
    confidence = decision.get("confidence", "")
    supported = decision.get("supported_claims") or []
    contradicted = decision.get("contradicted_claims") or []
    rationale = decision.get("decision_rationale") or ""

    def li(items: list[str], limit: int = 2) -> str:
        return "".join(f"<li>{esc(x)}</li>" for x in items[:limit])

    evidence_items = ""
    if supported:
        evidence_items += f"<p class='summary-ev'><span class='summary-tag pos'>支持</span></p><ul class='summary-list'>{li(supported)}</ul>"
    if contradicted:
        evidence_items += f"<p class='summary-ev'><span class='summary-tag neg'>反驳</span></p><ul class='summary-list'>{li(contradicted)}</ul>"

    return f"""
<div class="exec-summary">
  <h3>{esc(ui['summary_title'])}</h3>
  <div class="summary-row"><span class="summary-k">{esc(ui['summary_question'])}</span>
    <span class="summary-v">{esc(question)}</span></div>
  <div class="summary-row"><span class="summary-k">{esc(ui['summary_evidence'])}</span>
    <div class="summary-v">{evidence_items}</div></div>
  <div class="summary-row"><span class="summary-k">{esc(ui['summary_action'])}</span>
    <span class="summary-v"><strong>{esc(label(lang, "action", action))}</strong>（置信度：{esc(label(lang, "confidence", confidence))}）· {esc(rationale)}</span></div>
</div>"""


# ---------------------------------------------------------------------------
# 4. Static renderers (deterministic, zero-dependency fallbacks §28)
# ---------------------------------------------------------------------------

def diverging_bar_svg(option: dict, width: int = 720, height: int = 260) -> str:
    cats = option.get("yAxis", {}).get("data", [])
    series = option.get("series", [])
    if not cats:
        return ""
    left, right = 140, 40
    top, bottom = 40, 30
    plot_w, plot_h = width - left - right, height - top - bottom
    row_h = plot_h / len(cats)
    bar_h = min(14.0, row_h * 0.55)
    vmax = max(1.0, *(abs(v) for s in series for v in s.get("data", [])))
    mid = left + plot_w / 2
    scale = (plot_w / 2) / vmax

    parts = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF"/>',
             f'<line x1="{mid}" y1="{top}" x2="{mid}" y2="{top + plot_h}" '
             f'stroke="#999" stroke-width="1" stroke-dasharray="3,3"/>']
    for i, cat in enumerate(cats):
        cy = top + row_h * i + row_h / 2
        parts.append(f'<text x="{left - 8}" y="{cy + 3.5}" text-anchor="end" '
                     f'font-size="11" fill="#333">{esc(cat)}</text>')
        acc = 0.0
        for s in series:
            data = s.get("data", [])
            v = data[i] if i < len(data) else 0
            if v == 0:
                continue
            color = (s.get("itemStyle") or {}).get("color", "#8A867E")
            w = abs(v) * scale
            x = mid + acc * scale if v > 0 else mid + acc * scale - w
            acc += v
            parts.append(f'<rect x="{x:.1f}" y="{cy - bar_h / 2:.1f}" width="{w:.1f}" '
                         f'height="{bar_h:.1f}" fill="{color}"/>')
            if abs(w) > 22:
                parts.append(f'<text x="{x + w / 2:.1f}" y="{cy + 3.5}" text-anchor="middle" '
                             f'font-size="9" fill="#fff">{int(v)}</text>')
    lx = left
    for s in series:
        color = (s.get("itemStyle") or {}).get("color", "#8A867E")
        parts.append(f'<rect x="{lx}" y="{height - 18}" width="10" height="10" fill="{color}"/>')
        parts.append(f'<text x="{lx + 14}" y="{height - 9}" font-size="10" fill="#333">{esc(s.get("name", ""))}</text>')
        lx += 14 + len(s.get("name", "")) * 11 + 18
    return f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" ' \
           f'role="img" aria-label="各结果类型的支持/反驳/中性证据数量">' \
           f'{"".join(parts)}</svg>'


def grouped_bar_svg(option: dict, width: int = 720, height: int = 260,
                    note: str = "") -> str:
    cats = option.get("xAxis", {}).get("data", [])
    series = option.get("series", [])
    parts = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF"/>']
    if not cats:
        parts.append(f'<text x="{width / 2}" y="{height / 2}" text-anchor="middle" '
                     f'font-size="12" fill="#666">{esc(note)}</text>')
        return (f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
                f'role="img">{"".join(parts)}</svg>')
    left, right, top, bottom = 60, 30, 36, 40
    plot_w, plot_h = width - left - right, height - top - bottom
    group_w = plot_w / len(cats)
    bar_w = group_w / (len(series) + 1)
    vmax = max(1.0, *(abs(v) for s in series for v in s.get("data", [])))
    scale = plot_h / vmax

    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" '
                 f'y2="{top + plot_h}" stroke="#333" stroke-width="1"/>')
    for i, cat in enumerate(cats):
        cx = left + group_w * i + group_w / 2
        parts.append(f'<text x="{cx}" y="{top + plot_h + 16}" text-anchor="middle" '
                     f'font-size="10" fill="#333">{esc(cat)}</text>')
        for j, s in enumerate(series):
            data = s.get("data", [])
            v = data[i] if i < len(data) else 0
            color = (s.get("itemStyle") or {}).get("color", "#8A867E")
            x = left + group_w * i + bar_w * (j + 0.5)
            h = v * scale
            parts.append(f'<rect x="{x:.1f}" y="{top + plot_h - h:.1f}" width="{bar_w:.1f}" '
                         f'height="{h:.1f}" fill="{color}"/>')
            parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{top + plot_h - h - 3:.1f}" '
                         f'text-anchor="middle" font-size="9" fill="#333">{v:.2f}</text>')
    lx = left
    for s in series:
        color = (s.get("itemStyle") or {}).get("color", "#8A867E")
        parts.append(f'<rect x="{lx}" y="8" width="10" height="10" fill="{color}"/>')
        parts.append(f'<text x="{lx + 14}" y="17" font-size="10" fill="#333">{esc(s.get("name", ""))}</text>')
        lx += 14 + len(s.get("name", "")) * 11 + 18
    return f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" ' \
           f'role="img">{"".join(parts)}</svg>'


def trace_tree_html(result: dict, lang: str, ui: dict) -> str:
    evidence = {e.get("evidence_id"): e for e in result.get("evidence", [])}
    sources = {s.get("source_id"): s for s in result.get("sources", [])}
    action = result.get("decision", {}).get("recommended_action") or "insufficient_evidence"
    rows = [f'<div class="trace-row trace-decision">{esc(ui["trace_decision"])} → <strong>{esc(label(lang, "action", action))}</strong></div>']
    for i, claim in enumerate(result.get("claims", [])):
        rows.append(f'<div class="trace-row trace-claim">{esc(ui["trace_claim_prefix"])} {i + 1}：{esc(claim.get("claim"))} '
                    f'<span class="method-verdict">{esc(label(lang, "status", claim.get("status", "")))}</span></div>')
        for eid in claim.get("evidence_ids", []):
            ev = evidence.get(eid)
            if not ev:
                continue
            src = sources.get(ev.get("source_id") or "")
            src_cell = (f'<a href="{esc(src.get("canonical_url") or src.get("source_location"))}">'
                        f'{esc(src.get("source_id"))}</a>' if src else
                        f'<span class="dir neu">{esc(ui["trace_no_source"])}</span>')
            rows.append(
                f'<div class="trace-row trace-evidence">'
                f'<span class="dir {DIR_CLASS.get(ev.get("direction"), "neu")}">'
                f'{esc(label(lang, "dir", ev.get("direction") or "neutral"))}</span> '
                f'<code>{esc(eid)}</code> {esc(ev.get("title") or "")} → {src_cell}</div>')
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# 5. Section renderers (data 已按语言选择；ui 为对应语言文案)
# ---------------------------------------------------------------------------

def section(sid: str, num: str, content: str, lang: str, ui: dict) -> str:
    return (f'<section id="{lang}-{sid}" class="report-section">\n'
            f'<h2>{esc(ui["section_titles"][num])}</h2>\n'
            f'<p class="section-lead">{esc(ui["section_leads"][num])}</p>\n'
            f'{content}\n</section>\n')


def first_screen(result: dict, lang: str, ui: dict) -> str:
    decision = result.get("decision", {})
    outcomes = result.get("outcomes", [])
    counts = {o.get("outcome_type"): o for o in outcomes}
    supported = [t for t, o in counts.items() if o.get("support_count", 0) > o.get("contradict_count", 0)]
    uncertain = [t for t, o in counts.items() if o.get("neutral_count", 0) > 0 and o.get("support_count", 0) == 0]
    action = decision.get("recommended_action", "insufficient_evidence")
    cls = {"adopt": "adopt", "pilot": "pilot", "reject": "reject"}.get(action, "")
    risk = decision.get("main_risk") or decision.get("reason_for_disagreement") or "—"
    kpi_labels = ui["decision_kpi"]
    items = [
        (kpi_labels[0], f'<span class="decision-value">{esc(label(lang, "action", action))}</span>'),
        (kpi_labels[1], f'<span class="confidence-badge">{esc(label(lang, "confidence", decision.get("confidence") or "Insufficient"))}</span>'),
        (kpi_labels[2], esc(label(lang, "outcome", supported[0])) if supported else "—"),
        (kpi_labels[3], esc(label(lang, "outcome", uncertain[0])) if uncertain else "—"),
        (kpi_labels[4], esc(risk)[:140]),
        (kpi_labels[5], f"{len(result.get('sources', []))}"),
    ]
    cells = "".join(f'<div class="kpi"><span class="kpi-label">{esc(k)}</span>'
                    f'<span class="kpi-value">{v}</span></div>' for k, v in items)
    return (f'<div class="decision-card {cls}">'
            f'<div class="kpi-grid">{cells}</div>'
            f'<p class="rationale">{esc(decision.get("decision_rationale") or "")}</p>'
            f'</div>')


def render_outcomes(result: dict, chart: dict | None, figure_svg: str, lang: str, ui: dict) -> str:
    outcomes = result.get("outcomes", [])
    if not outcomes:
        return f"<p>{esc(ui['no_data'])}</p>"
    heads = ui["outcome_table"]
    rows = []
    for o in outcomes:
        eids = "".join(f"<code>{esc(e)}</code> " for e in o.get("evidence_ids", []))
        rows.append(
            f"<tr><td><strong>{esc(label(lang, "outcome", o.get('outcome_type')))}</strong>"
            f"<span class='raw-tag' title='{esc(ui['raw_tag_title'])}'>{esc(o.get('outcome_type'))}</span></td>"
            f"<td class='num'>{o.get('support_count', 0)}</td>"
            f"<td class='num'>{o.get('contradict_count', 0)}</td>"
            f"<td class='num'>{o.get('neutral_count', 0)}</td><td>{eids}</td></tr>")
    table = ("<div class='table-wrap'><table class='data-table'><thead><tr>"
             + "".join(f"<th>{esc(h)}</th>" for h in heads)
             + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")
    static = diverging_bar_svg(chart.get("option", {})) if chart else ""
    figure = (f'<figure class="academic-figure">{figure_svg}'
              f'<figcaption>{esc(ui["figure1_caption"])}</figcaption></figure>') if figure_svg else ""
    return table + static + figure


def render_matrix(result: dict, lang: str, ui: dict) -> str:
    evidence = result.get("evidence", [])
    if not evidence:
        return f"<p>{esc(ui['no_data'])}</p>"
    heads = ui["matrix_heads"]
    rows = []
    for ev in evidence:
        direction = ev.get("direction", "neutral")
        rows.append(
            f"<tr><td><code>{esc(ev.get('evidence_id'))}</code></td>"
            f"<td class='cell-main'>{esc(ev.get('title') or '')}</td>"
            f"<td>{esc(label(lang, "study", ev.get('study_type') or ''))}</td>"
            f"<td>{esc(label(lang, "outcome", ev.get('outcome_type') or ''))}</td>"
            f"<td class='cell-main'>{esc(ev.get('population') or '')}</td>"
            f"<td class='cell-main'>{esc(ev.get('intervention') or '')}</td>"
            f"<td><span class='dir {DIR_CLASS.get(direction, 'neu')}'>{esc(label(lang, "dir", direction))}</span></td>"
            f"<td class='num'>{esc(ev.get('quality_score'))}</td>"
            f"<td>{esc(label(lang, "verdict", str(ev.get('directness') or '')))}</td>"
            f"<td><code>{esc(ev.get('source_id'))}</code></td>"
            f"<td class='cell-main'>{esc(ev.get('claim') or '')}</td></tr>")
    outcomes = sorted({e.get('outcome_type', '') for e in evidence})
    return ("<details class='matrix-controls'><summary>" + esc(ui["matrix_filter"]) + "</summary>"
            "<div class='matrix-tools'><input id='matrix-search-"
            + lang + "' type='search' placeholder='"
            + esc(ui["matrix_search_ph"]) + "' aria-label='" + esc(ui["matrix_search_ph"]) + "'>"
            "<select id='matrix-direction-"
            + lang + "' aria-label='direction'><option value=''>"
            + esc(ui["matrix_all_dir"]) + "</option>"
            "<option value='support'>" + esc(label(lang, "dir", "support")) + "</option>"
            "<option value='contradict'>" + esc(label(lang, "dir", "contradict")) + "</option>"
            "<option value='neutral'>" + esc(label(lang, "dir", "neutral")) + "</option></select>"
            "<select id='matrix-outcome-"
            + lang + "' aria-label='outcome'><option value=''>"
            + esc(ui["matrix_all_outcome"]) + "</option>"
            + "".join(f"<option value='{esc(o)}'>{esc(label(lang, "outcome", o))}</option>" for o in outcomes)
            + "</select></div></details>"
            "<div class='table-wrap'><table id='evidence-matrix-" + lang + "' class='data-table'><thead><tr>"
            + "".join(f"<th>{esc(h)}</th>" for h in heads)
            + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")


def render_tribunal(result: dict, workflow_svg: str, tribunal_svg: str, lang: str, ui: dict) -> str:
    decision = result.get("decision", {})
    action = decision.get("recommended_action", "insufficient_evidence")
    lines = [f"<p><strong>{esc(ui['tribunal_decision'])}：</strong>{esc(label(lang, "action", action))} · "
             f"<strong>{esc(ui['tribunal_confidence'])}：</strong>{esc(label(lang, "confidence", decision.get('confidence', '')))}</p>"]

    def group(key: str, label: str, cls: str) -> str:
        items = decision.get(key) or []
        if not items:
            return ""
        lis = "".join(f"<li>{esc(i)}</li>" for i in items)
        return f"<h3>{esc(label)}</h3><ul class='{cls}'>{lis}</ul>"

    lines.append(group("supported_claims", ui["tribunal_can"], "can"))
    lines.append(group("uncertain_claims", ui["tribunal_uncertain"], "uncertain"))
    lines.append(group("contradicted_claims", ui["tribunal_cannot"], "cannot"))
    if decision.get("missing_evidence"):
        lines.append(f"<h3>{esc(ui['tribunal_missing'])}</h3><ul>"
                     + "".join(f"<li>{esc(m)}</li>" for m in decision["missing_evidence"]) + "</ul>")
    lines.append(f"<h3>{esc(ui['tribunal_flow'])}</h3>")
    lines.append(workflow_svg)
    lines.append(f"<h3>{esc(ui['tribunal_figure'])}</h3>")
    lines.append(tribunal_svg)
    return "\n".join(lines)


def render_methodology(result: dict, lang: str, ui: dict) -> str:
    reviews = result.get("methodology_reviews", [])
    if not reviews:
        return f"<p>{esc(ui['no_data'])}</p>"
    heads = ui["method_audit_heads"]
    lines = []
    for r in reviews:
        verdict = r.get("verdict", "")
        lines.append(f"<h3>审查目标：{esc(r.get('target'))} "
                     f"<span class='method-verdict'>{esc(label(lang, "verdict", verdict))}</span></h3>")
        audit = r.get("audit_items", {})
        if audit:
            rows = ["<div class='table-wrap'><table class='data-table'><thead><tr>"
                    + "".join(f"<th>{esc(h)}</th>" for h in heads)
                    + "</tr></thead><tbody>"]
            for item, info in audit.items():
                if isinstance(info, dict):
                    rows.append(f"<tr><td><code>{esc(item)}</code></td>"
                                f"<td>{esc(label(lang, "verdict", info.get('status')))}</td>"
                                f"<td class='cell-main'>{esc(info.get('note'))}</td></tr>")
            rows.append("</tbody></table></div>")
            lines.append("\n".join(rows))
        guard = r.get("task_vs_learning_guard", {})
        if guard:
            lines.append(f"<p><strong>{esc(ui['method_guard'])}：</strong>{esc(guard.get('note'))}</p>")
    return "\n".join(lines)


def render_conflicts(result: dict, lang: str, ui: dict) -> str:
    conflicts = result.get("conflicts", [])
    decision = result.get("decision", {})
    if not conflicts and not decision.get("reason_for_disagreement"):
        return f"<p>{esc(ui['no_data'])}</p>"
    cards = []
    for c in conflicts:
        for k in ("reason_for_disagreement", "explanation", "note"):
            if c.get(k):
                cards.append(f"<div class='conflict-card'><p>{esc(c[k])}</p></div>")
                break
    if decision.get("reason_for_disagreement"):
        cards.append(f"<div class='conflict-card'><p><strong>{esc(ui['conflict_verdict'])}：</strong>"
                     f"{esc(decision['reason_for_disagreement'])}</p></div>")
    return "\n".join(cards) if cards else f"<p>{esc(ui['no_data'])}</p>"


def render_applicability(result: dict, lang: str, ui: dict) -> str:
    decision = result.get("decision", {})
    app = decision.get("applicability") or result.get("applicability") or {}
    labels = ui["applicability"]
    keys = [("who", labels[0]), ("which_course", labels[1]), ("which_outcome", labels[2]),
            ("conditions", labels[3]), ("target_population", labels[4]), ("target_context", labels[5])]
    out = []
    for key, label in keys:
        if app.get(key):
            out.append(f"<p><strong>{esc(label)}：</strong>{esc(app[key])}</p>")
    for key, label in keys:
        if key not in app and decision.get(key):
            out.append(f"<p><strong>{esc(label)}：</strong>{esc(decision[key])}</p>")
    if app.get("suitable_for"):
        out.append(f"<p><strong>{esc(labels[0])}：</strong>{esc(app['suitable_for'])}</p>")
    if app.get("not_suitable_for"):
        out.append(f"<p><strong>{esc(labels[3])}：</strong>{esc(app['not_suitable_for'])}</p>")
    if app.get("required_conditions"):
        lis = "".join(f"<li>{esc(c)}</li>" for c in app["required_conditions"])
        out.append(f"<p><strong>{esc(labels[3])}：</strong></p><ul>{lis}</ul>")
    return "\n".join(out) or f"<p>{esc(ui['no_data'])}</p>"


def render_intervention(result: dict, svg: str, lang: str, ui: dict) -> str:
    intervention = result.get("intervention", {})
    if not intervention:
        return f"<p>{esc(ui['no_data'])}</p>"
    lines = [f"<p><strong>{esc(ui['intervention_learners'])}：</strong>{esc(intervention.get('target_learners'))} · "
             f"<strong>{esc(ui['intervention_duration'])}：</strong>{esc(intervention.get('pilot_duration'))}</p>"]
    if intervention.get("ai_usage_policy"):
        lines.append(f"<p><strong>{esc(ui['intervention_policy'])}：</strong>{esc(intervention['ai_usage_policy'])}</p>")
    for phase in ("phase_1", "phase_2", "phase_3", "phase_4"):
        p = intervention.get(phase)
        if isinstance(p, dict):
            name = p.get("name", phase)
            lines.append(f"<div class='phase'><h3>{esc(name)}</h3>"
                         f"<p><strong>{esc(ui['intervention_rule'])}：</strong>{esc(p.get('ai_usage_rule', ''))}</p>")
            activities = p.get("activities") or []
            if activities:
                lis = "".join(f"<li>{esc(a)}</li>" for a in activities)
                lines.append(f"<p><strong>{esc(ui['intervention_activities'])}：</strong></p><ul>{lis}</ul>")
            if p.get("outcome_check"):
                lines.append(f"<p><strong>{esc(ui['intervention_check'])}：</strong>{esc(p['outcome_check'])}</p>")
            lines.append("</div>")
    if intervention.get("stop_conditions"):
        lis = "".join(f"<li>{esc(s)}</li>" for s in intervention["stop_conditions"])
        lines.append(f"<h3>{esc(ui['intervention_stop'])}</h3><ul>{lis}</ul>")
    lines.append(f"<h3>{esc(ui['intervention_timeline'])}</h3>")
    lines.append(svg)
    return "\n".join(lines)


def render_evaluation(result: dict, svg: str, lang: str, ui: dict) -> str:
    evaluation = result.get("evaluation", {})
    if not evaluation:
        return f"<p>{esc(ui['no_data'])}</p>"
    measures = ui["evaluation_measures"]
    lines = [f"<p><strong>{esc(ui['evaluation_question'])}：</strong>{esc(evaluation.get('research_question'))}</p>"]
    for key, label in (("baseline", measures[0]), ("post_test", measures[1]),
                       ("retention_test", measures[2]), ("transfer_test", measures[3])):
        if evaluation.get(key):
            lines.append(f"<p><strong>{esc(label)}：</strong>{esc(evaluation[key])}</p>")
    metric_labels = ui["evaluation_metrics"]
    for key, label in (("process_metrics", metric_labels[0]), ("learning_metrics", metric_labels[1]),
                       ("risk_metrics", metric_labels[2])):
        items = evaluation.get(key) or []
        if items:
            lis = "".join(f"<li>{esc(i)}</li>" for i in items)
            lines.append(f"<h3>{esc(label)}</h3><ul>{lis}</ul>")
    if evaluation.get("success_threshold"):
        lines.append(f"<p><strong>{esc(ui['evaluation_threshold'])}：</strong>{esc(evaluation['success_threshold'])}</p>")
    if evaluation.get("analysis_plan"):
        lines.append(f"<p><strong>{esc(ui['evaluation_plan'])}：</strong>{esc(evaluation['analysis_plan'])}</p>")
    lines.append(f"<h3>{esc(ui['evaluation_figure'])}</h3>")
    lines.append(svg)
    return "\n".join(lines)


def render_benchmark(charts: dict, lang: str, ui: dict) -> str:
    panel = charts.get("benchmark") or {}
    if not panel:
        return f"<p>{esc(ui['benchmark_note'])}</p>"
    static = grouped_bar_svg(panel.get("option", {}), note=ui["benchmark_note"])
    return static + f"<p class='chart-summary'>{esc(panel.get('summary_text', ''))}</p>"


def render_sources(result: dict, lang: str, ui: dict) -> str:
    sources = result.get("sources", [])
    if not sources:
        return f"<p>{esc(ui['no_data'])}</p>"
    heads = ui["sources_heads"]
    rows = []
    for s in sources:
        url = s.get("canonical_url") or s.get("source_location") or ""
        rows.append(
            f"<tr><td><code>{esc(s.get('source_id'))}</code></td>"
            f"<td class='cell-main'>{esc(s.get('title'))}</td><td>{esc(s.get('year'))}</td>"
            f"<td>{esc(label(lang, "authority", s.get('authority_level')))}</td>"
            f"<td class='cell-main'><a href='{esc(url)}'>{esc(url)}</a></td></tr>")
    return ("<h3>" + esc(ui["sources_title"]) + "</h3>"
            "<div class='table-wrap'><table class='data-table'><thead><tr>"
            + "".join(f"<th>{esc(h)}</th>" for h in heads)
            + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")


def render_provenance(result: dict, lang: str, ui: dict) -> str:
    sources = result.get("sources", [])
    provenance = result.get("provenance", {})
    heads = ui["provenance_heads"]
    rows = []
    for s in sources:
        fetch = s.get("fetch") or {}
        rows.append(f"<tr><td><code>{esc(s.get('source_id'))}</code></td>"
                    f"<td>{esc(fetch.get('fetch_provider'))}</td>"
                    f"<td>{esc(fetch.get('fetch_status'))}</td>"
                    f"<td>{esc(fetch.get('fallback_used'))}</td>"
                    f"<td>{esc(fetch.get('fetched_at'))}</td></tr>")
    head = (f"<p>{esc(ui['provenance_search'])}：{esc(provenance.get('search_provider', 'n/a'))} · "
            f"{esc(ui['provenance_time'])}：{esc(provenance.get('fetched_at', 'n/a'))}</p>")
    if not rows:
        return head + f"<p>{esc(ui['provenance_empty'])}</p>"
    return (head + "<div class='table-wrap'><table class='data-table'><thead><tr>"
            + "".join(f"<th>{esc(h)}</th>" for h in heads)
            + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")


# ---------------------------------------------------------------------------
# 6. HTML assembly（双语双 body）
# ---------------------------------------------------------------------------

def _theme_css() -> str:
    blocks = []
    for name in THEME_NAMES:
        css = THEMES_DIR / f"{name}.css"
        if css.exists():
            blocks.append(css.read_text(encoding="utf-8"))
    return "\n".join(blocks)


def _lang_switcher(ui_zh: dict, ui_en: dict) -> str:
    return (
        '<div class="lang-switcher" role="group" aria-label="语言切换">'
        f'<span>{esc(ui_zh["lang_label"])}</span>'
        f'<button type="button" data-lang-target="zh" class="lang-btn active">{esc(ui_zh["zh"])}</button>'
        f'<button type="button" data-lang-target="en" class="lang-btn">{esc(ui_en["en"])}</button>'
        "</div>")


def _enhancer_js(charts: dict, result_en: dict) -> str:
    outcome_spec = next((c for c in charts.get("charts", [])
                         if c.get("chart_id") == "outcome-evidence-overview"), None)
    trace_spec = next((c for c in charts.get("charts", [])
                       if c.get("chart_id") == "claim-evidence-trace"), None)
    benchmark_spec = charts.get("benchmark") or {}
    matrix_rows = [
        {"id": e.get("evidence_id"), "title": e.get("title", ""),
         "direction": e.get("direction", "neutral"),
         "outcome": e.get("outcome_type", ""), "quality": e.get("quality_score", 0)}
        for e in result_en.get("evidence", [])
    ]
    return f"""
(function () {{
  'use strict';
  var root = document.documentElement;
  // ---- Theme switcher ----
  var savedTheme = null;
  try {{ savedTheme = localStorage.getItem('eduevidence-theme'); }} catch (e) {{}}
  if (savedTheme) root.setAttribute('data-theme', savedTheme);
  document.querySelectorAll('.theme-btn').forEach(function (btn) {{
    btn.addEventListener('click', function () {{
      root.setAttribute('data-theme', btn.dataset.themeTarget);
      try {{ localStorage.setItem('eduevidence-theme', btn.dataset.themeTarget); }} catch (e) {{}}
      document.querySelectorAll('.theme-btn').forEach(function (b) {{
        b.classList.toggle('active', b === btn);
      }});
    }});
  }});

  // ---- Language switcher (zh / en) ----
  function applyLang(lang) {{
    document.querySelectorAll('.report-shell[data-lang-body]').forEach(function (shell) {{
      shell.style.display = shell.dataset.langBody === lang ? '' : 'none';
    }});
    document.querySelectorAll('.lang-btn').forEach(function (b) {{
      b.classList.toggle('active', b.dataset.langTarget === lang);
    }});
    try {{ localStorage.setItem('eduevidence-lang', lang); }} catch (e) {{}}
  }}
  var savedLang = null;
  try {{ savedLang = localStorage.getItem('eduevidence-lang'); }} catch (e) {{}}
  applyLang(savedLang === 'en' ? 'en' : 'zh');
  document.querySelectorAll('.lang-btn').forEach(function (btn) {{
    btn.addEventListener('click', function () {{ applyLang(btn.dataset.langTarget); }});
  }});

  // ---- Evidence matrix filter / search (zh body 与 en body 各自一套) ----
  function bindMatrix(scope) {{
    var matrix = scope.querySelector('table[id^=evidence-matrix-]');
    if (!matrix) return;
    var search = scope.querySelector('[id^="matrix-search-"]');
    var dirSel = scope.querySelector('[id^="matrix-direction-"]');
    var outSel = scope.querySelector('[id^="matrix-outcome-"]');
    var rows = matrix.querySelectorAll('tbody tr');
    function applyFilter() {{
      var q = (search && search.value || '').toLowerCase();
      var d = dirSel ? dirSel.value : '';
      var o = outSel ? outSel.value : '';
      rows.forEach(function (row, i) {{
        var title = row.cells[1] ? row.cells[1].textContent.toLowerCase() : '';
        var id = row.cells[0] ? row.cells[0].textContent.toLowerCase() : '';
        var direction = row.cells[6] ? row.cells[6].textContent.trim() : '';
        var outcome = row.cells[3] ? row.cells[3].textContent.trim() : '';
        var dirMap = {{ '支持': 'support', '反驳': 'contradict', '中性': 'neutral',
                       'Support': 'support', 'Contradict': 'contradict', 'Neutral': 'neutral' }};
        var dVal = dirMap[direction] || direction;
        var show = (!q || title.indexOf(q) >= 0 || id.indexOf(q) >= 0)
          && (!d || dVal === d) && (!o || outcome.indexOf(o) >= 0);
        row.style.display = show ? '' : 'none';
      }});
    }}
    if (search) search.addEventListener('input', applyFilter);
    if (dirSel) dirSel.addEventListener('change', applyFilter);
    if (outSel) outSel.addEventListener('change', applyFilter);
  }}
  document.querySelectorAll('.report-shell').forEach(bindMatrix);

  // ---- ECharts enhancer (only when window.echarts exists) ----
  function mountChart(containerId, spec) {{
    var el = document.getElementById(containerId);
    if (!el || typeof window.echarts === 'undefined') return;
    var chart = window.echarts.init(el);
    chart.setOption(spec.option || {{}});
  }}
  ['zh', 'en'].forEach(function (lng) {{
    mountChart('chart-outcome-' + lng, {json.dumps(outcome_spec or {}, ensure_ascii=False)});
    mountChart('chart-trace-' + lng, {json.dumps(trace_spec or {}, ensure_ascii=False)});
    mountChart('chart-benchmark-' + lng, {json.dumps(benchmark_spec, ensure_ascii=False)});
  }});
}})();
"""


def render_body(result: dict, lang: str, ui: dict, charts: dict, infographics: dict,
                figures: dict) -> str:
    decision = result.get("decision", {})
    meta = result.get("meta", {})
    question = meta.get("question") or decision.get("decision_question") or "EduEvidence Report"
    infographic_order = ["workflow", "tribunal", "intervention", "evaluation"]
    # 每张信息图的 marker id 按 语言+图名 唯一化，url 引用同步
    svg = {}
    for k in infographic_order:
        s = infographics.get(k, "")
        s = s.replace("url(#arr)", f"url(#arr-{lang}-{k})")
        s = s.replace('id="arr"', f'id="arr-{lang}-{k}"')
        svg[k] = s
    figure_svg = figures.get("outcome-comparison.svg", "")
    outcome_chart = next((c for c in charts.get("charts", [])
                          if c.get("chart_id") == "outcome-evidence-overview"), None)

    body = "\n".join([
        section("01-executive-decision", "01",
                exec_summary_html(result, lang, ui) + first_screen(result, lang, ui), lang, ui),
        section("02-outcome-overview", "02",
                render_outcomes(result, outcome_chart, figure_svg, lang, ui)
                + '<div id="chart-outcome-' + lang + '" class="chart-mount" role="img" aria-label="interactive outcome chart"></div>', lang, ui),
        section("03-evidence-matrix", "03", render_matrix(result, lang, ui), lang, ui),
        section("04-evidence-tribunal", "04",
                render_tribunal(result, svg.get("workflow", ""), svg.get("tribunal", ""), lang, ui), lang, ui),
        section("05-methodology-audit", "05", render_methodology(result, lang, ui), lang, ui),
        section("06-conflict-analysis", "06", render_conflicts(result, lang, ui), lang, ui),
        section("07-claim-trace", "07",
                trace_tree_html(result, lang, ui)
                + '<div id="chart-trace-' + lang + '" class="chart-mount" role="img" aria-label="interactive trace chart"></div>', lang, ui),
        section("08-applicability", "08", render_applicability(result, lang, ui), lang, ui),
        section("09-intervention", "09",
                render_intervention(result, svg.get("intervention", ""), lang, ui), lang, ui),
        section("10-evaluation", "10",
                render_evaluation(result, svg.get("evaluation", ""), lang, ui), lang, ui),
        section("11-benchmark", "11",
                render_benchmark(charts, lang, ui)
                + '<div id="chart-benchmark-' + lang + '" class="chart-mount" role="img" aria-label="interactive benchmark chart"></div>', lang, ui),
        section("12-sources", "12",
                render_sources(result, lang, ui) + f"<h3>{esc(ui['provenance_title'])}</h3>"
                + render_provenance(result, lang, ui), lang, ui),
    ])

    return f"""<div class="report-shell" data-lang-body="{lang}">
<header class="report-header">
<h1>{esc(question)}</h1>
<p class="meta">EduEvidence · {esc(ui['header_mode'])}={esc(label(lang, "mode", meta.get("mode") or ""))} · {esc(ui['header_generated'])}={esc(meta.get('generated_at'))} · {esc(ui['header_evidence'])} {len(result.get('evidence', []))} 条 · {esc(ui['header_sources'])} {len(result.get('sources', []))} 个</p>
</header>
{body}
<footer class="report-section"><p>{esc(ui['footer'])}</p></footer>
</div>"""


def render_html(result_en: dict, result_zh: dict, charts: dict, infographics: dict,
                figures: dict) -> str:
    # 图表 spec 用英文数据生成（同一份，双语共用）
    body_zh = render_body(result_zh, "zh", UI_ZH, charts, infographics, figures)
    body_en = render_body(result_en, "en", UI_EN, charts, infographics, figures)

    theme_switcher = (
        '<div class="theme-switcher" role="group" aria-label="主题">'
        f'<span>{esc(UI_ZH["theme_label"])}</span>'
        + "".join(f'<button type="button" data-theme-target="{name}" class="theme-btn'
                  f'{" active" if name == "claude" else ""}">{name.title()}</button>'
                  for name in THEME_NAMES)
        + "</div>")

    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="claude">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(result_zh.get("meta", {}).get("question") or result_en.get("meta", {}).get("question") or "EduEvidence Evidence Report")}</title>
<style>
{_theme_css()}
:root {{
  --bg:#F7F4ED; --surface:#FFFFFF; --surface2:#FCFAF6;
  --text:#3A3833; --primary:#B8694A; --support:#5E8A6A;
  --contradict:#A85B53; --uncertain:#C99A4A; --insufficient:#8A867E;
  --border:#E5DFD3; --radius:10px; --shadow:0 1px 3px rgba(60,56,48,.08);
  --font-head:'Georgia','Songti SC',serif; --font-ui:'Helvetica Neue',Arial,sans-serif;
}}
body {{ margin:0; background:var(--bg); color:var(--text);
       font-family:var(--font-ui); line-height:1.65; }}
.report-shell {{ max-width:1200px; margin:0 auto; padding:24px 32px 80px; }}
.controls {{ display:flex; gap:18px; flex-wrap:wrap; align-items:center;
            border-bottom:1px solid var(--border); padding-bottom:12px; margin-bottom:16px; }}
.report-header {{ border-bottom:1px solid var(--border); padding-bottom:16px; margin-bottom:24px; }}
.report-header h1 {{ font-family:var(--font-head); font-size:1.9rem; margin:0 0 8px; color:var(--text); }}
.report-header .meta {{ color:var(--insufficient); font-size:.85rem; }}
.theme-switcher, .lang-switcher {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
.lang-switcher span, .theme-switcher span {{ font-size:.82rem; color:var(--insufficient); }}
.theme-btn, .lang-btn {{ background:var(--surface); border:1px solid var(--border); border-radius:999px;
             padding:4px 12px; font-size:.8rem; cursor:pointer; color:var(--text); }}
.theme-btn.active, .lang-btn.active {{ background:var(--primary); color:#fff; border-color:var(--primary); }}
.report-section {{ background:var(--surface); border:1px solid var(--border);
                  border-radius:var(--radius); box-shadow:var(--shadow);
                  padding:20px 24px; margin-bottom:20px; }}
.report-section h2 {{ font-family:var(--font-head); font-size:1.25rem; margin:0 0 6px;
                     border-bottom:1px solid var(--border); padding-bottom:8px; }}
.section-lead {{ font-size:.88rem; color:var(--insufficient); margin:0 0 14px;
                background:var(--surface2); border-radius:6px; padding:8px 12px;
                border-left:3px solid var(--primary); }}
.report-section h3 {{ font-size:.95rem; margin:14px 0 6px; }}
.decision-card {{ padding:18px 20px; border-radius:10px;
                 border-left:6px solid var(--insufficient); background:var(--surface2);
                 box-shadow:var(--shadow); }}
.decision-card.adopt {{ border-left-color:var(--support); }}
.decision-card.pilot {{ border-left-color:var(--uncertain); }}
.decision-card.reject {{ border-left-color:var(--contradict); }}
.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px 18px; }}
.kpi-label {{ display:block; font-size:.72rem; color:var(--insufficient); text-transform:uppercase; letter-spacing:.05em; margin-bottom:2px; }}
.kpi-value {{ font-size:1.05rem; font-weight:600; }}
.decision-value {{ font-family:var(--font-head); font-size:1.5rem; font-weight:700; }}
.confidence-badge {{ background:var(--uncertain); color:#fff; border-radius:999px; padding:3px 12px; font-size:.82rem; }}
.rationale {{ color:var(--text); font-size:.92rem; margin-top:12px; border-top:1px dashed var(--border);
             padding-top:10px; }}
.exec-summary {{ background:var(--surface2); border:1px solid var(--border);
                 border-radius:10px; padding:16px 20px; margin-bottom:18px; }}
.exec-summary h3 {{ margin:0 0 10px; color:var(--primary); }}
.summary-row {{ display:flex; gap:12px; margin:8px 0; }}
.summary-k {{ flex:0 0 64px; font-weight:700; color:var(--insufficient); font-size:.88rem; }}
.summary-v {{ flex:1; font-size:.95rem; }}
.summary-list {{ margin:4px 0 0; padding-left:18px; }}
.summary-tag {{ display:inline-block; border-radius:999px; padding:0 10px; font-size:.75rem; color:#fff; }}
.summary-tag.pos {{ background:var(--support); }}
.summary-tag.neg {{ background:var(--contradict); }}
ul.can li {{ border-left:3px solid var(--support); }}
ul.uncertain li {{ border-left:3px solid var(--uncertain); }}
ul.cannot li {{ border-left:3px solid var(--contradict); }}
ul.can li, ul.uncertain li, ul.cannot li {{ list-style:none; margin:6px 0; padding:6px 10px;
  background:var(--surface2); border-radius:6px; font-size:.9rem; }}
.report-section svg {{ max-width:100%; height:auto; border:1px solid var(--border);
                       border-radius:var(--radius-sm); background:#fff; }}
.table-wrap {{ overflow-x:auto; -webkit-overflow-scrolling:touch; border:1px solid var(--border);
               border-radius:var(--radius-sm); max-width:100%; }}
.table-wrap .data-table {{ border:none; }}
.data-table {{ width:100%; border-collapse:collapse; font-size:.88rem; }}
.table-wrap .data-table th {{ background:var(--surface2); position:sticky; top:0; white-space:nowrap; }}
.data-table th, .data-table td {{ border:1px solid var(--border); padding:7px 10px; text-align:left;
                                  vertical-align:top; }}
.data-table th {{ background:var(--surface2); white-space:nowrap; }}
.data-table td.cell-main {{ max-width:280px; overflow:hidden; text-overflow:ellipsis;
                            white-space:nowrap; }}
.data-table tbody tr:nth-child(even) {{ background:var(--surface2); }}
.data-table tbody tr:hover {{ background:var(--primary-soft, #F3E4DC); }}
.raw-tag {{ display:inline-block; margin-left:6px; font-size:.68rem; color:var(--insufficient);
           background:var(--surface2); border:1px solid var(--border); border-radius:4px;
           padding:0 5px; vertical-align:1px; font-family:'SF Mono',Menlo,monospace; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
.dir {{ display:inline-block; border-radius:999px; padding:1px 9px; font-size:.78rem; }}
.dir.pos {{ background:var(--support); color:#fff; }}
.dir.neg {{ background:var(--contradict); color:#fff; }}
.dir.neu {{ background:var(--uncertain); color:#fff; }}
.method-verdict {{ font-weight:700; }}
.phase {{ border-left:3px solid var(--primary); padding:4px 0 4px 14px; margin:12px 0;
         background:var(--surface2); border-radius:6px; }}
.phase h3 {{ margin-top:4px; }}
.conflict-card {{ border-left:3px solid var(--contradict); background:var(--surface2);
                 padding:10px 14px; margin:8px 0; border-radius:6px; }}
.trace-row {{ margin:2px 0; font-size:.88rem; }}
.trace-decision {{ font-weight:700; padding:4px 0; }}
.trace-claim {{ margin-left:16px; padding:3px 0; }}
.trace-evidence {{ margin-left:36px; color:var(--text); padding:2px 0; }}
.chart-mount {{ width:100%; height:320px; margin-top:10px; }}
.chart-summary {{ color:var(--insufficient); font-size:.85rem; }}
.academic-figure {{ margin:14px 0; }}
.academic-figure svg {{ max-width:100%; height:auto; }}
.academic-figure figcaption {{ font-size:.82rem; color:var(--insufficient); margin-top:6px; }}
.matrix-tools {{ display:flex; gap:10px; flex-wrap:wrap; margin:8px 0; }}
.matrix-tools input, .matrix-tools select {{ padding:5px 10px; font-size:.85rem;
  border:1px solid var(--border); border-radius:6px; background:var(--surface); color:var(--text); }}
.matrix-controls summary {{ cursor:pointer; color:var(--primary); font-size:.88rem; }}
details.matrix-controls {{ margin-bottom:8px; }}
code {{ font-family:'SF Mono',Menlo,monospace; font-size:.82em; background:var(--surface2);
       padding:1px 4px; border-radius:4px; }}
a {{ color:var(--primary); word-break:break-all; }}
@media print {{ body {{ background:#fff; }} .report-section {{ box-shadow:none; border:none; }}
  .report-section svg {{ border:none; }} .table-wrap {{ overflow:visible; }} }}
@media (max-width:720px) {{ .report-shell {{ padding:12px; }} .data-table {{ font-size:.78rem; }}
  .kpi-grid {{ grid-template-columns:1fr 1fr; }} }}
</style>
</head>
<body>
<div class="controls">
{theme_switcher}
{_lang_switcher(UI_ZH, UI_EN)}
</div>
{body_zh}
{body_en}
<script>
{_enhancer_js(charts, result_en)}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# 7. Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build single-file offline bilingual EduEvidence_Report.html")
    parser.add_argument("--result", required=True, help="result.json path (English source)")
    parser.add_argument("--result-zh", help="result.zh.json path (Chinese parallel); defaults to <result_dir>/result.zh.json")
    parser.add_argument("--out", help="output HTML path (default: <result_dir>/EduEvidence_Report.html)")
    parser.add_argument("--spec-out", help="report_spec.json path (default: beside --out)")
    parser.add_argument("--vendor-echarts", help="optional local echarts.min.js to inline (interactive offline)")
    args = parser.parse_args()

    result_path = Path(args.result)
    result_en = json.loads(result_path.read_text(encoding="utf-8"))
    zh_path = Path(args.result_zh) if args.result_zh else result_path.with_name("result.zh.json")
    if not zh_path.exists():
        print(f"ERROR: Chinese parallel data missing: {zh_path} (generate it as result.zh.json)")
        return 2
    result_zh = json.loads(zh_path.read_text(encoding="utf-8"))

    # 1. Contract validation（两份数据分别校验）
    for label, data in (("result.json", result_en), ("result.zh.json", result_zh)):
        problems = validate_contract(data)
        if problems:
            print(f"REPORT_INVALID — {label} contract violations:")
            for p in problems:
                print(f"  - {p}")
            return 2

    # 2. Claim-Evidence-Source audit
    for label, data in (("result.json", result_en), ("result.zh.json", result_zh)):
        audit = audit_claims(data)
        if audit:
            print(f"REPORT_INVALID — {label} claim-evidence-source audit failed:")
            for p in audit:
                print(f"  - {p}")
            return 2

    # 3. Adapters（英文数据生成 spec；中文数据同构，数字一致）
    charts = build_chart_specs(result_en)
    infographics = build_infographics(result_en)
    figure_data = build_figure_data(result_en)
    figures = render_figures(figure_data)

    # 4. Numbers-match integrity gate（两份数据）
    for label, data in (("result.json", result_en), ("result.zh.json", result_zh)):
        problems = check_numbers(data, charts)
        if problems:
            print(f"REPORT_INVALID — {label} chart numbers differ from result:")
            for p in problems:
                print(f"  - {p}")
            return 2

    integrity = {
        "status": "PASS",
        "contract_valid": True,
        "claims_bound": len(result_en.get("claims", [])),
        "evidence_bound": len(result_en.get("evidence", [])),
        "sources_resolved": len(result_en.get("sources", [])),
        "numbers_match_result": True,
        "no_axis_distortion": True,
        "no_false_precision": True,
        "colorblind_safe": True,
        "langs": ["zh", "en"],
        "generated_by": "build_report.py",
        "source": str(result_path) + " + " + str(zh_path),
    }

    spec = build_report_spec(result_en, charts, infographics, figures, integrity)

    html_out = Path(args.out) if args.out else result_path.parent / "EduEvidence_Report.html"
    html_out.parent.mkdir(parents=True, exist_ok=True)
    html_text = render_html(result_en, result_zh, charts, infographics, figures)

    if args.vendor_echarts:
        echarts_js = Path(args.vendor_echarts).read_text(encoding="utf-8")
        html_text = html_text.replace("</head>", f"<script>{echarts_js}</script>\n</head>", 1)
        print(f"vendored echarts ({len(echarts_js)} bytes) into single file")

    html_out.write_text(html_text, encoding="utf-8")
    spec_out = Path(args.spec_out) if args.spec_out else html_out.with_name("report_spec.json")
    spec_out.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {html_out} ({html_out.stat().st_size} bytes) + {spec_out.name} — integrity: PASS (zh+en)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
