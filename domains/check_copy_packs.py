#!/usr/bin/env python3
"""Assert domain copy packs stay in-domain.

Requirement: the policy dictionary must not contain teaching vocabulary.
Run: python3 domains/check_copy_packs.py
Exit 0 = clean; exit 1 = violation (prints every hit).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Reuse the report-layer ban list so load-time and CLI checks cannot drift.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "visualization" / "eduevidence-report" / "scripts"))
from report_copy_pack import COPY_PACK_FILES, load_copy_pack  # noqa: E402
from report_copy_policy_guard import (  # noqa: E402
    TEACHING_WORDS_EN,
    TEACHING_WORDS_ZH,
    assert_policy_copy_clean,
)

DOMAINS = Path(__file__).resolve().parent


def _iter_strings(node, path="$"):
    if isinstance(node, dict):
        for key, value in node.items():
            # Storage keys may be snake_case English (learning_metrics); the
            # ban applies to reader-facing values.
            yield from _iter_strings(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _iter_strings(value, f"{path}[{index}]")
    elif isinstance(node, str):
        yield path, node


def load_pack(domain: str) -> dict:
    return load_copy_pack(domain, strict=True)["files"]


def find_teaching_hits(domain: str) -> list[str]:
    pack = load_pack(domain)
    hits: list[str] = []
    for name, data in pack.items():
        for path, text in _iter_strings(data):
            for word in TEACHING_WORDS_ZH:
                if word in text:
                    hits.append(f"{domain}/{name} {path}: contains {word!r} in {text!r}")
            lowered = text.lower()
            for phrase in TEACHING_WORDS_EN:
                if phrase.lower() in lowered:
                    hits.append(f"{domain}/{name} {path}: contains {phrase!r} in {text!r}")
    return hits


def main() -> int:
    failures = 0
    # Hard requirement: policy dictionary free of teaching words.
    try:
        assert_policy_copy_clean(load_pack("policy"))
        print("OK  policy copy pack: no teaching vocabulary")
    except AssertionError as exc:
        print(f"FAIL  {exc}")
        failures += 1

    # Soft inventory: education pack is expected to carry teaching voice.
    edu_hits = find_teaching_hits("education")
    print(f"INFO  education copy pack teaching-term hits: {len(edu_hits)}")

    # Structural: every registered domain that has a copy/ dir is complete.
    for domain_dir in sorted(DOMAINS.iterdir()):
        if not domain_dir.is_dir() or domain_dir.name.startswith("_"):
            continue
        copy_dir = domain_dir / "copy"
        if not copy_dir.is_dir():
            continue
        try:
            pack = load_pack(domain_dir.name)
        except FileNotFoundError as exc:
            print(f"FAIL  {exc}")
            failures += 1
            continue
        for name, data in pack.items():
            if data.get("domain") != domain_dir.name:
                print(f"FAIL  {domain_dir.name}/copy/{name}: domain field mismatch")
                failures += 1
        # four-state few-shots
        states = set((pack.get("few_shots.json") or {}).get("states") or {})
        required = {"adopt", "pilot", "reject", "insufficient_evidence"}
        if not required <= states:
            print(f"FAIL  {domain_dir.name}/copy/few_shots.json: missing states {sorted(required - states)}")
            failures += 1

    if failures:
        print(f"FAILED ({failures} problem(s))")
        return 1
    print("ALL COPY PACK CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
