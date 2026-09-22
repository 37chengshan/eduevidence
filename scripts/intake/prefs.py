"""Durable non-question prefs at ~/.eduevidence/prefs.json."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from intake.constants import DEPTH_CHOICES, PREFS_NAME, SCHEMA_VERSION, THEME_NAMES


def prefs_path() -> Path:
    """~/.eduevidence/prefs.json (EDUEVIDENCE_HOME wins)."""
    home = Path(os.environ.get("EDUEVIDENCE_HOME", "~/.eduevidence")).expanduser()
    return home / PREFS_NAME


def default_prefs() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "enhancement": ["none"],
        "mcp": {"role_mapping": {}},
        "jev": {"tool_subset": []},
        "semdecide": {"purpose": ""},
        "depth_preference": "auto",
        "open_browser": True,
        "default_main_theme": "claude",
    }


def _sanitize(prefs: dict[str, Any]) -> dict[str, Any]:
    prefs.pop("question", None)
    prefs.pop("research_question", None)
    if prefs.get("default_main_theme") not in THEME_NAMES:
        prefs["default_main_theme"] = "claude"
    if prefs.get("depth_preference") not in DEPTH_CHOICES:
        prefs["depth_preference"] = "auto"
    enh = prefs.get("enhancement") or ["none"]
    if "none" in enh and len(enh) > 1:
        enh = ["none"]
    prefs["enhancement"] = enh or ["none"]
    return prefs


def load_prefs() -> dict[str, Any]:
    """Load prefs; missing/corrupt → defaults. Never contains a question."""
    path = prefs_path()
    prefs = default_prefs()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return prefs
    if not isinstance(data, dict):
        return prefs
    for key in ("schema_version", "enhancement", "mcp", "jev", "semdecide",
                "depth_preference", "open_browser", "default_main_theme"):
        if key in data:
            prefs[key] = data[key]
    return _sanitize(prefs)


def save_prefs(prefs: dict[str, Any]) -> Path:
    """Persist non-question prefs. Refuses to write a question field.

    Atomic write: temp file + os.replace so a crash cannot leave a torn prefs.json.
    """
    payload = {k: v for k, v in prefs.items()
               if k not in ("question", "research_question")}
    payload.setdefault("schema_version", SCHEMA_VERSION)
    path = prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)
    return path
