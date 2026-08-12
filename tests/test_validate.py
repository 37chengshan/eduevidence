"""Tests for retrieval/validate.py — Fetch Validation Gate (P0-6/P0-7).

No network access: pure function tests with synthetic fetch results.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.validate import (  # noqa: E402
    is_private_url,
    resolves_to_private,
    validate_fetch_result,
)

GOOD_BODY = (
    "Abstract. Generative AI without guardrails can harm learning: evidence from high school "
    "mathematics. We ran a three-arm randomized controlled trial with nearly a thousand students. "
    "Results show that unguarded GPT-4 access improved practice performance but harmed independent "
    "exam performance. Guardrail design largely eliminated the negative effect. "
    "References and discussion follow."
)


def _result(**overrides):
    base = {
        "original_url": "https://www.pnas.org/doi/10.1073/pnas.2422633122",
        "resolved_url": "https://www.pnas.org/doi/10.1073/pnas.2422633122",
        "fetch_status": "FETCH_VALID",
        "fetch_provider": "builtin",
        "content": GOOD_BODY,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------- is_private


def test_is_private_doi_url_not_private():
    # P0-7: the DOI "10." prefix must never trip the private check.
    assert is_private_url("https://doi.org/10.1145/3544548.3580919") is False
    assert is_private_url("https://dx.doi.org/10.1038/s41562-024-01983-y") is False


def test_is_private_loopback_and_link_local():
    assert is_private_url("http://127.0.0.1:8000") is True
    assert is_private_url("http://169.254.169.254") is True
    assert is_private_url("http://[::1]/") is True


def test_is_private_private_ranges():
    assert is_private_url("http://10.0.0.5/paper") is True
    assert is_private_url("http://192.168.1.10/") is True
    assert is_private_url("http://172.16.0.1/") is True
    assert is_private_url("http://100.64.0.1/") is True  # CGNAT (is_shared)


def test_is_private_local_hostnames():
    assert is_private_url("http://localhost:8000/") is True
    assert is_private_url("http://intranet.local/") is True


def test_is_private_non_http_schemes():
    assert is_private_url("file:///etc/passwd") is True
    assert is_private_url("ftp://example.com/file") is True


def test_is_private_public_url():
    assert is_private_url("https://www.pnas.org/doi/10.1073/pnas.2422633122") is False
    assert is_private_url("https://link.springer.com/article/10.1186/s40561-024-00295-9") is False


def test_is_private_path_content_ignored():
    # "login"/"10."/port-looking path segments must not affect the verdict.
    assert is_private_url("https://example.com/login?next=/10.1145/x") is False
    assert is_private_url("https://pnas.org/papers/10.1073/pnas.2422633122") is False


# ---------------------------------------------------------------- gate checks


def test_valid_fetch_passes():
    v = validate_fetch_result(_result())
    assert v["passed"] is True
    assert v["checks"]["url_matches"] is True


def test_url_matches_is_real_comparison():
    # P0-6: different resolved URL must fail the check (no more `or True`).
    v = validate_fetch_result(_result(resolved_url="https://attacker.example/mirror"))
    assert v["checks"]["url_matches"] is False
    assert v["passed"] is False
    assert any("resolved URL does not match" in i for i in v["issues"])


def test_url_matches_redirect_to_doi_target():
    # doi.org redirecting to the publisher keeps the same path -> still matches.
    v = validate_fetch_result(_result(
        original_url="https://doi.org/10.1073/pnas.2422633122",
        resolved_url="https://www.pnas.org/doi/10.1073/pnas.2422633122",
    ))
    assert v["checks"]["url_matches"] is True


def test_url_matches_none_for_wrapper_providers():
    # jina_reader / markdown_new fetch a wrapped URL by design -> N/A, not fail.
    v = validate_fetch_result(_result(
        fetch_provider="jina_reader",
        resolved_url="https://r.jina.ai/https://www.pnas.org/doi/10.1073/pnas.2422633122",
    ))
    assert v["checks"]["url_matches"] is None
    assert v["passed"] is True


def test_captcha_page_fails_gate():
    v = validate_fetch_result(_result(content="captcha: please verify you are human " * 30))
    assert v["checks"]["is_captcha_page"] is True
    assert v["passed"] is False


def test_login_page_fails_gate():
    v = validate_fetch_result(_result(content="sign in to continue: login required " * 30))
    assert v["checks"]["is_login_page"] is True
    assert v["passed"] is False


def test_error_page_fails_gate():
    v = validate_fetch_result(_result(content=("404 not found " * 10) + ("page not found " * 10)))
    assert v["checks"]["is_error_page"] is True
    assert v["passed"] is False


def test_short_body_fails_gate():
    v = validate_fetch_result(_result(content="<html><body><p>hi</p></body></html>"))
    assert v["checks"]["body_length_ok"] is False
    assert v["passed"] is False


def test_title_mismatch_fails_gate():
    v = validate_fetch_result(_result(), expect_title="Nonexistent Expected Title")
    assert v["checks"]["title_matches"] is False
    assert v["passed"] is False


def test_fetch_failed_never_passes():
    v = validate_fetch_result(_result(fetch_status="FETCH_FAILED", content=""))
    assert v["passed"] is False
    assert v["checks"]["http_success"] is False


def test_scheme_whitelist():
    v = validate_fetch_result(_result(original_url="ftp://example.com/paper.pdf"))
    assert v["checks"]["scheme_allowed"] is False
    assert v["passed"] is False


def test_private_redirect_target_fails_gate():
    v = validate_fetch_result(_result(resolved_url="http://127.0.0.1:8000/secret"))
    assert v["checks"]["private_target"] is True
    assert v["passed"] is False
    assert any("private/local" in i for i in v["issues"])


def test_private_original_stays_usable():
    # A locally-fetched private page (native only) must not be double-penalized.
    v = validate_fetch_result(_result(
        original_url="http://127.0.0.1:8000/report",
        resolved_url="http://127.0.0.1:8000/report",
    ))
    assert v["checks"]["private_target"] is True
    assert v["passed"] is True


def test_navigation_only_page_fails_gate():
    nav = "menu home about us contact us privacy policy " * 10  # 500 chars < 1000
    v = validate_fetch_result(_result(content=nav))
    assert v["checks"]["navigation_only"] is True
    assert v["passed"] is False


def test_resolves_to_private_public_host_is_false(monkeypatch):
    import socket
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))],
    )
    assert resolves_to_private("https://example.com/") is False


def test_resolves_to_private_private_ip_is_true(monkeypatch):
    import socket
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))],
    )
    assert resolves_to_private("https://example.com/") is True
