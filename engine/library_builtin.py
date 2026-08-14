"""Builtin evidence library + offline preliminary verdict (v4).

Two entry points:

  load_builtin_library()      -> read benchmarks/evidence-library.json, validate
                                 structurally, cache (lru_cache), return a deep
                                 copy. Raises FileNotFoundError when the library
                                 has not been built yet and ValueError when the
                                 shape is invalid.

  preliminary_verdict(question, *, top_k=10)
                              -> deterministic offline screening verdict. Matching
                                 is Chinese-keyword / outcome-token based using
                                 CJK bigram overlap (self-implemented; mirrors the
                                 logic of scripts/benchmark_evaluator.py without
                                 importing it): the question is tokenized into CJK
                                 bigrams + English words, each library entry is
                                 scored by bigram overlap over
                                 claim_text + effect_summary + title, and the
                                 top_k entries above MATCH_THRESHOLD with at least
                                 MIN_SHARED_BIGRAMS shared tokens count as matched.

Conservative verdict rules (offline preliminary gate):
    any matched contradict entry -> reject
    else any matched support  entry -> pilot
    else                            -> insufficient_evidence
    adopt is NEVER returned by the preliminary gate.

Output:
    {"verdict": ..., "coverage": {"matched_entries": [...],
     "matched_outcome_tokens": [...], "note": "..."},
     "preliminary": True, "library_version": ...}

This module is stdlib-only (consistent with engine/ "Native Core" policy).
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LIBRARY_PATH = ROOT / "benchmarks" / "evidence-library.json"

# --- matching knobs (conservative) ---
MATCH_THRESHOLD = 0.30       # min bigram-overlap ratio (intersection / min sizes)
MIN_SHARED_BIGRAMS = 2       # min absolute shared tokens (blocks tiny-query over-match)

VERDICT_ORDER = ("adopt", "pilot", "reject", "insufficient_evidence")
DIRECTIONS = ("support", "contradict", "neutral")

# ---------------------------------------------------------------------------
# tokenization (self-implemented, mirrors scripts/benchmark_evaluator.py)
# ---------------------------------------------------------------------------
_ID_RE = re.compile(r"\b([A-Za-z][A-Za-z-]{1,40})\b")


def _cjk_bigrams(text: str) -> set[str]:
    chars = [c for c in text if "\u4e00" <= c <= "\u9fff"]
    return {chars[i] + chars[i + 1] for i in range(len(chars) - 1)}


def _words(text: str) -> set[str]:
    return {w.lower() for w in _ID_RE.findall(text) if len(w) > 2}


def _tokenize(text: str) -> set[str]:
    return _cjk_bigrams(text) | _words(text)


def _overlap_tokens(ta: set[str], tb: set[str]) -> float:
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, min(len(ta), len(tb)))


# ---------------------------------------------------------------------------
# outcome-token detection (Chinese terms + direct English taxonomy words)
# ---------------------------------------------------------------------------
_OUTCOME_TAXONOMY = {
    "accuracy", "assignment_score", "retention", "transfer",
    "independent_problem_solving", "completion_time", "cognitive_load",
    "knowledge_gain", "concept_understanding", "engagement", "motivation",
    "metacognition", "help_seeking", "code_quality", "ai_dependency",
    "over_reliance", "reduced_effort", "reduced_transfer",
    "academic_integrity_risk", "false_confidence",
}

_CN_OUTCOME_TERMS = {
    "正确率": "accuracy", "准确率": "accuracy", "正确性": "accuracy",
    "期末考试成绩": "assignment_score", "考试成绩": "assignment_score",
    "作业得分": "assignment_score", "作业成绩": "assignment_score",
    "成绩": "assignment_score", "得分": "assignment_score",
    "记忆保持": "retention", "保持率": "retention", "保持": "retention",
    "保留": "retention", "记忆": "retention",
    "迁移能力": "transfer", "迁移": "transfer",
    "独立问题解决": "independent_problem_solving",
    "独立写作": "independent_problem_solving", "独立编程": "independent_problem_solving",
    "独立解题": "independent_problem_solving", "脱离工具": "independent_problem_solving",
    "无AI情境": "independent_problem_solving", "独立": "independent_problem_solving",
    "任务完成时间": "completion_time", "完成时间": "completion_time",
    "速度": "completion_time",
    "认知负荷": "cognitive_load", "负荷": "cognitive_load",
    "知识获得": "knowledge_gain", "知识": "knowledge_gain",
    "概念理解": "concept_understanding", "概念": "concept_understanding",
    "参与度": "engagement", "参与": "engagement", "投入": "engagement",
    "学习动机": "motivation", "动机": "motivation", "兴趣": "motivation",
    "元认知": "metacognition",
    "求助行为": "help_seeking", "求助": "help_seeking",
    "代码质量": "code_quality",
    "过度依赖": "over_reliance", "AI依赖": "ai_dependency",
    "依赖": "ai_dependency",
    "减少努力": "reduced_effort", "努力": "reduced_effort",
    "迁移受损": "reduced_transfer", "迁移下降": "reduced_transfer",
    "学术诚信": "academic_integrity_risk", "诚信": "academic_integrity_risk",
    "作弊": "academic_integrity_risk", "原创性": "academic_integrity_risk",
    "虚假自信": "false_confidence",
}
# longest phrase first so "保持率" wins over "保持", "期末考试成绩" over "成绩", ...
_CN_OUTCOME_ORDERED = sorted(_CN_OUTCOME_TERMS.items(), key=lambda kv: -len(kv[0]))


def _detect_outcome_tokens(question: str) -> set[str]:
    tokens: set[str] = set()
    for phrase, outcome in _CN_OUTCOME_ORDERED:
        if phrase in question:
            tokens.add(outcome)
    tokens |= {w for w in _words(question) if w in _OUTCOME_TAXONOMY}
    return tokens


# ---------------------------------------------------------------------------
# library loading: validate + cache
# ---------------------------------------------------------------------------
_TOP_REQUIRED = {"library_id", "version", "generated_at", "entries", "coverage_note"}
_ENTRY_REQUIRED = {
    "entry_id", "source_id", "title", "year", "outcome_token", "direction",
    "study_type", "claim_text", "effect_summary", "confidence_markers", "domains",
}


def _validate_library_shape(lib: dict[str, Any]) -> None:
    """Structural validation of the builtin library (stdlib-only).

    Keeps the engine dependency-free; the full JSON-Schema check lives in the
    build script (scripts/build_evidence_library.py -> validate_schema.Validator).
    """
    if not isinstance(lib, dict):
        raise ValueError("builtin library must be a JSON object")
    missing = _TOP_REQUIRED - lib.keys()
    if missing:
        raise ValueError(f"builtin library missing required fields: {sorted(missing)}")
    entries = lib.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("builtin library entries must be a non-empty list")
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"entry[{idx}] must be an object")
        miss = _ENTRY_REQUIRED - entry.keys()
        if miss:
            raise ValueError(f"entry[{idx}] missing required fields: {sorted(miss)}")
        if entry["direction"] not in DIRECTIONS:
            raise ValueError(
                f"entry[{idx}] direction {entry['direction']!r} not in {sorted(DIRECTIONS)}"
            )
        for field in ("entry_id", "source_id", "title", "outcome_token",
                      "claim_text", "effect_summary", "study_type"):
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise ValueError(f"entry[{idx}] {field!r} must be a non-empty string")
        if entry["year"] is not None and (
            not isinstance(entry["year"], int) or isinstance(entry["year"], bool)
        ):
            raise ValueError(f"entry[{idx}] year must be integer or null")
        if not isinstance(entry["confidence_markers"], list):
            raise ValueError(f"entry[{idx}] confidence_markers must be a list")
        if not isinstance(entry["domains"], list) or not entry["domains"]:
            raise ValueError(f"entry[{idx}] domains must be a non-empty list")


@lru_cache(maxsize=1)
def _read_library() -> dict[str, Any]:
    if not LIBRARY_PATH.is_file():
        raise FileNotFoundError(
            f"builtin evidence library not found: {LIBRARY_PATH}; "
            "run 'python scripts/build_evidence_library.py' first"
        )
    lib = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    _validate_library_shape(lib)
    return lib


def load_builtin_library() -> dict[str, Any]:
    """Load (validated + cached) builtin library; returns a deep copy."""
    return deepcopy(_read_library())


# ---------------------------------------------------------------------------
# preliminary verdict
# ---------------------------------------------------------------------------
def _entry_text(entry: dict[str, Any]) -> str:
    return " ".join(
        str(entry.get(k) or "")
        for k in ("claim_text", "effect_summary", "title")
    )


def preliminary_verdict(question: str, *, top_k: int = 10) -> dict[str, Any]:
    """Offline conservative preliminary verdict for a (Chinese) education question.

    Matching: CJK bigram overlap between the question and each entry's
    claim_text + effect_summary + title; the top_k entries are considered and an
    entry counts as matched when overlap >= MATCH_THRESHOLD and it shares at
    least MIN_SHARED_BIGRAMS tokens. Verdict: contradict => reject, else
    support => pilot, else insufficient_evidence. Never adopt. Never crashes on
    empty/blank questions.
    """
    lib = _read_library()
    question = (question or "").strip()
    q_tokens = _tokenize(question)
    q_outcomes = _detect_outcome_tokens(question)

    scored: list[tuple[float, int, bool, dict[str, Any]]] = []
    for entry in lib["entries"]:
        e_tokens = _tokenize(_entry_text(entry))
        base = _overlap_tokens(q_tokens, e_tokens)
        shared = len(q_tokens & e_tokens)
        has_outcome = entry.get("outcome_token") in q_outcomes
        scored.append((base, shared, has_outcome, entry))

    scored.sort(key=lambda t: (-t[0], -t[1], -int(t[2]), t[3].get("entry_id", "")))
    top = scored[: max(0, int(top_k))]

    matched = [
        entry
        for base, shared, _has_outcome, entry in top
        if base >= MATCH_THRESHOLD and shared >= MIN_SHARED_BIGRAMS
    ]

    directions = {entry["direction"] for entry in matched}
    if "contradict" in directions:
        verdict = "reject"
    elif "support" in directions:
        verdict = "pilot"
    else:
        verdict = "insufficient_evidence"

    note = _build_note(matched, directions, q_outcomes, top_k)
    return {
        "verdict": verdict,
        "coverage": {
            "matched_entries": [entry["entry_id"] for entry in matched],
            "matched_outcome_tokens": sorted(q_outcomes),
            "note": note,
        },
        "preliminary": True,
        "library_version": lib.get("version", ""),
    }


def _build_note(
    matched: list[dict[str, Any]],
    directions: set[str],
    q_outcomes: set[str],
    top_k: int,
) -> str:
    outcome_str = "、".join(sorted(q_outcomes)) or "无"
    if not matched:
        return (
            f"离线初步裁决未匹配到内置证据（阈值：bigram overlap≥{MATCH_THRESHOLD} 且"
            f"共享 bigram≥{MIN_SHARED_BIGRAMS}）；检测到结局词：{outcome_str}。"
            "建议进入在线证据检索流程进一步核实。"
        )
    counts = {d: sum(1 for e in matched if e["direction"] == d) for d in DIRECTIONS}
    return (
        f"离线初步裁决在 top_k={top_k} 内匹配到 {len(matched)} 条内置证据："
        f"support={counts['support']}、contradict={counts['contradict']}、"
        f"neutral={counts['neutral']}；匹配结局词：{outcome_str}。"
        "本裁决为初步（preliminary=true）且保守，从不直接给出 adopt，"
        "建议结合完整证据库与在线检索复核。"
    )
