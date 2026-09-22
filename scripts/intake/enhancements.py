"""Round-2 enhancement blocks: Agent MCP / Jev / SemDecide."""
from __future__ import annotations

from typing import Any, Callable

from intake.constants import ENHANCEMENTS
from intake.prompts import ask, ask_multi, ask_yes, split_csv


def normalize_enhancements(enhancements: list[str] | None) -> list[str]:
    if not enhancements:
        return ["none"]
    alias = {"mcp": "agent_mcp", "agent-mcp": "agent_mcp",
             "无": "none", "不启用": "none"}
    out: list[str] = []
    for e in enhancements:
        key = alias.get(str(e).strip().lower(), str(e).strip().lower())
        if key in ENHANCEMENTS and key not in out:
            out.append(key)
    if not out:
        return ["none"]
    if "none" in out and len(out) > 1:
        return ["none"]
    return out


def collect_round1_enhancements(*, prefs: dict[str, Any],
                                enhancements: list[str] | None,
                                interactive: bool,
                                printer: Callable[[str], None] = print) -> list[str]:
    from intake.constants import ENHANCEMENT_BLURBS

    if interactive and enhancements is None:
        printer("—— 第一轮 ——")
        printer("2) 执行增强（可多选）：")
        for key, blurb in ENHANCEMENT_BLURBS.items():
            printer(f"    [{key}] {blurb}")
        default_enh = [e for e in (prefs.get("enhancement") or ["none"])
                       if e in ENHANCEMENTS] or ["none"]
        enhancements = ask_multi("请选择增强", ENHANCEMENTS, default_enh)
    elif enhancements is None:
        enhancements = list(prefs.get("enhancement") or ["none"])
    return normalize_enhancements(enhancements)


def _collect_mcp(prefs: dict[str, Any], *, interactive: bool,
                 mcp_table: list[dict[str, str]] | None,
                 printer: Callable[[str], None]) -> dict[str, Any]:
    role_mapping: dict[str, Any] = {}
    if mcp_table:
        printer("  MCP 角色 → CLI / 模型 授权表：")
        for row in mcp_table:
            printer(f"    {row.get('role', '?')} → {row.get('cli', '?')} / {row.get('model', '?')}")
            if row.get("role") and row.get("cli") and row.get("model"):
                role_mapping[str(row["role"])] = {
                    "cli": str(row["cli"]), "model": str(row["model"])}
    elif (prefs.get("mcp") or {}).get("role_mapping"):
        role_mapping = dict((prefs.get("mcp") or {}).get("role_mapping") or {})
        printer("  复用 prefs 中的 MCP 角色映射（可在批准文件中复核）。")
    authorized = True
    if interactive and mcp_table:
        authorized = ask_yes("  采用上述角色→CLI/模型表并授权？(Y/n)", True)
    elif interactive:
        authorized = ask_yes("  启用 Agent MCP 增强（角色表将由批准流程生成）？(Y/n)", True)
    return {"authorized": authorized, "role_mapping": role_mapping,
            "note": "role table persisted via agent_mcp approval when authorized"}


def _collect_jev(prefs: dict[str, Any], *, interactive: bool,
                 printer: Callable[[str], None]) -> dict[str, Any]:
    default_tools = list((prefs.get("jev") or {}).get("tool_subset") or
                         ["search", "fetch", "validate"])
    tools = default_tools
    if interactive:
        printer("  Jev 工具子集（只派发确定性小步；缺省 search/fetch/validate）")
        tools = split_csv(ask("  工具子集（逗号分隔）", ",".join(default_tools)))
    return {"tool_subset": tools or default_tools,
            "note": "Jev dispatch stays limited to this tool subset"}


def _collect_sem(interactive: bool, printer: Callable[[str], None]) -> dict[str, Any]:
    default_purpose = "结构化上游 ResearchIntent / Frame，供 recommend_mode 使用"
    purpose = default_purpose
    if interactive:
        printer("  SemDecide 用途（只结构化上游意图，不改下游确定性路由）")
        purpose = ask("  用途说明", default_purpose) or default_purpose
    return {"purpose": purpose,
            "note": "SemDecide feeds intent only; mode_router stays deterministic"}


def collect_round2_enhancements(
    enhancements: list[str], *, prefs: dict[str, Any], interactive: bool,
    mcp_table: list[dict[str, str]] | None = None,
    printer: Callable[[str], None] = print,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    """Return (mcp_block, jev_block, sem_block); None when that enhancement is off."""
    wants_mcp = "agent_mcp" in enhancements
    wants_jev = "jev" in enhancements
    wants_sem = "semdecide" in enhancements
    if interactive and (wants_mcp or wants_jev or wants_sem):
        printer("—— 第二轮（仅增强相关）——")
    mcp = _collect_mcp(prefs, interactive=interactive, mcp_table=mcp_table,
                       printer=printer) if wants_mcp else None
    jev = _collect_jev(prefs, interactive=interactive, printer=printer) if wants_jev else None
    sem = _collect_sem(interactive, printer) if wants_sem else None
    return mcp, jev, sem
