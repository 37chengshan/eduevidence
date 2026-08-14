"""Regression tests for retrieval/validate.py — URL-match realism, private-target
classification and gate edge cases (review P0-1).

Pure-function tests over synthetic fetch results; no network access. The
no-network rule is enforced by never calling resolves_to_private with real DNS
(its socket.getaddrinfo is mocked where exercised).
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


# ---------------------------------------------------------- url_matches realism


def test_url_matches_false_when_query_changes():
    # Same host + path, different query -> different resource -> no match.
    v = validate_fetch_result(_result(
        original_url="https://example.com/paper",
        resolved_url="https://example.com/paper?p=1",
    ))
    assert v["checks"]["url_matches"] is False
    assert v["passed"] is False
    assert any("resolved URL does not match" in i for i in v["issues"])


def test_url_matches_false_when_path_changes():
    v = validate_fetch_result(_result(
        original_url="https://example.com/paper/a",
        resolved_url="https://example.com/paper/b",
    ))
    assert v["checks"]["url_matches"] is False


def test_url_matches_same_path_other_host_ok():
    # Canonical doi.org -> publisher redirect keeps the path: allowed.
    v = validate_fetch_result(_result(
        original_url="https://doi.org/paper/10.1000/xyz",
        resolved_url="https://www.publisher.example/paper/10.1000/xyz",
    ))
    assert v["checks"]["url_matches"] is True
    assert v["passed"] is True


def test_url_matches_same_doi_other_host_ok():
    # Different host AND different path, but the same DOI: still the same paper.
    v = validate_fetch_result(_result(
        original_url="https://doi.org/10.1073/pnas.2422633122",
        resolved_url="https://dl.acm.org/doi/10.1073/pnas.2422633122",
    ))
    assert v["checks"]["url_matches"] is True


def test_url_matches_none_without_resolved_url():
    v = validate_fetch_result(_result(resolved_url=""))
    assert v["checks"]["url_matches"] is None


# ------------------------------------------------------- is_private / redirects


def test_is_private_doi_urls_never_private():
    # P0-1: DOI URLs (10. in the path) must never be misjudged private.
    assert is_private_url("https://doi.org/10.1145/3544548.3580919") is False
    assert is_private_url("https://dx.doi.org/10.1038/s41562-024-01983-y") is False
    assert is_private_url("https://www.pnas.org/doi/10.1073/pnas.2422633122") is False
    assert is_private_url("https://DOI.ORG/10.1145/3544548.3580919") is False  # case-insensitive host


def test_is_private_loopback_forms():
    for url in (
        "http://127.0.0.1:8000/x",
        "http://localhost/x",
        "http://[::1]/",
        "http://0.0.0.0/",
        "http://[::ffff:127.0.0.1]/",  # IPv4-mapped loopback
    ):
        assert is_private_url(url) is True, url


def test_is_private_private_range_edges():
    assert is_private_url("http://10.0.0.1/") is True
    assert is_private_url("http://172.31.255.255/") is True   # 172.16/12 upper bound
    assert is_private_url("http://172.32.0.1/") is False       # just outside
    assert is_private_url("http://192.168.255.255/") is True
    assert is_private_url("http://100.127.255.255/") is True   # CGNAT upper bound
    assert is_private_url("http://100.128.0.1/") is False      # just outside CGNAT


def test_is_private_ipv6_unique_local():
    assert is_private_url("http://[fc00::1]/") is True
    assert is_private_url("http://[fd12:3456::1]/") is True


def test_redirect_target_on_private_network_fails_gate():
    # P0-1: a public request that lands (via redirect) on a private target must
    # be flagged private and fail the gate.
    v = validate_fetch_result(_result(
        original_url="https://doi.org/10.1073/pnas.2422633122",
        resolved_url="http://127.0.0.1:8000/secret",
    ))
    assert v["checks"]["private_target"] is True
    assert v["passed"] is False
    assert any("private/local" in i for i in v["issues"])


def test_private_original_stays_usable_but_flagged():
    # A locally-fetched private page is flagged private but not double-penalized.
    v = validate_fetch_result(_result(
        original_url="http://127.0.0.1:8000/report",
        resolved_url="http://127.0.0.1:8000/report",
    ))
    assert v["checks"]["private_target"] is True
    assert v["passed"] is True


# --------------------------------------------------------------- gate edges


def test_body_length_boundary_exact_200():
    assert validate_fetch_result(_result(content="x" * 200))["checks"]["body_length_ok"] is True
    assert validate_fetch_result(_result(content="x" * 199))["checks"]["body_length_ok"] is False


def test_navigation_only_needs_all_markers():
    # Missing "privacy policy" -> not navigation-only, so the page can pass.
    partial_nav = "menu home about us contact us " * 10  # 500 chars, all but one marker
    v = validate_fetch_result(_result(content=partial_nav))
    assert v["checks"]["navigation_only"] is False
    assert v["passed"] is True


def test_expect_title_match_from_content_head():
    content = "Randomized Controlled Trial of AI Tutors\n" + GOOD_BODY
    v = validate_fetch_result(_result(content=content), expect_title="Randomized Controlled Trial of AI Tutors")
    assert v["checks"]["title_matches"] is True
    assert v["passed"] is True


def test_expect_title_mismatch_fails_gate():
    v = validate_fetch_result(_result(), expect_title="Nonexistent Expected Title")
    assert v["checks"]["title_matches"] is False
    assert v["passed"] is False


def test_private_target_none_without_resolved_url():
    v = validate_fetch_result(_result(resolved_url=""))
    assert v["checks"]["private_target"] is None


def test_scheme_allowed_none_without_original_url():
    v = validate_fetch_result(_result(original_url=""))
    assert v["checks"]["scheme_allowed"] is None


def test_resolves_to_private_literal_private_ip():
    # Literal IP: judged directly, no DNS.
    assert resolves_to_private("http://127.0.0.1/x") is True
    assert resolves_to_private("http://10.0.0.5/x") is True


def test_resolves_to_private_dns_failure_is_none(monkeypatch):
    import socket

    def boom(*args, **kwargs):
        raise OSError("no DNS for tests")
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    assert resolves_to_private("https://example.com/") is None  # treated as not-private by callers
