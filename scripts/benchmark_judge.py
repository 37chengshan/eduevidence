#!/usr/bin/env python3
"""benchmark_judge.py - LLM judge evaluator for Layer B empirical runs (v3).

Runs an LLM judge (omp CLI, default model deepseek-v4-flash) over the
responses of an empirical run and scores every attempt on a 5-dimension
0-3 rubric, producing judge-evaluation.json next to the heuristic
evaluation.json. The report command renders judge-report.md with the
heuristic per_baseline metrics side by side.

Rubric dimensions (0-3, one-line rationale):
    citation_support       引用关键支持证据的可信度与具体性
    outcome_correctness    结局指标识别正确性（任务表现 != 学习效果）
    scope_calibration      结论边界限定是否恰当（不过度泛化）
    contradiction_handling 反方/负面/矛盾证据的识别与处理
    decision_calibration   最终决策动作与证据强度/期望决策范围的一致性

Independence caveat: the judge model is the same family as the execution
model (deepseek-v4-flash), so its review is NOT an independent third-party
judgement - it is reported as a semantic-complement view to the heuristic
(token-overlap) metrics, never as a standalone verdict.

Usage:
    python3 scripts/benchmark_judge.py run --run benchmarks/empirical/run-empirical-01 \
        --out benchmarks/empirical/judge-evaluation.json
    python3 scripts/benchmark_judge.py report --out benchmarks/empirical/judge-report.md

Budget control: --limit (default 60) caps how many completed attempts are
judged; attempts beyond the limit are recorded as "skipped". A failed model
call or unparseable judge output marks that attempt "failed" and continues.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark import load_questions  # noqa: E402
from benchmark_v3 import CliDriver, build_prompt  # noqa: E402,F401 (parity import per spec; judge uses build_judge_prompt)
from benchmark_evaluator import extract_json_block  # noqa: E402

JUDGE_DIMS = ("citation_support", "outcome_correctness", "scope_calibration",
              "contradiction_handling", "decision_calibration")
DEFAULT_JUDGE_MODEL = "deepseek-v4-flash"
DEFAULT_LIMIT = 60
HEURISTIC_METRICS = ("outcome_separation_accuracy", "decision_calibration",
                     "contradiction_recall", "contradiction_precision",
                     "citation_support_recall", "scope_calibration")

DIM_DESCRIPTIONS = {
    "citation_support": (
        "是否引用关键支持证据；来源标注是否具体可信（作者/年份/研究设计/效应量），"
        "是否把相关但非直接证据当作直接证据"),
    "outcome_correctness": (
        "是否正确识别题目对应的结局指标（如 accuracy / independent_problem_solving），"
        "是否混淆任务表现与学习效果（最高优先级）"),
    "scope_calibration": (
        "是否明确限定结论边界（能主张什么/不能主张什么/是否超出证据范围），"
        "是否过度泛化或把相关性说成因果"),
    "contradiction_handling": (
        "是否识别并恰当处理反方/负面/矛盾证据（null 结果、AI 依赖、迁移受损、新奇效应），"
        "冲突是否被强行裁决"),
    "decision_calibration": (
        "最终决策动作（adopt/pilot/reject/insufficient_evidence）是否与证据强度"
        "及期望决策范围一致"),
}

INDEPENDENCE_NOTE = (
    "judge 模型 deepseek-v4-flash 与执行模型同族（benchmark 运行环境 "
    "model_family=deepseek-v4-flash）。评审表达风格与执行模型同源，可能存在同族偏好，"
    "独立性受限：judge 结果不视为独立第三方评审，应与 heuristic 指标对照阅读。"
)

_OUTPUT_FORMAT = (
    "## 输出格式（严格 JSON，不要输出 JSON 以外的任何内容）\n"
    '{"citation_support": <0-3的整数>, "outcome_correctness": <0-3的整数>, '
    '"scope_calibration": <0-3的整数>, "contradiction_handling": <0-3的整数>, '
    '"decision_calibration": <0-3的整数>, '
    '"rationale": "一行中文理由，指出最关键的得/失分点"}\n'
)

RUBRIC_INTRO = (
    "你是 EduEvidence 实证基准的 LLM 评审员。请按 5 个维度，对下面的\"模型回答\"进行 "
    "0-3 评分（0=完全不符合/严重错误；1=部分符合但有明显缺陷；2=基本符合；3=完全符合），"
    "并给出一行中文理由。评审以\"参考答案要点（gold）\"为准绳：不要求回答逐字复述 gold，"
    "只判断实质符合程度；评分必须严格落在 0-3。\n"
)


# ---------------------------------------------------------------- prompt


def build_judge_prompt(question: dict, gold: dict, response: str) -> str:
    """Rubric prompt for one attempt: 题目 + gold 要点 + 模型回答 + 5 维 0-3 评分要求."""
    q_text = question.get("question", "")

    def _fmt(label: str, key: str) -> str | None:
        val = gold.get(key)
        if val is None:
            return None
        if isinstance(val, list):
            val = "; ".join(str(x) for x in val if str(x).strip())
        val = str(val).strip()
        return f"- {label}: {val}" if val else None

    gold_lines = [ln for ln in (
        _fmt("关键结论", "key_claims"),
        _fmt("正确结局指标", "correct_outcome_types"),
        _fmt("关键支持证据", "key_supporting_sources"),
        _fmt("已知反方/矛盾证据", "known_contradictions"),
        _fmt("允许的结论范围", "allowed_scope"),
        _fmt("期望决策范围", "expected_decision_range"),
        _fmt("已知方法学局限", "known_methodological_limitations"),
    ) if ln]
    gold_block = "\n".join(gold_lines) if gold_lines else "（无 gold 要点）"

    dim_lines = "\n".join(
        f"{i}. {dim} (0-3): {DIM_DESCRIPTIONS[dim]}"
        for i, dim in enumerate(JUDGE_DIMS, 1))

    return "\n".join([
        RUBRIC_INTRO,
        "## 题目",
        q_text,
        "",
        "## 参考答案要点（gold）",
        gold_block,
        "",
        "## 模型回答",
        response.strip() or "（空）",
        "",
        "## 评审维度",
        dim_lines,
        "",
        _OUTPUT_FORMAT,
    ])


# ---------------------------------------------------------------- parsing


def _coerce_score(value: Any) -> float | None:
    """Tolerant 0-3 score extraction: int/float, '2', '2/3', '2.5', '2.0/3'."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
    elif isinstance(value, str):
        s = value.strip()
        m = re.search(r"(-?\d+(?:\.\d+)?)\s*/\s*3", s, re.IGNORECASE)
        if m:
            v = float(m.group(1))
        else:
            m = re.search(r"(-?\d+(?:\.\d+)?)", s)
            if not m:
                return None
            v = float(m.group(1))
    else:
        return None
    if v != v:  # NaN
        return None
    return round(min(3.0, max(0.0, v)), 2)  # clamp out-of-range to 0-3


def parse_judge_output(text: str) -> dict[str, Any] | None:
    """Parse judge output into {'scores': {dim: float|None}, 'rationale': str|None}.

    Tries a JSON block first (preferred contract), then falls back to
    per-dimension line regexes. Missing dims stay None; if NO dim parses,
    returns None (caller marks the attempt failed).
    """
    text = (text or "").strip()
    if not text:
        return None
    scores: dict[str, float | None] = {}
    rationale: str | None = None

    data = extract_json_block(text)
    if isinstance(data, dict):
        for dim in JUDGE_DIMS:
            if dim in data:
                v = _coerce_score(data[dim])
                if v is not None:
                    scores[dim] = v
        r = data.get("rationale")
        if isinstance(r, str) and r.strip():
            rationale = r.strip()

    if len(scores) < len(JUDGE_DIMS):
        for dim in JUDGE_DIMS:
            if dim in scores:
                continue
            m = re.search(
                rf"{re.escape(dim)}\s*[:：=]\s*(\d+(?:\.\d+)?(?:\s*/\s*3)?)",
                text, re.IGNORECASE)
            if m:
                v = _coerce_score(m.group(1))
                if v is not None:
                    scores[dim] = v
        if rationale is None:
            m = re.search(r"(?:rationale|理由)\s*[:：=]\s*(.+)$", text,
                          re.IGNORECASE | re.MULTILINE)
            if m:
                cand = m.group(1).strip().strip('"').strip("'")
                if cand:
                    rationale = cand[:500]

    if not scores:
        return None
    for dim in JUDGE_DIMS:
        scores.setdefault(dim, None)
    return {"scores": scores, "rationale": rationale}


# ---------------------------------------------------------------- run


def load_golds(annotations_dir: Path) -> dict[str, dict[str, Any]]:
    golds: dict[str, dict[str, Any]] = {}
    for path in sorted(Path(annotations_dir).glob("gold-*.json")):
        g = json.loads(path.read_text(encoding="utf-8"))
        golds[g.get("id", path.stem.replace("gold-", ""))] = g
    return golds


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _per_baseline_means(per_attempt: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by: dict[str, list[dict[str, Any]]] = {}
    for row in per_attempt:
        if row.get("status") == "completed" and row.get("judge"):
            by.setdefault(row["baseline"], []).append(row)
    out: dict[str, dict[str, Any]] = {}
    for baseline, rows in by.items():
        means: dict[str, dict[str, Any]] = {}
        for dim in JUDGE_DIMS:
            values = [r["judge"].get(dim) for r in rows]
            values = [v for v in values if isinstance(v, (int, float))]
            # n=0 -> mean None (report renders "-"), never a misleading 0.0 (P2-4)
            entry: dict[str, Any] = {
                "mean": round(_mean(values), 4) if values else None,
                "n": len(values)}
            if values:
                entry["min"] = min(values)
                entry["max"] = max(values)
            means[dim] = entry
        out[baseline] = {"n": len(rows), "judge": means}
    return out


def run_judge(*, run_dir: Path, annotations_dir: Path, questions: list[dict],
              out_path: Path, driver: Any, limit: int | None = DEFAULT_LIMIT) -> dict[str, Any]:
    """Judge completed attempts of an empirical run; write judge-evaluation.json.

    Failed driver calls / unparseable outputs mark the attempt failed and
    never interrupt the run (P2-1 parity with benchmark_v3).
    """
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    golds = load_golds(annotations_dir)
    q_by_id = {q.get("id"): q for q in questions}
    model = getattr(driver, "model", DEFAULT_JUDGE_MODEL)

    per_attempt: list[dict[str, Any]] = []
    judged = 0
    for entry in manifest.get("attempts", []):
        if entry.get("status") != "completed":
            continue  # failed/budget_stopped attempts have no response to judge
        # tolerant field access: a malformed manifest row must degrade to
        # failed, never KeyError the whole run (review P2-3)
        aid = entry.get("attempt_id") or "unknown"
        row: dict[str, Any] = {
            "attempt_id": aid,
            "question_id": entry.get("question_id"),
            "baseline": entry.get("baseline"),
            "attempt": entry.get("attempt"),
            "status": "completed", "error": None, "judge": None, "usage": None,
        }
        if limit is not None and limit > 0 and judged >= limit:
            row["status"] = "skipped"
            per_attempt.append(row)
            continue
        judged += 1
        try:
            artifact_name = (entry.get("artifacts") or [None])[0]
            if not artifact_name:
                raise RuntimeError("no response artifact recorded")
            artifact = json.loads((run_dir / artifact_name).read_text(encoding="utf-8"))
            gold = golds.get(entry["question_id"])
            if not gold:
                raise RuntimeError(f"no gold annotation for {entry['question_id']}")
            question = q_by_id.get(entry["question_id"])
            if not question:
                raise RuntimeError(f"question {entry['question_id']} missing from questions file")
            response = (artifact.get("response") or "").strip()
            if not response:
                raise RuntimeError("empty response")

            prompt = build_judge_prompt(question, gold, response)
            text, usage = driver.call(prompt)
            parsed = parse_judge_output(text)
            if parsed is None:
                raise RuntimeError("judge output unparseable: " + (text or "")[:200])
            row["judge"] = {**parsed["scores"], "rationale": parsed["rationale"],
                            "method": "llm_judge", "raw": (text or "")[:800]}
            row["usage"] = usage
        except Exception as exc:  # noqa: BLE001 - one bad attempt must not kill the run
            row["status"] = "failed"
            row["error"] = str(exc)[:300]

        per_attempt.append(row)

    n_completed = sum(1 for r in per_attempt if r["status"] == "completed")
    n_failed = sum(1 for r in per_attempt if r["status"] == "failed")
    n_skipped = sum(1 for r in per_attempt if r["status"] == "skipped")
    summary = {
        "run_id": manifest.get("run_id"),
        "run_dir": str(run_dir),
        "judge": {
            "driver": getattr(driver, "name", "cli"),
            "model": model,
            "temperature": getattr(driver, "temperature", 0.0),
            "scale": "0-3",
            "dims": list(JUDGE_DIMS),
            "independence_note": INDEPENDENCE_NOTE,
        },
        "heuristic_evaluation": str(run_dir / "evaluation.json"),
        "limit": limit,
        "summary": {"attempts_total": len(per_attempt),
                    "completed": n_completed, "failed": n_failed, "skipped": n_skipped},
        "per_attempt": per_attempt,
        "per_baseline": _per_baseline_means(per_attempt),
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"wrote {out_path} (judged={n_completed}, failed={n_failed}, "
          f"skipped={n_skipped}, judge_model={model})")
    return summary


# ---------------------------------------------------------------- report


def render_report(eval_data: dict[str, Any], heuristic_data: dict[str, Any],
                  out_path: Path) -> str:
    """Side-by-side judge (0-3) vs heuristic (0-1) report, with the
    independence limitation statement."""
    judge_meta = eval_data.get("judge", {})
    model = judge_meta.get("model", DEFAULT_JUDGE_MODEL)
    per_baseline = eval_data.get("per_baseline", {})
    heur_pb = heuristic_data.get("per_baseline", {})
    run_dir = eval_data.get("run_dir", "?")
    summary = eval_data.get("summary", {})
    lines = [
        "# LLM Judge 评估报告",
        "",
        f"- run_id: {eval_data.get('run_id')}",
        f"- judge 模型: **{model}**（{judge_meta.get('driver', 'cli')} driver, "
        f"scale 0-3，3=完全符合）",
        f"- 对照来源: {eval_data.get('heuristic_evaluation', str(Path(run_dir) / 'evaluation.json'))} "
        f"（method:heuristic，0-1）",
        f"- attempts: judged={summary.get('completed')}, failed={summary.get('failed')}, "
        f"skipped={summary.get('skipped')}, limit={eval_data.get('limit')}",
        "",
        f"> ⚠️ **独立性受限声明**: {INDEPENDENCE_NOTE}",
        "",
        "## 对照表（每 baseline：judge 均值(0-3) vs heuristic 均值(0-1)，并排展示）",
        "",
        "| Baseline | n | J citation | H cit_recall | J outcome | H out_sep | "
        "J scope | H scope | J contra | H contra_recall | J decision | H decision |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for baseline in sorted(set(per_baseline) | set(heur_pb)):
        j = per_baseline.get(baseline, {}).get("judge", {})
        h = heur_pb.get(baseline, {}).get("metrics", {})
        n = per_baseline.get(baseline, {}).get("n", heur_pb.get(baseline, {}).get("n", 0))

        def jm(dim: str) -> str:
            m = j.get(dim, {}).get("mean")
            return f"{m:.3f}" if isinstance(m, (int, float)) else "-"

        def hm(metric: str) -> str:
            m = h.get(metric, {}).get("mean")
            return f"{m:.3f}" if isinstance(m, (int, float)) else "-"

        lines.append(
            f"| {baseline} | {n} | {jm('citation_support')} | {hm('citation_support_recall')} "
            f"| {jm('outcome_correctness')} | {hm('outcome_separation_accuracy')} "
            f"| {jm('scope_calibration')} | {hm('scope_calibration')} "
            f"| {jm('contradiction_handling')} | {hm('contradiction_recall')} "
            f"| {jm('decision_calibration')} | {hm('decision_calibration')} |")

    lines += [
        "",
        "## 维度对应说明",
        "- judge citation_support ↔ heuristic citation_support_recall",
        "- judge outcome_correctness ↔ heuristic outcome_separation_accuracy",
        "- judge scope_calibration ↔ heuristic scope_calibration",
        "- judge contradiction_handling ↔ heuristic contradiction_recall / contradiction_precision",
        "- judge decision_calibration ↔ heuristic decision_calibration",
        "- judge 为语义符合度（0-3），heuristic 为确定性 token 匹配（0-1），尺度不同不可直接相减。",
        "",
        "## 一致性摘要",
    ]
    for baseline in sorted(per_baseline):
        j = per_baseline[baseline].get("judge", {})
        j_vals = [j[d]["mean"] for d in JUDGE_DIMS
                  if isinstance(j.get(d, {}).get("mean"), (int, float))]
        h = heur_pb.get(baseline, {}).get("metrics", {})
        h_vals = [h[k]["mean"] for k in HEURISTIC_METRICS
                  if isinstance(h.get(k, {}).get("mean"), (int, float))]
        j_avg = _mean(j_vals) if j_vals else 0.0
        h_avg = _mean(h_vals) if h_vals else 0.0
        if j_vals:
            best = max(JUDGE_DIMS, key=lambda d: j.get(d, {}).get("mean", -1))
            worst = min(JUDGE_DIMS, key=lambda d: j.get(d, {}).get("mean", 4))
            lines.append(
                f"- **{baseline}**: judge 五维均值 **{j_avg:.3f}/3.0**，"
                f"heuristic 六指标均值 {h_avg:.3f}/1.0；judge 最高分维度 "
                f"{best}，最低分维度 {worst}。")
        else:
            lines.append(f"- **{baseline}**: 无有效 judge 结果（attempt 全部失败）。")
    lines.append(
        "- 判读：judge 与 heuristic 是互补视角；若某维度 judge 高分而 heuristic 低分，"
        "提示启发式漏检或 judge 同族偏好，建议人工抽查该维度样本。")

    lines += ["", "## 逐 attempt"]
    lines.append(
        "| attempt_id | baseline | status | citation | outcome | scope | contra | "
        "decision | rationale |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for row in eval_data.get("per_attempt", []):
        j = row.get("judge") or {}
        rationale = (j.get("rationale") or "").replace("|", "\\|")
        if len(rationale) > 80:
            rationale = rationale[:80] + "…"
        status = row.get("status", "?")
        if status != "completed":
            err = (row.get("error") or "")[:40].replace("|", "\\|")
            lines.append(f"| {row['attempt_id']} | {row.get('baseline')} | {status} "
                         f"| - | - | - | - | - | {err} |")
            continue
        lines.append(
            f"| {row['attempt_id']} | {row.get('baseline')} | completed "
            f"| {j.get('citation_support', '-')} | {j.get('outcome_correctness', '-')} "
            f"| {j.get('scope_calibration', '-')} | {j.get('contradiction_handling', '-')} "
            f"| {j.get('decision_calibration', '-')} | {rationale} |")

    markdown = "\n".join(lines) + "\n"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    return markdown


# ---------------------------------------------------------------- cli


def _cmd_run(args: argparse.Namespace) -> int:
    run_dir = Path(args.run)
    if not (run_dir / "manifest.json").is_file():
        print(f"no manifest.json in {run_dir}", file=sys.stderr)
        return 2
    driver = CliDriver(model=args.model, thinking=args.thinking)
    if not driver.available():
        print("cli driver unavailable: 'omp' not found on PATH", file=sys.stderr)
        return 2
    questions = load_questions(Path(args.questions))
    out_path = Path(args.out) if args.out else run_dir / "judge-evaluation.json"
    run_judge(run_dir=run_dir, annotations_dir=Path(args.annotations),
              questions=questions, out_path=out_path, driver=driver,
              limit=args.limit)
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    out_path = Path(args.out)
    eval_path = (Path(args.evaluation) if args.evaluation
                 else out_path.parent / "judge-evaluation.json")
    if not eval_path.is_file():
        print(f"no judge evaluation at {eval_path} (run the run command first, or pass --evaluation)",
              file=sys.stderr)
        return 2
    eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
    run_dir = Path(args.run) if args.run else Path(eval_data.get("run_dir", "."))
    heur_path = run_dir / "evaluation.json"
    if not heur_path.is_file():
        print(f"no heuristic evaluation at {heur_path} (expected run_dir/evaluation.json)",
              file=sys.stderr)
        return 2
    heuristic_data = json.loads(heur_path.read_text(encoding="utf-8"))
    render_report(eval_data, heuristic_data, out_path)
    print(f"wrote {out_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="EduEvidence LLM judge evaluator (omp CLI, deepseek-v4-flash)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="judge the responses of an empirical run")
    p_run.add_argument("--run", required=True, help="run directory with manifest.json")
    p_run.add_argument("--out", default=None,
                       help="judge-evaluation.json path (default: <run>/judge-evaluation.json)")
    p_run.add_argument("--questions", default="benchmarks/questions.jsonl")
    p_run.add_argument("--annotations", default="benchmarks/annotations")
    p_run.add_argument("--model", default=DEFAULT_JUDGE_MODEL)
    p_run.add_argument("--thinking", default="minimal")
    p_run.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                       help="max completed attempts to judge (default 60; <=0 = unlimited)")
    p_run.set_defaults(func=_cmd_run)

    p_report = sub.add_parser("report", help="render judge-report.md vs heuristic metrics")
    p_report.add_argument("--out", required=True)
    p_report.add_argument("--evaluation", default=None,
                          help="judge-evaluation.json (default: <out dir>/judge-evaluation.json)")
    p_report.add_argument("--run", default=None,
                          help="override run dir for heuristic evaluation.json")
    p_report.set_defaults(func=_cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
