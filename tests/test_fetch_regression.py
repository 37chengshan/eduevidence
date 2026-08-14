"""Regression tests for retrieval/fetch.py — the Validation Gate drives the chain.

P0-1 acceptance criteria at chain level: every provider attempt is validated
immediately, HTTP 200 with a login/captcha/error page or a too-short body keeps
falling back to the next provider in order, and ONLY validation.passed=True ends
the chain. Mocked provider table only — no real network access.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import retrieval.fetch as fetch_mod
from retrieval.fetch import FETCH_PROVIDERS, fetch_url

GOOD_BODY = (
    "Generative AI without guardrails can harm learning: evidence from high school mathematics. "
    "We ran a three-arm randomized controlled trial with nearly a thousand high school students "
    "in Turkey. Unguarded GPT-4 access improved practice performance but harmed independent exam "
    "performance by seventeen percent. Teacher-designed guardrails largely eliminated the "
    "negative learning effect. These findings have direct implications for classroom AI policy."
)

LOGIN_BODY = "sign in to continue: login required " * 30
CAPTCHA_BODY = "captcha: please verify you are human " * 40
ERROR_BODY = ("404 not found " * 10) + ("page not found " * 10)
NAV_BODY = "menu home about us contact us privacy policy " * 20  # all nav markers, < 1000 chars
SHORT_BODY = "too short."


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    """Never touch the network in tests: all fetches go through mocks."""
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


# ------------------------------------------------- gate drives the chain order


def test_blocked_200_pages_continue_in_provider_order(monkeypatch):
    # P0-1: HTTP 200 + login/captcha/error pages each fail the gate and the
    # chain keeps trying the next provider, in order, until one passes.
    calls = []

    def _r(url, provider):
        calls.append(provider)
        return {
            "builtin": (200, LOGIN_BODY, "https://pnas.org/paper"),
            "jina_reader": (200, CAPTCHA_BODY, "https://pnas.org/paper"),
            "defuddle": (200, ERROR_BODY, "https://pnas.org/paper"),
            "markdown_new": (200, GOOD_BODY, "https://pnas.org/paper"),
            "raw_html": (200, GOOD_BODY, "https://pnas.org/paper"),
        }[provider]

    _chain(monkeypatch, {name: (lambda u, p=name: _r(u, p)) for name in FETCH_PROVIDERS})
    result = fetch_url("https://pnas.org/paper")
    assert result["fetch_status"] == "FETCH_VALID"
    assert result["fetch_provider"] == "markdown_new"
    assert calls == ["builtin", "jina_reader", "defuddle", "markdown_new"]
    assert result["fallback_chain"] == ["builtin:200", "jina_reader:200", "defuddle:200", "markdown_new:200"]
    assert result["validation"]["passed"] is True


def test_every_provider_blocked_ends_partial_never_valid(monkeypatch):
    # All providers return 200 blocked/short pages: the best readable attempt is
    # kept as FETCH_PARTIAL with a failed gate — never FETCH_VALID.
    bodies = {
        "builtin": LOGIN_BODY,
        "jina_reader": CAPTCHA_BODY,
        "defuddle": ERROR_BODY,
        "markdown_new": NAV_BODY,
        "raw_html": SHORT_BODY,
    }

    def _r(url, provider):
        return 200, bodies[provider], "https://pnas.org/paper"

    _chain(monkeypatch, {name: (lambda u, p=name: _r(u, p)) for name in FETCH_PROVIDERS})
    result = fetch_url("https://pnas.org/paper")
    assert result["fetch_status"] == "FETCH_PARTIAL"
    assert result["validation"]["passed"] is False
    # The captcha body is the longest readable attempt -> best partial.
    assert result["fetch_provider"] == "jina_reader"
    assert result["fallback_chain"] == [
        "builtin:200", "jina_reader:200", "defuddle:200", "markdown_new:200", "raw_html:200",
    ]


def test_gate_runs_immediately_after_each_attempt(monkeypatch):
    # The chain stops at the FIRST provider whose validation passes; later
    # providers are never called.
    calls = []

    def _r(url, provider):
        calls.append(provider)
        if provider in ("builtin", "jina_reader"):
            return 200, SHORT_BODY, "https://pnas.org/paper"
        return 200, GOOD_BODY, "https://pnas.org/paper"

    _chain(monkeypatch, {name: (lambda u, p=name: _r(u, p)) for name in FETCH_PROVIDERS})
    result = fetch_url("https://pnas.org/paper")
    assert result["fetch_provider"] == "defuddle"
    assert result["fetch_status"] == "FETCH_VALID"
    assert calls == ["builtin", "jina_reader", "defuddle"]  # markdown_new / raw_html never tried


# ------------------------------------------------- url mismatch at chain level


def test_mismatched_resolved_url_continues_to_next_provider(monkeypatch):
    # P0-1: url_matches is a real comparison in the chain too — a non-wrapper
    # provider whose resolved_url points elsewhere (different host AND path)
    # fails the gate and the chain moves on to the next non-wrapper provider.
    # (jina_reader is a wrapper provider whose URL check is N/A by design, so it
    # is mocked as a provider error here to keep the URL gate exercised.)
    def _r(url, provider):
        if provider == "builtin":
            return 200, GOOD_BODY, "https://attacker.example/mirror"
        return 200, GOOD_BODY, "https://www.pnas.org/doi/10.1073/pnas.2422633122"

    _chain(monkeypatch, {"builtin": lambda u: _r(u, "builtin"),
                         "defuddle": lambda u: _r(u, "defuddle")})
    result = fetch_url("https://www.pnas.org/doi/10.1073/pnas.2422633122")
    assert result["fetch_status"] == "FETCH_VALID"
    assert result["fetch_provider"] == "defuddle"
    # builtin: URL gate failed (real comparison); jina_reader: provider error;
    # defuddle: first candidate whose url_matches is a real True.
    assert result["fallback_chain"] == ["builtin:200", "jina_reader:error", "defuddle:200"]
    assert result["validation"]["checks"]["url_matches"] is True


# ------------------------------------------------------ title gate at chain level


def test_expected_title_mismatch_continues_chain(monkeypatch):
    expect = "Randomized Controlled Trial of AI Tutors"

    def _r(url, provider):
        if provider == "builtin":
            return 200, GOOD_BODY, "https://pnas.org/paper"  # no matching title line
        return 200, f"{expect}\n{GOOD_BODY}", "https://pnas.org/paper"

    _chain(monkeypatch, {"builtin": lambda u: _r(u, "builtin"),
                         "jina_reader": lambda u: _r(u, "jina_reader")})
    result = fetch_url("https://pnas.org/paper", expect_title=expect)
    assert result["fetch_status"] == "FETCH_VALID"
    assert result["fetch_provider"] == "jina_reader"
    assert result["validation"]["checks"]["title_matches"] is True


# ------------------------------------------------------------- HTTP status gate


def test_http_error_status_continues_to_next_provider(monkeypatch):
    def _r(url, provider):
        if provider == "builtin":
            return 500, "<html>server error</html>", "https://pnas.org/paper"
        return 200, GOOD_BODY, "https://pnas.org/paper"

    _chain(monkeypatch, {"builtin": lambda u: _r(u, "builtin"),
                         "jina_reader": lambda u: _r(u, "jina_reader")})
    result = fetch_url("https://pnas.org/paper")
    assert result["fetch_status"] == "FETCH_VALID"
    assert result["fetch_provider"] == "jina_reader"
    assert result["fallback_chain"] == ["builtin:500", "jina_reader:200"]


def test_all_providers_http_error_returns_failed(monkeypatch):
    def _r(url, provider):
        return 500, "Internal Server Error", "https://pnas.org/paper"

    _chain(monkeypatch, {name: (lambda u, p=name: _r(u, p)) for name in FETCH_PROVIDERS})
    result = fetch_url("https://pnas.org/paper")
    assert result["fetch_status"] == "FETCH_FAILED"
    assert result["validation"]["passed"] is False
    assert len(result["fallback_chain"]) == len(FETCH_PROVIDERS)


# ------------------------------------------- P1-1/P1-2 security gates


def test_private_url_never_reaches_third_party_providers(monkeypatch):
    # P1-1: a private original URL must be fetched only by local providers;
    # jina_reader / markdown_new (third-party) must never be invoked.
    calls = []

    def _r(url, provider):
        calls.append(provider)
        return 200, GOOD_BODY, url

    _chain(monkeypatch, {name: (lambda u, p=name: _r(u, p)) for name in FETCH_PROVIDERS})
    result = fetch_url("http://127.0.0.1:8080/internal")
    assert all(p in ("builtin", "defuddle", "raw_html") for p in calls), calls
    assert "jina_reader" not in calls and "markdown_new" not in calls


def test_non_http_scheme_refused_before_read(monkeypatch):
    # P1-2: file:// etc. must be refused before any read attempt — urllib would
    # happily read local files with its default handlers.
    def boom(*a, **k):
        raise AssertionError("must not attempt to read non-http scheme")

    monkeypatch.setattr(fetch_mod, "_http_get", boom)
    result = fetch_url("file:///etc/passwd")
    assert result["fetch_status"] == "FETCH_FAILED"
    assert result["validation"]["passed"] is False
    assert result["validation"]["checks"]["scheme_allowed"] is False
