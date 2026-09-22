"""claim_verify — claim vs evidence relation (assist only)."""
from __future__ import annotations

from typing import Any

from .config import ESCALATE_TO_LLM, JEV_INVALID_RESPONSE, THRESHOLDS
from .gateway import _prob, system_one


def verify(claims: list[str], evidence: str | list[dict[str, Any]], *,
           approval: dict[str, Any] | None = None,
           auto_accept: float | None = None,
           timeout: float = 20.0) -> dict[str, Any]:
    """claim_verify — claim vs evidence relation (assist only).

    Does NOT replace Skeptic nine checks or scripts/pre_verdict_gate.py.
    """
    auto_accept = (THRESHOLDS["verify_auto_accept"]
                   if auto_accept is None else auto_accept)
    if isinstance(evidence, str):
        ev_state: Any = evidence[:50_000]
    else:
        ev_state = [
            {"id": str(e.get("id", i)), "text": str(e.get("text", ""))[:20_000]}
            for i, e in enumerate(evidence[:16])
        ]
    state = {
        "claims": [str(c)[:2_000] for c in claims[:16]],
        "evidence": ev_state,
    }
    questions = {
        f"claim{j}": {
            "type": "choice",
            "instructions": {
                "claim": state["claims"][j],
                "question": "How does the evidence relate to the claim? "
                            "Use only the evidence, not world knowledge.",
            },
            "criteria": {
                "supports": "Evidence states or directly implies the claim is true",
                "contradicts": "Evidence states or implies the claim is false",
                "says_nothing": "Evidence does not address the claim",
            },
        }
        for j in range(len(state["claims"]))
    }
    result = system_one(state, questions, approval=approval, tool="verify",
                        timeout=timeout)
    if result.get("status") != "ok":
        result["results"] = []
        result["summary"] = {}
        return result

    verdict_map = {
        "supports": "verified",
        "contradicts": "contradicted",
        "says_nothing": "unsupported",
    }
    outputs: list[dict[str, Any]] = []
    for j, claim in enumerate(state["claims"]):
        ans = result["answers"].get(f"claim{j}") or {}
        relation = ans.get("choice")
        conf = _prob(ans.get("confidence"))
        if relation not in verdict_map:
            outputs.append({"claim": claim, "verdict": "unknown",
                            "status": JEV_INVALID_RESPONSE, "confidence": None,
                            "action": "review"})
            continue
        verdict = verdict_map[relation]
        auto = conf is not None and conf >= auto_accept
        outputs.append({
            "claim": claim,
            "relation": relation,
            "verdict": verdict,
            "confidence": conf,
            "action": "auto" if auto else "review",
            "probabilities": ans.get("probabilities"),
        })
    summary = {"verified": 0, "contradicted": 0, "unsupported": 0,
               "unknown": 0, "needs_review": 0}
    for row in outputs:
        key = row.get("verdict", "unknown")
        if key in summary:
            summary[key] += 1
        if row.get("action") != "auto":
            summary["needs_review"] += 1
    result["results"] = outputs
    result["summary"] = summary
    result["auto_accept"] = auto_accept
    result["does_not_replace"] = ["Skeptic nine checks", "pre_verdict_gate",
                                  "methodology_appraisal", "tribunal"]
    if any(r.get("status") == JEV_INVALID_RESPONSE for r in outputs):
        result["status"] = JEV_INVALID_RESPONSE
        result["escalate"] = ESCALATE_TO_LLM
    return result
