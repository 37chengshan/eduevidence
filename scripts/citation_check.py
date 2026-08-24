#!/usr/bin/env python3
"""CLI: verify every DOI in a pack's sources/evidence against registries (E6).

Usage:
    python3 scripts/citation_check.py --pack examples/ai-coding-assistant-evidence
    python3 scripts/citation_check.py --sources examples/X/sources.jsonl --out /tmp/cite.json

Writes citation_check.json (+ .md) into the pack dir by default and exits 1
when any not_found/mismatch/retracted is found unless --no-fail.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.citation_check import RegistryClient, extract_dois  # noqa: E402


def load_records(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return [json.loads(text)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", help="example pack directory")
    parser.add_argument("--sources", help="single sources.jsonl / evidence.jsonl")
    parser.add_argument("--out", help="output JSON path (default <pack>/citation_check.json)")
    parser.add_argument("--no-fail", action="store_true")
    parser.add_argument("--write-back", action="store_true",
                        help="inject doi_verified/retracted into the pack's sources.jsonl")
    args = parser.parse_args()

    targets: list[Path] = []
    out_path: Path | None = None
    if args.pack:
        pack = Path(args.pack)
        for name in ("sources.jsonl", "evidence.jsonl"):
            f = pack / name
            if f.exists():
                targets.append(f)
        out_path = pack / "citation_check.json"
    elif args.sources:
        targets.append(Path(args.sources))
        out_path = Path(args.out) if args.out else Path("citation_check.json")
    else:
        parser.error("pass --pack or --sources")
    if not targets:
        print("no sources/evidence files found; nothing to check")
        return 0

    records: list[tuple[str, dict]] = []
    for t in targets:
        records.extend((t.name, rec) for rec in load_records(t))

    client = RegistryClient()
    seen: set[str] = set()
    rows = []
    for fname, rec in records:
        for doi, title in extract_dois(rec):
            if doi in seen:
                continue
            seen.add(doi)
            verdict = client.check(doi, title)
            rows.append({"file": fname, **verdict})
            print(f"{verdict['status']:9s} retracted={verdict['retracted']!s:5s} {doi}")

    bad = [r for r in rows if r["status"] != "ok" or r["retracted"]]
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "checked": len(rows),
        "bad": len(bad),
        "results": rows,
    }
    assert out_path is not None
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = out_path.with_suffix(".md")
    lines = ["# Citation Check", "",
             f"生成时间：{report['generated_at']}；核验 DOI：{len(rows)}；异常：{len(bad)}", ""]
    if bad:
        lines += ["| DOI | 状态 | 撤稿 | 注册表标题 |", "|---|---|---|---|"]
        for r in bad:
            t = (r.get("registry_title") or "")[:70].replace("|", "\\|")
            lines.append(f"| `{r['doi']}` | {r['status']} | {'⚠️ 是' if r['retracted'] else '否'} | {t} |")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\ncitation check -> {out_path} (bad={len(bad)})")

    if args.write_back and args.pack:
        by_doi = {r["doi"]: r for r in rows}
        src_file = Path(args.pack) / "sources.jsonl"
        if src_file.exists():
            lines = []
            changed = 0
            for line in src_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                for doi, v in by_doi.items():
                    rec_doi = (rec.get("doi") or "").strip()
                    if rec_doi == doi or doi in json.dumps(rec):
                        new_flags = {"doi_verified": v["doi_verified"], "retracted": v["retracted"]}
                        if any(rec.get(k) != val for k, val in new_flags.items()):
                            rec.update(new_flags)
                            changed += 1
                        break
                lines.append(json.dumps(rec, ensure_ascii=False))
            src_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"write-back: {changed} source rows updated in {src_file}")

    return (1 if bad else 0) if not args.no_fail else 0


if __name__ == "__main__":
    sys.exit(main())
