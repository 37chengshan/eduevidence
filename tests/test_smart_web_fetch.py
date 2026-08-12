"""Tests for integrations/smart_web_fetch.py — private-URL routing (P0-7).

No network access: smart_fetch is exercised with mocked provider tables.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import retrieval.fetch as fetch_mod
from integrations.smart_web_fetch import fetch_summary, is_private, smart_fetch
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


def _chain(monkeypatch, calls, resolved_url):
    def make(provider):
        def _fetch(url, timeout):
            calls.append(provider)
            return 200, GOOD_BODY, resolved_url
        return _fetch

    monkeypatch.setattr(fetch_mod, "_PROVIDER_FETCHERS", {
        name: make(name) for name in FETCH_PROVIDERS
    })


# ---------------------------------------------------------------- is_private


def test_is_private_doi_url_not_private():
    # P0-7: DOI URLs (with "10." in the path) must not be flagged private.
    assert is_private("https://doi.org/10.1145/3544548.3580919") is False
    assert is_private("https://www.pnas.org/doi/10.1073/pnas.2422633122") is False


def test_is_private_loopback_link_local():
    assert is_private("http://127.0.0.1:8000") is True
    assert is_private("http://169.254.169.254") is True
    assert is_private("http://localhost/") is True


def test_is_private_private_ranges():
    assert is_private("http://10.0.0.1/") is True
    assert is_private("http://192.168.1.5/") is True
    assert is_private("http://172.20.0.1/") is True


def test_is_private_ignores_path_hints():
    # URL path content ("10.", "login", "account") must not matter.
    assert is_private("https://example.com/login?next=/10.1145/foo") is False
    assert is_private("https://papers.example.com/10.1073/pnas.2422633122") is False


# ---------------------------------------------------------------- smart_fetch


def test_public_doi_url_uses_smart_chain(monkeypatch):
    calls = []

    def _r(url, provider):
        calls.append(provider)
        if provider == "builtin":
            return 200, "captcha: verify you are human " * 40, "https://doi.org/10.1145/3544548.3580919"
        return 200, GOOD_BODY, "https://dl.acm.org/doi/10.1145/3544548.3580919"

    def _make(provider):
        def _f(url, timeout):
            return _r(url, provider)
        return _f

    monkeypatch.setattr(fetch_mod, "_PROVIDER_FETCHERS", {name: _make(name) for name in FETCH_PROVIDERS})
    result = smart_fetch("https://doi.org/10.1145/3544548.3580919")
    # P0-7: DOI URL is public -> third-party fallback is allowed and used.
    assert result["fetch_status"] == "FETCH_VALID"
    assert result["fetch_provider"] == "jina_reader"
    assert "jina_reader" in calls


def test_private_url_native_only(monkeypatch):
    calls = []

    def _r(url, provider):
        calls.append(provider)
        return 200, GOOD_BODY, "http://127.0.0.1:8000/report"

    def _make(provider):
        def _f(url, timeout):
            return _r(url, provider)
        return _f

    monkeypatch.setattr(fetch_mod, "_PROVIDER_FETCHERS", {name: _make(name) for name in FETCH_PROVIDERS})
    result = smart_fetch("http://127.0.0.1:8000/report")
    assert result["fetch_status"] == "FETCH_VALID"
    assert result["validation"]["checks"].get("private_url_local_only") is True
    assert result["fallback_used"] is False
    assert not any(p in calls for p in ("jina_reader", "markdown_new"))


def test_fetch_summary_shape():
    result = {
        "original_url": "https://doi.org/10.x",
        "resolved_url": "https://publisher.example/10.x",
        "fetch_provider": "builtin",
        "fetch_status": "FETCH_VALID",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "fallback_used": False,
        "validation": {"passed": True},
    }
    summary = fetch_summary(result)
    assert summary["original_url"] == result["original_url"]
    assert summary["resolved_url"] == result["resolved_url"]
    assert summary["content_verified"] is True
