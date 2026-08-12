#!/usr/bin/env python3
"""source.py — Source Registry (总体实施计划 §11 / Smart Web Fetch v3 §9, §14).

Unified source structure; Evidence Objects reference only source_id. The fetch
provider is a reading path and must NEVER be shown as the citation target
(v3 §6): r.jina.ai / markdown.new / defuddle are not papers.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

AUTHORITY_LEVELS = {
    "tier1_paper_doi": 1,
    "tier2_academic_database": 2,
    "tier3_professional_institution": 3,
    "tier4_news_secondary": 4,
    "tier5_general_web": 5,
}


def title_fingerprint(title: str) -> str:
    """Normalized title fingerprint for dedup (v3 §13): lowercase, alnum only."""
    norm = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", title.lower())
    return norm[:64]


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def make_source(
    *,
    source_id: str,
    title: str,
    canonical_url: str,
    authority_level: str,
    source_type: str = "paper",
    authors: list[str] | None = None,
    year: int | None = None,
    doi: str | None = None,
    discovered_by: str = "search",
    discovery_provider: str = "",
    fetch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a Source Object with dedupe keys precomputed."""
    if authority_level not in AUTHORITY_LEVELS:
        raise ValueError(f"unknown authority_level {authority_level!r}")
    # Auto-extract DOI from a doi.org/dx.doi.org URL when not given explicitly,
    # so the same paper behind a doi.org URL and a mirror URL dedupes correctly.
    if not doi:
        doi = parse_doi_from_url(canonical_url)
    return {
        "source_id": source_id,
        "title": title,
        "authors": authors or [],
        "year": year,
        "doi": doi or "",
        "canonical_url": canonical_url,
        "source_type": source_type,
        "authority_level": authority_level,
        "discovered_by": discovered_by,
        "discovery_provider": discovery_provider,
        "fetch": fetch or {},
        "content_hash": (fetch or {}).get("content_hash", ""),
        "dedupe_keys": {
            "canonical_url": canonical_url.rstrip("/"),
            "doi": (doi or "").lower(),
            "title_fingerprint": title_fingerprint(title),
            "content_hash": (fetch or {}).get("content_hash", ""),
        },
        "status": "DISCOVERED",
    }


def is_higher_authority(a: str, b: str) -> bool:
    """True if source a is a more authoritative tier than source b."""
    return AUTHORITY_LEVELS.get(a, 5) < AUTHORITY_LEVELS.get(b, 5)


def parse_doi_from_url(url: str) -> str | None:
    """Extract a DOI from common URL shapes:
    https://doi.org/10.xxxx/yyyy · https://dx.doi.org/10.xxxx/yyyy ·
    https://dl.acm.org/doi/10.xxxx/yyyy · any URL containing a bare DOI.
    """
    if not url:
        return None
    m = re.search(r"(10\.\d{4,9}/[^\s/?&#;]+)", url, re.I)
    return m.group(1).rstrip(")") if m else None


def update_source_status(source: dict[str, Any], status: str) -> dict[str, Any]:
    source["status"] = status
    return source
