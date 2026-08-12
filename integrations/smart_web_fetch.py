#!/usr/bin/env python3
"""smart_web_fetch.py — Smart Web Fetch integration wrapper (v3 方案).

Positioning: Fetch Reliability Layer, NOT a search layer. It reads a known URL
reliably through the provider degradation chain and records provenance.

Security principles (v3 §26):
  - record provider, keep original_url
  - NEVER send private/login/session pages to third-party cleaning services
  - never send local files; never send private teaching data
  - private materials are handled locally only

Usage:
    from integrations.smart_web_fetch import smart_fetch
    result = smart_fetch("https://doi.org/10.xxxx", expect_title="...")
    # result["fetch_status"] in {"FETCH_VALID", "FETCH_PARTIAL", "FETCH_FAILED"}
"""
from __future__ import annotations

from typing import Any

from retrieval.fetch import fetch_url
from retrieval.validate import is_private_url


def is_private(url: str) -> bool:
    """Private/local URLs must never go through third-party cleaning providers.

    Host-based judgement (urllib.parse.urlparse + ipaddress): loopback, private,
    link-local, CGNAT, reserved ranges and local hostnames. URL path content —
    e.g. a DOI's "10." prefix — never influences the verdict, so
    https://doi.org/10.1145/... is NOT private. See retrieval.validate.is_private_url.
    """
    return is_private_url(url)


def smart_fetch(url: str, *, expect_title: str | None = None, timeout: int = 20) -> dict[str, Any]:
    """Fetch a known URL through the Smart Web Fetch chain.

    Private URLs are fetched natively only (no third-party cleaning).
    """
    if is_private(url):
        result = fetch_url(url, use_smart_fetch=False, timeout=timeout, expect_title=expect_title)
        result["validation"]["checks"]["private_url_local_only"] = True
        return result
    return fetch_url(url, use_smart_fetch=True, timeout=timeout, expect_title=expect_title)


def fetch_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Compact fetch provenance summary for report Sources & Provenance panel."""
    return {
        "original_url": result.get("original_url"),
        "resolved_url": result.get("resolved_url"),
        "fetch_provider": result.get("fetch_provider"),
        "fetch_status": result.get("fetch_status"),
        "fetched_at": result.get("fetched_at"),
        "fallback_used": result.get("fallback_used", False),
        "content_verified": result.get("validation", {}).get("passed", False),
    }
