"""intake — one-shot two-round user intake + durable prefs + report open."""
from __future__ import annotations

from intake.browser import (
    maybe_open_after_run,
    open_report,
    open_url,
    resolve_main_report,
)
from intake.constants import (
    DEPTH_CHOICES,
    ENHANCEMENTS,
    ENHANCEMENT_BLURBS,
    DEPTH_BLURBS,
    FRAME_SLOTS,
    THEME_NAMES,
)
from intake.depth import auto_resolve_depth, resolve_depth
from intake.background import infer_frame_hints
from intake.prefs import default_prefs, load_prefs, prefs_path, save_prefs
from intake.prompts import PROMPT_SCRIPT
from intake.session import run_intake

__all__ = [
    "DEPTH_BLURBS", "DEPTH_CHOICES", "ENHANCEMENTS", "ENHANCEMENT_BLURBS",
    "FRAME_SLOTS", "PROMPT_SCRIPT", "THEME_NAMES",
    "auto_resolve_depth", "default_prefs", "infer_frame_hints",
    "load_prefs", "maybe_open_after_run", "open_report", "open_url",
    "prefs_path", "resolve_depth", "resolve_main_report", "run_intake",
    "save_prefs",
]
