"""Regression tests for retrieval/dedupe.py — multi-index dedupe (P1-4).

Review scenario: the same paper behind different URLs / with/without a DOI must
dedupe through the doi/url/title/hash indexes and merge keeping the
higher-authority entry. Also covers the stale-index regression: when a
higher-authority incoming replaces an indexed entry, later sources hitting the
replaced entry's old keys must not crash.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.dedupe import dedupe_sources
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


# ------------------------------------------------------ review P0-1 scenarios


def test_dedupe_same_url_one_has_doi_one_not_keeps_higher_authority():
    # Same canonical_url, same title: one entry has a DOI, the other does not.
    # Must dedupe (url index hit) and keep the higher-authority entry + its DOI.
    news = _src_no_doi("S-news", title="The same paper title",
                       url="https://edutopia.org/ai-tutor-study", level="tier4_news_secondary")
    paper = _src("S-paper", title="The same paper title",
                 url="https://edutopia.org/ai-tutor-study", doi="10.1000/xyz", level="tier1_paper_doi")
    out = dedupe_sources([news, paper])
    assert len(out) == 1
    assert out[0]["source_id"] == "S-paper"
    assert out[0]["doi"] == "10.1000/xyz"


def test_dedupe_title_only_hit_with_doi_vs_no_doi(monkeypatch=None):
    # Different mirror URLs, no DOI on one side: the title fingerprint index is
    # what collides; the higher-authority DOI entry is kept.
    mirror = _src_no_doi("S-mirror", title="Attention is all you need",
                         url="https://mirror.example/attn", level="tier5_general_web")
    paper = _src("S-paper", title="Attention is all you need",
                 url="https://doi.org/10.48550/arxiv.1706.03762",
                 doi="10.48550/arxiv.1706.03762", level="tier1_paper_doi")
    out = dedupe_sources([mirror, paper])
    assert len(out) == 1
    assert out[0]["source_id"] == "S-paper"
    assert out[0]["doi"] == "10.48550/arxiv.1706.03762"


def test_dedupe_order_independent_keeps_higher_authority():
    mirror = _src_no_doi("S-mirror", title="Attention is all you need",
                         url="https://mirror.example/attn", level="tier5_general_web")
    paper = _src("S-paper", title="Attention is all you need",
                 url="https://doi.org/10.48550/arxiv.1706.03762",
                 doi="10.48550/arxiv.1706.03762", level="tier1_paper_doi")
    assert {s["source_id"] for s in dedupe_sources([mirror, paper])} == {"S-paper"}
    assert {s["source_id"] for s in dedupe_sources([paper, mirror])} == {"S-paper"}


def test_dedupe_authority_tie_keeps_more_complete_metadata():
    # Same tier: the entry with more identifying metadata (DOI/year/authors)
    # wins the merge.
    sparse = _src("S-sparse", title="Title T", url="https://x.example/1",
                  doi=None, year=None, authors=())
    rich = _src("S-rich", title="Title T", url="https://x.example/1",
                doi="10.1000/abc", year=2025, authors=("Author A",))
    out = dedupe_sources([sparse, rich])
    assert len(out) == 1
    assert out[0]["source_id"] == "S-rich"


# ------------------------------------------------------- stale-index regression


def test_dedupe_no_crash_when_later_source_hits_replaced_index_key():
    # Regression: source B (tier1, DOI) replaces source A (tier5, mirror URL)
    # via the title index. A's old URL key stays in the url index; a third
    # source reusing that URL must dedupe cleanly (previously ValueError:
    # "... is not in list") and keep the highest-authority entry.
    a = _src_no_doi("S-A", title="Same paper title",
                    url="https://mirror.example/a", level="tier5_general_web")
    b = _src("S-B", title="Same paper title",
             url="https://doi.org/10.1000/xyz", doi="10.1000/xyz", level="tier1_paper_doi")
    c = _src_no_doi("S-C", title="A different paper entirely",
                    url="https://mirror.example/a", level="tier2_academic_database")
    out = dedupe_sources([a, b, c])
    assert len(out) == 1
    assert out[0]["source_id"] == "S-B"


def test_dedupe_replaced_key_still_dedupes_further_hits(monkeypatch=None):
    # After B replaces A, a third entry hitting the OLD title key must still be
    # caught as a duplicate of the kept entry (indexes stay coherent).
    a = _src_no_doi("S-A", title="Same paper title",
                    url="https://mirror.example/a", level="tier5_general_web")
    b = _src("S-B", title="Same paper title",
             url="https://doi.org/10.1000/xyz", doi="10.1000/xyz", level="tier1_paper_doi")
    d = _src_no_doi("S-D", title="Same paper title",
                    url="https://another-mirror.example/b", level="tier3_professional_institution")
    out = dedupe_sources([a, b, d])
    assert len(out) == 1
    assert out[0]["source_id"] == "S-B"
