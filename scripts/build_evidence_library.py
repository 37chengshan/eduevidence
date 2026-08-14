#!/usr/bin/env python3
"""build_evidence_library.py — Build the builtin evidence library (v4).

Extracts condensed evidence summaries from two read-only corpora:

  1. benchmarks/annotations/gold-Q01.json .. gold-Q30.json
       key_claims            -> support/contradict entries (direction by question)
       key_supporting_sources -> support/contradict entries
       known_contradictions  -> entries in the opposite direction
       correct_outcome_types -> outcome_token
  2. examples/{ai-coding-assistant,ai-tutor,ai-writing-assistant}/evidence.jsonl
       claim / outcome_type / relation_to_claim / decision_relation / ...

Emits benchmarks/evidence-library.json (>= 100 entries, deduplicated on
(source_id, outcome_token, claim_text)) and validates it against
schemas/v4/evidence-library.schema.json using the repo's zero-dependency
validator (scripts/validate_schema.py).

Direction semantics (adoption-relevant, conservative):
  support    -> evidence favors adopting the intervention  (=> pilot)
  contradict -> evidence opposes adopting the intervention (=> reject)
  neutral    -> inconclusive
For gold units the coarse rule is: if a question's expected decision range is
purely reject-oriented ("reject" present and "pilot" absent), its
key_claims/key_supporting_sources are harmful evidence => contradict, and its
known_contradictions are beneficial evidence => support. Otherwise
claims/sources => support and contradictions => contradict. For example
evidence rows, direction is mapped from decision_relation
(support_adoption=>support, oppose_adoption=>contradict,
conditional=>support, neutral=>neutral), falling back to relation_to_claim.

Usage:
    python scripts/build_evidence_library.py [--out benchmarks/evidence-library.json]
Exit code 0 = generated and schema-valid; 1 = failure.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from validate_schema import SchemaError, Validator  # noqa: E402

LIBRARY_ID = "eduevidence-builtin-library"
LIBRARY_VERSION = "1.0.0"
DEFAULT_OUT = ROOT / "benchmarks" / "evidence-library.json"
SCHEMA_PATH = ROOT / "schemas" / "v4" / "evidence-library.schema.json"

ANNOTATIONS_DIR = ROOT / "benchmarks" / "annotations"
QUESTIONS_PATH = ROOT / "benchmarks" / "questions.jsonl"
EXAMPLE_EVIDENCE = {
    "ai-coding-assistant": ROOT / "examples" / "ai-coding-assistant" / "evidence.jsonl",
    "ai-tutor": ROOT / "examples" / "ai-tutor" / "evidence.jsonl",
    "ai-writing-assistant": ROOT / "examples" / "ai-writing-assistant" / "evidence.jsonl",
}

_WS_RE = re.compile(r"\s+")


def _norm_claim(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip().lower()


def _load_questions_meta() -> dict[str, dict[str, Any]]:
    """question id -> {domain, question} from benchmarks/questions.jsonl (read-only)."""
    meta: dict[str, dict[str, Any]] = {}
    if not QUESTIONS_PATH.is_file():
        return meta
    for line in QUESTIONS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        q = json.loads(line)
        meta[q["id"]] = {"domain": q.get("domain", "unspecified"), "question": q.get("question", "")}
    return meta


#: Negative-semantics markers: a claim stating harm/deterioration/dependency is
#: evidence AGAINST adoption (direction=contradict), never support (review P1-1).
NEGATIVE_MARKERS = ("受损", "下降", "降低", "削弱", "减少", "依赖", "风险",
                    "危害", "不利于", "更差", "低于", "有害", "负面", "负向",
                    "退化", "赤字", "损害", "虚增", "侵蚀", "削弱"
                    "reduce", "harm", "worsen", "depend", "reliance", "risk"
                    "lower", "worse", "negative"
                    "reduces", "harms", "damage")
#: Null-result markers: no-difference evidence is neutral, not a counter-argument.
NULL_MARKERS = ("无显著差异", "未发现显著", "零结果", "没有显著", "无差异",
                "no significant", "null", "not significant", "no difference")


def _claim_direction(text: str, base: str) -> str:
    """Per-claim direction: null-result claims are neutral; negative-semantics
    claims are contradict (they argue AGAINST adoption)."""
    if any(m in text for m in NULL_MARKERS):
        return "neutral"
    if any(m in text for m in NEGATIVE_MARKERS):
        return "contradict"
    return base


def _gold_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    q_meta = _load_questions_meta()
    gold_paths = sorted(ANNOTATIONS_DIR.glob("gold-Q*.json"))
    if not gold_paths:
        raise SystemExit(f"no gold annotations found under {ANNOTATIONS_DIR}")
    for path in gold_paths:
        gold = json.loads(path.read_text(encoding="utf-8"))
        qid = gold.get("id") or path.stem
        domain = q_meta.get(qid, {}).get("domain", "unspecified")
        outcomes = gold.get("correct_outcome_types") or ["unspecified"]
        outcome_token = outcomes[0] if outcomes else "unspecified"
        outcome_tokens = [o for o in outcomes if o != "unspecified"] or [outcome_token]
        expected = list(gold.get("expected_decision_range") or [])
        # Coarse direction rule documented in the module docstring.
        pure_reject = "reject" in expected and "pilot" not in expected
        claims_direction = "contradict" if pure_reject else "support"
        contra_direction = "support" if pure_reject else "contradict"

        units: list[tuple[str, str, str, str]] = []  # (kind, text, direction, label)
        for i, text in enumerate(gold.get("key_claims") or [], start=1):
            units.append(("claim", text, _claim_direction(text, claims_direction),
                         f"关键断言 {i}"))
        for i, text in enumerate(gold.get("key_supporting_sources") or [], start=1):
            units.append(("source", text, _claim_direction(text, claims_direction),
                         f"支持来源 {i}"))
        for i, text in enumerate(gold.get("known_contradictions") or [], start=1):
            units.append(("contra", text, contra_direction, f"已知矛盾 {i}"))

        for kind, text, direction, label in units:
            text = text.strip()
            if not text:
                continue
            if kind == "contra":
                summary = f"反证/矛盾证据（{direction}）：{text}"
            elif kind == "source":
                summary = f"支持来源标注（{direction}）：{text}"
            else:
                summary = f"金标准断言（{direction}）：{text}"
            entry: dict[str, Any] = {
                "entry_id": f"gold-{qid}-{kind}-{label.split()[-1]}",
                "source_id": f"GOLD-{qid}",
                "title": f"金标准 {qid} {label}",
                "year": None,
                "outcome_token": outcome_token,
                "outcome_tokens": outcome_tokens,
                "direction": direction,
                "study_type": "benchmark_annotation",
                "claim_text": text,
                "effect_summary": summary,
                "confidence_markers": ["gold_annotation", "benchmark_source"],
                "domains": [domain],
            }
            if expected:
                entry["confidence_markers"].append("expected_decision:" + ",".join(expected))
            if kind == "contra":
                entry["confidence_markers"].append("contradiction_evidence")
            entries.append(entry)
    return entries


def _example_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for domain, path in EXAMPLE_EVIDENCE.items():
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)
            direction = _map_example_direction(ev)
            claim = (ev.get("claim") or "").strip()
            if not claim:
                continue
            markers: list[str] = []
            if ev.get("evidence_level"):
                markers.append("evidence_level:" + str(ev["evidence_level"]))
            if ev.get("quality_score") is not None:
                markers.append("quality_score:" + str(ev["quality_score"]))
            if ev.get("confidence") is not None:
                markers.append("confidence:" + str(ev["confidence"]))
            if ev.get("decision_relation"):
                markers.append("decision_relation:" + str(ev["decision_relation"]))
            if not markers:
                markers.append("example_workflow")
            entry: dict[str, Any] = {
                "entry_id": f"lib-{domain}-{ev.get('evidence_id', 'E')}",
                "source_id": ev.get("source_id") or f"SRC-{domain}-{ev.get('evidence_id', 'E')}",
                "title": (ev.get("title") or "").strip() or f"{domain} evidence",
                "year": ev.get("year"),
                "outcome_token": ev.get("outcome_type") or "unspecified",
                "outcome_tokens": [ev.get("outcome_type") or "unspecified"],
                "direction": direction,
                "study_type": ev.get("study_type") or "example_workflow",
                "claim_text": claim,
                "effect_summary": (ev.get("effect") or claim).strip(),
                "confidence_markers": markers,
                "domains": [domain],
            }
            entries.append(entry)
    return entries


def _map_example_direction(ev: dict[str, Any]) -> str:
    decision = ev.get("decision_relation")
    mapping = {
        "support_adoption": "support",
        "oppose_adoption": "contradict",
        "conditional": "support",  # conservative pilot path
        "neutral": "neutral",
    }
    if decision in mapping:
        return mapping[decision]
    relation = ev.get("relation_to_claim") or ev.get("direction")
    if relation in ("support", "contradict", "neutral"):
        return relation
    return "neutral"


def _dedupe(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    merged = 0
    for entry in entries:
        key = (entry["source_id"], entry["outcome_token"], _norm_claim(entry["claim_text"]))
        if key in seen:
            seen[key]["confidence_markers"] = list(
                dict.fromkeys(seen[key]["confidence_markers"] + entry["confidence_markers"])
            )
            if "merged_duplicate" not in seen[key]["confidence_markers"]:
                seen[key]["confidence_markers"].append("merged_duplicate")
            merged += 1
        else:
            seen[key] = entry
    return list(seen.values()), merged


def _validate(library: dict[str, Any], schema_path: Path = SCHEMA_PATH) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Validator(schema, base_dir=schema_path.parent.parent)
    validator.validate(library, schema, "$")


def build(generated_at: str | None = None) -> tuple[dict[str, Any], int]:
    gold = _gold_entries()
    examples = _example_entries()
    raw = gold + examples
    entries, merged = _dedupe(raw)
    entries.sort(key=lambda e: (e["entry_id"]))
    library: dict[str, Any] = {
        "library_id": LIBRARY_ID,
        "version": LIBRARY_VERSION,
        "generated_at": (generated_at or datetime.now(timezone.utc).isoformat()),
        "entries": entries,
        "coverage_note": (
            "内置证据库：由 30 份金标准标注（benchmarks/annotations/gold-Q01..Q30 的 "
            "key_claims/key_supporting_sources/known_contradictions/correct_outcome_types）"
            "+ 3 个示例工作流 evidence.jsonl（ai-coding-assistant / ai-tutor / ai-writing-assistant）"
            "抽取生成；按 (source_id, outcome_token, claim_text) 去重合并。"
            "direction 语义为采纳方向：support=支持采纳（初步裁决=>pilot），"
            "contradict=反对采纳（=>reject），neutral=中性；金标准条目按 expected_decision_range "
            "粗粒度映射方向（纯 reject 问题反向映射），conflict 与混合方向问题的单条断言方向可能不精确。"
            "仅用于离线初步裁决（preliminary，保守），从不直接给出 adopt。"
        ),
    }
    _validate(library)
    return library, merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the builtin evidence library (v4).")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output JSON path")
    parser.add_argument("--generated-at", default=None,
                        help="fixed ISO timestamp for reproducibility (tests pass a constant)")
    args = parser.parse_args(argv)

    library, merged = build(generated_at=args.generated_at)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(library, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    from collections import Counter
    dirs = Counter(e["direction"] for e in library["entries"])
    kinds = Counter(e["study_type"] for e in library["entries"])
    print(f"library written: {out_path}")
    print(f"entries: {len(library['entries'])}  (merged duplicates: {merged})")
    print("direction:", dict(dirs))
    print("study_type:", dict(kinds))
    print(f"schema: {SCHEMA_PATH}  -> OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SchemaError as exc:
        print(f"SCHEMA ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
