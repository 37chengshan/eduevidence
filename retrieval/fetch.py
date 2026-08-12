#!/usr/bin/env python3
"""fetch.py — Fetch Reliability Layer (Smart Web Fetch 方案 v3 §2-8).

Fetch only, never search. Responsibility: given a known URL, reliably read the
content and clean it into Markdown/text. Degradation chain (v3 §3 / §12):

    native (builtin)
      -> jina_reader
      -> defuddle     (local HTML -> main-text extraction, no third party)
      -> markdown_new
      -> raw_html
      -> FETCH_FAILED

Every provider attempt is validated immediately (v3 §7): only
validation.passed=True ends the chain. HTTP 200 with a captcha/login/error
page or a too-short body continues to the next provider. Each attempt records
Fetch Provenance (original_url preserved, the real resp.geturl() as
resolved_url, provider tracked). Only FETCH_VALID (or rule-confirmed
FETCH_PARTIAL) may enter Evidence Extraction; FETCH_FAILED must never let the
model guess content from search snippets (v3 §8).
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable

from retrieval.validate import (
    is_private_url,
    resolves_to_private,
    validate_fetch_result,
)

FETCH_PROVIDERS = ("builtin", "jina_reader", "defuddle", "markdown_new", "raw_html")
JINA_READER_PREFIX = "https://r.jina.ai/"
MARKDOWN_NEW_PREFIX = "https://markdown.new/"
MAX_REDIRECTS = 5
MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB
USER_AGENT = "EduEvidence/1.0 (+evidence)"

# Providers that fetch the original URL directly (locally). A private-network
# resolution on these aborts the whole chain — third-party providers must
# never receive private content.
LOCAL_PROVIDERS = ("builtin", "defuddle", "raw_html")


class _BodyTooLarge(Exception):
    """Raised when a fetch response exceeds MAX_BODY_BYTES."""


class _MaxRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler that aborts after max_redirects hops (default 5)."""

    def __init__(self, max_redirects: int = MAX_REDIRECTS):
        super().__init__()
        self.max_redirects = max_redirects

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        hops = getattr(req, "_redirect_count", 0)
        if hops >= self.max_redirects:
            raise urllib.error.HTTPError(
                req.full_url, code, f"redirect limit ({self.max_redirects}) exceeded", headers, fp
            )
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is not None:
            new_req._redirect_count = hops + 1  # type: ignore[attr-defined]
        return new_req


def _http_get(
    url: str,
    timeout: int = 20,
    max_redirects: int = MAX_REDIRECTS,
    max_bytes: int = MAX_BODY_BYTES,
) -> tuple[int, str, str]:
    """GET url; returns (status, body, resolved_url=resp.geturl()).

    Raises URLError / HTTPError / OSError / ValueError on network problems and
    _BodyTooLarge when the response exceeds max_bytes. Redirects are limited
    to max_redirects hops.
    """
    opener = urllib.request.build_opener(_MaxRedirectHandler(max_redirects))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener.open(req, timeout=timeout) as resp:
        body = resp.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise _BodyTooLarge(f"response body exceeds {max_bytes} bytes")
        return resp.status, body.decode("utf-8", errors="replace"), resp.geturl()


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- defuddle


_SKIP_TAGS = {
    "script", "style", "nav", "header", "footer", "aside", "iframe",
    "noscript", "svg", "form", "button", "select", "template",
}
_MAIN_TAGS = {"main", "article"}
_BLOCK_TAGS = {
    "p", "div", "section", "article", "main", "blockquote", "pre",
    "li", "tr", "ul", "ol", "table", "h1", "h2", "h3", "h4", "h5", "h6",
}


class _MainTextExtractor(HTMLParser):
    """html.parser-based main-content extraction (the local 'defuddle')."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._main_depth = 0
        self._in_main = False
        self._main_parts: list[str] = []
        self._fallback_parts: list[str] = []

    def _target(self) -> list[str]:
        return self._main_parts if self._in_main else self._fallback_parts

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in _MAIN_TAGS:
            if self._main_depth == 0:
                self._in_main = True
            self._main_depth += 1
        if tag in _BLOCK_TAGS:
            self._target().append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag in _MAIN_TAGS:
            self._main_depth = max(0, self._main_depth - 1)
            if self._main_depth == 0:
                self._in_main = False
        if tag in _BLOCK_TAGS:
            self._target().append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._target().append(data)

    def result(self) -> str:
        parts = self._main_parts if self._main_parts else self._fallback_parts
        text = "".join(parts)
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def extract_main_text(html: str) -> str:
    """Local HTML -> readable-text cleaning (defuddle provider).

    Drops script/style/nav/header/footer/aside etc. and prefers the text inside
    <main>/<article> when present; falls back to the full cleaned body.
    """
    parser = _MainTextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        # malformed HTML must never crash the degradation chain
        return re.sub(r"<[^>]+>", " ", html)
    return parser.result()


# ------------------------------------------------------------- providers


def _fetch_builtin(url: str, timeout: int) -> tuple[int, str, str]:
    return _http_get(url, timeout=timeout)


def _fetch_jina_reader(url: str, timeout: int) -> tuple[int, str, str]:
    return _http_get(JINA_READER_PREFIX + url, timeout=timeout)


def _fetch_defuddle(url: str, timeout: int) -> tuple[int, str, str]:
    return _http_get(url, timeout=timeout)


def _fetch_markdown_new(url: str, timeout: int) -> tuple[int, str, str]:
    return _http_get(MARKDOWN_NEW_PREFIX + url, timeout=timeout)


def _fetch_raw_html(url: str, timeout: int) -> tuple[int, str, str]:
    return _http_get(url, timeout=timeout)


_PROVIDER_FETCHERS: dict[str, Callable[[str, int], tuple[int, str, str]]] = {
    "builtin": _fetch_builtin,
    "jina_reader": _fetch_jina_reader,
    "defuddle": _fetch_defuddle,
    "markdown_new": _fetch_markdown_new,
    "raw_html": _fetch_raw_html,
}


def _clean_for_provider(provider: str, body: str) -> str:
    if provider in ("builtin", "raw_html"):
        return _strip_html_to_text(body)
    if provider == "defuddle":
        return extract_main_text(body)
    return body.strip()  # jina_reader / markdown_new already return text


def _strip_html_to_text(html: str) -> str:
    """Minimal HTML noise reduction: drop scripts/styles/nav, keep text."""
    html = re.sub(r"(?is)<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def _build_candidate(
    *,
    original_url: str,
    provider: str,
    status: int,
    body: str,
    resolved_url: str,
    fetched_at: str,
    expect_title: str | None,
) -> "FetchResult":
    """Turn one raw provider response into a validated FetchResult candidate."""
    ok = status < 400 and bool(body.strip())
    clean = _clean_for_provider(provider, body) if ok else ""
    cand = FetchResult(
        original_url=original_url,
        resolved_url=resolved_url or original_url,
        fetch_provider=provider,
        fetch_status="FETCH_VALID" if ok else "FETCH_FAILED",
        fetched_at=fetched_at,
        raw_size=len(body.encode("utf-8")),
        content=clean,
    )
    cand.clean_size = len(clean.encode("utf-8")) if clean else 0
    cand.content_hash = _hash(clean) if clean else ""
    cand.content_length = cand.clean_size
    if cand.raw_size > 0 and cand.clean_size > 0:
        cand.compression_ratio = 1 - (cand.clean_size / cand.raw_size)
    cand.validation = validate_fetch_result(cand.to_dict(), expect_title=expect_title)
    return cand


def _copy_candidate(target: "FetchResult", cand: "FetchResult", *, status: str) -> None:
    """Copy a candidate's content/provenance into the final result."""
    target.resolved_url = cand.resolved_url
    target.fetch_provider = cand.fetch_provider
    target.fetch_status = status
    target.content = cand.content
    target.raw_size = cand.raw_size
    target.clean_size = cand.clean_size
    target.compression_ratio = cand.compression_ratio
    target.content_hash = cand.content_hash
    target.content_length = cand.content_length
    target.validation = cand.validation


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


def fetch_url(
    url: str,
    *,
    use_smart_fetch: bool = True,
    timeout: int = 20,
    expect_title: str | None = None,
) -> dict[str, Any]:
    """Fetch a URL through the degradation chain.

    fetch -> validate -> decide fallback per provider: each attempt is validated
    immediately and only validation.passed=True ends the chain; HTTP 200 with a
    captcha/login/error page or a too-short body continues to the next provider.
    If no provider passes, the best readable attempt is kept as FETCH_PARTIAL
    (rule-confirmed before extraction), otherwise FETCH_FAILED. Never raises
    for content issues.

    Private targets (original URL private, or a redirect/DNS resolution landing
    on a private network) abort the chain: third-party providers never see
    private content.
    """
    result = FetchResult(original_url=url, fetched_at=datetime.now(timezone.utc).isoformat())
    # Private URLs are handled locally only (no third-party cleaning providers).
    chain = FETCH_PROVIDERS if use_smart_fetch else ("builtin", "raw_html")
    original_private = is_private_url(url)
    best_partial: FetchResult | None = None

    for provider in chain:
        if result.fetch_status == "FETCH_VALID":
            break
        try:
            status, body, resolved_url = _PROVIDER_FETCHERS[provider](url, timeout)
        except (_BodyTooLarge, urllib.error.URLError, OSError, ValueError):
            result.fallback_chain.append(f"{provider}:error")
            continue
        result.fallback_chain.append(f"{provider}:{status}")

        # Security gate: a public request that resolves (directly or via DNS)
        # to a private network must abort the whole chain.
        if provider in LOCAL_PROVIDERS and not original_private:
            if is_private_url(resolved_url) or resolves_to_private(resolved_url) is True:
                result.fallback_chain.append(f"{provider}:private_target")
                result.validation = {
                    "passed": False,
                    "checks": {"private_target": True, "http_success": False},
                    "issues": ["fetch resolved to a private/local network; chain aborted"],
                }
                return result.to_dict()

        cand = _build_candidate(
            original_url=url,
            provider=provider,
            status=status,
            body=body,
            resolved_url=resolved_url,
            fetched_at=result.fetched_at,
            expect_title=expect_title,
        )
        if cand.validation.get("passed"):
            # The gate passed: accept this provider's content and stop.
            _copy_candidate(result, cand, status="FETCH_VALID")
            result.fallback_used = provider != "builtin"
            break
        # Validation failed (captcha / login / error / short body / URL
        # mismatch): keep the best readable attempt as FETCH_PARTIAL and
        # continue down the chain.
        if cand.fetch_status == "FETCH_VALID" and (
            best_partial is None or cand.clean_size > best_partial.clean_size
        ):
            best_partial = cand

    if result.fetch_status != "FETCH_VALID":
        if best_partial is not None:
            _copy_candidate(result, best_partial, status="FETCH_PARTIAL")
            result.fallback_used = True
        else:
            result.fetch_status = "FETCH_FAILED"
            result.validation = {
                "passed": False,
                "checks": {"http_success": False, "body_length_ok": False},
                "issues": ["all providers failed"],
            }

    return result.to_dict()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: fetch.py <url> [expected_title]", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(fetch_url(sys.argv[1], expect_title=sys.argv[2] if len(sys.argv) > 2 else None),
                     ensure_ascii=False, indent=2))
