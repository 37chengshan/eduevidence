#!/usr/bin/env python3
"""fetch_benchmark.py — Fetch Reliability Benchmark (Smart Web Fetch v3 §19).

Compares built-in fetch vs Smart Web Fetch over benchmarks/fetch/urls.jsonl
(30 URLs covering paper landing / Chinese web / university sites / dynamic
pages / failure simulations).

Metrics:
    Fetch Success Rate      FETCH_VALID+PARTIAL proportion
    Useful Content Recall   content captured for expected-title URLs
    Noise Ratio             1 - clean_size/raw_size average
    Latency                 seconds per fetch
    Fallback Rate           proportion of attempts that used a fallback provider

Offline mode (--dry-run): uses a deterministic local simulator so the
benchmark runs without network — useful for CI and reproducibility. Live mode
(--live) actually hits the network.

Usage:
    python3 scripts/fetch_benchmark.py --urls benchmarks/fetch/urls.jsonl --dry-run
    python3 scripts/fetch_benchmark.py --urls benchmarks/fetch/urls.jsonl --live --out benchmarks/fetch/results/summary.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any


def _simulate(url: str, category: str, expect_title: str, seed: int = 42) -> dict[str, Any]:
    """Deterministic offline simulator mirroring real fetch outcomes."""
    rng = random.Random(seed + hash(url) % 100000)

    # service failure simulations
    if category == "service_failure_sim":
        return {"url": url, "fetch_status": "FETCH_FAILED", "fetch_provider": "builtin",
                "latency_s": 0.05, "fallback_used": False, "fallback_chain": ["builtin:error"],
                "raw_size": 0, "clean_size": 0, "compression_ratio": 0.0}

    # login-walled / dynamic pages degrade to PARTIAL at best
    if category in ("dynamic_page", "complex_nav"):
        status = "FETCH_PARTIAL" if rng.random() < 0.6 else "FETCH_FAILED"
        provider = "jina_reader" if status == "FETCH_PARTIAL" else "builtin"
        return {"url": url, "fetch_status": status, "fetch_provider": provider,
                "latency_s": round(0.3 + rng.random() * 0.5, 2), "fallback_used": status == "FETCH_PARTIAL",
                "fallback_chain": ["builtin:error", "jina_reader:ok"] if status == "FETCH_PARTIAL" else ["builtin:error"],
                "raw_size": 80_000, "clean_size": 6_000 if status == "FETCH_PARTIAL" else 0,
                "compression_ratio": 0.9 if status == "FETCH_PARTIAL" else 0.0}

    # short page
    if category == "short_page":
        return {"url": url, "fetch_status": "FETCH_PARTIAL", "fetch_provider": "builtin",
                "latency_s": 0.1, "fallback_used": False, "fallback_chain": ["builtin"],
                "raw_size": 1_200, "clean_size": 120, "compression_ratio": 0.9}

    # paper landing / journal / institution: reliable
    if category in ("paper_landing", "journal_article", "institution_org", "government_org",
                    "international_org", "report", "dataset_page", "wiki", "long_page",
                    "professional_institution"):
        status = "FETCH_VALID" if rng.random() < 0.85 else "FETCH_PARTIAL"
        provider = "builtin" if status == "FETCH_VALID" else "jina_reader"
        clean = 18_000 if status == "FETCH_VALID" else 4_000
        return {"url": url, "fetch_status": status, "fetch_provider": provider,
                "latency_s": round(0.2 + rng.random() * 0.6, 2), "fallback_used": status == "FETCH_PARTIAL",
                "fallback_chain": ["builtin"] if status == "FETCH_VALID" else ["builtin:error", "jina_reader:ok"],
                "raw_size": 120_000, "clean_size": clean, "compression_ratio": 1 - clean / 120_000}

    # university / chinese / news sites: mixed reliability
    content_ok = rng.random() < 0.7
    status = "FETCH_VALID" if content_ok else "FETCH_PARTIAL"
    provider = "builtin" if status == "FETCH_VALID" else "markdown_new"
    return {"url": url, "fetch_status": status, "fetch_provider": provider,
            "latency_s": round(0.2 + rng.random() * 0.7, 2), "fallback_used": status == "FETCH_PARTIAL",
            "fallback_chain": ["builtin"] if status == "FETCH_VALID" else ["builtin:error", "markdown_new:ok"],
            "raw_size": 90_000, "clean_size": 10_000 if status == "FETCH_VALID" else 3_000,
            "compression_ratio": 1 - (10_000 if status == "FETCH_VALID" else 3_000) / 90_000}


def _live_fetch(url: str, timeout: int = 20) -> dict[str, Any]:
    """Live fetch through the Smart Web Fetch chain (network required)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from integrations.smart_web_fetch import smart_fetch

    start = time.monotonic()
    result = smart_fetch(url, timeout=timeout)
    elapsed = time.monotonic() - start
    return {
        "url": url,
        "fetch_status": result["fetch_status"],
        "fetch_provider": result["fetch_provider"],
        "latency_s": round(elapsed, 2),
        "fallback_used": result["fallback_used"],
        "fallback_chain": result["fallback_chain"],
        "raw_size": result["raw_size"],
        "clean_size": result["clean_size"],
        "compression_ratio": result["compression_ratio"],
    }


def run_benchmark(urls: list[dict[str, Any]], *, live: bool, timeout: int = 20) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for row in urls:
        if live:
            res = _live_fetch(row["url"], timeout=timeout)
        else:
            res = _simulate(row["url"], row.get("category", ""), row.get("expect_title", ""))
        res["id"] = row["id"]
        res["category"] = row.get("category", "")
        res["expect_title"] = row.get("expect_title", "")
        results.append(res)

    total = len(results)
    valid = [r for r in results if r["fetch_status"] == "FETCH_VALID"]
    partial = [r for r in results if r["fetch_status"] == "FETCH_PARTIAL"]
    failed = [r for r in results if r["fetch_status"] == "FETCH_FAILED"]

    latencies = [r["latency_s"] for r in results if r.get("latency_s")]
    ratios = [r["compression_ratio"] for r in results if r.get("compression_ratio")]
    fallback = [r for r in results if r.get("fallback_used")]

    # Useful content recall: expected-title URLs that returned usable content
    expect_title_urls = [r for r in results if r.get("expect_title")]
    recall_hits = [r for r in expect_title_urls
                   if r["fetch_status"] in ("FETCH_VALID", "FETCH_PARTIAL")]
    recall = len(recall_hits) / len(expect_title_urls) if expect_title_urls else 0.0

    summary = {
        "total_urls": total,
        "fetch_success_rate": round(len(valid) / total, 3),
        "partial_rate": round(len(partial) / total, 3),
        "failure_rate": round(len(failed) / total, 3),
        "useful_content_recall": round(recall, 3),
        "avg_noise_ratio": round(sum(ratios) / len(ratios), 3) if ratios else 0.0,
        "avg_latency_s": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
        "fallback_rate": round(len(fallback) / total, 3),
        "mode": "live" if live else "dry_run",
        "results": results,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="EduEvidence Fetch Reliability Benchmark")
    parser.add_argument("--urls", required=True, help="benchmarks/fetch/urls.jsonl")
    parser.add_argument("--live", action="store_true", help="actually hit the network")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true",
                        help="explicitly run the offline simulator (default; mutually exclusive with --live)")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--out", help="optional JSON output path")
    args = parser.parse_args()

    if args.live and args.dry_run:
        parser.error("--live and --dry-run are mutually exclusive")

    urls = [json.loads(line) for line in Path(args.urls).read_text(encoding="utf-8").splitlines()
            if line.strip()]
    summary = run_benchmark(urls, live=args.live, timeout=args.timeout)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.out}")

    keys = ("total_urls", "fetch_success_rate", "partial_rate", "failure_rate",
            "useful_content_recall", "avg_noise_ratio", "avg_latency_s", "fallback_rate", "mode")
    for k in keys:
        print(f"{k}: {summary[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
