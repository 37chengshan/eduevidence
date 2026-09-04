#!/usr/bin/env python3
"""generate_metrics.py — Single source of truth for headline project metrics.

Docs must stop hard-coding counts that drift (plan R5). This script derives
the authoritative numbers from the repository itself and writes
docs/metrics.json. Run with --check (CI) to fail when a doc-facing metric
changed without regenerating this file.

Metrics:
- engine_version          from engine/versions.py (the version authority)
- test_functions          grep 'def test_' across tests/
- test_files              number of collected test modules in tests/
- schema_count            schemas/*.json recursively
- reference_doc_count     references/*.md
- gold_annotation_count   benchmarks/annotations/gold-Q*.json
- example_packs           real examples/*/ directories shipping result.json
                          (compatibility symlink aliases are excluded)

Usage:
    python3 scripts/generate_metrics.py            # regenerate docs/metrics.json
    python3 scripts/generate_metrics.py --check    # exit 1 if file is stale
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def collect() -> dict:
    versions_py = (REPO_ROOT / "engine" / "versions.py").read_text(encoding="utf-8")
    m = re.search(r'^ENGINE_VERSION\s*=\s*"(\d+\.\d+\.\d+)"', versions_py, re.M)
    engine_version = m.group(1) if m else "unknown"

    test_functions = test_files = 0
    tests_dir = REPO_ROOT / "tests"
    if tests_dir.is_dir():
        for path in tests_dir.glob("test_*.py"):
            test_files += 1
            test_functions += len(re.findall(r"^\s*def test_", path.read_text(encoding="utf-8"), re.M))

    schema_count = 0
    schemas_dir = REPO_ROOT / "schemas"
    if schemas_dir.is_dir():
        schema_count = len(list(schemas_dir.rglob("*.json")))

    reference_doc_count = len(list((REPO_ROOT / "references").glob("*.md"))) \
        if (REPO_ROOT / "references").is_dir() else 0

    gold_annotation_count = len(list((REPO_ROOT / "benchmarks" / "annotations").glob("gold-Q*.json"))) \
        if (REPO_ROOT / "benchmarks" / "annotations").is_dir() else 0

    example_packs = sorted(
        p.name for p in (REPO_ROOT / "examples").iterdir()
        if not p.is_symlink() and p.is_dir() and (p / "result.json").exists()
    ) if (REPO_ROOT / "examples").is_dir() else []

    return {
        "engine_version": engine_version,
        "test_functions": test_functions,
        "test_files": test_files,
        "schema_count": schema_count,
        "reference_doc_count": reference_doc_count,
        "gold_annotation_count": gold_annotation_count,
        "example_packs": example_packs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="fail if docs/metrics.json is stale")
    args = parser.parse_args()

    metrics = collect()
    out_path = REPO_ROOT / "docs" / "metrics.json"
    current = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else None

    if args.check:
        if current != metrics:
            print("FAIL: docs/metrics.json is stale; rerun scripts/generate_metrics.py")
            print(f"expected: {json.dumps(metrics, ensure_ascii=False)}")
            print(f"found:    {json.dumps(current, ensure_ascii=False)}")
            return 1
        print(f"metrics OK ({metrics['engine_version']}, "
              f"{metrics['test_functions']} tests, {metrics['schema_count']} schemas)")
        return 0

    out_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
