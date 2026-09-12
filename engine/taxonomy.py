"""engine/taxonomy.py - Outcome taxonomy authority (domain registry backed).

Every domain registers its own outcome taxonomy in
``domains/<id>/outcome_taxonomy.json``. Each file declares the domain category
buckets (``categories``) and one entry per outcome token carrying an explicit
``category`` (``tokens[].category``).

This module is the ONLY reader of that contract. Before it existed, the token
set and the token-to-category mapping were hard-coded in ``engine/pilot.py``
with a ``.get(token, "learning")`` fallback, so a policy outcome was silently
classified as a learning outcome and policy runs could not complete. Callers
must no longer keep private copies of either table.

Fail-closed rule: an unknown token or an unregistered domain raises. Silent
classification is what produced the original defect; unknown input must be
visible as an error, never absorbed into a default bucket.

Stdlib only; results are cached per process.
"""
from __future__ import annotations

import json
from typing import Any, Iterable

from engine.evidencecore import list_domains, load_domain

#: Bucket used when a caller must render an outcome whose category could not be
#: resolved. It is deliberately not a domain category: it marks the value as
#: unclassified instead of pretending it belongs to a real bucket.
UNCLASSIFIED = "unclassified"

_cache: dict[str, Any] = {}


class TaxonomyError(ValueError):
    """Raised when taxonomy data is missing, malformed, or unknown."""


def _taxonomy_path(domain_id: str) -> str:
    """Registered relative path of a domain taxonomy file."""
    entry = load_domain(domain_id)
    raw = entry.get("outcome_taxonomy")
    if not raw:
        raise TaxonomyError(
            "domain " + repr(domain_id) + " registers no outcome_taxonomy")
    return str(raw).partition("#")[0]


def _load(domain_id: str) -> dict:
    """Load (and cache) one domain taxonomy, validating its shape."""
    key = "taxonomy:" + domain_id
    if key in _cache:
        return _cache[key]
    from engine._resources import resource_root

    path = resource_root() / _taxonomy_path(domain_id)
    if not path.is_file():
        raise TaxonomyError(
            "domain " + repr(domain_id) + ": taxonomy file missing: " + str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    categories = data.get("categories")
    tokens = data.get("tokens")
    if not isinstance(categories, dict) or not categories:
        raise TaxonomyError(
            "domain " + repr(domain_id) + ": taxonomy declares no categories")
    if not isinstance(tokens, list) or not tokens:
        raise TaxonomyError(
            "domain " + repr(domain_id) + ": taxonomy declares no tokens")
    seen: set[str] = set()
    for item in tokens:
        if not isinstance(item, dict) or not item.get("id"):
            raise TaxonomyError(
                "domain " + repr(domain_id) + ": token entry without an id")
        token = str(item["id"])
        if token in seen:
            raise TaxonomyError(
                "domain " + repr(domain_id) + ": duplicate token " + repr(token))
        seen.add(token)
        category = item.get("category")
        if not category:
            raise TaxonomyError(
                "domain " + repr(domain_id) + ": token " + repr(token)
                + " declares no category (silent defaults are forbidden)")
        if str(category) not in categories:
            raise TaxonomyError(
                "domain " + repr(domain_id) + ": token " + repr(token)
                + " uses category " + repr(category) + " absent from "
                + repr(sorted(categories)))
    _cache[key] = data
    return data


def _domain_ids(domain_id: str | None = None) -> tuple[str, ...]:
    if domain_id:
        return (domain_id,)
    return tuple(d["id"] for d in list_domains())


def tokens(domain_id: str) -> tuple[str, ...]:
    """Outcome tokens declared by one domain, in registry order."""
    return tuple(str(item["id"]) for item in _load(domain_id)["tokens"])


def categories(domain_id: str) -> dict[str, dict]:
    """Category buckets declared by one domain (id -> descriptor)."""
    return dict(_load(domain_id)["categories"])


def category_of(domain_id: str, token: str) -> str:
    """Category bucket for a token in a domain.

    Raises TaxonomyError for an unknown token: a caller that cannot classify a
    value must surface that, not guess. Use category_of_or_unclassified at
    rendering boundaries where an unclassified value is acceptable.
    """
    for item in _load(domain_id)["tokens"]:
        if str(item["id"]) == token:
            return str(item["category"])
    raise TaxonomyError(
        "domain " + repr(domain_id) + ": unknown outcome token " + repr(token)
        + " (" + str(len(tokens(domain_id))) + " tokens known)")


def category_of_or_unclassified(domain_id: str, token: str) -> str:
    """Rendering-safe variant: unknown tokens map to UNCLASSIFIED."""
    try:
        return category_of(domain_id, token)
    except TaxonomyError:
        return UNCLASSIFIED


def category_labels(domain_id: str, lang: str = "zh") -> dict[str, str]:
    """Display label per category bucket (falls back to the category id)."""
    suffix = "_en" if lang == "en" else "_zh"
    out: dict[str, str] = {}
    for key, descriptor in categories(domain_id).items():
        if isinstance(descriptor, dict):
            label = descriptor.get("name" + suffix) or descriptor.get("name")
            out[key] = str(label or key)
        else:
            out[key] = key
    return out


def all_tokens() -> dict[str, str]:
    """Every registered token -> owning domain, across registered domains.

    A token registered by two domains is a contract conflict and raises: the
    token would otherwise mean different things depending on lookup order.
    """
    key = "all_tokens"
    if key in _cache:
        return _cache[key]
    out: dict[str, str] = {}
    for domain_id in _domain_ids():
        for token in tokens(domain_id):
            owner = out.get(token)
            if owner is not None and owner != domain_id:
                raise TaxonomyError(
                    "outcome token " + repr(token) + " is registered by both "
                    + repr(owner) + " and " + repr(domain_id))
            out[token] = domain_id
    _cache[key] = out
    return out


def domain_of(token: str, default: str = "education") -> str:
    """Owning domain for a token; default when the token is unregistered."""
    return all_tokens().get(token, default)


def all_tokens_ordered() -> tuple[str, ...]:
    """Every registered token in domain-registry then taxonomy order."""
    ordered: list[str] = []
    for domain_id in _domain_ids():
        ordered.extend(tokens(domain_id))
    return tuple(ordered)


def all_categories() -> tuple[str, ...]:
    """Every category bucket across domains, de-duplicated, order preserved."""
    ordered: list[str] = []
    for domain_id in _domain_ids():
        for name in categories(domain_id):
            if name not in ordered:
                ordered.append(name)
    return tuple(ordered)


def categories_for_tokens(
    token_list: Iterable[str], domain_id: str = "education"
) -> dict[str, list[str]]:
    """Group tokens by category; unregistered tokens land in UNCLASSIFIED."""
    grouped: dict[str, list[str]] = {}
    for token in token_list:
        bucket = category_of_or_unclassified(domain_id, token)
        grouped.setdefault(bucket, []).append(token)
    return grouped


def reset_cache() -> None:
    """Drop memoised taxonomies (tests and long-lived processes)."""
    _cache.clear()


__all__ = [
    "UNCLASSIFIED", "TaxonomyError",
    "tokens", "categories", "category_of", "category_of_or_unclassified",
    "category_labels", "all_tokens", "all_tokens_ordered", "all_categories",
    "categories_for_tokens", "domain_of", "reset_cache",
]
