"""tests/test_search.py — Comprehensive tests for retrieval/search.py multi-channel search."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

from retrieval.search import (
    SearchHit,
    OpenAlexProvider,
    SemanticScholarProvider,
    CrossRefProvider,
    AIHotProvider,
    MultiSearchRouter,
    search_evidence,
)


def test_search_hit_to_dict():
    hit = SearchHit(
        title="Test Paper",
        url="https://example.com/paper",
        snippet="Abstract snippet",
        provider="openalex",
        doi="10.1000/182",
        year=2024,
        citation_count=50,
        is_academic=True,
    )
    d = hit.to_dict()
    assert d["title"] == "Test Paper"
    assert d["doi"] == "10.1000/182"
    assert d["is_academic"] is True


@patch("retrieval.search._safe_get_json")
def test_openalex_provider(mock_get):
    mock_get.return_value = {
        "results": [
            {
                "id": "W123456",
                "display_name": "Evaluating AI Coding Assistants in CS1",
                "doi": "https://doi.org/10.1145/3544548.3581388",
                "publication_year": 2023,
                "cited_by_count": 85,
                "primary_location": {"landing_page_url": "https://dl.acm.org/doi/10.1145/3544548.3581388"},
                "abstract_inverted_index": {"We": [0], "study": [1], "Copilot": [2]},
                "authorships": [{"author": {"display_name": "Majid Kazemitabaar"}}],
            }
        ]
    }
    provider = OpenAlexProvider()
    hits = provider.search("AI coding assistants", limit=5)
    assert len(hits) == 1
    assert hits[0].title == "Evaluating AI Coding Assistants in CS1"
    assert hits[0].doi == "10.1145/3544548.3581388"
    assert hits[0].citation_count == 85
    assert hits[0].is_academic is True


@patch("retrieval.search._safe_get_json")
def test_crossref_provider(mock_get):
    mock_get.return_value = {
        "message": {
            "items": [
                {
                    "title": ["Generative AI in Education: Randomized Controlled Trial"],
                    "DOI": "10.1073/pnas.2412345122",
                    "URL": "https://doi.org/10.1073/pnas.2412345122",
                    "issued": {"date-parts": [[2025]]},
                    "is-referenced-by-count": 42,
                    "author": [{"given": "Hamsa", "family": "Bastani"}],
                }
            ]
        }
    }
    provider = CrossRefProvider()
    hits = provider.search("Bastani Generative AI", limit=5)
    assert len(hits) == 1
    assert hits[0].title == "Generative AI in Education: Randomized Controlled Trial"
    assert hits[0].year == 2025
    assert hits[0].authors == ["Hamsa Bastani"]


@patch("retrieval.search._safe_get_json")
def test_aihot_provider(mock_get):
    mock_get.return_value = {
        "code": 0,
        "data": [
            {
                "title": "OpenAI Introduces New Socratic Reasoning Model for Tutors",
                "url": "https://aihot.today/item/123",
                "summary": "Benchmark evaluation on high school physics and coding.",
                "category": "EdTech",
            }
        ]
    }
    provider = AIHotProvider()
    hits = provider.search("Socratic reasoning tutor", limit=5)
    assert len(hits) == 1
    assert "OpenAI" in hits[0].title
    assert hits[0].provider == "aihot"


def test_router_and_deduplication():
    router = MultiSearchRouter()
    # Mock only internal provider lists
    mock_p1 = MagicMock()
    mock_p1.search.return_value = [
        SearchHit(title="Paper 1", url="https://doi.org/10.1000/1", snippet="Snippet 1", provider="openalex", doi="10.1000/1", citation_count=100)
    ]
    mock_p2 = MagicMock()
    mock_p2.search.return_value = [
        SearchHit(title="Paper 1 duplicate", url="https://doi.org/10.1000/1", snippet="Snippet 2", provider="crossref", doi="10.1000/1", citation_count=50)
    ]

    router.zero_config_academic = [mock_p1, mock_p2]
    router.zero_config_web = []
    router.configured_providers = []

    results = router.search("test query", limit=5)
    assert len(results) == 1
    assert results[0].url == "https://doi.org/10.1000/1"
