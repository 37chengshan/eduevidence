"""Tests for retrieval/dedupe.py — multi-index source dedupe (P1-4)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.dedupe import count_duplicates, dedupe_evidence, dedupe_sources
from retrieval.source import make_source


def _src(source_id, title="Generative AI without guardrails can harm learning",
         url="https://www.pnas.org/doi/10.1073/pnas.2422633122", doi="10.1073/pnas.2422633122",
         level="tier1_paper_doi", year=2025, authors=("Bastani, Osbert",), **kw):
    return make_source(
        source_id=source_id, title=title, canonical_url=url, authority_level=level,
        doi=doi, year=year, authors=list(authors), **kw,
    )


def _src_no_doi(source_id, title="Generative AI without guardrails can harm learning",
                url="https://www.pnas.org/content/article/2422633122",
                level="tier1_paper_doi", year=2025, authors=("Bastani, Osbert",)):
    """A mirror entry whose URL carries no DOI pattern (make_source would
    otherwise auto-extract a DOI from the URL)."""
    return make_source(
        source_id=source_id, title=title, canonical_url=url, authority_level=level,
        doi=None, year=year, authors=list(authors),
    )


def test_dedupe_identical_doi_url_title():
    a = _src("S-1")
    b = _src("S-2")
    out = dedupe_sources([a, b])
    assert len(out) == 1
    assert out[0]["source_id"] == "S-1"  # same tier -> first entry kept


def test_dedupe_doi_vs_url_only_same_paper():
    # P1-4: A has a DOI, B has no DOI but the same paper (title + mirror URL).
    a = _src("S-1")
    b = _src_no_doi("S-2")
    out = dedupe_sources([a, b])
    assert len(out) == 1
    assert out[0]["source_id"] == "S-1"  # keeps the one with the DOI


def test_dedupe_mirror_url_no_doi_matches_by_title():
    # Different mirror URLs, no DOI on either side -> title fingerprint hits.
    a = _src_no_doi("S-1", url="https://pnas.org/content/article/2422633122")
    b = _src_no_doi("S-2", url="https://www.pnas.org/content/article/2422633122")
    out = dedupe_sources([a, b])
    assert len(out) == 1


def test_dedupe_title_hit_keeps_higher_authority():
    # Same paper title on a news site (tier4) and the paper itself (tier1),
    # different URLs and no DOI on the news side -> title index collides.
    news = _src_no_doi("S-news", level="tier4_news_secondary",
                       url="https://edutopia.org/ai-tutor-study")
    paper = _src("S-paper", level="tier1_paper_doi")
    out = dedupe_sources([news, paper])
    assert len(out) == 1
    assert out[0]["source_id"] == "S-paper"


def test_dedupe_content_hash_collision():
    a = _src("S-1", doi=None, url="https://a.example/1")
    b = _src("S-2", doi=None, url="https://b.example/2")
    a["content_hash"] = b["content_hash"] = "deadbeef"
    a["dedupe_keys"]["content_hash"] = b["dedupe_keys"]["content_hash"] = "deadbeef"
    out = dedupe_sources([a, b])
    assert len(out) == 1


def test_dedupe_keeps_distinct_papers():
    a = _src("S-1")
    b = _src("S-2", title="Impact of ChatGPT on ESL students' academic writing skills",
             url="https://link.springer.com/article/10.1186/s40561-024-00295-9",
             doi="10.1186/s40561-024-00295-9")
    out = dedupe_sources([a, b])
    assert len(out) == 2


def test_dedupe_is_stable_across_input_order():
    a = _src("S-1")
    b = _src_no_doi("S-2")
    assert {s["source_id"] for s in dedupe_sources([a, b])} == {"S-1"}
    assert {s["source_id"] for s in dedupe_sources([b, a])} == {"S-1"}


def test_count_duplicates():
    a = _src("S-1")
    b = _src_no_doi("S-2")
    assert count_duplicates([a, b]) == 1
    assert count_duplicates([a]) == 0


def test_dedupe_evidence_by_source_and_claim():
    rows = [
        {"source_id": "S-1", "claim": "claim A"},
        {"source_id": "S-1", "claim": "claim A"},   # duplicate
        {"source_id": "S-1", "claim": "claim B"},
        {"source_id": "S-2", "claim": "claim A"},
    ]
    out = dedupe_evidence(rows)
    assert len(out) == 3
