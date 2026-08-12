#!/usr/bin/env python3
"""fetch.py — Fetch Reliability Layer (Smart Web Fetch 方案 v3 §2-8).

Fetch only, never search. Responsibility: given a known URL, reliably read the
content and clean it into Markdown/text. Degradation chain (v3 §3 / §12):

    native (built-in fetch)
      -> jina_reader
      -> markdown_new
      -> defuddle
      -> raw_html
      -> FETCH_FAILED

Every attempt records Fetch Provenance (original_url preserved, provider
tracked). Only FETCH_VALID (or rule-confirmed FETCH_PARTIAL) may enter
Evidence Extraction; FETCH_FAILED must never let the model guess content
from search snippets (v3 §8).
"""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from retrieval.validate import validate_fetch_result

FETCH_PROVIDERS = ("builtin", "jina_reader", "markdown_new", "defuddle", "raw_html")
JINA_READER_PREFIX = "https://r.jina.ai/"
MARKDOWN_NEW_PREFIX = "https://markdown.new/"


@dataclass
class FetchResult:
    """One fetch attempt outcome (mirrors schemas/fetch-result.schema.json)."""

    original_url: str
    resolved_url: str = ""
    fetch_method: str = "smart_web_fetch"
    fetch_provider: str = "builtin"
    fetch_status: str = "FETCH_FAILED"
    fetched_at: str = ""
    content_hash: str = ""
    content_length: int = 0
    raw_size: int = 0
    clean_size: int = 0
    compression_ratio: float = 0.0
    fallback_used: bool = False
    fallback_chain: list[str] = field(default_factory=list)
    content: str = ""
    validation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_url": self.original_url,
            "resolved_url": self.resolved_url,
            "fetch_method": self.fetch_method,
            "fetch_provider": self.fetch_provider,
            "fetch_status": self.fetch_status,
            "fetched_at": self.fetched_at,
            "content_hash": self.content_hash,
            "content_length": self.content_length,
            "raw_size": self.raw_size,
            "clean_size": self.clean_size,
            "compression_ratio": round(self.compression_ratio, 3),
            "fallback_used": self.fallback_used,
            "fallback_chain": self.fallback_chain,
            "content": self.content if self.fetch_status != "FETCH_FAILED" else "",
            "validation": self.validation,
        }


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _http_get(url: str, timeout: int = 20) -> tuple[int, str]:
    """Best-effort native GET; returns (status, body). Raises on network error."""
    req = urllib.request.Request(url, headers={"User-Agent": "EduEvidence/1.0 (+evidence)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def _strip_html_to_text(html: str) -> str:
    """Minimal HTML noise reduction: drop scripts/styles/nav, keep text."""
    import re

    html = re.sub(r"(?is)<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def fetch_url(
    url: str,
    *,
    use_smart_fetch: bool = True,
    timeout: int = 20,
    expect_title: str | None = None,
) -> dict[str, Any]:
    """Fetch a URL through the degradation chain.

    Returns a FetchResult dict. Never raises for content issues — worst case is
    fetch_status == "FETCH_FAILED" with a recorded fallback_chain.
    """
    result = FetchResult(original_url=url, fetched_at=datetime.now(timezone.utc).isoformat())

    # --- attempt 0: builtin native fetch ---
    try:
        status, raw = _http_get(url, timeout=timeout)
        result.resolved_url = url
        result.raw_size = len(raw.encode("utf-8"))
        result.fetch_provider = "builtin"
        if status >= 400:
            result.fetch_status = "FETCH_FAILED"
        else:
            clean = _strip_html_to_text(raw)
            result.content = clean
            result.clean_size = len(clean.encode("utf-8"))
            result.fetch_status = "FETCH_VALID"
        result.fallback_chain.append("builtin")
    except (urllib.error.URLError, OSError, ValueError):
        result.fallback_chain.append("builtin:error")

    # --- degradation chain (only if smart fetch enabled and not yet valid) ---
    if use_smart_fetch and result.fetch_status != "FETCH_VALID":
        for provider, wrap in (
            ("jina_reader", lambda u: JINA_READER_PREFIX + u),
            ("markdown_new", lambda u: MARKDOWN_NEW_PREFIX + u),
        ):
            try:
                status, body = _http_get(wrap(url), timeout=timeout)
                result.fallback_used = True
                result.fallback_chain.append(f"{provider}:{status}")
                if status < 400 and len(body.strip()) > 200:
                    result.content = body.strip()
                    result.resolved_url = url  # original URL stays the citation target
                    result.fetch_provider = provider
                    result.fetch_status = "FETCH_VALID"
                    break
            except (urllib.error.URLError, OSError, ValueError):
                result.fallback_chain.append(f"{provider}:error")

    # --- final raw-html attempt ---
    if result.fetch_status != "FETCH_VALID":
        try:
            status, raw = _http_get(url, timeout=timeout)
            if status < 400 and len(raw.strip()) > 200:
                result.fallback_used = True
                result.fallback_chain.append("raw_html:ok")
                result.content = _strip_html_to_text(raw)
                result.fetch_provider = "raw_html"
                result.fetch_status = "FETCH_PARTIAL"
        except (urllib.error.URLError, OSError, ValueError):
            result.fallback_chain.append("raw_html:error")

    # --- finalize ---
    result.content_hash = _hash(result.content) if result.content else ""
    result.content_length = len(result.content.encode("utf-8")) if result.content else 0
    if result.raw_size > 0 and result.clean_size > 0:
        result.compression_ratio = 1 - (result.clean_size / result.raw_size)

    # --- Validation Gate (v3 §7) ---
    result.validation = validate_fetch_result(result.to_dict(), expect_title=expect_title)
    if result.fetch_status == "FETCH_VALID" and not result.validation.get("passed", False):
        result.fetch_status = "FETCH_PARTIAL"

    return result.to_dict()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: fetch.py <url> [expected_title]", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(fetch_url(sys.argv[1], expect_title=sys.argv[2] if len(sys.argv) > 2 else None),
                     ensure_ascii=False, indent=2))
