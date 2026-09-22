"""One-shot two-round intake session (question → mode → confirm → unattended)."""
from __future__ import annotations

from typing import Any, Callable

from intake.background import collect_frame_hints
from intake.constants import DEPTH_BLURBS, DEPTH_CHOICES, FRAME_SLOTS, SCHEMA_VERSION, THEME_NAMES
from intake.depth import normalize_depth_choice, resolve_depth
from intake.enhancements import collect_round1_enhancements, collect_round2_enhancements
from intake.prefs import load_prefs, prefs_path, save_prefs
from intake.prompts import ask, ask_yes, is_interactive


def _round1_question(question: str | None, *, interactive: bool) -> str:
    q = (question or "").strip()
    if interactive and not q:
        q = ask("1) 研究问题（必填）")
    if not q:
        raise ValueError("research question is required (round 1)")
    return q


def _round1_depth(depth: str | None, *, prefs: dict[str, Any],
                  interactive: bool,
                  printer: Callable[[str], None]) -> str | None:
    depth_choice = normalize_depth_choice(depth)
    if interactive and depth_choice is None:
        printer("3) 深度：")
        for key, blurb in DEPTH_BLURBS.items():
            printer(f"    [{key}] {blurb}")
        picked = ask("请选择深度 (S/M/L/auto)", prefs.get("depth_preference") or "auto")
        depth_choice = picked if picked in DEPTH_CHOICES else "auto"
    return depth_choice


def _wrap_up(*, question: str, enhancements: list[str], depth_resolved: str,
             depth_why: str, frame_hints: dict[str, Any],
             open_browser_flag: bool, theme: str, interactive: bool,
             printer: Callable[[str], None]) -> bool:
    if not interactive:
        return True
    printer("—— 收尾摘要（一次确认后无人值守）——")
    printer(f"  问题：{question}")
    printer(f"  增强：{', '.join(enhancements)}")
    printer(f"  深度：{depth_resolved}（{depth_why}）")
    printer(f"  边界：{ {k: frame_hints.get(k) for k in FRAME_SLOTS} }")
    printer(f"  结束后打开报告：{'是' if open_browser_flag else '否'} ｜ 主主题：{theme}")
    confirmed = ask_yes("  确认并开始无人值守执行？(Y/n)", True)
    if not confirmed:
        raise ValueError("intake summary not confirmed; abort before unattended run")
    return True


def _persist_prefs(enhancements: list[str], mcp_block: dict[str, Any] | None,
                   jev_block: dict[str, Any] | None, sem_block: dict[str, Any] | None,
                   prefs: dict[str, Any], *, depth_choice: str,
                   open_browser_flag: bool, theme: str) -> None:
    next_prefs = {
        "schema_version": SCHEMA_VERSION,
        "enhancement": enhancements,
        "mcp": {"role_mapping": (mcp_block or {}).get("role_mapping")
                or (prefs.get("mcp") or {}).get("role_mapping") or {}},
        "jev": {"tool_subset": (jev_block or {}).get("tool_subset")
                or (prefs.get("jev") or {}).get("tool_subset") or []},
        "depth_preference": depth_choice,
        "open_browser": open_browser_flag,
        "default_main_theme": theme,
    }
    if sem_block and sem_block.get("purpose"):
        next_prefs["semdecide"] = {"purpose": sem_block["purpose"]}
    save_prefs(next_prefs)


def run_intake(
    question: str | None = None,
    *,
    depth: str | None = None,
    enhancements: list[str] | None = None,
    domain: str = "education",
    interactive: bool | None = None,
    assume_yes: bool = False,
    open_browser: bool | None = None,
    default_main_theme: str | None = None,
    mcp_table: list[dict[str, str]] | None = None,
    persist_prefs: bool = True,
    printer: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Run the one-shot two-round intake and return a validated intake record.

    - `assume_yes` / non-TTY → silent: prefs + explicit args only, no prompts.
    - `interactive` forces TTY behaviour (tests can inject `printer` + stdin).
    - User answers only mode and questions; everything else is inferred with
      hard no-fabrication rules.
    """
    prefs = load_prefs()
    if interactive is None:
        interactive = (not assume_yes) and is_interactive()

    q = _round1_question(question, interactive=interactive)
    enhancements = collect_round1_enhancements(
        prefs=prefs, enhancements=enhancements,
        interactive=interactive, printer=printer)
    depth_choice = _round1_depth(depth, prefs=prefs, interactive=interactive,
                                 printer=printer)

    mcp_block, jev_block, sem_block = collect_round2_enhancements(
        enhancements, prefs=prefs, interactive=interactive,
        mcp_table=mcp_table, printer=printer)

    frame_hints = collect_frame_hints(q, domain=domain, interactive=interactive,
                                      printer=printer)

    depth_choice, depth_resolved, depth_why = resolve_depth(
        depth_choice if depth_choice in DEPTH_CHOICES else (depth_choice or None),
        q, frame_hints, prefs)

    open_browser_flag = (prefs.get("open_browser", True) if open_browser is None
                         else bool(open_browser))
    theme = default_main_theme or prefs.get("default_main_theme") or "claude"
    if theme not in THEME_NAMES:
        theme = "claude"

    source = "interactive" if interactive else ("yes_flag" if assume_yes else "silent")
    summary_confirmed = _wrap_up(
        question=q, enhancements=enhancements, depth_resolved=depth_resolved,
        depth_why=depth_why, frame_hints=frame_hints,
        open_browser_flag=open_browser_flag, theme=theme,
        interactive=interactive, printer=printer)

    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "research_question": q,
        "enhancements": enhancements,
        "depth": depth_resolved,
        "depth_choice": depth_choice if depth_choice in DEPTH_CHOICES else "auto",
        "depth_rationale": depth_why,
        "mcp": mcp_block,
        "jev": jev_block,
        "semdecide": sem_block,
        "frame_hints": frame_hints,
        "summary_confirmed": summary_confirmed,
        "open_browser": open_browser_flag,
        "default_main_theme": theme,
        "interactive": bool(interactive),
        "source": source,
    }
    if persist_prefs:
        _persist_prefs(enhancements, mcp_block, jev_block, sem_block, prefs,
                       depth_choice=record["depth_choice"],
                       open_browser_flag=open_browser_flag, theme=theme)
        record["prefs_path"] = str(prefs_path())
    return record
