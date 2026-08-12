"""Tests for retrieval/fetch.py — degradation chain (P0-6).

The fetch chain (fetch -> validate -> decide fallback) is exercised with a
mocked provider table; no real network access.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import retrieval.fetch as fetch_mod
from retrieval.fetch import FETCH_PROVIDERS, extract_main_text, fetch_url

GOOD_HTML = """<html><head><title>Paper</title></head><body>
<nav>menu home</nav>
<main><article><h1>Generative AI without guardrails can harm learning</h1>
<p>Evidence from high school mathematics. A three-arm randomized controlled
trial with nearly a thousand high school students in Turkey. Unguarded GPT-4
access improved practice performance but harmed independent exam performance
by seventeen percent. Teacher-designed guardrails largely eliminated the
negative learning effect. These findings have direct implications for
classroom AI policy.</p>
<p>Methods, results and references complete this abstract.</p></article></main>
</body></html>"""

# Passes the body_length_ok check (>200 chars) and carries no block markers.
GOOD_BODY = (
    "Generative AI without guardrails can harm learning: evidence from high school mathematics. "
    "We ran a three-arm randomized controlled trial with nearly a thousand high school students "
    "in Turkey. Unguarded GPT-4 access improved practice performance but harmed independent exam "
    "performance by seventeen percent. Teacher-designed guardrails largely eliminated the "
    "negative learning effect. These findings have direct implications for classroom AI policy."
)

# Fails the body_length_ok check (too short).
SHORT_BODY = "Generative AI without guardrails."

CAPTCHA_BODY = "captcha: please verify you are human " * 40
LOGIN_BODY = "sign in to continue: login required " * 30


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    """Never touch the network in tests: all fetches go through mocks."""
    def boom(*args, **kwargs):
        raise AssertionError("unexpected real network access")
    monkeypatch.setattr(fetch_mod, "_http_get", boom)
    # DNS is part of the network layer: mock hosts resolve publicly.
    monkeypatch.setattr(fetch_mod, "resolves_to_private", lambda url: False)


def _fake_responses(monkeypatch, responses):
    """responses: dict provider_name -> callable(url) -> (status, body, resolved_url)."""
    def fake(provider):
        def _fetch(url, timeout):
            return responses[provider](url)
        return _fetch

    monkeypatch.setattr(fetch_mod, "_PROVIDER_FETCHERS", {
        name: fake(name) for name in FETCH_PROVIDERS
    })


# ------------------------------------------------------------- defuddle


def test_extract_main_text_prefers_main_article():
    text = extract_main_text(GOOD_HTML)
    assert "Generative AI without guardrails" in text
    assert "menu" not in text


def test_extract_main_text_strips_script_style_nav():
    html = "<html><head><style>body{}</style></head><body><nav>nav junk</nav>" \
           "<script>var x=1;</script><p>Real content with enough words to pass.</p></body></html>"
    text = extract_main_text(html)
    assert "nav junk" not in text
    assert "var x=1" not in text
    assert "Real content" in text


def test_extract_main_text_falls_back_to_body():
    html = "<html><body><div><p>Paragraph one of the fallback body text.</p>" \
           "<p>Paragraph two with additional real content.</p></div></body></html>"
    text = extract_main_text(html)
    assert "Paragraph one" in text and "Paragraph two" in text


def test_defuddle_provider_registered():
    assert "defuddle" in FETCH_PROVIDERS


# ------------------------------------------------------------- chain behavior


def test_valid_first_provider_stops_chain(monkeypatch):
    called = []

    def resp(provider):
        def _r(url):
            called.append(provider)
            return 200, GOOD_BODY, "https://www.pnas.org/doi/10.1073/pnas.2422633122"
        return _r

    _fake_responses(monkeypatch, {name: resp(name) for name in FETCH_PROVIDERS})
    result = fetch_url("https://www.pnas.org/doi/10.1073/pnas.2422633122")
    assert result["fetch_status"] == "FETCH_VALID"
    assert result["fetch_provider"] == "builtin"
    assert result["validation"]["passed"] is True
    assert called == ["builtin"]  # only one provider tried


def test_captcha_200_continues_to_next_provider(monkeypatch):
    # P0-6: HTTP 200 + captcha body must NOT stop the chain.
    calls = []

    def _r(url, provider):
        calls.append(provider)
        if provider == "builtin":
            return 200, CAPTCHA_BODY, "https://www.pnas.org/doi/10.1073/pnas.2422633122"
        return 200, GOOD_BODY, "https://www.pnas.org/doi/10.1073/pnas.2422633122"

    def _make(provider):
        def _f(url, timeout):
            return _r(url, provider)
        return _f

    monkeypatch.setattr(fetch_mod, "_PROVIDER_FETCHERS", {name: _make(name) for name in FETCH_PROVIDERS})
    result = fetch_url("https://www.pnas.org/doi/10.1073/pnas.2422633122")
    assert result["fetch_status"] == "FETCH_VALID"
    assert result["fetch_provider"] == "jina_reader"
    assert result["fallback_used"] is True
    assert result["fallback_chain"][0] == "builtin:200"
    assert calls == ["builtin", "jina_reader"]


def test_login_page_falls_through_to_defuddle(monkeypatch):
    calls = []

    def _r(url, provider):
        calls.append(provider)
        if provider in ("builtin", "jina_reader"):
            return 200, LOGIN_BODY, "https://pnas.org/paper"
        return 200, GOOD_HTML, "https://pnas.org/paper"

    def _make(provider):
        def _f(url, timeout):
            return _r(url, provider)
        return _f

    monkeypatch.setattr(fetch_mod, "_PROVIDER_FETCHERS", {name: _make(name) for name in FETCH_PROVIDERS})
    result = fetch_url("https://pnas.org/paper")
    assert result["fetch_provider"] == "defuddle"
    assert result["fetch_status"] == "FETCH_VALID"
    assert result["validation"]["passed"] is True
    assert "menu" not in result["content"]


def test_short_body_continues_fallback(monkeypatch):
    calls = []

    def _r(url, provider):
        calls.append(provider)
        if provider in ("builtin", "jina_reader", "defuddle"):
            return 200, SHORT_BODY, "https://pnas.org/paper"
        return 200, GOOD_BODY, "https://pnas.org/paper"

    def _make(provider):
        def _f(url, timeout):
            return _r(url, provider)
        return _f

    monkeypatch.setattr(fetch_mod, "_PROVIDER_FETCHERS", {name: _make(name) for name in FETCH_PROVIDERS})
    result = fetch_url("https://pnas.org/paper")
    assert result["fetch_status"] == "FETCH_VALID"
    assert result["fetch_provider"] == "markdown_new"
    assert calls == ["builtin", "jina_reader", "defuddle", "markdown_new"]


def test_redirect_resolved_url_recorded(monkeypatch):
    # resp.geturl() after a redirect must be recorded as resolved_url.
    monkeypatch.setattr(fetch_mod, "_PROVIDER_FETCHERS", {
        "builtin": lambda u, t=20: (200, GOOD_BODY, "https://pnas.org/doi/10.1073/pnas.2422633122"),
    })
    result = fetch_url("https://doi.org/10.1073/pnas.2422633122")
    assert result["resolved_url"] == "https://pnas.org/doi/10.1073/pnas.2422633122"
    assert result["fetch_status"] == "FETCH_VALID"


def test_all_providers_fail_returns_failed(monkeypatch):
    def fail(url, provider=None):
        raise fetch_mod.urllib.error.URLError("boom")

    monkeypatch.setattr(fetch_mod, "_PROVIDER_FETCHERS", {
        name: (lambda u, p=name: fail(u, p)) for name in FETCH_PROVIDERS
    })
    result = fetch_url("https://pnas.org/paper")
    assert result["fetch_status"] == "FETCH_FAILED"
    assert result["content"] == ""
    assert len(result["fallback_chain"]) == len(FETCH_PROVIDERS)


def test_no_valid_keeps_best_partial(monkeypatch):
    # All providers return blocked/short bodies: the longest readable attempt
    # is kept as FETCH_PARTIAL, never silently FETCH_VALID.
    long_blocked = "captcha: please verify you are human " * 60

    def _r(url, provider):
        if provider == "jina_reader":
            return 200, long_blocked, "https://pnas.org/paper"
        return 200, SHORT_BODY, "https://pnas.org/paper"

    def _make(provider):
        def _f(url, timeout):
            return _r(url, provider)
        return _f

    monkeypatch.setattr(fetch_mod, "_PROVIDER_FETCHERS", {name: _make(name) for name in FETCH_PROVIDERS})
    result = fetch_url("https://pnas.org/paper")
    assert result["fetch_status"] == "FETCH_PARTIAL"
    assert result["fetch_provider"] == "jina_reader"


def test_private_url_uses_native_chain_only(monkeypatch):
    calls = []

    def _r(url, provider):
        calls.append(provider)
        return 200, GOOD_BODY, "http://127.0.0.1:8000/report"

    def _make(provider):
        def _f(url, timeout):
            return _r(url, provider)
        return _f

    monkeypatch.setattr(fetch_mod, "_PROVIDER_FETCHERS", {name: _make(name) for name in FETCH_PROVIDERS})
    result = fetch_url("http://127.0.0.1:8000/report", use_smart_fetch=False)
    assert result["fetch_status"] == "FETCH_VALID"
    assert result["fetch_provider"] == "builtin"
    assert "jina_reader" not in calls and "markdown_new" not in calls


def test_private_redirect_target_aborts_chain(monkeypatch):
    # A public URL that redirects to 127.0.0.1 must abort, not fall through
    # to third-party providers with private content.
    def _r(url, provider):
        if provider == "builtin":
            return 200, GOOD_BODY, "http://127.0.0.1:8000/secret"
        return 200, GOOD_BODY, "https://pnas.org/paper"

    def _make(provider):
        def _f(url, timeout):
            return _r(url, provider)
        return _f

    monkeypatch.setattr(fetch_mod, "_PROVIDER_FETCHERS", {name: _make(name) for name in FETCH_PROVIDERS})
    result = fetch_url("https://pnas.org/paper")
    assert result["fetch_status"] == "FETCH_FAILED"
    assert result["fallback_chain"] == ["builtin:200", "builtin:private_target"]
