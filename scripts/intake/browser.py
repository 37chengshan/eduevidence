"""Main-report resolution and optional system-browser open."""
from __future__ import annotations

import webbrowser
from pathlib import Path

from intake.constants import THEME_NAMES
from intake.prefs import load_prefs
from intake.prompts import is_interactive


def resolve_main_report(directory: Path | str, theme: str | None = None) -> Path | None:
    """Pick the main report file. All five themes stay on disk.

    Preference order:
      reports-5themes/EduEvidence_Report_<theme>.html
      reports-5themes/EduEvidence_Report_claude.html
      report.html
      EduEvidence_Report.html
    """
    root = Path(directory)
    if not root.is_dir():
        return None
    theme = theme if theme in THEME_NAMES else "claude"
    variants = root / "reports-5themes"
    candidates = [
        variants / f"EduEvidence_Report_{theme}.html",
        variants / "EduEvidence_Report_claude.html",
        root / "report.html",
        root / "EduEvidence_Report.html",
    ]
    for path in candidates:
        if path.is_file() and path.stat().st_size > 2:
            return path
    return None


def open_report(directory: Path | str, theme: str | None = None,
                *, force: bool = False) -> bool:
    """Open the preferred main report in the system browser.

    Only opens when `force` or prefs.open_browser is set. The caller should
    also suppress this on non-TTY if silent behaviour is required.
    """
    prefs = load_prefs()
    if not force and not prefs.get("open_browser", True):
        return False
    path = resolve_main_report(directory, theme or prefs.get("default_main_theme"))
    if path is None:
        return False
    try:
        webbrowser.open(path.resolve().as_uri())
    except Exception:
        return False
    return True


def open_url(url: str, *, force: bool = False) -> bool:
    prefs = load_prefs()
    if not force and not prefs.get("open_browser", True):
        return False
    try:
        webbrowser.open(url)
    except Exception:
        return False
    return True


def maybe_open_after_run(run_dir: Path | str, *, theme: str | None = None,
                         interactive: bool | None = None) -> bool:
    """End-of-run auto-open. Silent on non-TTY so tests stay quiet."""
    if interactive is None:
        interactive = is_interactive()
    if not interactive:
        return False
    prefs = load_prefs()
    if not prefs.get("open_browser", True):
        return False
    return open_report(run_dir, theme or prefs.get("default_main_theme"), force=True)
