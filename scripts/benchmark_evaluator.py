#!/usr/bin/env python3
"""benchmark_evaluator.py - gold-based evaluator for Layer B empirical runs (v3).

Metrics are computed against gold annotations (benchmarks/annotations/gold-<id>.json),
never against the model's own claims:

    outcome_separation_accuracy   Jaccard(response outcomes, gold correct_outcome_types)
    decision_calibration          1 if response action in gold expected_decision_range else 0
    contradiction_recall          fraction of gold known_contradictions detected in response
    contradiction_precision       fraction of response contradiction units that match a gold item
    citation_support_recall       fraction of gold key_supporting_sources mentioned in response
    scope_calibration             1 if response scope section bounds claims (can/cannot/boundary)

Matching is deterministic token-overlap (CJK bigram + word) - no LLM judge is
required; method:heuristic is recorded on every metric so the report never
overstates precision. Means are reported with a normal-approximation 95% CI.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark import OUTCOME_SET  # noqa: E402

ACTION_TOKENS = ("adopt", "pilot", "reject", "insufficient_evidence")
ACTION_ZH = {"adopt": "采用", "pilot": "试点", "reject": "拒绝",
             "insufficient_evidence": "证据不足"}
SCOPE_BOUNDARY_MARKERS = ("不能主张", "不能", "不适用", "范围", "超出", "仅限",
                          "cannot", "not extend", "beyond", "boundary", "only",
                          "不扩展到", "不推断")
CONTRADICTION_HINT = (
    "contradict", "negative", "null", "但", "然而", "未发现", "没有显著", "下降",
    "负向", "不一致", "反方", "however", "no significant", "did not",
)

_ID_RE = re.compile(r"\b([A-Za-z][A-Za-z-]{1,40})\b")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _cjk_bigrams(text: str) -> set[str]:
    chars = [c for c in text if "\u4e00" <= c <= "\u9fff"]
    return {chars[i] + chars[i + 1] for i in range(len(chars) - 1)}


def _words(text: str) -> set[str]:
    return {w.lower() for w in _ID_RE.findall(text) if len(w) > 2}


def _tokenize(text: str) -> set[str]:
    return _cjk_bigrams(text) | _words(text)


def _overlap(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, min(len(ta), len(tb)))


def extract_json_block(text: str) -> dict[str, Any] | None:
    """Best-effort JSON extraction (first balanced {...} block)."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                block = text[start:i + 1]
                try:
                    data = json.loads(block)
                    return data if isinstance(data, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def _flatten(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        return " ".join(_flatten(x) for x in obj)
    if isinstance(obj, dict):
        return " ".join(_flatten(v) for v in obj.values())
    return str(obj)


def extract_outcomes(text: str) -> set[str]:
    found = {o for o in OUTCOME_SET if o in text}
    data = extract_json_block(text)
    if data:
        for c in data.get("claims") or []:
            ot = (c or {}).get("outcome_type")
            if ot in OUTCOME_SET:
                found.add(ot)
    return found


def extract_action(text: str) -> str | None:
    data = extract_json_block(text)
    if data:
        for key in ("recommended_action", "final_recommendation", "decision"):
            val = data.get(key)
            if isinstance(val, str) and val in ACTION_TOKENS:
                return val
    low = text.lower()
    for token in ACTION_TOKENS:
        if token in low:
            return token
    for token, zh in ACTION_ZH.items():
        if zh in text:
            return token
    return None


def _split_contradiction_units(text: str) -> list[str]:
    """Heuristic units: JSON contradictions list, else hint sentences."""
    data = extract_json_block(text)
    if data:
        for key in ("contradictions", "contradictory_evidence", "risks"):
            val = data.get(key)
            if isinstance(val, list):
                units = [_flatten(x).strip() for x in val]
                if any(units):
                    return [u for u in units if u]
    sentences = re.split(r"[。！？!?；;\n]", text)
    return [s.strip() for s in sentences
            if s.strip() and any(h in s.lower() for h in CONTRADICTION_HINT)]


def _mentions_source(resp_text: str, gold_source: str) -> bool:
    """Does the response plausibly cite this gold source? Heuristic: strong
    token overlap with the source string, or author name + year co-occurrence."""
    if _overlap(resp_text, gold_source) >= 0.5:
        return True
    years = _YEAR_RE.findall(gold_source)
    names = [w for w in _words(gold_source) if w not in ("the", "and", "et", "al", "study")]
    if names and years:
        return any(n in resp_text.lower() for n in names) and any(y in resp_text for y in years)
    return False


def evaluate_attempt(response_text: str, gold: dict[str, Any]) -> dict[str, Any]:
    resp = response_text or ""
    gold_outcomes = set(gold.get("correct_outcome_types") or [])
    resp_outcomes = extract_outcomes(resp)
    if gold_outcomes:
        outcome_jaccard = len(gold_outcomes & resp_outcomes) / max(
            1, len(gold_outcomes | resp_outcomes))
    else:
        outcome_jaccard = 1.0 if not resp_outcomes else 0.0

    action = extract_action(resp)
    decision_ok = action in set(gold.get("expected_decision_range") or [])

    gold_contra = [str(x) for x in (gold.get("known_contradictions") or []) if str(x).strip()]
    resp_units = _split_contradiction_units(resp)
    detected = [g for g in gold_contra if any(_overlap(u, g) >= 0.35 for u in resp_units)]
    contra_recall = len(detected) / len(gold_contra) if gold_contra else 1.0
    contra_precision = (
        sum(1 for u in resp_units if any(_overlap(u, g) >= 0.35 for g in gold_contra))
        / len(resp_units) if resp_units else 1.0)

    gold_sources = [str(x) for x in (gold.get("key_supporting_sources") or []) if str(x).strip()]
    cited = [s for s in gold_sources if _mentions_source(resp, s)]
    citation_recall = len(cited) / len(gold_sources) if gold_sources else 1.0

    scope_text = resp.lower()
    scope_ok = any(m in scope_text for m in SCOPE_BOUNDARY_MARKERS)

    return {
        "outcome_separation_accuracy": round(outcome_jaccard, 4),
        "decision_calibration": 1.0 if decision_ok else 0.0,
        "contradiction_recall": round(contra_recall, 4),
        "contradiction_precision": round(contra_precision, 4),
        "citation_support_recall": round(citation_recall, 4),
        "scope_calibration": 1.0 if scope_ok else 0.0,
        "detected_outcomes": sorted(resp_outcomes),
        "detected_action": action,
        "method": "heuristic",
    }


METRIC_KEYS = ("outcome_separation_accuracy", "decision_calibration",
               "contradiction_recall", "contradiction_precision",
               "citation_support_recall", "scope_calibration")


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _ci95(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    m = _mean(values)
    sd = math.sqrt(sum((v - m) ** 2 for v in values) / (n - 1))
    return 1.96 * sd / math.sqrt(n)


def evaluate_run(run_dir: Path, manifest: dict[str, Any], annotations_dir: Path) -> dict[str, Any]:
    golds: dict[str, dict[str, Any]] = {}
    for path in sorted(Path(annotations_dir).glob("gold-*.json")):
        g = json.loads(path.read_text(encoding="utf-8"))
        golds[g.get("id", path.stem.replace("gold-", ""))] = g

    per_attempt: list[dict[str, Any]] = []
    for entry in manifest.get("attempts", []):
        row = {"attempt_id": entry["attempt_id"], "question_id": entry["question_id"],
               "baseline": entry["baseline"], "attempt": entry["attempt"],
               "status": entry["status"]}
        if entry["status"] != "completed":
            per_attempt.append(row)
            continue
        artifact_name = (entry.get("artifacts") or [None])[0]
        if not artifact_name:
            per_attempt.append(row)
            continue
        artifact = json.loads((run_dir / artifact_name).read_text(encoding="utf-8"))
        gold = golds.get(entry["question_id"])
        if not gold:
            row["metrics"] = None
            row["error"] = "no gold annotation"
            per_attempt.append(row)
            continue
        metrics = evaluate_attempt(artifact.get("response", ""), gold)
        row["metrics"] = {k: metrics[k] for k in METRIC_KEYS}
        row["detected_action"] = metrics["detected_action"]
        row["cost_usd"] = entry.get("cost_usd")
        per_attempt.append(row)

    by_baseline: dict[str, list[dict[str, Any]]] = {}
    for row in per_attempt:
        if row["status"] == "completed" and row.get("metrics"):
            by_baseline.setdefault(row["baseline"], []).append(row)

    per_baseline: dict[str, dict[str, Any]] = {}
    for baseline, rows in by_baseline.items():
        metrics: dict[str, dict[str, float]] = {}
        for key in METRIC_KEYS:
            values = [r["metrics"][key] for r in rows]
            metrics[key] = {"mean": round(_mean(values), 4),
                            "ci95": round(_ci95(values), 4), "n": len(values)}
        per_baseline[baseline] = {
            "metrics": metrics,
            "n": len(rows),
            "total_cost_usd": round(sum(r.get("cost_usd") or 0.0 for r in rows), 4),
        }

    return {
        "run_id": manifest.get("run_id"),
        "run_mode": manifest.get("run_mode"),
        "environment": manifest.get("environment"),
        "per_baseline": per_baseline,
        "per_attempt": per_attempt,
    }


def report_from_run(run_dir: Path, manifest: dict[str, Any], out_path: Path) -> str:
    """Render the empirical benchmark report. The header states the run mode
    explicitly so SIMULATED data can never be read as real performance."""
    eval_path = run_dir / "evaluation.json"
    if eval_path.is_file():
        summary = json.loads(eval_path.read_text(encoding="utf-8"))
    else:
        summary = evaluate_run(run_dir, manifest, run_dir.parent.parent / "annotations")

    mode = summary.get("run_mode", "unknown")
    env = summary.get("environment", {}) or {}
    attempts = manifest.get("attempts", [])
    n_failed = sum(1 for a in attempts if a.get("status") == "failed")
    n_budget = sum(1 for a in attempts if a.get("status") == "budget_stopped")
    notes = manifest.get("notes") or ""
    lines = [
        "# EduEvidence Benchmark Report (v3)",
        "",
        f"- run_id: {summary.get('run_id')}",
        f"- mode: **{'SIMULATED - harness validation only, NOT model performance' if mode == 'simulated' else 'EMPIRICAL'}**",
        f"- driver: {env.get('driver')} | model: {env.get('model_family')} "
        f"({env.get('model_version')}) | temperature: {env.get('temperature')}",
        f"- tools: {', '.join(env.get('tools') or []) or 'none'} | "
        f"search_provider: {env.get('search_provider')} | agent_mcp_used: {env.get('agent_mcp_used')}",
        f"- attempts: {len(attempts)} total | failed: {n_failed} | budget_stopped: {n_budget}",
        f"- notes: {notes or 'none'}",
        "- cost: usage not metered by the cli/api driver (reported as 0.0 = NOT CAPTURED, not free)",
        "",
        "| Baseline | n | outcome_sep | decision_cal | contra_recall | contra_precision | citation_recall | scope_cal | cost_usd |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for baseline in sorted(summary.get("per_baseline", {})):
        m = summary["per_baseline"][baseline]["metrics"]
        line = (f"| {baseline} | {m['outcome_separation_accuracy']['n']} "
                f"| {m['outcome_separation_accuracy']['mean']:.3f}+-{m['outcome_separation_accuracy']['ci95']:.3f} "
                f"| {m['decision_calibration']['mean']:.3f}+-{m['decision_calibration']['ci95']:.3f} "
                f"| {m['contradiction_recall']['mean']:.3f}+-{m['contradiction_recall']['ci95']:.3f} "
                f"| {m['contradiction_precision']['mean']:.3f}+-{m['contradiction_precision']['ci95']:.3f} "
                f"| {m['citation_support_recall']['mean']:.3f}+-{m['citation_support_recall']['ci95']:.3f} "
                f"| {m['scope_calibration']['mean']:.3f}+-{m['scope_calibration']['ci95']:.3f} "
                f"| {summary['per_baseline'][baseline]['total_cost_usd']} |")
        lines.append(line)
    if mode == "simulated":
        lines += [
            "",
            "> **SIMULATED**: deterministic synthetic data. This report validates the harness only "
            "and must never be presented as model performance (docs/benchmark.md Layer A vs Layer B).",
        ]
    markdown = "\n".join(lines) + "\n"
    out_path.write_text(markdown, encoding="utf-8")
    return markdown
