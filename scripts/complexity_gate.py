#!/usr/bin/env python3
"""complexity_gate.py — Deterministic complexity grading gate (plan section 9, Phase 6).

Decides whether an EduEvidence task should run in single-agent mode (S),
with one independent check (M), or enter the full 8-role workflow (L), and
whether delegation to Agent MCP is warranted at all.

Pure local heuristics — zero tokens, no spawn. The result is a suggestion:
the main agent's judgment of the actual task always wins ("宁可不拆").

Rules (per EduEvidence 实施方案 §9 and agent-mcp 编排 skill):
- S: single question, single outcome, few sources, no obvious conflict
  -> Frame → Retrieve → Extract → Verify → Answer (0 spawn)
- M: multiple studies, 2-3 outcomes, partial conflict, one independent check
  -> Primary Analysis + Independent Check (<=2-3 roles)
- L: multiple outcomes, multiple learner groups, strong conflict,
  needs teaching deployment plan -> full 8-role workflow

Do-NOT-delegate list (hit any -> delegate=False):
  quick Q&A, single-source check, formatting-only task, trivial edit,
  strong sequential dependency chain.

Usage:
    python scripts/complexity_gate.py --question "..." --depth standard \\
        --target teaching_decision --outcomes retention transfer \\
        --multi-learner --needs-pilot
"""
from __future__ import annotations

import argparse
import json
import re
from typing import Any

# Signals that push complexity up (from plan §9 / §13)
L_SIGNALS = [
    "长期", "迁移", "保持", "retention", "transfer", "长期效果",
    "多学习者", "多群体", "不同学生", "全面部署", "全校", "试点", "pilot",
    "风险", "依赖", "over-reliance", "ai dependency", "冲突", "矛盾",
]
M_SIGNALS = [
    "是否有效", "提高", "影响", "比较", "对比", "vs", "与", "不同研究",
    "证据", "研究", "结论",
]

# Do-not-delegate triggers
NO_DELEGATE_SIGNALS = [
    "一句话", "简要", "快速回答", "解释一下", "这个文件", "格式化",
    "重命名", "改个名字", "简单回答",
]


def _signal_count(text: str, signals: list[str]) -> int:
    low = text.lower()
    return sum(1 for s in signals if s.lower() in low)


def _count_outcomes(outcomes: list[str] | None) -> int:
    if not outcomes:
        return 0
    return len([o for o in outcomes if o])


def grade(
    question: str,
    *,
    depth: str = "standard",
    target: str = "evidence_review",
    outcomes: list[str] | None = None,
    multi_learner: bool = False,
    needs_pilot: bool = False,
    needs_evaluation: bool = False,
    conflict_hint: bool = False,
) -> dict[str, Any]:
    """Grade a task S/M/L and decide whether delegation is warranted.

    Returns {level, rationale, delegate, suggestion}.
    """
    question = question or ""
    l_score = _signal_count(question, L_SIGNALS)
    m_score = _signal_count(question, M_SIGNALS)
    n_outcomes = _count_outcomes(outcomes)
    no_delegate = _signal_count(question, NO_DELEGATE_SIGNALS) > 0

    # --- do-not-delegate gate (hit any -> never spawn) ---
    if no_delegate:
        return {
            "level": "S",
            "rationale": "do-not-delegate signal in question (quick/simple/formulaic task)",
            "delegate": False,
            "suggestion": "主 Agent 直接执行，禁止 spawn。",
        }

    # --- explicit inputs push complexity ---
    score = 0
    reasons: list[str] = []

    if depth == "deep":
        score += 2
        reasons.append("depth=deep")
    elif depth == "standard":
        score += 1
        reasons.append("depth=standard")

    if target in ("teaching_decision", "pilot_design", "evaluation_design"):
        score += 1
        reasons.append(f"target={target}")
    if multi_learner:
        score += 1
        reasons.append("multi-learner")
    if needs_pilot or needs_evaluation:
        score += 1
        reasons.append("needs pilot/evaluation")
    if conflict_hint:
        score += 1
        reasons.append("conflict hinted")
    if n_outcomes >= 4:
        score += 2
        reasons.append(f"{n_outcomes} outcomes")
    elif n_outcomes >= 2:
        score += 1
        reasons.append(f"{n_outcomes} outcomes")

    # --- question-language signals ---
    score += min(2, l_score)
    score += min(1, m_score)
    if l_score:
        reasons.append(f"L-signals x{l_score}")
    if m_score:
        reasons.append(f"M-signals x{m_score}")

    if score >= 4:
        level = "L"
    elif score >= 2:
        level = "M"
    else:
        level = "S"

    delegate = level in ("M", "L") and not no_delegate
    suggestion = {
        "S": "Frame → Retrieve → Extract → Verify → Answer（单 Agent 串行，0 spawn）",
        "M": "Primary Analysis + Independent Check（增强模式 ≤2-3 角色）",
        "L": "完整 8 角色工作流（Planner/Retriever/Analyst/Skeptic/Method Reviewer/Judge/Intervention Designer/Evaluation Designer）",
    }[level]

    rationale = f"complexity score {score} ({', '.join(reasons) if reasons else 'no signals'})"
    return {"level": level, "rationale": rationale, "delegate": delegate, "suggestion": suggestion}


def main() -> int:
    parser = argparse.ArgumentParser(description="EduEvidence deterministic complexity gate")
    parser.add_argument("--question", required=True, help="education question text")
    parser.add_argument("--depth", choices=["quick", "standard", "deep"], default="standard")
    parser.add_argument("--target", choices=["evidence_review", "teaching_decision",
                                            "pilot_design", "evaluation_design"],
                        default="evidence_review")
    parser.add_argument("--outcomes", nargs="*", default=None)
    parser.add_argument("--multi-learner", action="store_true")
    parser.add_argument("--needs-pilot", action="store_true")
    parser.add_argument("--needs-evaluation", action="store_true")
    parser.add_argument("--conflict-hint", action="store_true")
    args = parser.parse_args()

    result = grade(
        args.question,
        depth=args.depth,
        target=args.target,
        outcomes=args.outcomes,
        multi_learner=args.multi_learner,
        needs_pilot=args.needs_pilot,
        needs_evaluation=args.needs_evaluation,
        conflict_hint=args.conflict_hint,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
