"""field_extract — pick verbatim regex matches; never model-written values."""
from __future__ import annotations

import re as _re
from typing import Any

from .config import ESCALATE_TO_LLM, JEV_INVALID_RESPONSE, THRESHOLDS
from .gateway import _prob, system_one


def extract(document: str, fields: list[dict[str, Any]], *,
            approval: dict[str, Any] | None = None,
            auto_accept: float | None = None,
            minimum_margin: float | None = None,
            timeout: float = 20.0) -> dict[str, Any]:
    """field_extract — pick verbatim regex matches; never model-written values."""
    auto_accept = THRESHOLDS["extract_auto_accept"] if auto_accept is None else auto_accept
    minimum_margin = (THRESHOLDS["extract_minimum_margin"]
                      if minimum_margin is None else minimum_margin)
    doc = document[:50_000]
    prepared: list[dict[str, Any]] = []
    questions: dict[str, Any] = {}
    for i, field in enumerate(fields[:32]):
        fid = str(field.get("id") or f"field{i}")
        pattern = field.get("pattern") or ""
        try:
            matches = [m.group(0) for m in _re.finditer(pattern, doc)]
        except _re.error as exc:
            prepared.append({"id": fid, "value": None, "status": "invalid_pattern",
                             "reason": str(exc)})
            continue
        matches = [m for m in matches if 0 < len(m) <= 2_000][:20]
        if not matches:
            prepared.append({"id": fid, "value": None, "status": "not_found",
                             "reason": "no_regex_matches", "candidates_considered": 0})
            continue
        uniq: list[str] = []
        for m in matches:
            if m not in uniq:
                uniq.append(m)
        criteria = {f"m{j}": (m[:200] if m else m) for j, m in enumerate(uniq)}
        criteria["none_of_them"] = "None of the candidate matches is this field's value"
        questions[f"f{i}"] = {
            "type": "choice",
            "instructions": {
                "description": str(field.get("description") or fid)[:500],
                "question": "Which candidate is the field's real value in the document?",
            },
            "criteria": {k: None for k in criteria},
        }
        prepared.append({
            "id": fid, "question_key": f"f{i}", "status": "pending",
            "candidates": uniq, "value": None,
        })

    if not questions:
        return {"status": "ok", "tool": "extract", "results": prepared,
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "note": "all fields zero-match or invalid; no API call made",
                "escalate": None}

    result = system_one({"document": doc}, questions, approval=approval,
                        tool="extract", timeout=timeout)
    if result.get("status") != "ok":
        result["results"] = prepared
        return result

    outputs: list[dict[str, Any]] = []
    for row in prepared:
        if row.get("status") in ("not_found", "invalid_pattern"):
            outputs.append(row)
            continue
        ans = result["answers"].get(row["question_key"]) or {}
        choice = ans.get("choice")
        probs = ans.get("probabilities") or {}
        conf = _prob(ans.get("confidence"))
        candidates = row["candidates"]
        if choice == "none_of_them":
            outputs.append({"id": row["id"], "value": None, "status": "not_found",
                            "reason": "none_of_them", "confidence": conf,
                            "candidates_considered": len(candidates)})
            continue
        try:
            idx = int(str(choice)[1:]) if str(choice).startswith("m") else -1
        except ValueError:
            idx = -1
        if idx < 0 or idx >= len(candidates):
            outputs.append({"id": row["id"], "value": None,
                            "status": JEV_INVALID_RESPONSE, "confidence": conf,
                            "candidates_considered": len(candidates)})
            continue
        values = sorted(((_prob(p) or 0.0) for p in probs.values()), reverse=True)
        margin = (values[0] - values[1]) if len(values) >= 2 else 1.0
        auto = (conf is not None and conf >= auto_accept and margin >= minimum_margin)
        outputs.append({
            "id": row["id"],
            "value": candidates[idx],
            "status": "auto" if auto else "review",
            "confidence": conf,
            "margin": margin,
            "candidates_considered": len(candidates),
            "verbatim": True,
        })

    result["results"] = outputs
    result["auto_accept"] = auto_accept
    result["minimum_margin"] = minimum_margin
    if any(r.get("status") == JEV_INVALID_RESPONSE for r in outputs):
        result["status"] = JEV_INVALID_RESPONSE
        result["escalate"] = ESCALATE_TO_LLM
    return result
