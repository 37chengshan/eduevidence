"""System One transport (stdlib urllib only) + provider error mapping."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .approval import _check_approval, detect_jev_mcp, load_approval
from .config import (
    ESCALATE_TO_LLM,
    JEV_APPROVAL_REQUIRED,
    JEV_INVALID_RESPONSE,
    JEV_PROVIDER_ERROR,
    JEV_UNAVAILABLE,
    api_key,
    model_id,
    system_one_url,
)


def _http_post_json(url: str, payload: dict[str, Any], *,
                    timeout: float = 20.0) -> tuple[int, dict[str, Any] | None, str]:
    """POST JSON with Bearer key. Returns (status, body|None, error)."""
    key = api_key()
    if not key:
        return 0, None, "AI_GATEWAY_API_KEY missing"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw), ""
            except json.JSONDecodeError:
                return resp.status, None, "response is not JSON"
    except urllib.error.HTTPError as exc:
        # Never echo Authorization / key fragments.
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:400]
        except OSError:
            pass
        return exc.code, None, f"HTTP {exc.code}: {detail}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, None, f"network error: {type(exc).__name__}"


def _map_provider_error(status: int) -> str:
    """Map HTTP status to a fail-closed JEV_* status code."""
    return (JEV_PROVIDER_ERROR if status in (401, 403, 429, 529) or status >= 500
            else JEV_INVALID_RESPONSE)


def system_one(state: Any, questions: dict[str, Any], *,
               approval: dict[str, Any] | None,
               tool: str | None = None,
               timeout: float = 20.0) -> dict[str, Any]:
    """UNIFIED network entry. Business code MUST NOT POST directly.

    Gate: approval exists -> tool approved -> credentials present -> POST.
    Fail-closed: every transport / envelope problem returns a structured
    error that callers must escalate to the large model (never invent answers).

    FreeJev: any request_id is a one-shot idempotency key — never retry the
    same request_id after timeout / 5xx / unknown outcome. Escalate instead;
    a deliberate re-ask must mint a new request_id.
    """
    approval = approval if approval is not None else load_approval()
    if tool is not None:
        failure = _check_approval(approval, tool)
        if failure is not None:
            return {"status": failure, "tool": tool, "answers": None,
                    "escalate": ESCALATE_TO_LLM}
    elif not approval or not approval.get("approved"):
        return {"status": JEV_APPROVAL_REQUIRED, "answers": None,
                "escalate": ESCALATE_TO_LLM}

    report = detect_jev_mcp()
    if not report["available"]:
        return {"status": JEV_UNAVAILABLE, "tool": tool, "answers": None,
                "escalate": ESCALATE_TO_LLM, "hint": report.get("hint", "")}

    payload = {
        "model": model_id(),
        "state": state,
        "questions": questions,
    }
    status, body, err = _http_post_json(system_one_url(), payload, timeout=timeout)
    if body is None:
        code = _map_provider_error(status)
        return {"status": code, "tool": tool, "http_status": status,
                "error": err, "answers": None, "escalate": ESCALATE_TO_LLM}

    answers = body.get("answers")
    usage = body.get("usage") or {}
    if not isinstance(answers, dict):
        return {"status": JEV_INVALID_RESPONSE, "tool": tool,
                "error": "missing or non-object answers envelope",
                "answers": None, "escalate": ESCALATE_TO_LLM}
    return {
        "status": "ok",
        "tool": tool,
        "model": body.get("model") or model_id(),
        "answers": answers,
        "usage": {
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
        },
        "escalate": None,
    }


def _prob(value: Any) -> float | None:
    try:
        p = float(value)
    except (TypeError, ValueError):
        return None
    if p != p or p < 0.0 or p > 1.0:  # NaN or out of range
        return None
    return p
