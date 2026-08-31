#!/usr/bin/env python3
"""Execute an audited, bounded search plan and persist provenance.

For every explicit query (core / expansion / counter_evidence) this records
each provider attempt, then exports search-provenance.json,
search-attempts.jsonl, source-screening.csv and exclusion-log.csv into the
output directory. A search result without this provenance file is a candidate,
never evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from retrieval.audit import AuditedSearchExecutor, SearchPlan  # noqa: E402
from retrieval.search import search_router  # noqa: E402


CHANNELS = {
    "academic": lambda router: router.zero_config_academic,
    "web": lambda router: router.zero_config_web + router.configured_providers,
    "all": lambda router: (router.zero_config_academic + router.zero_config_web
                            + [p for p in router.configured_providers if p.is_available()]),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="audited external search with provenance")
    parser.add_argument("question", help="research question")
    parser.add_argument("--out", required=True, type=Path, help="provenance output directory")
    parser.add_argument("--domain", default="education", choices=["education", "policy"])
    parser.add_argument("--concept", action="append", default=[], help="concept term (repeatable)")
    parser.add_argument("--synonym", action="append", default=[], help="synonym term (repeatable)")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--channel", default="all", choices=list(CHANNELS))
    parser.add_argument("--policy", default="2026.09", help="search policy version")
    args = parser.parse_args(argv)
    plan = SearchPlan.from_question(args.question, domain=args.domain,
                                    concepts=args.concept, synonyms=args.synonym)
    plan = SearchPlan(plan.question, plan.domain, plan.concepts, plan.synonyms,
                      plan.inclusion_criteria, plan.exclusion_criteria, plan.queries,
                      provider_budget=args.limit, policy_version=args.policy)
    providers = CHANNELS[args.channel](search_router)
    hits = AuditedSearchExecutor(providers).execute(plan, args.out, limit=args.limit)
    print(json.dumps({
        "output": str(args.out),
        "sources": len(hits),
        "query_count": len(plan.queries),
        "counter_evidence_queries": sum(q.purpose == "counter_evidence" for q in plan.queries),
        "provenance_files": ["search-provenance.json", "search-attempts.jsonl",
                             "source-screening.csv", "exclusion-log.csv"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
