#!/usr/bin/env python3
"""benchmark_v3.py — Layer B Empirical Benchmark harness (v3).

Runs B0-B4 baselines over benchmarks/questions.jsonl with REAL model calls and
records a full run manifest (schemas/v3/run-manifest.schema.json). The
deterministic simulation (benchmark_v2) remains only as harness validation and
is always labelled SIMULATED — empirical numbers are the only performance
evidence (docs/benchmark.md Layer A vs Layer B).

Baselines:
    B0_direct_llm           直接问模型，无检索无协议
    B1_search_llm           一次搜索再回答（驱动不支持真实搜索时降级并如实记录）
    B2_standard_agent       有检索无教育协议
    B3_eduevidence_single   完整 EvidenceFlow 单 Agent（精简协议）
    B4_eduevidence_agent_mcp 增强模式（API 驱动下如实标注 agent_mcp_used=false）

Drivers:
    api   OpenAI-compatible chat completions
          env: EDUEVIDENCE_LLM_API_KEY / EDUEVIDENCE_LLM_BASE_URL / EDUEVIDENCE_LLM_MODEL
    sim   deterministic simulation (SIMULATED) — harness validation only

Usage:
    python3 scripts/benchmark_v3.py run --baselines B2_standard_agent,B3_eduevidence_single \
        --questions benchmarks/questions.jsonl --annotations benchmarks/annotations \
        --repeats 3 --out benchmarks/empirical/run-20260813-120000
    python3 scripts/benchmark_v3.py eval --run benchmarks/empirical/run-20260813-120000
    python3 scripts/benchmark_v3.py report --run benchmarks/empirical/run-20260813-120000
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark import load_questions, validate_questions  # noqa: E402

BASELINES = (
    "B0_direct_llm", "B1_search_llm", "B2_standard_agent",
    "B3_eduevidence_single", "B4_eduevidence_agent_mcp",
)
LEVEL_N_CLAIMS = {"S": 2, "M": 3, "L": 4}
DEFAULT_BUDGET_TOKENS = 1_000_000

# ---------------------------------------------------------------- prompts


def _prompt_b0(q: dict) -> str:
    return (
        "请直接回答以下教育决策问题，给出明确结论（采用/试点/拒绝/证据不足）和理由。\n\n"
        f"问题：{q['question']}\n"
    )


def _prompt_b1(q: dict) -> str:
    return (
        "请先使用可用检索工具搜索相关研究证据，再基于搜索结果回答以下教育决策问题，"
        "给出明确结论（采用/试点/拒绝/证据不足）并引用来源。\n\n"
        f"问题：{q['question']}\n"
    )


def _prompt_b2(q: dict) -> str:
    return (
        "你是研究助理。请检索并分析相关文献，然后回答以下教育决策问题。"
        "必须：列出支持与反对的证据并标注来源；评估证据质量；给出结论（采用/试点/拒绝/证据不足）。\n\n"
        f"问题：{q['question']}\n"
    )


_PROTOCOL_B3 = (
    "你是 EduEvidence 教育证据决策引擎（单 Agent 完整协议）。对问题执行：\n"
    "1) Frame：确定学习者/干预/对照/目标结果（结果必须使用枚举：knowledge_gain, concept_understanding, "
    "retention, transfer, independent_problem_solving, completion_time, accuracy, code_quality, "
    "assignment_score, engagement, motivation, cognitive_load, help_seeking, metacognition, ai_dependency, "
    "over_reliance, reduced_effort, reduced_transfer, academic_integrity_risk, false_confidence）；\n"
    "2) 检索支持证据与独立反方证据（null/negative result、AI 依赖、迁移受损、新奇效应）；\n"
    "3) 方法学审查（任务完成表现 ≠ 学习效果，最高优先级）；\n"
    "4) 证据裁决（支持/反驳/中性分开；冲突不强行裁决）；\n"
    "5) 结论边界（能主张什么/不能主张什么/是否超出证据范围）；\n"
    "6) 决策动作（adopt / pilot / reject / insufficient_evidence）。\n"
    "严格区分：任务表现提升 ≠ 学习效果提升。"
)


def _prompt_b3(q: dict) -> str:
    return (
        _PROTOCOL_B3 + "\n\n" + f"问题：{q['question']}\n" +
        "\n请以 JSON 输出：{\"frame\": {...}, \"claims\": [{\"claim\": ..., \"outcome_type\": ..., "
        "\"direction\": \"support|contradict|neutral\", \"source\": ...}], \"contradictions\": [...], "
        "\"scope\": {\"can_claim\": [...], \"cannot_claim\": [...], \"exceeds_boundary\": [...]}, "
        "\"recommended_action\": \"adopt|pilot|reject|insufficient_evidence\", "
        "\"confidence\": \"High|Moderate|Low|Insufficient\"}\n"
    )


def _prompt_b4(q: dict) -> str:
    return (
        _PROTOCOL_B3 + "\n" +
        "（增强模式：检索者、反证挑战者、方法学审查者、证据裁决者由独立上下文分别执行并交叉复核。）\n\n"
        + f"问题：{q['question']}\n" +
        "\n请以 JSON 输出：{\"frame\": {...}, \"claims\": [...], \"contradictions\": [...], "
        "\"scope\": {...}, \"recommended_action\": ..., \"confidence\": ..., "
        "\"cross_review\": {\"agreement\": \"agree|disagree\", \"final_recommendation\": ...}}\n"
    )


def build_prompt(baseline: str, q: dict) -> str:
    fn = {"B0_direct_llm": _prompt_b0, "B1_search_llm": _prompt_b1,
          "B2_standard_agent": _prompt_b2, "B3_eduevidence_single": _prompt_b3,
          "B4_eduevidence_agent_mcp": _prompt_b4}[baseline]
    return fn(q)


# ---------------------------------------------------------------- drivers


class ApiDriver:
    """OpenAI-compatible chat completions driver (no SDK dependency)."""

    name = "api"

    def __init__(self, *, model: str | None = None,
                 base_url: str | None = None, api_key: str | None = None,
                 temperature: float = 0.0, timeout: int = 180):
        self.model = model or os.environ.get("EDUEVIDENCE_LLM_MODEL", "")
        self.base_url = (base_url or os.environ.get("EDUEVIDENCE_LLM_BASE_URL", "")
                         or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or os.environ.get("EDUEVIDENCE_LLM_API_KEY", "")
        self.temperature = temperature
        self.timeout = timeout

    def available(self) -> bool:
        return bool(self.model and self.api_key)

    def call(self, prompt: str) -> tuple[str, dict[str, Any]]:
        import time
        t0 = time.monotonic()
        body = json.dumps({
            "model": self.model,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 (user-configured endpoint)
            payload = json.loads(resp.read().decode("utf-8"))
        usage = payload.get("usage") or {}
        text = (payload.get("choices") or [{}])[0].get("message", {}).get("content", "")
        latency = time.monotonic() - t0
        usage_out = {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "latency_s": round(latency, 2),
        }
        return text, usage_out


class SimDriver:
    """Deterministic simulation — harness validation ONLY. Never performance evidence."""

    name = "sim"

    def __init__(self, temperature: float = 0.0):
        self.temperature = temperature

    def available(self) -> bool:
        return True

    def call(self, prompt: str) -> tuple[str, dict[str, Any]]:
        from benchmark_v2 import simulate_question_result  # noqa: PLC0415

        # Deterministic pseudo-usage from prompt length; response is a stub
        # that the evaluator must never use as model performance.
        import random
        rng = random.Random(len(prompt) * 7919 % 2**31)
        usage = {
            "prompt_tokens": len(prompt) // 4,
            "completion_tokens": 300 + rng.randint(0, 200),
            "latency_s": round(0.01 + rng.random() * 0.05, 3),
        }
        return (
            '{"claims": [], "contradictions": [], "scope": {"can_claim": [], '
            '"cannot_claim": [], "exceeds_boundary": []}, '
            '"recommended_action": "insufficient_evidence", '
            '"confidence": "Insufficient", "simulated": true}',
            usage,
        )


def make_driver(name: str) -> Any:
    if name == "api":
        return ApiDriver()
    if name == "sim":
        return SimDriver()
    raise ValueError(f"unknown driver: {name}")


# ---------------------------------------------------------------- run


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_benchmark(*, questions: list[dict], baselines: list[str], repeats: int,
                  out_dir: Path, driver_name: str, budget_tokens: int | None,
                  temperature: float = 0.0) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    driver = make_driver(driver_name)
    if not driver.available():
        raise RuntimeError(
            f"driver '{driver_name}' unavailable (api needs EDUEVIDENCE_LLM_MODEL "
            "and EDUEVIDENCE_LLM_API_KEY)")

    run_id = "run-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "run_mode": "simulated" if driver_name == "sim" else "empirical",
        "created_at": _now_iso(),
        "questions_version": _questions_version(),
        "baselines": list(baselines),
        "repeats": repeats,
        "budget_tokens": budget_tokens,
        "environment": {
            "driver": driver.name,
            "model_family": getattr(driver, "model", "sim") or "unknown",
            "model_version": getattr(driver, "model", "sim") or "unknown",
            "temperature": temperature,
            "tools": [],
            "search_provider": "none" if driver_name == "sim" else "host_tool",
            "agent_mcp_used": False,
        },
        "attempts": [],
        "notes": ("SIMULATED: harness validation only, not model performance" if driver_name == "sim"
                  else "empirical run; see per-attempt artifacts"),
    }

    total_tokens = 0
    budget_stopped = False
    for question in questions:
        if budget_stopped:
            break
        for baseline in baselines:
            for attempt in range(1, repeats + 1):
                if budget_stopped:
                    break
                attempt_id = f"{question['id']}-{baseline}-a{attempt}"
                started = _now_iso()
                entry: dict[str, Any] = {
                    "attempt_id": attempt_id,
                    "question_id": question["id"],
                    "baseline": baseline,
                    "attempt": attempt,
                    "status": "completed",
                    "error": None,
                    "started_at": started,
                    "finished_at": None,
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "latency_s": None,
                    "cost_usd": None,
                    "artifacts": [],
                }
                try:
                    prompt = build_prompt(baseline, question)
                    text, usage = driver.call(prompt)
                    entry.update({
                        "finished_at": _now_iso(),
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                        "latency_s": usage.get("latency_s"),
                    })
                    pt = usage.get("prompt_tokens") or 0
                    ct = usage.get("completion_tokens") or 0
                    total_tokens += pt + ct
                    artifact = out_dir / f"{attempt_id}.response.json"
                    artifact.write_text(json.dumps({
                        "attempt_id": attempt_id,
                        "prompt": prompt,
                        "response": text,
                        "usage": usage,
                    }, ensure_ascii=False, indent=2), encoding="utf-8")
                    entry["artifacts"] = [artifact.name]
                except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
                    entry.update({"status": "failed", "error": str(exc),
                                  "finished_at": _now_iso()})
                manifest["attempts"].append(entry)

                if budget_tokens is not None and total_tokens >= budget_tokens:
                    budget_stopped = True
                    manifest["notes"] = (manifest["notes"] + " BUDGET STOPPED at "
                                         f"{total_tokens} tokens.")
                    break

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    _validate_manifest(manifest_path)
    print(f"wrote {manifest_path} (attempts={len(manifest['attempts'])}, "
          f"mode={manifest['run_mode']}, total_tokens~{total_tokens})")
    return manifest


def _questions_version() -> str:
    try:
        out = os.popen("git -C . rev-parse --short HEAD 2>/dev/null").read().strip()
        return out or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def _validate_manifest(path: Path) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from validate_schema import Validator, SchemaError  # noqa: PLC0415

    import json as _json
    schema = _json.loads(
        (Path(__file__).resolve().parent.parent / "schemas" / "v3"
         / "run-manifest.schema.json").read_text(encoding="utf-8"))
    data = _json.loads(path.read_text(encoding="utf-8"))
    try:
        Validator(schema).validate(data, schema, "$")
    except SchemaError as exc:
        raise ValueError(f"manifest failed schema validation: {exc}") from exc


def _cmd_run(args: argparse.Namespace) -> int:
    questions = load_questions(Path(args.questions))
    errors = validate_questions(questions)
    if errors:
        print("invalid questions:", errors, file=sys.stderr)
        return 2
    baselines = [b for b in BASELINES if b in args.baselines.split(",")]
    if not baselines:
        print(f"--baselines must be a subset of {BASELINES}", file=sys.stderr)
        return 2
    run_benchmark(
        questions=[q for q in questions if q["id"] in (args.ids.split(",") if args.ids else
                                                       [q["id"] for q in questions])],
        baselines=baselines, repeats=args.repeats,
        out_dir=Path(args.out), driver_name=args.driver,
        budget_tokens=args.budget_tokens, temperature=args.temperature)
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from benchmark_evaluator import report_from_run  # noqa: PLC0415

    run_dir = Path(args.run)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    markdown = report_from_run(run_dir, manifest, Path(args.out))
    print(markdown if args.stdout else f"wrote {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EduEvidence Layer B empirical benchmark (v3)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run baselines and write a manifest")
    p_run.add_argument("--baselines", required=True,
                       help="comma-separated subset of " + ",".join(BASELINES))
    p_run.add_argument("--questions", default="benchmarks/questions.jsonl")
    p_run.add_argument("--ids", default=None, help="comma-separated question ids to run")
    p_run.add_argument("--repeats", type=int, default=3)
    p_run.add_argument("--driver", choices=["api", "sim"], default=None,
                       help="api (needs env keys) or sim (harness validation only)")
    p_run.add_argument("--out", required=True)
    p_run.add_argument("--budget-tokens", type=int, default=DEFAULT_BUDGET_TOKENS)
    p_run.add_argument("--temperature", type=float, default=0.0)
    p_run.set_defaults(func=_cmd_run)

    p_eval = sub.add_parser("eval", help="evaluate a run against gold annotations")
    p_eval.add_argument("--run", required=True)
    p_eval.add_argument("--annotations", default="benchmarks/annotations")
    p_eval.add_argument("--out", default=None)
    p_eval.set_defaults(func=_cmd_eval)

    p_report = sub.add_parser("report", help="render the empirical benchmark report (markdown)")
    p_report.add_argument("--run", required=True)
    p_report.add_argument("--out", required=True)
    p_report.add_argument("--stdout", action="store_true")
    p_report.set_defaults(func=_cmd_report)

    args = parser.parse_args(argv)
    if args.driver is None:
        args.driver = "api" if ApiDriver().available() else "sim"
    return args.func(args)


def _cmd_eval(args: argparse.Namespace) -> int:
    from benchmark_evaluator import evaluate_run  # noqa: PLC0415

    run_dir = Path(args.run)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    summary = evaluate_run(run_dir, manifest, Path(args.annotations))
    out_path = Path(args.out) if args.out else run_dir / "evaluation.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
