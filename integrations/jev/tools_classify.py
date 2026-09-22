"""classify_check — batch label items against a closed class catalog."""
from __future__ import annotations

from typing import Any

from .config import ESCALATE_TO_LLM, JEV_INVALID_RESPONSE, THRESHOLDS
from .gateway import _prob, system_one


def classify(items: list[dict[str, Any]], classes: list[dict[str, Any]],
             *, purpose: str = "classify", approval: dict[str, Any] | None = None,
             auto_accept: float | None = None,
             minimum_margin: float | None = None,
             timeout: float = 20.0) -> dict[str, Any]:
    """classify_check — batch label items against a closed class catalog."""
    auto_accept = (THRESHOLDS["classify_auto_accept"]
                   if auto_accept is None else auto_accept)
    minimum_margin = (THRESHOLDS["classify_minimum_margin"]
                      if minimum_margin is None else minimum_margin)
    class_map = {str(c.get("id")): str(c.get("description") or c.get("id"))
                 for c in classes[:250] if c.get("id")}
    if not class_map:
        return {"status": JEV_INVALID_RESPONSE, "tool": "classify", "results": [],
                "error": "empty class catalog", "escalate": ESCALATE_TO_LLM}
    state = {
        "purpose": purpose[:500],
        "classes": class_map,
        "items": [
            {"id": str(it.get("id", i)), "text": str(it.get("text", ""))[:2_000]}
            for i, it in enumerate(items[:64])
        ],
    }
    questions = {
        f"i{j}": {
            "type": "choice",
            "instructions": {
                "purpose": purpose[:500],
                "item": state["items"][j]["text"],
                "question": "Which class best describes this item?",
            },
            "criteria": {cid: None for cid in class_map},
        }
        for j in range(len(state["items"]))
    }
    result = system_one(state, questions, approval=approval, tool="classify",
                        timeout=timeout)
    if result.get("status") != "ok":
        result["results"] = []
        return result

    outputs: list[dict[str, Any]] = []
    for j, item in enumerate(state["items"]):
        ans = result["answers"].get(f"i{j}") or {}
        label = ans.get("choice")
        probs = {str(k): _prob(v) or 0.0 for k, v in (ans.get("probabilities") or {}).items()}
        conf = _prob(ans.get("confidence"))
        values = sorted(probs.values(), reverse=True)
        margin = (values[0] - values[1]) if len(values) >= 2 else 1.0
        if label not in class_map:
            outputs.append({"id": item["id"], "classification": None,
                            "status": JEV_INVALID_RESPONSE, "confidence": conf})
            continue
        auto = (conf is not None and conf >= auto_accept and margin >= minimum_margin)
        outputs.append({
            "id": item["id"],
            "classification": label,
            "margin": margin,
            "confidence": conf,
            "decision": "auto" if auto else "review",
            "probabilities": probs,
        })
    by_class: dict[str, int] = {}
    for row in outputs:
        if row.get("classification"):
            by_class[row["classification"]] = by_class.get(row["classification"], 0) + 1
    result["results"] = outputs
    result["summary"] = {
        "items": len(outputs),
        "auto": sum(1 for r in outputs if r.get("decision") == "auto"),
        "review": sum(1 for r in outputs if r.get("decision") != "auto"),
        "by_class": by_class,
    }
    result["auto_accept"] = auto_accept
    result["minimum_margin"] = minimum_margin
    if any(r.get("status") == JEV_INVALID_RESPONSE for r in outputs):
        result["status"] = JEV_INVALID_RESPONSE
        result["escalate"] = ESCALATE_TO_LLM
    return result
