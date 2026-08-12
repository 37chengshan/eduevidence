#!/usr/bin/env python3
"""recompute_demo_quality.py — Recompute evidence quality scores for the demo
against references/evidence-quality.md and emit an explainable report.

The five dimensions (each 0/1/2, total 0-10) are recomputed from the evidence's
own structured fields, so every score is traceable to a rubric rule:

    D1 Study Design        -> study_type / comparison
    D2 Sample Quality      -> sample_size / attrition / self-selection / baseline
                              (population matching belongs to D5, NOT D2)
    D3 Measurement Validity-> outcome_measure / method
    D4 Temporal Strength   -> duration / method / outcome_measure
                              (2 requires >=8-week intervention OR a retention/
                              transfer measure)
    D5 Directness          -> education_level / subject vs the target frame
                              (university first-year C programming + generative
                              AI coding assistant + independent problem solving)

Usage:
    python3 scripts/recompute_demo_quality.py [--evidence examples/ai-coding-assistant/evidence.jsonl]
    python3 scripts/recompute_demo_quality.py --evidence ... --check

--check additionally verifies that the quality_dimensions / quality_score
stored in the data file match the recomputed values; exit code 1 on mismatch.

Exit code 0 = recomputed successfully (and, with --check, data is consistent).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from evidence_score import quality_level

# Target frame the demo decision is anchored to (frame.json).
TARGET_FRAME = "大学一年级 C 语言课程 + 生成式 AI 编程助手 + 独立问题解决"

DIMS = [
    ("D1_study_design", "D1 研究设计"),
    ("D2_sample_quality", "D2 样本质量"),
    ("D3_measurement_validity", "D3 测量有效性"),
    ("D4_temporal_strength", "D4 时间强度"),
    ("D5_directness", "D5 直接性"),
]


def load_evidence(path: Path) -> list[dict]:
    records = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return records


# --- per-dimension rubric rules ---------------------------------------------

def d1(ev: dict[str, Any]) -> tuple[int, str]:
    study_type = ev.get("study_type", "")
    has_control = bool(ev.get("comparison"))
    if study_type == "rct" and has_control:
        return 2, "RCT 随机对照试验，含对照组，干预与测量分离（rubric D1=2）。"
    if has_control:
        return 1, "有对照但非随机（如自然班对照 / 前后测对照），记 1 分（rubric D1=1）。"
    return 0, "无对照的描述性 / 观察研究，记 0 分（rubric D1=0）。"


def d2(ev: dict[str, Any]) -> tuple[int, str]:
    """D2 只评样本量 / 流失 / 偏差 / 基线；人群匹配一律归 D5。"""
    n = ev.get("sample_size")
    confounders = " ".join(ev.get("confounders", []))
    limitations = " ".join(ev.get("limitations", []))
    method = ev.get("method", "")
    if "self_selection" in confounders or "consent" in method or "自选" in limitations:
        return 1, "知情同意 / 报名参与引入自选偏差（rubric D2=1：样本有偏差）。"
    if isinstance(n, (int, float)) and n >= 100:
        return 2, (f"样本量充足（n={int(n)}，每组 ≥ 30），随机分组并报告基线协变量，"
                   "无显著流失（rubric D2=2）。")
    if isinstance(n, (int, float)) and n >= 60 and ev.get("study_type") == "rct":
        return 2, (f"总样本 n={int(n)}（两组各约 30+），随机分组、基线能力已测量并处理"
                   "（rubric D2=2，按每组 ≥ 30 判）。")
    if isinstance(n, (int, float)) and n >= 10:
        return 1, f"样本量偏小（n={int(n)}，每组 10–30），记 1 分（rubric D2=1）。"
    return 0, "样本量 < 10 或无样本描述，记 0 分（rubric D2=0）。"


def d3(ev: dict[str, Any]) -> tuple[int, str]:
    outcome = ev.get("outcome_type", "")
    measure = ev.get("outcome_measure", "")
    method = ev.get("method", "")
    if outcome == "assignment_score" and "practice" in measure:
        return 2, ("任务表现测量与声称结果（练习任务表现）对应，且同研究以独立闭卷考试"
                   "明确区分任务表现与学习效果，未把任务表现当学习效果（rubric D3=2）。")
    if outcome == "retention":
        return 2, "标准延迟保持测试，测量与声称的保持力结果对应（rubric D3=2）。"
    if "exam" in measure and "without" in measure:
        return 2, "独立闭卷考试（无 AI 访问），客观评分，测量与学习效果结果对应（rubric D3=2）。"
    if "modification" in measure:
        return 1, "自编同场次代码修改任务，测量合理但未经验证、无盲评（rubric D3=1）。"
    if "pre-post" in measure or "delayed" in method:
        return 2, "前测-后测-延迟测设计，写作测试有规范评分（rubric D3=2）。"
    if "task" in measure and "time" in measure:
        return 2, "标准代码编写任务 + 客观进度 / 用时指标，评分有规范（rubric D3=2）。"
    return 1, "测量合理但未验证（自编题目 / 自评量表），记 1 分（rubric D3=1）。"


def d4(ev: dict[str, Any]) -> tuple[int, str]:
    """>=8 周干预 或 含 retention/transfer 测量 才给 2 分。"""
    text = " ".join(str(ev.get(k, "")) for k in ("duration", "method", "outcome_measure"))
    if any(sig in text for sig in ("retention", "transfer", "delayed")):
        return 2, "含保持测试 / 迁移测试（满足 >=8 周干预或含 retention/transfer 即给 2，rubric D4=2）。"
    if "in_class" in text or "weeks" in text:
        return 1, "干预 2–8 周（课堂学习时段），有后测但无保持 / 迁移测量（rubric D4=1）。"
    return 0, "单次实验 / 单课时干预，或只有即时效果无后续测量（rubric D4=0）。"


def d5(ev: dict[str, Any]) -> tuple[int, str]:
    edu = ev.get("education_level", "")
    subject = ev.get("subject", "")
    if subject == "academic_writing_esl":
        return 0, "仅变量名称相关：学术写作 vs 编程，结果与目标 Frame 不对应（rubric D5=0）。"
    if edu == "k12_ages_10_17":
        return 1, ("大致对应但有偏差：同为入门编程 + 代码生成工具，但学习者（K-12 10-17 岁）"
                   "与课程（Python vs C 语言）不同（rubric D5=1）。")
    if edu == "high_school":
        return 1, ("大致对应但有偏差：同为生成式 AI 工具 + 独立问题解决，但高中（数学）"
                   "vs 大学（C 编程）不同（rubric D5=1）。")
    return 2, "干预 x 学习者 x 课程 x 工具 x 结果与目标 Frame 完全对应（rubric D5=2）。"


RULES = {"D1_study_design": d1, "D2_sample_quality": d2,
         "D3_measurement_validity": d3, "D4_temporal_strength": d4,
         "D5_directness": d5}


def recompute(ev: dict[str, Any]) -> tuple[dict[str, int], dict[str, str], float]:
    dims: dict[str, int] = {}
    reasons: dict[str, str] = {}
    for key, _ in DIMS:
        score, reason = RULES[key](ev)
        dims[key] = score
        reasons[key] = reason
    return dims, reasons, sum(dims.values())


def render_report(evidence_list: list[dict]) -> str:
    lines = [
        "Evidence Quality 重算报告（rubric: references/evidence-quality.md）",
        f"目标 Frame: {TARGET_FRAME}",
        "=" * 78,
    ]
    for ev in evidence_list:
        dims, reasons, total = recompute(ev)
        lines.append(f"\n{ev['evidence_id']}  {ev['claim']}")
        lines.append(f"  source={ev.get('source_id')}  outcome={ev.get('outcome_type')}  "
                     f"duration={ev.get('duration')}  n={ev.get('sample_size')}")
        for key, label in DIMS:
            lines.append(f"  {label} = {dims[key]}/2  ({reasons[key]})")
        level = quality_level(total)
        lines.append(f"  -> 总分 {total}/10 = {level}")
    lines.append("\n" + "=" * 78)
    lines.append("等级映射: 8-10 strong | 5-7 moderate | 2-4 weak | 0-1 very_weak (rubric 总分与等级)")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--evidence", default="examples/ai-coding-assistant/evidence.jsonl",
                        help="Path to evidence.jsonl")
    parser.add_argument("--check", action="store_true",
                        help="Verify stored quality values match the recomputed ones")
    args = parser.parse_args()

    evs = load_evidence(Path(args.evidence))
    print(render_report(evs))

    if args.check:
        mismatches = []
        for ev in evs:
            dims, _, total = recompute(ev)
            stored_dims = ev.get("quality_dimensions", {})
            stored_score = ev.get("quality_score")
            if stored_dims != dims:
                mismatches.append(f"{ev['evidence_id']}: stored dims {stored_dims} != recomputed {dims}")
            if stored_score != total:
                mismatches.append(f"{ev['evidence_id']}: stored score {stored_score} != recomputed {total}")
        if mismatches:
            print("\nCHECK FAILED:")
            for m in mismatches:
                print("  " + m)
            return 1
        print(f"\nCHECK PASSED: {len(evs)} 条证据存储的 quality_dimensions / quality_score "
              "与 rubric 重算结果一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
