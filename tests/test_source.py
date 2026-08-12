"""Tests for retrieval/source.py — Source Registry (P1-5)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.source import (
    generate_source_id,
    make_source,
    parse_doi_from_url,
    title_fingerprint,
)


# ------------------------------------------------------------- parse_doi_from_url


def test_parse_doi_from_doi_org():
    assert parse_doi_from_url("https://doi.org/10.1145/3544548.3580919") == "10.1145/3544548.3580919"


def test_parse_doi_from_publisher_urls():
    assert parse_doi_from_url("https://www.pnas.org/doi/10.1073/pnas.2422633122") == "10.1073/pnas.2422633122"
    assert parse_doi_from_url("https://dl.acm.org/doi/10.1145/3544548.3580919") == "10.1145/3544548.3580919"


def test_parse_doi_returns_none_without_doi():
    assert parse_doi_from_url("https://edutopia.org/article/ai-tutors") is None
    assert parse_doi_from_url("") is None


# ------------------------------------------------------------- source_id


def test_generate_source_id_is_year_independent():
    # P1-5: the same source must produce the same ID regardless of the year.
    id_a = generate_source_id(authors=["Bastani, Osbert"], title="Generative AI without guardrails can harm learning")
    assert id_a == "S-BASTANI-GENERATIVE-AI-WITHOUT"


def test_generate_source_id_handles_first_last_name_order():
    assert generate_source_id(authors=["Osbert Bastani"], title="Generative AI in education") == \
        "S-BASTANI-GENERATIVE-AI-EDUCATION"


def test_generate_source_id_falls_back_to_doi_suffix():
    sid = generate_source_id(title="", doi="10.1073/pnas.2422633122")
    assert sid.startswith("S-SOURCE-")


def test_generate_source_id_falls_back_to_url_host():
    sid = generate_source_id(title="", canonical_url="https://edutopia.org/article/ai-tutors")
    assert sid == "S-SOURCE-EDUTOPIA-ORG"


# ------------------------------------------------------------- make_source


def test_make_source_auto_extracts_doi_from_url():
    src = make_source(
        source_id="S-1", title="Paper", canonical_url="https://doi.org/10.1145/3544548.3580919",
        authority_level="tier1_paper_doi",
    )
    assert src["doi"] == "10.1145/3544548.3580919"
    assert src["dedupe_keys"]["doi"] == "10.1145/3544548.3580919"


def test_make_source_generates_id_when_omitted():
    src = make_source(
        title="Generative AI without guardrails can harm learning",
        canonical_url="https://doi.org/10.1073/pnas.2422633122",
        authority_level="tier1_paper_doi",
        authors=["Bastani, Osbert"],
        year=2025,
    )
    assert src["source_id"] == "S-BASTANI-GENERATIVE-AI-WITHOUT"
    assert src["year"] == 2025  # year stays metadata, not part of the ID


def test_make_source_rejects_unknown_authority():
    import pytest
    with pytest.raises(ValueError):
        make_source(source_id="S-1", title="t", canonical_url="https://x.example/",
                    authority_level="tier9_bogus")


def test_make_source_precomputes_dedupe_keys():
    src = make_source(
        source_id="S-1", title="Generative AI without guardrails can harm learning",
        canonical_url="https://www.pnas.org/doi/10.1073/pnas.2422633122",
        authority_level="tier1_paper_doi", doi="10.1073/pnas.2422633122",
        fetch={"content_hash": "abc123"},
    )
    keys = src["dedupe_keys"]
    assert keys["doi"] == "10.1073/pnas.2422633122"
    assert keys["title_fingerprint"] == title_fingerprint(src["title"])
    assert keys["content_hash"] == "abc123"
    assert src["content_hash"] == "abc123"
    assert src["fetch"]["content_hash"] == "abc123"


def test_title_fingerprint_normalizes():
    fp = title_fingerprint("Generative AI without guardrails: Evidence from High-School Mathematics!")
    assert fp == "generativeaiwithoutguardrailsevidencefromhighschoolmathematics"[ :64]
