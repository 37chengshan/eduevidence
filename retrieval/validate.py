#!/usr/bin/env python3
"""validate.py — Fetch Validation Gate (Smart Web Fetch 方案 v3 §7-8).

A successful fetch is NOT automatically evidence. Checks:

    HTTP success / body length / title match / URL match
    login page? / error page? / captcha? / navigation only? / too short?
    scheme whitelist (http/https) / private-network target (incl. redirects)

Output: passed(bool) + per-check results. FETCH_FAILED content must never be
used for Evidence Extraction (v3 §8).
"""
from __future__ import annotations

import ipaddress
import re
import socket
from typing import Any
from urllib.parse import urlparse

ERROR_PATTERNS = [
    r"(?i)404 not found",
    r"(?i)page not found",
    r"(?i)access denied",
    r"(?i)forbidden",
    r"(?i)service unavailable",
]
LOGIN_PATTERNS = [
    r"(?i)sign in to continue",
    r"(?i)please log in",
    r"(?i)login required",
]
CAPTCHA_PATTERNS = [
    r"(?i)captcha",
    r"(?i)verify you are human",
    r"(?i)cloudflare",
    r"(?i)robot check",
]
NAV_ONLY_MARKERS = ["menu", "home", "about us", "contact us", "privacy policy"]

ALLOWED_SCHEMES = ("http", "https")

# Third-party cleaning providers fetch a wrapped URL (r.jina.ai/<url>), not the
# original — a resolved-vs-original URL equality check is meaningless for them.
WRAPPER_PROVIDERS = ("jina_reader", "markdown_new")


def _count(text: str, patterns: list[str]) -> int:
    return sum(1 for p in patterns if re.search(p, text))


# ---------------------------------------------------------------- private URL


_CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")


def _ip_is_private(addr: ipaddress._BaseAddress) -> bool:
    """Loopback / private / link-local / CGNAT / reserved / multicast / unspecified."""
    return (
        addr.is_loopback
        or addr.is_private
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
        or addr in _CGNAT_NET
    )


def is_private_url(url: str) -> bool:
    """True if the URL targets a private/local/unsafe location.

    Host-based judgement only (urllib.parse.urlparse + ipaddress): loopback,
    private, link-local, CGNAT, reserved, multicast and unspecified address
    ranges, plus local hostnames (localhost / *.localhost / *.local). URL path
    content — e.g. a DOI's "10." prefix — never influences the verdict.

    Non-http(s) schemes (file://, ftp://, data:, ...) also count as private:
    such URLs must never reach third-party cleaning providers.
    """
    if not url:
        return True
    try:
        parsed = urlparse(url)
    except ValueError:
        return True
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        return True
    host = (parsed.hostname or "").lower()
    if not host:
        return True
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        return True
    try:
        addr = ipaddress.ip_address(host)  # IPv4 literals and bracketed IPv6
    except ValueError:
        return False  # a normal DNS name is not private by itself
    return _ip_is_private(addr)


def resolves_to_private(url: str) -> bool | None:
    """Best-effort DNS re-check: does the URL's host resolve to a private IP?

    Guards against redirect targets whose hostname resolves to a loopback /
    private address (e.g. DNS-rebinding style redirects). Returns None when
    the host cannot be resolved — that is treated as "not private" by callers.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return True
    host = parsed.hostname
    if not host:
        return True
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return is_private_url(url)  # literal IP: judge directly
    try:
        infos = socket.getaddrinfo(host, parsed.port or 80, proto=socket.IPPROTO_TCP)
    except OSError:
        return None
    for info in infos:
        try:
            addr = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if _ip_is_private(addr):
            return True
    return False


# ------------------------------------------------------------- URL comparison


def _normalize_url(url: str) -> str:
    """Normalize for comparison: lowercase scheme/host, drop default port,
    strip fragment and trailing slash."""
    try:
        p = urlparse(url)
    except ValueError:
        return url
    scheme = (p.scheme or "").lower()
    host = (p.hostname or "").lower()
    if p.port is None or p.port == {"http": 80, "https": 443}.get(scheme):
        port_str = ""
    else:
        port_str = f":{p.port}"
    path = p.path.rstrip("/") or "/"
    query = f"?{p.query}" if p.query else ""
    return f"{scheme}://{host}{port_str}{path}{query}"


def _same_path_and_query(resolved: str, original: str) -> bool:
    """True when both URLs denote the same resource path/query even if the host
    changed — the canonical doi.org -> publisher redirect pattern."""
    try:
        rp = urlparse(resolved)
        op = urlparse(original)
    except ValueError:
        return False
    return (rp.path.rstrip("/") or "/") == (op.path.rstrip("/") or "/") and rp.query == op.query


def _same_doi(resolved: str, original: str) -> bool:
    """True when both URLs reference the same DOI (doi.org -> publisher hops)."""
    from retrieval.source import parse_doi_from_url

    r_doi = parse_doi_from_url(resolved)
    o_doi = parse_doi_from_url(original)
    return bool(r_doi and o_doi and r_doi.lower() == o_doi.lower())


# ---------------------------------------------------------------- validation


def validate_fetch_result(result: dict[str, Any], *, expect_title: str | None = None) -> dict[str, Any]:
    """Run the Fetch Validation Gate over a fetch result dict.

    Returns {"passed": bool, "checks": {...}, "issues": [...]}.
    """
    content = result.get("content", "") or ""
    status = result.get("fetch_status", "FETCH_FAILED")
    checks: dict[str, Any] = {}
    issues: list[str] = []

    if status == "FETCH_FAILED":
        checks["http_success"] = False
        checks["body_length_ok"] = False
        return {"passed": False, "checks": checks, "issues": ["FETCH_FAILED: no content"]}

    checks["http_success"] = True
    checks["body_length_ok"] = len(content) >= 200
    if not checks["body_length_ok"]:
        issues.append("body too short")

    checks["is_error_page"] = _count(content, ERROR_PATTERNS) >= 2
    checks["is_login_page"] = _count(content, LOGIN_PATTERNS) >= 1
    checks["is_captcha_page"] = _count(content, CAPTCHA_PATTERNS) >= 1
    checks["navigation_only"] = all(m in content.lower() for m in NAV_ONLY_MARKERS) and len(content) < 1000

    if expect_title:
        title = content.splitlines()[0].strip() if content.splitlines() else ""
        checks["title_matches"] = expect_title.lower() in (title.lower() or content[:200].lower())
        if not checks["title_matches"]:
            issues.append("expected title not found in content head")
    else:
        checks["title_matches"] = None

    # URL match: real comparison between the resolved URL (resp.geturl(), after
    # redirects) and the original URL. Wrapper providers fetch a different URL
    # by design, so the check is not applicable (None) for them.
    provider = result.get("fetch_provider", "")
    resolved_url = result.get("resolved_url") or ""
    original_url = result.get("original_url") or ""
    if provider in WRAPPER_PROVIDERS or not resolved_url or not original_url:
        checks["url_matches"] = None
    else:
        checks["url_matches"] = (
            _normalize_url(resolved_url) == _normalize_url(original_url)
            or _same_path_and_query(resolved_url, original_url)
            or _same_doi(resolved_url, original_url)
        )
        if not checks["url_matches"]:
            issues.append("resolved URL does not match original URL")

    # Scheme whitelist: only http/https may enter Evidence Extraction.
    if original_url:
        checks["scheme_allowed"] = (urlparse(original_url).scheme or "").lower() in ALLOWED_SCHEMES
        if not checks["scheme_allowed"]:
            issues.append("unsupported URL scheme (only http/https)")
    else:
        checks["scheme_allowed"] = None

    # Private-target re-check after redirects/DNS. A public request that landed
    # on a private network is a security event and must fail; a local request
    # (original already private, fetched natively) stays usable.
    if resolved_url and original_url:
        original_private = is_private_url(original_url)
        checks["private_target"] = is_private_url(resolved_url)
        if checks["private_target"] and not original_private:
            issues.append("fetch resolved to a private/local network")
    elif resolved_url:
        checks["private_target"] = is_private_url(resolved_url)
    else:
        checks["private_target"] = None

    failed_hard = any(checks[k] for k in ("is_error_page", "is_login_page", "is_captcha_page", "navigation_only"))
    if failed_hard:
        issues.append("blocked/error-like page detected")

    passed = not failed_hard and checks["body_length_ok"] and not issues
    return {"passed": passed, "checks": checks, "issues": issues}
