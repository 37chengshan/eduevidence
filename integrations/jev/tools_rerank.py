"""semantic_rerank — score and sort candidates by relevance (discovery order)."""
from __future__ import annotations

from typing import Any

from .config import ESCALATE_TO_LLM, JEV_INVALID_RESPONSE, THRESHOLDS
from .gateway import _prob, system_one


def rerank(query: str, candidates: list[dict[str, Any]], *,
           approval: dict[str, Any] | None = None,
           auto_accept: float | None = None,
           timeout: float = 20.0) -> dict[str, Any]:
    """semantic_rerank — score and sort candidates by relevance (discovery order)."""
    auto_accept = THRESHOLDS["rerank_auto_accept"] if auto_accept is None else auto_accept
    capped = candidates[:250]
    state = {
        "query": query[:2_000],
        "candidates": [
            {"id": str(c.get("id", i)), "text": str(c.get("text", ""))[:2_000]}
            for i, c in enumerate(capped)
        ],
    }
    questions = {
        f"c{i}": {
            "type": "noul",
            "instructions": {
                "query": query[:2_000],
                "candidate": state["candidates"][i]["text"],
                "question": "Is this candidate relevant to `query`?",
            },
        }
        for i in range(len(state["candidates"]))
    }
    result = system_one(state, questions, approval=approval, tool="rerank",
                        timeout=timeout)
    if result.get("status") != "ok":
        result["ranked"] = []
        return result

    scored: list[dict[str, Any]] = []
    invalid = False
    for i, cand in enumerate(state["candidates"]):
        ans = result["answers"].get(f"c{i}") or {}
        rel = _prob(ans.get("noul"))
        if rel is None:
            invalid = True
            rel = 0.0
        scored.append({
            "id": cand["id"],
            "relevance": rel,
            "auto": rel >= auto_accept,
            "text": cand["text"],
        })
    scored.sort(key=lambda r: r["relevance"], reverse=True)
    ranked = []
    for rank, row in enumerate(scored, start=1):
        ranked.append({
            "rank": rank,
            "id": row["id"],
            "relevance": row["relevance"],
            "auto": row["auto"],
        })
    if invalid:
        result["status"] = JEV_INVALID_RESPONSE
        result["escalate"] = ESCALATE_TO_LLM
        result["reason"] = "one or more relevance scores missing; order provisional"
    result["ranked"] = ranked
    result["auto_accept"] = auto_accept
    result["note"] = "ranking is discovery order only; never evidence"
    return result
