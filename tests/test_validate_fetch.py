"""Tests for the fetch -> validate -> decide fallback integration (P0-6).

Exercises validate_fetch_result together with the fetch chain using mocked
providers; no real network access.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import retrieval.fetch as fetch_mod
from retrieval.fetch import FETCH_PROVIDERS, fetch_url
from retrieval.validate import validate_fetch_result

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
    """Install per-provider responses; anything not listed raises URLError."""
    def make(provider):
        def _fetch(url, timeout):
            if provider not in responses:
                raise fetch_mod.urllib.error.URLError("not mocked")
            return responses[provider](url)
        return _fetch

    monkeypatch.setattr(fetch_mod, "_PROVIDER_FETCHERS", {
        name: make(name) for name in FETCH_PROVIDERS
    })


def test_validate_gate_decides_chain_stop(monkeypatch):
    """The chain stops exactly when validate_fetch_result says passed=True."""
    calls = []

    def resp(provider):
        def _r(url):
            calls.append(provider)
            return 200, GOOD_BODY, "https://pnas.org/doi/10.1073/pnas.2422633122"
        return _r

    _chain(monkeypatch, {name: resp(name) for name in FETCH_PROVIDERS})
    result = fetch_url("https://doi.org/10.1073/pnas.2422633122")
    assert result["fetch_status"] == "FETCH_VALID"
    assert result["validation"]["passed"] is True
    assert result["fetch_provider"] == "builtin"
    assert calls == ["builtin"]


def test_http_200_with_error_page_keeps_falling_back(monkeypatch):
    """HTTP 200 + error page fails validation and must continue the chain."""
    error_body = ("404 not found " * 10) + ("page not found " * 10)
    calls = []

    def _r(url, provider):
        calls.append(provider)
        if provider == "builtin":
            return 200, error_body, "https://pnas.org/paper"
        return 200, GOOD_BODY, "https://pnas.org/paper"

    _chain(monkeypatch, {"builtin": lambda u: _r(u, "builtin"),
                         "jina_reader": lambda u: _r(u, "jina_reader")})
    result = fetch_url("https://pnas.org/paper")
    assert result["fetch_status"] == "FETCH_VALID"
    assert result["fetch_provider"] == "jina_reader"
    assert result["fallback_chain"] == ["builtin:200", "jina_reader:200"]
    assert calls == ["builtin", "jina_reader"]


def test_failed_fetch_validation_never_passes(monkeypatch):
    """validate_fetch_result on a FETCH_FAILED result must never pass."""
    _chain(monkeypatch, {})  # every provider raises URLError
    result = fetch_url("https://pnas.org/paper")
    assert result["fetch_status"] == "FETCH_FAILED"
    v = validate_fetch_result(result)
    assert v["passed"] is False
    assert v["checks"]["http_success"] is False


def test_validation_checks_surface_in_result(monkeypatch):
    _chain(monkeypatch, {
        "builtin": lambda u: (200, "captcha: verify you are human " * 30, "https://pnas.org/paper"),
    })
    result = fetch_url("https://pnas.org/paper")
    assert result["validation"]["checks"]["is_captcha_page"] is True
    assert result["validation"]["passed"] is False
    # No provider passed, but the captcha body is the longest readable attempt.
    assert result["fetch_status"] == "FETCH_PARTIAL"
