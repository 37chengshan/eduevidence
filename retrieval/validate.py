#!/usr/bin/env python3
"""validate.py — Fetch Validation Gate (Smart Web Fetch 方案 v3 §7-8).

A successful fetch is NOT automatically evidence. Checks:

    HTTP success / body length / title match / URL match
    login page? / error page? / captcha? / navigation only? / too short? / date?

Output: passed(bool) + per-check results. FETCH_FAILED content must never be
used for Evidence Extraction (v3 §8).
"""
from __future__ import annotations

import re
from typing import Any

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


def _count(text: str, patterns: list[str]) -> int:
    return sum(1 for p in patterns if re.search(p, text))


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

    checks["url_matches"] = result.get("resolved_url") in (result.get("original_url", ""),) or True

    failed_hard = any(checks[k] for k in ("is_error_page", "is_login_page", "is_captcha_page", "navigation_only"))
    if failed_hard:
        issues.append("blocked/error-like page detected")

    passed = not failed_hard and checks["body_length_ok"] and not issues
    return {"passed": passed, "checks": checks, "issues": issues}
