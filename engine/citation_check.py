#!/usr/bin/env python3
"""citation_check — per-citation DOI verification against registries (plan E6).

Turns the v5.2.0 integrity audit into a first-class engine capability:

- every Source/Evidence citation can carry `doi_verified` and `retracted`
  fields, produced by this module against Crossref (most DOIs) and DataCite
  (arXiv 10.48550/*);
- verification is evidence-grade: it never guesses. A DOI that does not
  resolve is `not_found`; a resolved record whose title clearly differs from
  the local title is `mismatch`; a registered retraction is surfaced as
  `retracted=True`.

Security: identical discipline to scripts/audit_dois.py — strict DOI shape,
two allow-listed HTTPS registry hosts, redirects confined to those hosts.

Stdlib only. Network calls happen only in `verify()`/`check_doi`;
`classify()` is pure and fully unit-testable offline.
"""

from __future__ import annotations

import http.client
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

CROSSREF_API = "https://api.crossref.org/works/{doi}"
DATACITE_API = "https://api.datacite.org/dois/{doi}"
ALLOWED_HOSTS = {"api.crossref.org", "api.datacite.org"}
DATACITE_PREFIXES = {"10.48550"}
MAILTO = "citation-check@eduevidence.local"

STRICT_DOI_RE = re.compile(r"^10\.\d{4,9}/[A-Za-z0-9._()/:-]+$")
DOI_CLEAN_RE = re.compile(r"\b(10\.\d{4,9}/[A-Za-z0-9._()/:;-]+)")
STRIP_SUFFIX = ".,;)"

TITLE_OVERLAP_THRESHOLD = 0.5

# Classification vocabulary used by callers and schemas.
STATUS_OK = "ok"
STATUS_MISMATCH = "mismatch"
STATUS_NOT_FOUND = "not_found"
STATUS_ERROR = "error"


def clean_doi(doi: str) -> str:
    return doi.strip().rstrip(STRIP_SUFFIX)


def token_set(text: str) -> set[str]:
    out: set[str] = set()
    for tok in re.split(r"[^a-z0-9]+", text.lower()):
        if len(tok) > 2:
            out.add(tok)
            if tok.endswith("s") and len(tok) > 3:
                out.add(tok[:-1])
    return out


def title_overlap(a: str | None, b: str | None) -> float | None:
    if not a or not b:
        return None
    ta, tb = token_set(a), token_set(b)
    if not ta or not tb:
        return None
    return len(ta & tb) / min(len(ta), len(tb))


def classify(doi: str, registry_status: str, registry_msg: dict[str, Any] | None,
             local_title: str | None) -> dict[str, Any]:
    """Pure classifier: registry outcome + optional local title → verdict dict."""
    cr_title = None
    if isinstance(registry_msg, dict):
        titles = registry_msg.get("title") or []
        cr_title = titles[0] if titles else None
    status = registry_status
    similarity = title_overlap(local_title, cr_title)
    if status == STATUS_OK and similarity is not None and similarity < TITLE_OVERLAP_THRESHOLD:
        status = STATUS_MISMATCH

    retracted = False
    if isinstance(registry_msg, dict) and status == STATUS_OK:
        updates = registry_msg.get("update-to") or []
        if isinstance(updates, list):
            retracted = any(
                isinstance(u, dict) and str(u.get("type", "")).lower() == "retraction"
                for u in updates)
        if not retracted:
            # Some deposits mark retraction in the title itself ("Retracted: ...").
            t = (cr_title or "").strip().lower()
            retracted = t.startswith("retracted") or "(retracted" in t

    result: dict[str, Any] = {
        "doi": doi,
        "status": status,
        "doi_verified": status == STATUS_OK,
        "retracted": retracted,
        "registry_title": cr_title,
    }
    if similarity is not None:
        result["title_overlap"] = round(similarity, 3)
    return result


class _SameHostRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlparse(newurl).hostname not in ALLOWED_HOSTS:
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class RegistryClient:
    """Small cached HTTP client bound to the two registry hosts."""

    def __init__(self, timeout_s: int = 20, sleep_s: float = 0.25):
        self.timeout_s = timeout_s
        self.sleep_s = sleep_s
        self.cache: dict[str, tuple[str, dict | None]] = {}
        self.opener = urllib.request.build_opener(_SameHostRedirectHandler)

    def fetch_raw(self, doi: str) -> tuple[str, dict | None]:
        """Return (registry_status, payload_message) for a cleaned DOI."""
        if not STRICT_DOI_RE.match(doi):
            return (STATUS_ERROR, {"detail": f"strict shape check failed: {doi!r}"})
        template = DATACITE_API if doi.split("/", 1)[0] in DATACITE_PREFIXES else CROSSREF_API
        url = template.format(doi=urllib.request.quote(doi, safe=""))
        req = urllib.request.Request(url, headers={
            "User-Agent": f"EduEvidence-citation-check/1.0 (mailto:{MAILTO})"})
        result: tuple[str, dict | None] = (STATUS_ERROR, None)
        for attempt in range(2):
            try:
                with self.opener.open(req, timeout=self.timeout_s) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                message = payload.get("message", payload.get("data", {}))
                if isinstance(message, dict) and "attributes" in message:
                    attrs = message["attributes"]
                    titles = [t.get("title") for t in attrs.get("titles", []) if t.get("title")]
                    message = {"title": titles}
                result = (STATUS_OK, message)
                break
            except urllib.error.HTTPError as exc:
                result = ((STATUS_NOT_FOUND, {"status": exc.code}) if exc.code == 404
                          else (STATUS_ERROR, {"status": exc.code}))
                break
            except (urllib.error.URLError, http.client.RemoteDisconnected, ConnectionError,
                    TimeoutError, OSError, json.JSONDecodeError) as exc:
                result = (STATUS_ERROR, {"detail": str(exc)})
                if attempt == 0:
                    time.sleep(1.5)
        time.sleep(self.sleep_s)
        return result

    def check(self, doi: str, local_title: str | None = None) -> dict[str, Any]:
        doi = clean_doi(doi)
        cache_key = (doi, local_title or "")
        if cache_key not in self.cache:
            status, msg = self.fetch_raw(doi)
            self.cache[cache_key] = classify(doi, status, msg, local_title)
        return self.cache[cache_key]


def extract_dois(record: dict[str, Any]) -> list[tuple[str, str | None]]:
    """Pull (doi, paired_title) pairs from a flat artifact record."""
    pairs: list[tuple[str, str | None]] = []
    doi_val = None
    title_val = None
    for key, val in record.items():
        if not isinstance(val, str):
            continue
        k = key.strip().lower()
        if k.endswith("_doi") or k == "doi":
            d = clean_doi(val)
            if STRICT_DOI_RE.match(d):
                doi_val = d
        elif k == "title" or k == "source_title":
            title_val = val
    if doi_val:
        pairs.append((doi_val, title_val))
    else:
        for key, val in record.items():
            if isinstance(val, str):
                for raw in DOI_CLEAN_RE.findall(val):
                    d = clean_doi(raw)
                    if STRICT_DOI_RE.match(d):
                        pairs.append((d, title_val))
                        break
    return pairs
