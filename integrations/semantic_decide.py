"""SemDecide CLI integration (experimental mode 2 / hybrid 3).

Exit 2/3/4 never resolve silently — escalate to the host large model.
Secrets stay in env files; never passed on argv.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

SEMDECIDE_ENV_FILE = os.environ.get("JEV_ENV_FILE", "~/.eduevidence/env")
SEMDECIDE_BIN_ENV = "SEMDECIDE_BIN"
SEMDECIDE_UNAVAILABLE = "SEMDECIDE_UNAVAILABLE"
SEMDECIDE_APPROVAL_REQUIRED = "SEMDECIDE_APPROVAL_REQUIRED"
ESCALATE_TO_LLM = "ESCALATE_TO_LLM"
DEFAULT_THRESHOLD = 0.7
DEFAULT_TIMEOUT = 10.0
DEFAULT_MIN_CONFIDENCE = 0.0
SEMDECIDE_TIMEOUT = DEFAULT_TIMEOUT
EXIT_OK = 0
EXIT_FALSE = 1
ESCALATE_EXIT_CODES = frozenset({2, 3, 4})
EXIT_MEANINGS = {
    0: "true/selected/match",
    1: "false/no match",
    2: "invalid input",
    3: "uncertain",
    4: "provider failure",
}
WRAPPED_COMMANDS = ("is", "filter", "choose", "score", "guard")

def _env_file_values(path: str | Path | None = None) -> dict[str, str]:
    try:
        text = Path(os.path.expanduser(path or SEMDECIDE_ENV_FILE)).read_text(
            encoding="utf-8")
    except OSError:
        return {}
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("\"'")
    return values


def binary_path() -> str | None:
    override = os.environ.get(SEMDECIDE_BIN_ENV)
    if override and os.path.exists(os.path.expanduser(override)):
        return os.path.expanduser(override)
    return shutil.which("semdecide")


def detect_semdecide() -> dict[str, Any]:
    """Probe the local semdecide CLI (never the network)."""
    path = binary_path()
    env_values = _env_file_values()
    has_key = bool(
        os.environ.get("TYPESAFE_API_KEY")
        or env_values.get("TYPESAFE_API_KEY")
        or os.environ.get("AI_GATEWAY_API_KEY")
        or env_values.get("AI_GATEWAY_API_KEY")
    )
    available = path is not None
    reasons: list[str] = []
    if not available:
        reasons.append("semdecide binary not on PATH (pipx/uv tool install "
                       "from sharziki/semdecide release wheel)")
    if not has_key:
        reasons.append("TYPESAFE_API_KEY / AI_GATEWAY_API_KEY not set — "
                       "semdecide will exit 4 (provider_failure)")
    return {
        "available": available,
        "state": "available" if available else "unavailable",
        "mode": "semdecide" if available else "none",
        "binary": path,
        "credentials_declared": has_key,
        "reason": "; ".join(reasons) or "semdecide on PATH",
        "reasons": reasons,
        "hint": ("install: pipx install "
                 "https://github.com/sharziki/semdecide/releases/download/"
                 "v0.2.1/semdecide-0.2.1-py3-none-any.whl"
                 if not available else ""),
        "commands": list(WRAPPED_COMMANDS),
        "escalate_exit_codes": sorted(ESCALATE_EXIT_CODES),
    }



def requires_llm_escalation(result: dict[str, Any]) -> bool:
    """True for exit 2 / 3 / 4 (and missing binary)."""
    if result.get("status") == SEMDECIDE_UNAVAILABLE:
        return True
    return result.get("exit_code") in ESCALATE_EXIT_CODES


def _run(argv: list[str], *, stdin_text: str | None = None,
         timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    path = binary_path()
    if not path:
        return {
            "status": SEMDECIDE_UNAVAILABLE,
            "exit_code": None,
            "escalate": ESCALATE_TO_LLM,
            "reason": "semdecide binary not found",
        }
    # Credentials come from the process env / credentials.env — never argv.
    env = os.environ.copy()
    for key, value in _env_file_values().items():
        env.setdefault(key, value)
    try:
        proc = subprocess.run(
            [path, *argv],
            input=stdin_text if stdin_text is not None else "",
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "SEMDECIDE_TIMEOUT",
            "exit_code": None,
            "escalate": ESCALATE_TO_LLM,
            "reason": f"semdecide timed out after {timeout}s",
        }
    except OSError as exc:
        return {
            "status": SEMDECIDE_UNAVAILABLE,
            "exit_code": None,
            "escalate": ESCALATE_TO_LLM,
            "reason": f"semdecide spawn failed: {type(exc).__name__}",
        }

    code = proc.returncode
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    payload: Any = None
    if stdout.strip().startswith("{") or stdout.strip().startswith("["):
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = None

    escalate = code in ESCALATE_EXIT_CODES
    return {
        "status": "ok" if code in (EXIT_OK, EXIT_FALSE) else EXIT_MEANINGS.get(
            code, "unknown_exit"),
        "exit_code": code,
        "exit_meaning": EXIT_MEANINGS.get(code, "unknown_exit"),
        "stdout": stdout,
        "stderr": stderr[-2000:],
        "json": payload,
        "escalate": ESCALATE_TO_LLM if escalate else None,
        "requires_llm": escalate,
    }



def is_predicate(text: str, predicate: str, *, threshold: float = DEFAULT_THRESHOLD,
                 uncertainty_margin: float = 0.0, use_json: bool = True,
                 timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """`semdecide is` — semantic predicate. Exit 2/3/4 escalate to the LLM."""
    argv = ["is", predicate, f"--threshold={threshold}",
            f"--uncertainty-margin={uncertainty_margin}"]
    if use_json:
        argv.append("--json")
    result = _run(argv, stdin_text=text, timeout=timeout)
    result["command"] = "is"
    result["predicate"] = predicate
    if isinstance(result.get("json"), dict):
        result["verdict"] = result["json"].get("verdict")
        result["probability"] = result["json"].get("probability")
        result["confidence"] = result["json"].get("confidence")
    return result


def filter_records(records: list[dict[str, Any]] | str, predicate: str, *,
                   field: str | None = "text", raw: bool = False,
                   max_records: int | None = None,
                   timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """`semdecide filter` — semantic JSONL filtering (order preserved)."""
    if isinstance(records, str):
        jsonl = records
    else:
        jsonl = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
    argv = ["filter", predicate]
    if field:
        argv.extend(["--field", field])
    if raw:
        argv.append("--raw")
    if max_records is not None:
        argv.extend(["--max-records", str(int(max_records))])
    result = _run(argv, stdin_text=jsonl + ("\n" if jsonl else ""), timeout=timeout)
    result["command"] = "filter"
    result["predicate"] = predicate
    matched: list[Any] = []
    for line in (result.get("stdout") or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            matched.append(json.loads(line))
        except json.JSONDecodeError:
            matched.append(line)
    result["matched"] = matched
    result["match_count"] = len(matched)
    # filter: exit 1 means no definite match — not an escalation by itself.
    if result.get("exit_code") == EXIT_FALSE:
        result["escalate"] = None
        result["requires_llm"] = False
    return result


def choose_route(text: str, question: str,
                 options: dict[str, str], *,
                 min_confidence: float = DEFAULT_MIN_CONFIDENCE,
                 use_json: bool = True,
                 timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """`semdecide choose` — route among named options. Exit 2/3/4 escalate."""
    argv = ["choose", question, f"--min-confidence={min_confidence}"]
    for key, description in options.items():
        argv.append(f"--option={key}={description}")
    if use_json:
        argv.append("--json")
    result = _run(argv, stdin_text=text, timeout=timeout)
    result["command"] = "choose"
    result["question"] = question
    if isinstance(result.get("json"), dict):
        result["selected"] = result["json"].get("selected") or result["json"].get("choice")
        result["probabilities"] = result["json"].get("probabilities")
        result["confidence"] = result["json"].get("confidence")
    return result


def escalate_plan(result: dict[str, Any], *, stage: str = "") -> dict[str, Any]:
    """Build the fail-closed hand-off when exit is 2/3/4 (or binary missing)."""
    code = result.get("exit_code")
    meaning = result.get("exit_meaning") or EXIT_MEANINGS.get(code, "unknown")
    return {
        "action": ESCALATE_TO_LLM,
        "reason": meaning,
        "exit_code": code,
        "stage": stage,
        "policy": {
            2: "invalid input — repair inputs and re-run, or hand the whole "
               "decision to the large model (never invent a verdict)",
            3: "uncertain under margin — route to large model / human; do not "
               "force true/false",
            4: "provider failure — degrade to large model for this call only; "
               "record the attempt",
        }.get(code if isinstance(code, int) else -1,
              "unavailable — use Platform Native / large model path"),
        "raw_status": result.get("status"),
    }



__all__ = [
    "DEFAULT_THRESHOLD", "DEFAULT_TIMEOUT", "ESCALATE_TO_LLM",
    "SEMDECIDE_APPROVAL_REQUIRED", "SEMDECIDE_BIN_ENV", "SEMDECIDE_ENV_FILE",
    "SEMDECIDE_UNAVAILABLE", "binary_path", "choose_route", "detect_semdecide",
    "escalate_plan", "filter_records", "is_predicate", "requires_llm_escalation",
]
