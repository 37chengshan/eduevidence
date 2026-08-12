#!/usr/bin/env python3
"""build_infographics.py — AntV-style infographic adapter (v5 Iteration 3, §33/§38).

Produces inline-SVG research infographics (process/story purpose) from
result.json — engine mapping per Visualization Router (v5 §34):
process_or_story -> AntV Infographic -> inline SVG.

First-version scope (v5 §51): 4 infographics:
    - workflow        Research / EvidenceFlow 流程
    - tribunal        证据裁决三段式（CAN CLAIM / CANNOT CLAIM / WHY）
    - intervention    教学干预阶段时间线
    - evaluation      评价设计流程

语言（P0-13）：render_infographics(result, lang='zh'|'en') 按 lang 渲染——
zh 使用 result.zh.json 的 claim / reason_for_disagreement / intervention /
evaluation 等文本，en 使用 result.json；数字与结构两边一致（双语同构门校验）。
Generated SVG is deterministic, zero-dependency, embedded in the report as
InfographicBlock components (v5 §36). Numbers always come from result.json.

Usage:
    python3 visualization/eduevidence-report/scripts/build_infographics.py \
        --result examples/ai-coding-assistant/result.json \
        --out examples/ai-coding-assistant/infographics.json
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.sax.saxutils as sax
from pathlib import Path
from typing import Any

from zh_labels import label

W = 720
H = 260
PALETTE = {"primary": "#B8694A", "support": "#5E8A6A", "contradict": "#A85B53",
           "uncertain": "#C99A4A", "muted": "#8A867E", "bg": "#FCFAF6",
           "border": "#E5DFD3", "text": "#3A3833"}

TITLES = {
    "zh": {"workflow": "EvidenceFlow 协议", "tribunal": "证据裁决",
           "intervention": "教学干预时间线", "evaluation": "评价设计流程"},
    "en": {"workflow": "EvidenceFlow Protocol", "tribunal": "Evidence Tribunal",
           "intervention": "Intervention Timeline", "evaluation": "Evaluation Design Flow"},
}

TRIBUNAL_LABELS = {
    "zh": {"can": "可以主张", "cannot": "不可主张", "source": "冲突来源", "none": "（无）"},
    "en": {"can": "Can claim", "cannot": "Cannot claim", "source": "Source of conflict", "none": "(none)"},
}

FLOW_STEPS = {
    "zh": ["问题框架", "检索", "抓取\n验证", "证据抽取", "反方质疑",
           "方法\n审计", "裁决", "适用性", "干预\n评价"],
    "en": ["Frame", "Retrieve", "Fetch\nVerify", "Extract", "Challenge",
           "Audit\nMethod", "Adjudicate", "Applicability", "Intervene\nEvaluate"],
}

EVAL_NODES = {
    "zh": [("基线", "前测"), ("后测", "后测"), ("保持", "保持测试"),
           ("迁移", "迁移测试（无 AI）")],
    "en": [("Baseline", "pre-test"), ("Post test", "post-test"),
           ("Retention", "retention test"), ("Transfer", "transfer test (no AI)")],
}


def _esc(text: Any) -> str:
    return sax.escape(str(text if text is not None else ""))


def _box(x: int, y: int, w: int, h: int, label: str, fill: str, text_color: str = "#FFFFFF",
         font_size: int = 13, sub: str = "") -> str:
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}"/>']
    ty = y + h / 2 - (5 if sub else 0)
    parts.append(f'<text x="{x + w / 2}" y="{ty}" text-anchor="middle" fill="{text_color}" '
                 f'font-size="{font_size}" font-weight="600">{_esc(label)}</text>')
    if sub:
        parts.append(f'<text x="{x + w / 2}" y="{ty + 16}" text-anchor="middle" '
                     f'fill="{text_color}" font-size="11" opacity="0.85">{_esc(sub)}</text>')
    return "".join(parts)


def _arrow(x1: int, y1: int, x2: int, y2: int) -> str:
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{PALETTE["muted"]}" '
            f'stroke-width="2" marker-end="url(#arr)"/>')


def _svg(title: str, body: str) -> str:
    return (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-label="{_esc(title)}">'
            f'<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" '
            f'orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="{PALETTE["muted"]}"/></marker></defs>'
            f'<rect width="{W}" height="{H}" fill="{PALETTE["bg"]}" rx="12"/>'
            f'<text x="24" y="34" font-size="16" font-weight="700" fill="{PALETTE["text"]}">{_esc(title)}</text>'
            f'{body}</svg>')


def workflow_svg(lang: str = "zh") -> str:
    steps = FLOW_STEPS[lang]
    n = len(steps)
    bw, gap = 64, 12
    total = n * bw + (n - 1) * gap
    x0 = (W - total) // 2
    y = 100
    boxes = []
    for i, lab in enumerate(steps):
        x = x0 + i * (bw + gap)
        fill = PALETTE["support"] if i in (4, 5) else (PALETTE["primary"] if i < 6 else PALETTE["uncertain"])
        boxes.append(_box(x, y, bw, 52, lab, fill, font_size=10))
        if i < n - 1:
            boxes.append(_arrow(x + bw, y + 26, x + bw + gap, y + 26))
    return _svg(TITLES[lang]["workflow"], "".join(boxes))


def tribunal_svg(verdict: dict, lang: str = "zh") -> str:
    labs = TRIBUNAL_LABELS[lang]
    none_text = labs["none"]
    can = verdict.get("supported_claims") or verdict.get("what_can_be_claimed") or [none_text]
    cannot = verdict.get("contradicted_claims") or verdict.get("what_cannot_be_claimed") or [none_text]
    why = verdict.get("reason_for_disagreement") or (
        "证据冲突或缺失" if lang == "zh" else "Conflicting or missing evidence")
    action = verdict.get("recommended_action", "insufficient_evidence").upper()

    def col(x: int, title: str, items: list[str], color: str) -> str:
        parts = [f'<text x="{x + 10}" y="80" font-size="13" font-weight="700" fill="{color}">{_esc(title)}</text>']
        for i, item in enumerate(items[:4]):
            yy = 105 + i * 22
            parts.append(f'<circle cx="{x + 14}" cy="{yy - 5}" r="3" fill="{color}"/>')
            parts.append(f'<text x="{x + 26}" y="{yy}" font-size="11" fill="{PALETTE["text"]}">'
                         f'{_esc(item[:44])}</text>')
        return "".join(parts)

    body = (
        f'<text x="24" y="180" font-size="13" font-weight="700" fill="{PALETTE["text"]}">{_esc(labs["source"])}</text>'
        f'<text x="24" y="202" font-size="11" fill="{PALETTE["muted"]}">{_esc(why[:80])}</text>'
        f'<rect x="24" y="216" width="180" height="28" rx="14" fill="{PALETTE["uncertain"]}"/>'
        f'<text x="114" y="235" text-anchor="middle" font-size="13" font-weight="700" fill="#fff">{_esc(action)}</text>'
        + col(240, labs["can"], can, PALETTE["support"])
        + col(480, labs["cannot"], cannot, PALETTE["contradict"])
    )
    return _svg(TITLES[lang]["tribunal"], body)


def intervention_svg(intervention: dict, lang: str = "zh") -> str:
    phases = [intervention.get(p) for p in ("phase_1", "phase_2", "phase_3", "phase_4")]
    phases = [p for p in phases if isinstance(p, dict)]
    if not phases:
        phases = [{"name": "Phase 1", "ai_usage_rule": "—"}]
    bw, gap, y = 160, 16, 100
    rule_label = "AI 规则: " if lang == "zh" else "AI rule: "
    boxes = []
    for i, p in enumerate(phases):
        x = 24 + i * (bw + gap)
        name = p.get("name", f"Phase {i + 1}")
        rule = p.get("ai_usage_rule", "")
        boxes.append(_box(x, y, bw, 96, name, PALETTE["primary"], font_size=12))
        boxes.append(f'<text x="{x + 8}" y="{y + 30}" font-size="9" fill="#fff" opacity="0.95">'
                     f'{_esc(rule_label + rule[:34])}</text>')
        if i < len(phases) - 1:
            boxes.append(_arrow(x + bw, y + 48, x + bw + gap, y + 48))
    return _svg(TITLES[lang]["intervention"], "".join(boxes))


def evaluation_svg(evaluation: dict, lang: str = "zh") -> str:
    nodes = EVAL_NODES[lang]
    keys = ("baseline", "post_test", "retention_test", "transfer_test")
    bw, gap, y = 150, 12, 110
    boxes = []
    for i, ((lab, fallback), key) in enumerate(zip(nodes, keys)):
        x = 30 + i * (bw + gap)
        sub = evaluation.get(key) or fallback
        boxes.append(_box(x, y, bw, 56, lab, PALETTE["support"], font_size=12))
        boxes.append(f'<text x="{x + bw / 2}" y="{y + 38}" text-anchor="middle" font-size="9" '
                     f'fill="#fff" opacity="0.95">{_esc((sub or "")[:30])}</text>')
        if i < len(nodes) - 1:
            boxes.append(_arrow(x + bw, y + 28, x + bw + gap, y + 28))
    return _svg(TITLES[lang]["evaluation"], "".join(boxes))


def render_infographics(result: dict, lang: str = "zh") -> dict[str, str]:
    """按语言渲染 4 张信息图（zh 数据 = result.zh.json，en 数据 = result.json）。"""
    return {
        "workflow": workflow_svg(lang),
        "tribunal": tribunal_svg(result.get("decision", {}), lang),
        "intervention": intervention_svg(result.get("intervention", {}), lang),
        "evaluation": evaluation_svg(result.get("evaluation", {}), lang),
    }


def build_all(result: dict, lang: str = "zh") -> dict[str, str]:
    """兼容别名：等价于 render_infographics(result, lang)。"""
    return render_infographics(result, lang)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build AntV-style infographic SVGs from result.json")
    parser.add_argument("--result", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--lang", choices=["zh", "en"], default="zh")
    args = parser.parse_args()

    result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    infographics = build_all(result, lang=args.lang)
    out = Path(args.out)
    out.write_text(json.dumps(infographics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.out} ({', '.join(infographics.keys())})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
