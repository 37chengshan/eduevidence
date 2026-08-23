#!/usr/bin/env python3
"""render_report_html.py — Static-first HTML Evidence Report renderer (v5 Iteration 1).

Turns a validated result.json into a semantic, static, print-friendly HTML
report. Iteration 1 acceptance: **even with JavaScript fully disabled, the
report already has value** — Decision, Outcome summary, Evidence Matrix,
Tribunal, Intervention, Evaluation and Sources are all real HTML.

Theme system (Iteration 1-2) hooks in via `data-theme` + CSS variables; this
renderer emits the default `claude` theme tokens inline so the file works
standalone with zero JS and zero CDN.

Usage:
    python3 scripts/render_report_html.py \
        --result examples/ai-coding-assistant/result.json \
        --out examples/ai-coding-assistant/report.html
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

THEMES_DIR = Path(__file__).resolve().parent.parent / "visualization" / "eduevidence-report" / "themes"
THEME_NAMES = ("claude", "academic", "datalab", "presentation")  # W5: ghost removed

DIRECTION_LABELS = {"support": "支持", "contradict": "反驳", "neutral": "中性"}
DIRECTION_CLASS = {"support": "pos", "contradict": "neg", "neutral": "neu"}


def esc(text: Any) -> str:
    return html.escape(str(text if text is not None else ""))


def section(title: str, content: str, sid: str) -> str:
    return f'<section id="{sid}" class="report-section">\n<h2>{esc(title)}</h2>\n{content}\n</section>\n'


def render_decision(decision: dict) -> str:
    action = decision.get("recommended_action", "insufficient_evidence")
    confidence = decision.get("confidence", "")
    cls = {"adopt": "adopt", "pilot": "pilot", "reject": "reject",
           "insufficient_evidence": "insufficient"}.get(action, "insufficient")
    rows = [
        f'<div class="decision-card {cls}">',
        f'<span class="decision-label">决策</span>',
        f'<span class="decision-value">{esc(action.upper())}</span>',
        f'<span class="confidence-badge">{esc(confidence)}</span>',
        "</div>",
    ]
    if decision.get("decision_rationale"):
        rows.append(f'<p class="rationale">{esc(decision["decision_rationale"])}</p>')

    def bullet_list(key: str, label: str) -> str:
        items = decision.get(key) or []
        if not items:
            return ""
        lis = "".join(f"<li>{esc(i)}</li>" for i in items)
        return f"<h3>{esc(label)}</h3><ul>{lis}</ul>"

    rows.append(bullet_list("what_can_be_claimed", "可以主张 (Can Claim)"))
    rows.append(bullet_list("what_cannot_be_claimed", "不能主张 (Cannot Claim)"))
    rows.append(bullet_list("missing_evidence", "缺失证据"))
    rows.append(bullet_list("exceeds_evidence_boundary", "超出证据边界"))
    return "\n".join(rows)


def render_outcomes(outcomes: list[dict]) -> str:
    if not outcomes:
        return "<p>无 Outcome 数据。</p>"
    rows = ["<table class='data-table'><thead><tr><th>Outcome</th><th>正向效应</th>"
            "<th>负向效应</th><th>零效应</th></tr></thead><tbody>"]
    for o in outcomes:
        rows.append(
            f"<tr><td>{esc(o.get('outcome_type'))}</td>"
            f"<td class='num'>{o.get('positive_count', 0)}</td>"
            f"<td class='num'>{o.get('negative_count', 0)}</td>"
            f"<td class='num'>{o.get('null_count', 0)}</td></tr>")
    rows.append("</tbody></table>")
    return "\n".join(rows)


def render_matrix(evidence: list[dict]) -> str:
    if not evidence:
        return "<p>无证据数据。</p>"
    rows = ["<table class='data-table matrix'><thead><tr>"
            "<th>ID</th><th>Outcome</th><th>方向</th><th>Claim</th>"
            "<th>来源</th><th>质量</th></tr></thead><tbody>"]
    for ev in evidence:
        direction = ev.get("direction", "neutral")
        rows.append(
            f"<tr><td><code>{esc(ev.get('evidence_id'))}</code></td>"
            f"<td>{esc(ev.get('outcome_type'))}</td>"
            f"<td><span class='dir {DIRECTION_CLASS.get(direction, 'neu')}'>{esc(DIRECTION_LABELS.get(direction, direction))}</span></td>"
            f"<td>{esc(ev.get('claim'))}</td>"
            f"<td><code>{esc(ev.get('source_id'))}</code></td>"
            f"<td class='num'>{esc(ev.get('quality_score'))}</td></tr>")
    rows.append("</tbody></table>")
    return "\n".join(rows)


def render_tribunal(verdict: dict) -> str:
    lines = [f"<p><strong>决策：</strong>{esc(verdict.get('recommended_action', '').upper())} "
             f"· <strong>置信度：</strong>{esc(verdict.get('confidence', ''))}</p>"]

    def group(key: str, label: str) -> str:
        items = verdict.get(key) or []
        if not items:
            return ""
        lis = "".join(f"<li>{esc(i)}</li>" for i in items)
        return f"<h3>{esc(label)}</h3><ul>{lis}</ul>"

    lines.append(group("supported_claims", "支持的结论"))
    lines.append(group("uncertain_claims", "不确定的结论"))
    lines.append(group("contradicted_claims", "被反驳的结论"))
    if verdict.get("reason_for_disagreement"):
        lines.append(f"<p><strong>冲突来源：</strong>{esc(verdict['reason_for_disagreement'])}</p>")
    return "\n".join(lines)


def render_methodology(reviews: list[dict]) -> str:
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


def render_intervention(intervention: dict) -> str:
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
            rule = p.get("ai_usage_rule", "")
            lines.append(f"<div class='phase'><h3>{esc(name)}</h3>"
                         f"<p><strong>AI 规则：</strong>{esc(rule)}</p></div>")
    if intervention.get("stop_conditions"):
        lis = "".join(f"<li>{esc(s)}</li>" for s in intervention["stop_conditions"])
        lines.append(f"<h3>停止条件</h3><ul>{lis}</ul>")
    return "\n".join(lines)


def render_evaluation(evaluation: dict) -> str:
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
    return "\n".join(lines)


def render_sources(sources: list[dict]) -> str:
    if not sources:
        return "<p>无来源数据。</p>"
    rows = ["<table class='data-table'><thead><tr><th>ID</th><th>标题</th>"
            "<th>年份</th><th>权威级别</th><th>位置</th></tr></thead><tbody>"]
    for s in sources:
        rows.append(f"<tr><td><code>{esc(s.get('source_id'))}</code></td>"
                    f"<td>{esc(s.get('title'))}</td><td>{esc(s.get('year'))}</td>"
                    f"<td>{esc(s.get('authority_level'))}</td>"
                    f"<td><a href='{esc(s.get('canonical_url') or s.get('source_location'))}'>"
                    f"{esc(s.get('source_location') or s.get('canonical_url'))}</a></td></tr>")
    rows.append("</tbody></table>")
    return "\n".join(rows)


def render_sources_provenance(sources: list[dict]) -> str:
    """SWF Iteration E: fetch provenance lives in Sources & Provenance panel
    (v3 方案 §20) — never in the main evidence surface."""
    if not sources:
        return "<p>无 fetch 信息。</p>"
    lines = ["<table class='data-table'><thead><tr><th>来源</th><th>Fetch 方式</th>"
             "<th>状态</th><th>降级</th><th>时间</th></tr></thead><tbody>"]
    for s in sources:
        fetch = s.get("fetch", {})
        lines.append(f"<tr><td><code>{esc(s.get('source_id'))}</code></td>"
                     f"<td>{esc(fetch.get('fetch_provider'))}</td>"
                     f"<td>{esc(fetch.get('fetch_status'))}</td>"
                     f"<td>{esc(fetch.get('fallback_used'))}</td>"
                     f"<td>{esc(fetch.get('fetched_at'))}</td></tr>")
    lines.append("</tbody></table>")
    return "\n".join(lines)


def _theme_css() -> str:
    """Load all five theme CSS files (visualization/.../themes/*.css) and the
    base (claude) tokens; the report supports live theme switching via
    data-theme + CSS variables (v5 方案 §3-9)."""
    base = THEMES_DIR / "claude.css"
    blocks = [base.read_text(encoding="utf-8")] if base.exists() else []
    for name in THEME_NAMES:
        if name == "claude":
            continue
        css = THEMES_DIR / f"{name}.css"
        if css.exists():
            blocks.append(css.read_text(encoding="utf-8"))
    return "\n".join(blocks)


def render_html(result: dict) -> str:
    frame = result.get("research_frame", {})
    decision = result.get("decision", {})
    outcomes = result.get("outcomes", [])
    evidence = result.get("evidence", [])
    reviews = result.get("methodology_reviews", [])
    intervention = result.get("intervention", {})
    evaluation = result.get("evaluation", {})
    sources = result.get("sources", [])
    meta = result.get("meta", {})

    # W5: 主题在生成时烘焙；最终 HTML 不做运行时主题切换（仅中英文切换/language switch）

    body = "\n".join([
        section("01 Executive Decision", render_decision(decision), "01-executive-decision"),
        section("02 Outcome Evidence Overview", render_outcomes(outcomes), "02-outcome-overview"),
        section("03 Evidence Matrix", render_matrix(evidence), "03-evidence-matrix"),
        section("04 Evidence Tribunal", render_tribunal(decision), "04-evidence-tribunal"),
        section("05 Methodology Audit", render_methodology(reviews), "05-methodology-audit"),
        section("06 Conflict Analysis",
                f"<p>{esc(decision.get('reason_for_disagreement', '无冲突分析数据。'))}</p>",
                "06-conflict-analysis"),
        section("07 Claim-Evidence Trace",
                "<p>交互式 Claim→Evidence→Source 图将在 JS 增强层启用；"
                "静态表格见 Evidence Matrix 与 Sources。</p>",
                "07-claim-trace"),
        section("08 Applicability", f"<pre>{esc(json.dumps(decision.get('applicability', {}), ensure_ascii=False, indent=2))}</pre>",
                "08-applicability"),
        section("09 Teaching Intervention", render_intervention(intervention), "09-intervention"),
        section("10 Evaluation Plan", render_evaluation(evaluation), "10-evaluation"),
        section("11 Benchmark", "<p>Benchmark 数据见独立 Benchmark 报告（benchmarks/results/v2-report.md）。</p>",
                "11-benchmark"),
        section("12 Sources & Provenance",
                render_sources(sources) + "<h3>Fetch Provenance</h3>" + render_sources_provenance(sources),
                "12-sources"),
    ])

    theme_css = _theme_css()

    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="claude">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(meta.get('question', 'EduEvidence Evidence Report'))}</title>
<style>
{theme_css}
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
             padding:4px 12px; font-size:.8rem; cursor:pointer; color:var(--text); }}
.report-section {{ background:var(--surface); border:1px solid var(--border);
                  border-radius:var(--radius); box-shadow:var(--shadow);
                  padding:20px 24px; margin-bottom:20px; }}
.report-section h2 {{ font-family:var(--font-head); font-size:1.25rem; margin:0 0 12px;
                     border-bottom:1px solid var(--border); padding-bottom:8px; }}
.report-section h3 {{ font-size:.95rem; margin:14px 0 6px; }}
.decision-card {{ display:flex; align-items:center; gap:14px; padding:14px 18px; border-radius:8px;
                 border-left:6px solid var(--insufficient); background:var(--surface2); }}
.decision-card.adopt {{ border-left-color:var(--support); }}
.decision-card.pilot {{ border-left-color:var(--uncertain); }}
.decision-card.reject {{ border-left-color:var(--contradict); }}
.decision-value {{ font-family:var(--font-head); font-size:1.5rem; font-weight:700; }}
.confidence-badge {{ background:var(--uncertain); color:#fff; border-radius:999px; padding:2px 10px; font-size:.8rem; }}
.rationale {{ color:var(--text); font-size:.92rem; }}
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
<h1>{esc(meta.get('question', 'EduEvidence Evidence Report'))}</h1>
<p class="meta">EduEvidence · {esc(meta.get('mode'))} · {esc(meta.get('generated_at'))}</p>
</header>
{body}
<footer class="report-section"><p>EduEvidence Evidence Report · 由 eduevidence-report Skill 确定性渲染 · 数据源：result.json</p></footer>
</div>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render static-first HTML Evidence Report")
    parser.add_argument("--result", required=True, help="result.json path")
    parser.add_argument("--out", required=True, help="output report.html path")
    args = parser.parse_args()

    result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.write_text(render_html(result), encoding="utf-8")
    print(f"wrote {args.out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
