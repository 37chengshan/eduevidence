#!/usr/bin/env python3
"""evidence_matrix.py — Build the Evidence Matrix (plan section 15).

Standard presentation:

| Claim | Outcome | Support | Contradiction | Quality | Directness | Verdict |

Users should not need to read a long report first; the Evidence Matrix is one
of the primary product surfaces.

Usage:
    python scripts/evidence_matrix.py examples/ai-coding-assistant/evidence.jsonl [--out matrix.md]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evidence_score import quality_score


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


def evidence_matrix(evidence_list: list[dict]) -> list[dict[str, str]]:
    """Aggregate evidence into matrix rows keyed by (claim, outcome)."""
    rows: dict[tuple[str, str], dict[str, list]] = {}
    for ev in evidence_list:
        key = (ev.get("claim", ""), ev.get("outcome_type", ""))
        row = rows.setdefault(key, {"claim": key[0], "outcome": key[1],
                                    "support": [], "contradiction": [],
                                    "quality": [], "directness": []})
        direction = ev.get("direction", "neutral")
        # Support vs contradiction columns; neutral evidence is appended as
        # context to the contradiction column so it is never silently dropped.
        bucket = "support" if direction == "support" else "contradiction"
        row[bucket].append(ev.get("evidence_id", "?"))

        dims = ev.get("quality_dimensions", {})
        if ev.get("quality_score") is None and dims:
            row["quality"].append(quality_score(dims))
        elif isinstance(ev.get("quality_score"), (int, float)):
            row["quality"].append(float(ev["quality_score"]))
        directness = dims.get("D5_directness", 0)
        row["directness"].append(float(directness) if isinstance(directness, (int, float)) else 0.0)

    result = []
    for key, row in sorted(rows.items()):
        quality = sum(row["quality"]) / len(row["quality"]) if row["quality"] else None
        directness = sum(row["directness"]) / len(row["directness"]) if row["directness"] else 0.0
        verdict = _verdict(row["support"], row["contradiction"], quality)
        result.append({
            "claim": row["claim"],
            "outcome": row["outcome"],
            "support": ", ".join(row["support"]) or "-",
            "contradiction": ", ".join(row["contradiction"]) or "-",
            "quality": f"{quality:.1f}/10" if quality is not None else "-",
            "directness": f"{directness:.1f}/2",
            "verdict": verdict,
        })
    return result


def _verdict(support: list, contradiction: list, quality: float | None) -> str:
    if contradiction and not support:
        return "CONTRADICTED"
    if not support and not contradiction:
        return "NO_EVIDENCE"
    if quality is None or quality < 5:
        return "WEAK"
    if contradiction:
        return "CONFLICTED"
    if quality >= 7:
        return "SUPPORTED"
    return "PARTIALLY_SUPPORTED"


def render_markdown(matrix: list[dict[str, str]]) -> str:
    header = "| Claim | Outcome | Support | Contradiction | Quality | Directness | Verdict |"
    sep = "|---|---|---|---|---|---|---|"
    lines = [header, sep]
    for row in matrix:
        claim = row["claim"].replace("|", "\\|")
        lines.append(
            f"| {claim} | {row['outcome']} | {row['support']} | {row['contradiction']} "
            f"| {row['quality']} | {row['directness']} | {row['verdict']} |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Evidence Matrix from evidence JSONL")
    parser.add_argument("evidence", help="Path to evidence.jsonl")
    parser.add_argument("--out", help="Optional output markdown path")
    args = parser.parse_args()

    evs = load_evidence(Path(args.evidence))
    matrix = evidence_matrix(evs)
    md = render_markdown(matrix)
    if args.out:
        Path(args.out).write_text(md + "\n", encoding="utf-8")
        print(f"wrote {args.out} ({len(matrix)} rows)")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
