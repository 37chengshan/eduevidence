#!/usr/bin/env python3
"""dedupe.py — Evidence / Source deduplication (Smart Web Fetch v3 §13, P1-4).

The same paper behind different mirror URLs must not count as multiple
independent evidence items. Multi-index dedupe (P1-4):

    doi_index / url_index / title_index / hash_index

Any index hit marks a candidate duplicate; the hit source and the new source
are then merged keeping the entry with the higher authority tier and the more
complete metadata.
"""
from __future__ import annotations

from typing import Any, Iterable

from retrieval.source import title_fingerprint


def _source_keys(src: dict[str, Any]) -> dict[str, str]:
    """Extract the four dedupe keys (lowercased/normalized) from a source."""
    keys = src.get("dedupe_keys", {}) or {}
    return {
        "doi": (keys.get("doi") or "").strip().lower(),
        "url": (keys.get("canonical_url") or "").strip().rstrip("/").lower(),
        "title": keys.get("title_fingerprint") or title_fingerprint(src.get("title", "")),
        "hash": keys.get("content_hash") or src.get("content_hash", ""),
    }


def _metadata_score(src: dict[str, Any]) -> int:
    """Completeness score: how much identifying metadata does this entry have."""
    keys = _source_keys(src)
    score = 0
    if keys["doi"]:
        score += 4
    if keys["url"]:
        score += 2
    if keys["title"]:
        score += 1
    if src.get("authors"):
        score += 1
    if src.get("year") is not None:
        score += 1
    return score


def _merge_sources(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Merge two duplicate candidates: keep the higher-authority entry (lower
    tier number); on ties keep the more complete one."""
    from retrieval.source import is_higher_authority

    a_authority = existing.get("authority_level", "tier5_general_web")
    b_authority = incoming.get("authority_level", "tier5_general_web")
    if is_higher_authority(b_authority, a_authority):
        return incoming
    if is_higher_authority(a_authority, b_authority):
        return existing
    return incoming if _metadata_score(incoming) > _metadata_score(existing) else existing


def dedupe_sources(sources: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedupe sources through four parallel indexes
    (doi -> url -> title_fingerprint -> content_hash).

    A new source that hits ANY index is a candidate duplicate of the indexed
    entry; the pair is merged keeping the higher-authority / more complete one
    (v3 §13: 同一论文不同镜像 URL 不能算成多个独立证据).
    """
    indexes: dict[str, dict[str, dict[str, Any]]] = {
        "doi": {},
        "url": {},
        "title": {},
        "hash": {},
    }
    unique: list[dict[str, Any]] = []
    for src in sources:
        keys = _source_keys(src)
        hit: dict[str, Any] | None = None
        hit_index = ""
        for name in ("doi", "url", "title", "hash"):
            key = keys[name]
            if key and key in indexes[name]:
                hit = indexes[name][key]
                hit_index = name
                break
        if hit is None:
            unique.append(src)
            for name in ("doi", "url", "title", "hash"):
                key = keys[name]
                if key:
                    indexes[name][key] = src
            continue
        # Candidate duplicate: merge, keep the better entry, reindex it.
        kept = _merge_sources(hit, src)
        if kept is src:
            unique[unique.index(hit)] = src
            # The replaced entry's keys may still point at the stale object; a
            # later source hitting any of them would crash (ValueError) or
            # silently mis-merge. Repoint them at the kept source too.
            for name in ("doi", "url", "title", "hash"):
                key = _source_keys(hit)[name]
                if key:
                    indexes[name][key] = src
        for name in ("doi", "url", "title", "hash"):
            key = keys[name]
            if key:
                indexes[name][key] = kept
    return unique


def dedupe_evidence(evidence: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedupe evidence rows by source_id + claim (same claim from same source)."""
    seen: set[tuple[str, str]] = set()
    result = []
    for ev in evidence:
        key = (ev.get("source_id", ""), ev.get("claim", ""))
        if key not in seen:
            seen.add(key)
            result.append(ev)
    return result


def count_duplicates(sources: Iterable[dict[str, Any]]) -> int:
    """Number of sources removed by dedupe (for benchmark metrics)."""
    as_list = list(sources)
    return len(as_list) - len(dedupe_sources(as_list))
