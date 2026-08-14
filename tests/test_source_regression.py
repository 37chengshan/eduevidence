"""Regression tests for retrieval/source.py — Source Registry extras (P1-5/P1-04).

Authority ranking, DOI parsing variants, CJK fingerprints, dedupe-key wiring and
year-independent source_id stability. Pure functions — no network.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.source import (  # noqa: E402
    AUTHORITY_LEVELS,
    content_hash,
    generate_source_id,
    is_higher_authority,
    make_source,
    parse_doi_from_url,
    title_fingerprint,
    update_source_status,
)


# --------------------------------------------------------------- DOI parsing


def test_parse_doi_from_dx_doi_org():
    assert parse_doi_from_url("https://dx.doi.org/10.1038/s41562-024-01983-y") == "10.1038/s41562-024-01983-y"


def test_parse_doi_strips_trailing_paren():
    assert parse_doi_from_url("see (10.1145/3544548.3580919) for details") == "10.1145/3544548.3580919"


def test_parse_doi_none_for_non_doi_path():
    assert parse_doi_from_url("https://example.com/10-wrong/xyz") is None
    assert parse_doi_from_url("https://example.com/article") is None


# ------------------------------------------------------------ authority ranking


def test_is_higher_authority_directionality():
    assert is_higher_authority("tier1_paper_doi", "tier4_news_secondary") is True
    assert is_higher_authority("tier4_news_secondary", "tier1_paper_doi") is False
    assert is_higher_authority("tier2_academic_database", "tier2_academic_database") is False
    # Unknown tiers rank at the bottom (tier5).
    assert is_higher_authority("tier1_paper_doi", "tier9_bogus") is True


def test_authority_levels_ordered():
    assert AUTHORITY_LEVELS["tier1_paper_doi"] < AUTHORITY_LEVELS["tier5_general_web"]


# --------------------------------------------------------------- fingerprints


def test_title_fingerprint_keeps_cjk():
    fp = title_fingerprint("人工智能在教育中的应用：证据综述 (AI in Education)")
    assert "人工智能在教育中的应用证据综述" in fp
    assert len(fp) <= 64


def test_content_hash_deterministic():
    assert content_hash("hello") == content_hash("hello")
    assert content_hash("hello") != content_hash("hello!")


# ---------------------------------------------------------------- source_id


def test_generate_source_id_cjk_title():
    sid = generate_source_id(authors=["张三"], title="人工智能在教育中的应用")
    assert sid.startswith("S-")


def test_generate_source_id_stable_for_same_paper():
    kwargs = dict(authors=["Bastani, Osbert"],
                  title="Generative AI without guardrails can harm learning",
                  doi="10.1073/pnas.2422633122")
    assert generate_source_id(**kwargs) == generate_source_id(**kwargs)


# ---------------------------------------------------------------- make_source


def test_make_source_doi_key_empty_when_no_doi():
    src = make_source(source_id="S-1", title="A news story", canonical_url="https://news.example/art",
                      authority_level="tier4_news_secondary", doi=None)
    assert src["doi"] == ""
    assert src["dedupe_keys"]["doi"] == ""


def test_make_source_wires_content_hash_into_dedupe_keys():
    src = make_source(source_id="S-1", title="Paper", canonical_url="https://x.example/",
                      authority_level="tier1_paper_doi", fetch={"content_hash": "abc123"})
    assert src["content_hash"] == "abc123"
    assert src["dedupe_keys"]["content_hash"] == "abc123"


def test_make_source_fetch_never_becomes_citation_target():
    # The provider is a reading path; it must never surface as the source URL.
    src = make_source(source_id="S-1", title="Paper",
                      canonical_url="https://doi.org/10.1073/pnas.2422633122",
                      authority_level="tier1_paper_doi",
                      fetch={"fetch_provider": "jina_reader", "resolved_url": "https://r.jina.ai/..."})
    assert src["canonical_url"] == "https://doi.org/10.1073/pnas.2422633122"
    assert src["dedupe_keys"]["canonical_url"] == "https://doi.org/10.1073/pnas.2422633122"


def test_update_source_status():
    src = make_source(source_id="S-1", title="Paper", canonical_url="https://x.example/",
                      authority_level="tier1_paper_doi")
    assert src["status"] == "DISCOVERED"
    update_source_status(src, "VERIFIED")
    assert src["status"] == "VERIFIED"
