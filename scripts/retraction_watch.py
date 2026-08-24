#!/usr/bin/env python3
"""retraction_watch.py — 定期重查已引 DOI 的撤稿状态（plan F4）。

引用可信不是一次性校验：文献可能在报告产出后被撤稿/更正。本脚本读取
examples/*/sources.jsonl（或 --state 指定的上次快照），仅查询每个 DOI 的
registry 记录变化，输出：

- benchmarks/retraction-watch/state.json   本次全量快照（doi → status）
- benchmarks/retraction-watch/report.md    与上次快照的 diff + 当前撤稿清单

退出码：发现新增撤稿或核验失败 → 1；否则 0（--no-fail 恒 0）。
Stdlib only；网络纪律同 engine/citation_check.py（域名白名单 + 严格 DOI 形态）。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.citation_check import RegistryClient, clean_doi  # noqa: E402
from engine.log import get_log  # noqa: E402

log = get_log("retraction-watch")
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "benchmarks" / "retraction-watch"


def collect_dois() -> dict[str, list[str]]:
    """doi -> 出现的示例包列表（读 sources.jsonl 的 doi 字段）。"""
    out: dict[str, list[str]] = {}
    examples = ROOT / "examples"
    for pack in sorted(examples.iterdir()):
        src = pack / "sources.jsonl"
        if not (pack.is_dir() and src.exists()):
            continue
        for line in src.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            doi = rec.get("doi")
            if doi:
                doi = clean_doi(doi)
                packs = out.setdefault(doi, [])
                if pack.name not in packs:
                    packs.append(pack.name)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sleep", type=float, default=0.3)
    parser.add_argument("--no-fail", action="store_true")
    args = parser.parse_args()

    dois = collect_dois()
    log.info("watching %d DOIs from %d packs", len(dois), len({p for v in dois.values() for p in v}))
    client = RegistryClient(sleep_s=args.sleep)

    snapshot: dict[str, dict] = {}
    for doi in sorted(dois):
        verdict = client.check(doi)
        snapshot[doi] = {
            "status": verdict["status"],
            "retracted": verdict["retracted"],
            "registry_title": verdict.get("registry_title"),
            "packs": dois[doi],
        }
        flag = " ⚠️RETRACTED" if verdict["retracted"] else ""
        print(f"{verdict['status']:9s}{flag} {doi}")

    state_path = OUT_DIR / "state.json"
    prev = json.loads(state_path.read_text(encoding="utf-8"))["dois"] if state_path.exists() else {}
    newly_retracted = [d for d, v in snapshot.items()
                       if v["retracted"] and not prev.get(d, {}).get("retracted")]
    broken = [d for d, v in snapshot.items() if v["status"] in ("not_found", "mismatch", "error")]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "state.json").write_text(
        json.dumps({"updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "dois": snapshot},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")

    lines = ["# Retraction Watch", "",
             f"更新时间：{time.strftime('%Y-%m-%d %H:%M %Z')}；监控 DOI：{len(snapshot)}",
             f"撤稿：{sum(1 for v in snapshot.values() if v['retracted'])}；"
             f"本次新增撤稿：{len(newly_retracted)}；核验异常：{len(broken)}", ""]
    if newly_retracted:
        lines += ["## 🆕 本次新增撤稿", ""]
        lines += [f"- `{d}`（{', '.join(snapshot[d]['packs'])}）" for d in newly_retracted]
        lines.append("")
    retracted_all = [d for d, v in snapshot.items() if v["retracted"]]
    if retracted_all:
        lines += ["## 已知撤稿（持续监控）", ""]
        lines += [f"- `{d}`" for d in retracted_all] + [""]
    if broken:
        lines += ["## 核验异常", ""] + [f"- `{d}` ({snapshot[d]['status']})" for d in broken] + [""]
    (OUT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\nreport -> {OUT_DIR}/report.md "
          f"(newly_retracted={len(newly_retracted)}, broken={len(broken)})")
    return 1 if ((newly_retracted or broken) and not args.no_fail) else 0


if __name__ == "__main__":
    sys.exit(main())
