"""Regression tests for integrations/smart_web_fetch.py — private-URL routing and
fetch provenance summary (review P0-1/P0-7).

No network access: smart_fetch is exercised with mocked provider tables.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import retrieval.fetch as fetch_mod
from integrations.smart_web_fetch import fetch_summary, smart_fetch
from retrieval.fetch import FETCH_PROVIDERS

GOOD_BODY = (
    "Generative AI without guardrails can harm learning: evidence from high school mathematics. "
    "We ran a three-arm randomized controlled trial with nearly a thousand high school students "
    "in Turkey. Unguarded GPT-4 access improved practice performance but harmed independent exam "
    "performance by seventeen percent. Teacher-designed guardrails largely eliminated the "
    "negative learning effect. These findings have direct implications for classroom AI policy."
)


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("unexpected real network access")
    monkeypatch.setattr(fetch_mod, "_http_get", boom)
    # DNS is part of the network layer: mock hosts resolve publicly.
    monkeypatch.setattr(fetch_mod, "resolves_to_private", lambda url: False)


def _chain(monkeypatch, responses):
    def make(provider):
        def _fetch(url, timeout):
            if provider not in responses:
                raise fetch_mod.urllib.error.URLError("not mocked")
            return responses[provider](url)
        return _fetch

    monkeypatch.setattr(fetch_mod, "_PROVIDER_FETCHERS", {
        name: make(name) for name in FETCH_PROVIDERS
    })


# ------------------------------------------------------------------- routing


def test_public_url_redirect_to_private_aborts_chain(monkeypatch):
    # P0-1: a public request that resolves to a private network must abort the
    # whole chain — third-party providers never see the private content.
    def _r(url, provider):
        if provider == "builtin":
            return 200, GOOD_BODY, "http://127.0.0.1:8000/secret"
        return 200, GOOD_BODY, "https://pnas.org/paper"

    _chain(monkeypatch, {"builtin": lambda u: _r(u, "builtin"),
                         "jina_reader": lambda u: _r(u, "jina_reader")})
    result = smart_fetch("https://pnas.org/paper")
    assert result["fetch_status"] == "FETCH_FAILED"
    assert result["validation"]["passed"] is False
    assert result["fallback_chain"] == ["builtin:200", "builtin:private_target"]
    assert "jina_reader" not in result["fallback_chain"]


def test_private_url_only_uses_native_chain(monkeypatch):
    # Third-party cleaning providers must never be called for a private URL.
    calls = []

    def _r(url, provider):
        calls.append(provider)
        return 200, GOOD_BODY, "http://127.0.0.1:8000/report"

    _chain(monkeypatch, {name: (lambda u, p=name: _r(u, p)) for name in FETCH_PROVIDERS})
    result = smart_fetch("http://127.0.0.1:8000/report")
    assert result["fetch_status"] == "FETCH_VALID"
    assert result["validation"]["checks"].get("private_url_local_only") is True
    assert calls == ["builtin"]  # native chain only, stops at first pass
    assert "jina_reader" not in calls and "markdown_new" not in calls


def test_wrapper_provider_resolved_url_is_na_not_failure(monkeypatch):
    # jina_reader fetches r.jina.ai/<url>: the resolved URL differs by design,
    # so the gate must treat url_matches as N/A — not a failure.
    _chain(monkeypatch, {
        "builtin": lambda u: (200, "captcha: verify you are human " * 30,
                              "https://doi.org/10.1145/3544548.3580919"),
        "jina_reader": lambda u: (200, GOOD_BODY,
                                  "https://r.jina.ai/https://doi.org/10.1145/3544548.3580919"),
    })
    result = smart_fetch("https://doi.org/10.1145/3544548.3580919")
    assert result["fetch_status"] == "FETCH_VALID"
    assert result["fetch_provider"] == "jina_reader"
    assert result["validation"]["checks"]["url_matches"] is None
    assert result["validation"]["passed"] is True


# --------------------------------------------------------------- fetch_summary


def test_fetch_summary_partial_content_not_verified():
    partial = {
        "original_url": "https://pnas.org/paper",
        "resolved_url": "https://pnas.org/paper",
        "fetch_provider": "builtin",
        "fetch_status": "FETCH_PARTIAL",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "fallback_used": True,
        "validation": {"passed": False},
    }
    s = fetch_summary(partial)
    assert s["fetch_status"] == "FETCH_PARTIAL"
    assert s["fallback_used"] is True
    assert s["content_verified"] is False  # partial content is NOT verified


def test_fetch_summary_failed_content_not_verified():
    failed = {
        "original_url": "https://pnas.org/paper",
        "resolved_url": "",
        "fetch_provider": "",
        "fetch_status": "FETCH_FAILED",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "fallback_used": True,
        "validation": {"passed": False},
    }
    s = fetch_summary(failed)
    assert s["fetch_status"] == "FETCH_FAILED"
    assert s["content_verified"] is False


def test_fetch_summary_missing_validation_defaults_false():
    # No validation verdict -> not verified (fail closed).
    s = fetch_summary({"fetch_status": "FETCH_VALID"})
    assert s["content_verified"] is False
