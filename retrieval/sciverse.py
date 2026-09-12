#!/usr/bin/env python3
"""sciverse.py — Sciverse Open Platform retrieval channel (key-based).

Sciverse exposes citation-grade academic retrieval to agents through four
endpoints used here (canonical spec: openapi.yaml v0.14.2 of
opendatalab/Sciverse-Agent-Tools, archived in docs/sciverse-api.md):

    POST /meta-search            structured metadata search  -> Source-level hits
    POST /agentic-search         semantic chunk retrieval    -> chunk locators
    GET  /content                read original text slice   -> evidence content
    POST /meta-paper-relations   citations / references      -> citation chain

Scientific discipline encoded here (RULE 2): an /agentic-search chunk is a
discovery locator, never evidence. It must be expanded through ``/content``
and pass the fetch/validate gate before any extraction stage may use it.

The module is stdlib-only and never raises for network or API content issues:
every failure is reported as a typed status so the pipeline degrades cleanly
to the zero-config channels.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, List, Optional

from engine.log import get_log

log = get_log("sciverse")

BASE_URL = os.environ.get("SCIVERSE_BASE_URL", "https://api.sciverse.space").rstrip("/")
TOKEN_ENV = "SCIVERSE_API_TOKEN"
DEFAULT_TIMEOUT = 20
USER_AGENT = "EduEvidence-Research-Agent/6.1 (+https://github.com/37chengshan/eduevidence)"

#: Reading window used when expanding a chunk locator into evidence content.
DEFAULT_CONTENT_LIMIT = 4096
MAX_CONTENT_LIMIT = 16384  # LLM-facing ceiling recommended by the spec

#: Typed failure statuses (never exceptions) surfaced to callers and audits.
STATUS_OK = "ok"
STATUS_UNAVAILABLE = "SCIVERSE_UNAVAILABLE"      # no token configured
STATUS_UNAUTHORIZED = "SCIVERSE_UNAUTHORIZED"    # 401/403
STATUS_BAD_REQUEST = "SCIVERSE_BAD_REQUEST"      # 400/404/429
STATUS_UPSTREAM = "SCIVERSE_UPSTREAM_ERROR"      # 502/503/5xx
STATUS_NETWORK = "SCIVERSE_NETWORK_ERROR"        # timeout / DNS / TLS


def api_token() -> str:
    """Bearer token from the environment; empty string means unavailable."""
    return os.environ.get(TOKEN_ENV, "").strip()


def available() -> bool:
    return bool(api_token())


@dataclass
class SciverseResponse:
    """One endpoint call outcome. ``data`` is empty unless ``ok`` is True."""

    status: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    http_status: Optional[int] = None

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK


def _classify(http_status: int) -> str:
    if http_status in (401, 403):
        return STATUS_UNAUTHORIZED
    if http_status in (400, 404, 429):
        return STATUS_BAD_REQUEST
    if http_status >= 500:
        return STATUS_UPSTREAM
    return STATUS_UPSTREAM


def _error_message(body: str) -> str:
    """Extract ApiError.message without leaking tokens or full payloads."""
    try:
        payload = json.loads(body)
    except (ValueError, TypeError):
        return body.strip()[:200]
    if isinstance(payload, dict):
        for key in ("message", "error", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:200]
    return ""


def _request(
    method: str,
    path: str,
    *,
    params: Optional[dict[str, Any]] = None,
    payload: Optional[dict[str, Any]] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> SciverseResponse:
    """Single typed HTTP call. Never raises; never logs the token."""
    token = api_token()
    if not token:
        return SciverseResponse(STATUS_UNAVAILABLE, error=f"{TOKEN_ENV} is not set")

    url = BASE_URL + path
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        if clean:
            url = f"{url}?{urllib.parse.urlencode(clean)}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    body_bytes: Optional[bytes] = None
    if payload is not None:
        body_bytes = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw) if raw.strip() else {}
            return SciverseResponse(STATUS_OK, data=data if isinstance(data, dict) else {},
                                    http_status=resp.status)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = _error_message(exc.read().decode("utf-8", errors="replace"))
        except Exception:  # pragma: no cover - body already consumed/closed
            detail = ""
        status = _classify(exc.code)
        log.debug("sciverse http error path=%s status=%s", path, exc.code)
        return SciverseResponse(status, error=detail or f"HTTP {exc.code}", http_status=exc.code)
    except Exception as exc:  # timeouts, DNS, TLS, decode
        log.debug("sciverse network error path=%s err=%s", path, type(exc).__name__)
        return SciverseResponse(STATUS_NETWORK, error=type(exc).__name__)


# ---------------------------------------------------------------------------
# Endpoint wrappers (core four)
# ---------------------------------------------------------------------------

def meta_search(
    query: str,
    *,
    limit: int = 10,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    filters: Optional[list[dict[str, Any]]] = None,
    collection: str = "papers",
) -> SciverseResponse:
    """Structured metadata search (``/meta-search``). Source-level hits.

    Returns paper metadata including ``unique_id`` (always) and ``doc_id``
    (only when full text exists) — both are required for downstream
    ``/content`` and ``/meta-paper-relations`` calls.
    """
    payload: dict[str, Any] = {
        "collection": collection,
        "query": query,
        "page": 1,
        "page_size": max(1, min(limit, 50)),
    }
    advanced: list[dict[str, Any]] = list(filters or [])
    if year_from is not None:
        advanced.append({"field": "publication_published_year",
                         "operator": "FILTER_OP_GTE", "value": year_from})
    if year_to is not None:
        advanced.append({"field": "publication_published_year",
                         "operator": "FILTER_OP_LTE", "value": year_to})
    if advanced:
        payload["filters_advanced"] = advanced
    return _request("POST", "/meta-search", payload=payload)


def agentic_search(
    query: str,
    *,
    top_k: int = 10,
    mode: str = "balanced",
    filters: Optional[dict[str, Any]] = None,
) -> SciverseResponse:
    """Natural-language chunk retrieval (``/agentic-search``).

    Each hit is a locator (chunk_id/doc_id/offset/score) — a discovery aid.
    ``offset`` is a Unicode code-point offset usable directly by
    :func:`read_content`.
    """
    payload: dict[str, Any] = {
        "query": query,
        "top_k": max(1, min(top_k, 100)),
        "mode": mode if mode in ("fast", "balanced", "quality") else "balanced",
    }
    if filters:
        payload["filters"] = filters
    return _request("POST", "/agentic-search", payload=payload)


def read_content(
    doc_id: str,
    *,
    offset: int = 0,
    limit: int = DEFAULT_CONTENT_LIMIT,
) -> SciverseResponse:
    """Read original text by code-point range (``/content``).

    ``offset`` is always sent explicitly: omitting it makes the server return
    the whole document and ignore ``limit``.
    """
    return _request("GET", "/content", params={
        "doc_id": doc_id,
        "offset": max(0, int(offset)),
        "limit": max(1, min(int(limit), MAX_CONTENT_LIMIT)),
    })


def paper_relations(
    unique_id: str,
    *,
    relation: str = "REFERENCES",
    page: int = 1,
    page_size: int = 25,
) -> SciverseResponse:
    """Paginate citations / references / related works (``/meta-paper-relations``).

    ``unique_id`` (not ``doc_id``) identifies the target paper. CITATIONS is
    incoming (who cites me); REFERENCES is outgoing (who I cite).
    """
    relation_name = relation.upper()
    if relation_name not in ("CITATIONS", "REFERENCES", "RELATED_WORKS"):
        relation_name = "REFERENCES"
    return _request("POST", "/meta-paper-relations", payload={
        "unique_id": unique_id,
        "relation": relation_name,
        "page": max(1, int(page)),
        "page_size": max(1, min(int(page_size), 200)),
    })


# ---------------------------------------------------------------------------
# Chunk / relation record helpers (run-workspace working sets)
# ---------------------------------------------------------------------------

def chunk_records(response: SciverseResponse, *, query_id: str = "") -> list[dict[str, Any]]:
    """Normalize ``/agentic-search`` hits into chunk-locator records.

    These records are a working set, never evidence: they carry the locator
    (doc_id/offset) that :func:`read_content` needs.
    """
    if not response.ok:
        return []
    records: list[dict[str, Any]] = []
    for hit in response.data.get("hits") or []:
        if not isinstance(hit, dict):
            continue
        doc_id = str(hit.get("doc_id") or "")
        if not doc_id:
            continue
        records.append({
            "chunk_id": str(hit.get("chunk_id") or ""),
            "doc_id": doc_id,
            "offset": int(hit.get("offset") or 0),
            "score": float(hit.get("score") or 0.0),
            "chunk": str(hit.get("chunk") or ""),
            "title": str(hit.get("title") or ""),
            "page_no": hit.get("page_no"),
            "source_type": str(hit.get("source_type") or ""),
            "query_id": query_id,
        })
    return records


def relation_records(response: SciverseResponse, *, unique_id: str = "",
                     relation: str = "") -> list[dict[str, Any]]:
    """Normalize a ``/meta-paper-relations`` page into citation-chain records."""
    if not response.ok:
        return []
    records: list[dict[str, Any]] = []
    for item in response.data.get("items") or []:
        if not isinstance(item, dict):
            continue
        records.append({
            "source_unique_id": unique_id,
            "relation": relation,
            "id": str(item.get("id") or ""),
            "id_type": str(item.get("id_type") or ""),
            "title": str(item.get("title") or ""),
        })
    return records


# ---------------------------------------------------------------------------
# Router provider (priority: key-based academic channel)
# ---------------------------------------------------------------------------

class SciverseProvider:
    """MultiSearchRouter-compatible provider over ``/meta-search`` + ``/agentic-search``.

    ``meta_search`` is the Source-level channel; ``agentic`` (opt-in via
    ``include_chunks``) additionally records chunk locators on the hit so the
    run workspace can expand them through ``/content``.
    """

    name = "sciverse"

    def __init__(self, *, token: Optional[str] = None, include_chunks: bool = True):
        if token is not None:
            os.environ[TOKEN_ENV] = token
        self.include_chunks = include_chunks

    def is_available(self) -> bool:
        return available()

    def search(self, query: str, limit: int = 10) -> List[Any]:
        from retrieval.search import SearchHit

        if not self.is_available():
            return []
        response = meta_search(query, limit=limit)
        if not response.ok:
            log.debug("sciverse meta-search unavailable status=%s", response.status)
            return []

        chunk_index: dict[str, dict[str, Any]] = {}
        if self.include_chunks:
            semantic = agentic_search(query, top_k=max(1, min(limit, 50)))
            for record in chunk_records(semantic):
                chunk_index.setdefault(record["doc_id"], record)

        hits: List[Any] = []
        for item in response.data.get("results") or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "Untitled")
            doi = _normalize_doi(item.get("doi"))
            doc_id = str(item.get("doc_id") or "")
            unique_id = str(item.get("unique_id") or "")
            locator = chunk_index.get(doc_id, {}) if doc_id else {}

            authors = [
                str(a.get("name")) for a in (item.get("author") or [])
                if isinstance(a, dict) and a.get("name")
            ]
            hit = SearchHit(
                title=title,
                url=_source_url(doi),
                snippet=str(item.get("abstract") or title),
                provider=self.name,
                doi=doi,
                year=item.get("publication_published_year"),
                citation_count=item.get("citation_count"),
                authors=authors[:5],
                is_academic=True,
                score=1.35,
                doc_id=doc_id or None,
                chunk_id=locator.get("chunk_id"),
                offset=locator.get("offset"),
                unique_id=unique_id or None,
            )
            hits.append(hit)
        return hits


def _normalize_doi(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    doi = value.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
    return doi or None


def _source_url(doi: Optional[str]) -> str:
    """Canonical citation pointer. Never fabricate a URL for a DOI-less record:
    the empty string marks it as ``needs_manual_location`` downstream."""
    return f"https://doi.org/{doi}" if doi else ""


__all__ = [
    "BASE_URL", "TOKEN_ENV", "DEFAULT_CONTENT_LIMIT", "MAX_CONTENT_LIMIT",
    "STATUS_OK", "STATUS_UNAVAILABLE", "STATUS_UNAUTHORIZED", "STATUS_BAD_REQUEST",
    "STATUS_UPSTREAM", "STATUS_NETWORK",
    "SciverseResponse", "SciverseProvider",
    "api_token", "available", "meta_search", "agentic_search", "read_content",
    "paper_relations", "chunk_records", "relation_records",
]
