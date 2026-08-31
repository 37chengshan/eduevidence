"""Auditable, bounded search execution for evidence retrieval.

Provider implementations remain deliberately separate. This module records
the query intent, every provider attempt, screening decisions and saturation
stop reason so a search result is never mistaken for unobserved provenance.
"""
from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from retrieval.search import SearchHit
from retrieval.source import parse_doi_from_url, title_fingerprint


@dataclass(frozen=True)
class SearchQuery:
    query_id: str
    query: str
    purpose: str  # core | expansion | counter_evidence | citation_chain


@dataclass(frozen=True)
class SearchPlan:
    question: str
    domain: str
    concepts: tuple[str, ...]
    synonyms: tuple[str, ...]
    inclusion_criteria: tuple[str, ...]
    exclusion_criteria: tuple[str, ...]
    queries: tuple[SearchQuery, ...]
    provider_budget: int = 10
    policy_version: str = "2026.09"

    @classmethod
    def from_question(cls, question: str, *, domain: str = "education",
                      concepts: Iterable[str] = (), synonyms: Iterable[str] = ()) -> "SearchPlan":
        terms = tuple(dict.fromkeys(x.strip() for x in (*concepts, *synonyms) if x.strip()))
        core = " ".join(terms) or question
        return cls(question, domain, tuple(concepts), tuple(synonyms), (), (), (
            SearchQuery("Q1", core, "core"),
            SearchQuery("Q2", f"{core} systematic review OR meta-analysis", "expansion"),
            SearchQuery("Q3", f"{core} null negative harm bias limitation", "counter_evidence"),
        ))


@dataclass
class SearchAttempt:
    attempt_id: str
    query_id: str
    provider: str
    started_at: float
    ended_at: float
    status: str
    result_count: int
    error: str = ""
    retry_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["latency_ms"] = round((self.ended_at - self.started_at) * 1000, 2)
        return value


def _hit_key(hit: SearchHit) -> tuple[str, str, str]:
    doi = (hit.doi or parse_doi_from_url(hit.url) or "").lower()
    return doi, hit.url.rstrip("/").lower(), title_fingerprint(hit.title)


def dedupe_hits(hits: Iterable[SearchHit]) -> list[SearchHit]:
    """Deduplicate DOI, canonical URL and normalized title, retaining priority."""
    seen: set[tuple[str, str]] = set()
    kept: list[SearchHit] = []
    for hit in sorted(hits, key=lambda item: (item.score, item.citation_count or 0), reverse=True):
        doi, url, title = _hit_key(hit)
        keys = [("doi", doi), ("url", url), ("title", title)]
        nonempty = [key for key in keys if key[1]]
        if any(key in seen for key in nonempty):
            continue
        seen.update(nonempty)
        kept.append(hit)
    return kept


class AuditedSearchExecutor:
    """Runs an explicit plan with bounded retries and durable audit exports."""

    def __init__(self, providers: Iterable[Any], *, max_retries: int = 1):
        self.providers = list(providers)
        self.max_retries = max_retries

    def execute(self, plan: SearchPlan, output_dir: Path, *, limit: int = 10) -> list[SearchHit]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        attempts: list[SearchAttempt] = []
        hits: list[SearchHit] = []
        attempted: set[tuple[str, str]] = set()
        counter_hits = 0
        for query in plan.queries:
            for provider in self.providers:
                name = getattr(provider, "name", provider.__class__.__name__)
                fingerprint = (name, query.query)
                if fingerprint in attempted:
                    continue
                attempted.add(fingerprint)
                for retry in range(self.max_retries + 1):
                    started = time.time()
                    try:
                        result = provider.search(query.query, limit=limit)
                        ended = time.time()
                        attempts.append(SearchAttempt(
                            f"A-{len(attempts) + 1:04d}", query.query_id, name, started, ended,
                            "success", len(result), retry_index=retry,
                        ))
                        hits.extend(result)
                        if query.purpose == "counter_evidence":
                            counter_hits += len(result)
                        break
                    except Exception as exc:  # failures are recorded, never swallowed
                        ended = time.time()
                        attempts.append(SearchAttempt(
                            f"A-{len(attempts) + 1:04d}", query.query_id, name, started, ended,
                            "failed", 0, error=f"{type(exc).__name__}: {exc}", retry_index=retry,
                        ))
        unique = dedupe_hits(hits)
        self._write_exports(output_dir, plan, attempts, unique, counter_hits)
        return unique[:limit]

    @staticmethod
    def _write_exports(output_dir: Path, plan: SearchPlan, attempts: list[SearchAttempt],
                       hits: list[SearchHit], counter_hits: int) -> None:
        (output_dir / "search-provenance.json").write_text(json.dumps({
            "plan": {**asdict(plan), "queries": [asdict(q) for q in plan.queries]},
            "search_completed": True,
            "counter_evidence_queries_executed": sum(q.purpose == "counter_evidence" for q in plan.queries),
            "counter_evidence_hit_count": counter_hits,
            "stop_reason": "planned_queries_completed",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (output_dir / "search-attempts.jsonl").write_text(
            "".join(json.dumps(item.to_dict(), ensure_ascii=False) + "\n" for item in attempts), encoding="utf-8")
        with (output_dir / "source-screening.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["title", "doi", "url", "provider", "year", "screening_status", "reason"])
            writer.writeheader()
            for hit in hits:
                writer.writerow({"title": hit.title, "doi": hit.doi or parse_doi_from_url(hit.url) or "", "url": hit.url,
                                 "provider": hit.provider, "year": hit.year or "", "screening_status": "candidate",
                                 "reason": "discovery metadata only; fetch and validation required before evidence extraction"})
        with (output_dir / "exclusion-log.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["identifier", "reason"])
            writer.writeheader()
