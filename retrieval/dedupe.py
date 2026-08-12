#!/usr/bin/env python3
"""dedupe.py — Evidence / Source deduplication (Smart Web Fetch v3 §13).

The same paper behind different mirror URLs must not count as multiple
independent evidence items. Dedupe keys:

    canonical_url / doi / title fingerprint / content_hash
"""
from __future__ import annotations

from typing import Any, Iterable

from retrieval.source import title_fingerprint


def dedupe_sources(sources: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedupe sources by (doi -> canonical_url -> title_fingerprint -> content_hash).

    Keeps the highest-authority entry when duplicates collide (v3 §13: 同一论文
    不同镜像 URL 不能算成多个独立证据).
    """
    from retrieval.source import is_higher_authority

    unique: dict[str, dict[str, Any]] = {}
    for src in sources:
        keys = src.get("dedupe_keys", {})
        doi = (keys.get("doi") or "").strip().lower()
        canon = (keys.get("canonical_url") or "").strip().rstrip("/").lower()
        fp = keys.get("title_fingerprint") or title_fingerprint(src.get("title", ""))
        chash = keys.get("content_hash") or src.get("content_hash", "")

        chosen_key: str | None = None
        for candidate in (doi, canon, fp, chash):
            if candidate:
                chosen_key = candidate
                break
        if not chosen_key:
            continue

        existing = unique.get(chosen_key)
        if existing is None:
            unique[chosen_key] = src
            continue
        # keep the higher-authority (lower tier number) source
        if is_higher_authority(src.get("authority_level", "tier5_general_web"),
                               existing.get("authority_level", "tier5_general_web")):
            unique[chosen_key] = src
    return list(unique.values())


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
