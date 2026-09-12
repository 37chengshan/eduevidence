"""Tests for the Sciverse retrieval channel (retrieval/sciverse.py + fetch bridge).

No network access: every HTTP call is faked. The acceptance points are the
scientific ones — a chunk locator is never evidence, a DOI-less record never
gets a fabricated URL, and every failure degrades to a typed status instead of
an exception.
"""
from __future__ import annotations

import io
import json
import urllib.error

import pytest

from retrieval import sciverse
from retrieval.fetch import fetch_sciverse_content
from retrieval.search import MultiSearchRouter, SearchHit

TOKEN = "sv-test-token-not-real"

LONG_TEXT = (
    "Abstract. We ran a randomized controlled trial with first-year students. "
    "Unguarded access improved practice performance but harmed independent exam "
    "performance, and guardrail design largely removed the negative effect. "
    "Discussion, limitations and references follow in the full text."
)


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self._body = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_urlopen(payload: dict, status: int = 200, record: list | None = None):
    def _open(request, timeout=None):  # noqa: ARG001 - signature mirror
        if record is not None:
            record.append(request)
        return _FakeResponse(payload, status)

    return _open


def _http_error(code: int, message: str = "boom"):
    def _open(request, timeout=None):  # noqa: ARG001
        raise urllib.error.HTTPError(
            url=request.full_url, code=code, msg=message,
            hdrs=None, fp=io.BytesIO(json.dumps({"code": "E", "message": message}).encode()),
        )

    return _open


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(sciverse.TOKEN_ENV, raising=False)


# --------------------------------------------------------------- availability


def test_without_token_every_endpoint_is_unavailable():
    assert sciverse.available() is False
    for response in (sciverse.meta_search("q"), sciverse.agentic_search("q"),
                     sciverse.read_content("doc"), sciverse.paper_relations("u")):
        assert response.ok is False
        assert response.status == sciverse.STATUS_UNAVAILABLE


def test_provider_skipped_by_router_without_token():
    router = MultiSearchRouter()
    assert router.academic_key_providers == []
    statuses = {s["provider"]: s for s in router.get_provider_status()}
    assert "sciverse" not in statuses  # inactive channel is not advertised


def test_provider_activates_with_token(monkeypatch):
    monkeypatch.setenv(sciverse.TOKEN_ENV, TOKEN)
    router = MultiSearchRouter()
    assert [p.name for p in router.academic_key_providers] == ["sciverse"]
    entry = next(s for s in router.get_provider_status() if s["provider"] == "sciverse")
    assert entry["type"] == "academic_key" and entry["requires_a_key" if False else "requires_key"] is True


def test_provider_search_returns_empty_when_unavailable():
    assert sciverse.SciverseProvider().search("q") == []


# ------------------------------------------------------------------- endpoints


def test_meta_search_parses_source_level_hits(monkeypatch):
    monkeypatch.setenv(sciverse.TOKEN_ENV, TOKEN)
    captured: list = []
    payload = {
        "results": [{
            "unique_id": "paper:10.1073/pnas.2422633122",
            "doc_id": "a" * 64,
            "title": "Generative AI without guardrails can harm learning",
            "abstract": "RCT with high school students.",
            "author": [{"name": "Hamsa Bastani"}],
            "publication_published_year": 2025,
            "doi": "https://doi.org/10.1073/pnas.2422633122",
        }],
        "total_count": 1, "page": 1, "page_size": 10,
    }
    semantic = {"hits": [{
        "chunk_id": "c1", "doc_id": "a" * 64, "title": "t",
        "chunk": "upharmed", "score": 0.9, "offset": 12480, "page_no": 3,
        "source_type": "pdf",
    }]}

    calls = {"n": 0}

    def _open(request, timeout=None):
        captured.append(request)
        calls["n"] += 1
        return _FakeResponse(payload if calls["n"] == 1 else semantic)

    monkeypatch.setattr(sciverse.urllib.request, "urlopen", _open)
    hits = sciverse.SciverseProvider().search("guardrails", limit=5)

    assert len(hits) == 1
    hit = hits[0]
    assert isinstance(hit, SearchHit)
    assert hit.doi == "10.1073/pnas.2422633122"  # doi.org prefix normalised
    assert hit.url == "https://doi.org/10.1073/pnas.2422633122"
    assert hit.doc_id == "a" * 64
    assert hit.unique_id == "paper:10.1073/pnas.2422633122"
    assert hit.chunk_id == "c1"
    assert hit.offset == 12480
    assert hit.is_academic is True
    assert hit.citation_count is None  # absent field stays absent, never invented


def test_doi_less_record_never_gets_a_fabricated_url(monkeypatch):
    monkeypatch.setenv(sciverse.TOKEN_ENV, TOKEN)
    payload = {"results": [{"unique_id": "paper:x", "title": "No DOI here"}],
               "total_count": 1, "page": 1, "page_size": 10}
    monkeypatch.setattr(sciverse.urllib.request, "urlopen", _fake_urlopen(payload))
    provider = sciverse.SciverseProvider(include_chunks=False)
    hit = provider.search("q", limit=1)[0]
    assert hit.doi is None
    assert hit.url == ""
    assert hit.doc_id is None


def test_agentic_search_normalises_chunk_locators(monkeypatch):
    monkeypatch.setenv(sciverse.TOKEN_ENV, TOKEN)
    payload = {"hits": [{
        "chunk_id": "c9", "doc_id": "b" * 64, "title": "t", "chunk": "text",
        "score": 0.71, "offset": 4096, "page_no": 2, "source_type": "pdf",
    }, {"chunk_id": "c10", "title": "missing doc_id"}]}
    monkeypatch.setattr(sciverse.urllib.request, "urlopen", _fake_urlopen(payload))
    records = sciverse.chunk_records(sciverse.agentic_search("q", top_k=3), query_id="Q1")
    assert len(records) == 1  # a locator without doc_id cannot be expanded
    assert records[0]["offset"] == 4096
    assert records[0]["query_id"] == "Q1"


def test_read_content_sends_offset_explicitly(monkeypatch):
    monkeypatch.setenv(sciverse.TOKEN_ENV, TOKEN)
    captured: list = []
    payload = {"text": LONG_TEXT, "bytes_returned": len(LONG_TEXT.encode()),
               "next_offset": 99, "more": True}
    monkeypatch.setattr(sciverse.urllib.request, "urlopen", _fake_urlopen(payload, record=captured))
    response = sciverse.read_content("d" * 64, offset=0, limit=4096)
    assert response.ok
    query = captured[0].full_url.split("?", 1)[1]
    assert "offset=0" in query  # omitting offset would return the whole document
    assert "limit=4096" in query


def test_relation_records_carry_direction(monkeypatch):
    monkeypatch.setenv(sciverse.TOKEN_ENV, TOKEN)
    payload = {"items": [{"id": "paper:1", "id_type": "unique_id", "title": "A"}],
               "total_count": 1, "page": 1, "page_size": 25, "total_pages": 1}
    monkeypatch.setattr(sciverse.urllib.request, "urlopen", _fake_urlopen(payload))
    response = sciverse.paper_relations("paper:x", relation="CITATIONS")
    records = sciverse.relation_records(response, unique_id="paper:x", relation="CITATIONS")
    assert records == [{"source_unique_id": "paper:x", "relation": "CITATIONS",
                        "id": "paper:1", "id_type": "unique_id", "title": "A"}]


# ---------------------------------------------------------------- error types


@pytest.mark.parametrize("code,expected", [
    (401, sciverse.STATUS_UNAUTHORIZED),
    (403, sciverse.STATUS_UNAUTHORIZED),
    (400, sciverse.STATUS_BAD_REQUEST),
    (404, sciverse.STATUS_BAD_REQUEST),
    (429, sciverse.STATUS_BAD_REQUEST),
    (502, sciverse.STATUS_UPSTREAM),
    (503, sciverse.STATUS_UPSTREAM),
])
def test_http_errors_become_typed_statuses(monkeypatch, code, expected):
    monkeypatch.setenv(sciverse.TOKEN_ENV, TOKEN)
    monkeypatch.setattr(sciverse.urllib.request, "urlopen", _http_error(code))
    response = sciverse.meta_search("q")
    assert response.status == expected
    assert response.http_status == code
    assert TOKEN not in response.error  # never leak credentials into messages


def test_network_failure_is_typed_not_raised(monkeypatch):
    monkeypatch.setenv(sciverse.TOKEN_ENV, TOKEN)

    def _boom(request, timeout=None):  # noqa: ARG001
        raise TimeoutError("timed out")

    monkeypatch.setattr(sciverse.urllib.request, "urlopen", _boom)
    response = sciverse.agentic_search("q")
    assert response.status == sciverse.STATUS_NETWORK
    assert response.ok is False


def test_empty_hits_is_success_not_failure(monkeypatch):
    monkeypatch.setenv(sciverse.TOKEN_ENV, TOKEN)
    monkeypatch.setattr(sciverse.urllib.request, "urlopen", _fake_urlopen({"hits": []}))
    response = sciverse.agentic_search("nothing matches")
    assert response.ok is True
    assert sciverse.chunk_records(response) == []


# ------------------------------------------------------- content -> FetchResult


def test_read_content_becomes_a_valid_fetch_result(monkeypatch):
    monkeypatch.setenv(sciverse.TOKEN_ENV, TOKEN)
    payload = {"text": LONG_TEXT, "bytes_returned": len(LONG_TEXT.encode()),
               "next_offset": len(LONG_TEXT), "more": False}
    monkeypatch.setattr(sciverse.urllib.request, "urlopen", _fake_urlopen(payload))
    result = fetch_sciverse_content("c" * 64, offset=12480, limit=4096,
                                    canonical_url="https://doi.org/10.1073/pnas.2422633122")
    assert result["fetch_status"] == "FETCH_VALID"
    assert result["fetch_provider"] == "sciverse_content"
    assert result["validation"]["passed"] is True
    assert result["content"] == LONG_TEXT
    location = result["extensions"]["sciverse"]
    assert location["doc_id"] == "c" * 64
    assert location["offset"] == 12480
    assert location["location_unit"] == "unicode_code_point"
    assert location["more"] is False


def test_content_fetch_fails_closed_without_token():
    result = fetch_sciverse_content("c" * 64)
    assert result["fetch_status"] == "FETCH_FAILED"
    assert result["content"] == ""
    assert any("SCIVERSE_UNAVAILABLE" in issue for issue in result["validation"]["issues"])


def test_content_fetch_fails_closed_on_upstream_error(monkeypatch):
    monkeypatch.setenv(sciverse.TOKEN_ENV, TOKEN)
    monkeypatch.setattr(sciverse.urllib.request, "urlopen", _http_error(503))
    result = fetch_sciverse_content("c" * 64)
    assert result["fetch_status"] == "FETCH_FAILED"
    assert any("SCIVERSE_UPSTREAM_ERROR" in issue for issue in result["validation"]["issues"])


def test_short_content_is_partial_not_valid(monkeypatch):
    monkeypatch.setenv(sciverse.TOKEN_ENV, TOKEN)
    monkeypatch.setattr(sciverse.urllib.request, "urlopen",
                        _fake_urlopen({"text": "too short", "bytes_returned": 9,
                                       "next_offset": 9, "more": False}))
    result = fetch_sciverse_content("c" * 64)
    assert result["fetch_status"] == "FETCH_PARTIAL"


# ------------------------------------------------------------------- auditing


def test_executor_writes_chunk_provenance(tmp_path):
    from retrieval.audit import AuditedSearchExecutor, SearchPlan

    class _Provider:
        name = "sciverse"

        def search(self, query, limit=10):
            return [SearchHit(title="Paper", url="https://doi.org/10.1/x", snippet="s",
                              provider=self.name, doi="10.1/x", doc_id="e" * 64,
                              chunk_id="c1", offset=512, is_academic=True)]

    plan = SearchPlan.from_question("Does it work?", concepts=("guardrails",))
    hits = AuditedSearchExecutor([_Provider()]).execute(plan, tmp_path)
    assert len(hits) == 1

    records = [json.loads(line) for line in (tmp_path / "chunks.jsonl").read_text().splitlines()]
    assert records[0]["doc_id"] == "e" * 64
    assert records[0]["offset"] == 512
    assert records[0]["locator_state"] == "discovery_only_requires_content_fetch"

    header = (tmp_path / "source-screening.csv").read_text().splitlines()[0]
    for column in ("doc_id", "chunk_id", "offset"):
        assert column in header


def test_doi_less_hit_is_flagged_for_manual_location(tmp_path):
    from retrieval.audit import AuditedSearchExecutor, SearchPlan

    class _Provider:
        name = "sciverse"

        def search(self, query, limit=10):
            return [SearchHit(title="Metadata only", url="", snippet="s", provider=self.name,
                              is_academic=True)]

    plan = SearchPlan.from_question("q")
    AuditedSearchExecutor([_Provider()]).execute(plan, tmp_path)
    rows = (tmp_path / "source-screening.csv").read_text().splitlines()
    assert any("needs_manual_location" in row for row in rows)
    assert not (tmp_path / "chunks.jsonl").exists()


# ------------------------------------------------------------------ discipline


def test_module_never_logs_or_returns_the_token(monkeypatch):
    monkeypatch.setenv(sciverse.TOKEN_ENV, TOKEN)
    monkeypatch.setattr(sciverse.urllib.request, "urlopen", _http_error(401, "unauthorized"))
    response = sciverse.meta_search("q")
    assert TOKEN not in json.dumps({"status": response.status, "error": response.error})


def test_chunk_locator_is_not_evidence_by_construction():
    """A chunk record has no evidence fields at all: it cannot be mistaken for
    an Evidence Object, because /content must be read first (RULE 2)."""
    record = sciverse.chunk_records(sciverse.SciverseResponse(
        sciverse.STATUS_OK,
        data={"hits": [{"chunk_id": "c", "doc_id": "d" * 64, "offset": 1, "score": 0.5}]},
    ))[0]
    for evidence_field in ("evidence_id", "claim_id", "relation_to_claim", "source_location"):
        assert evidence_field not in record
