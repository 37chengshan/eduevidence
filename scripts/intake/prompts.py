"""TTY prompt helpers and the fixed two-round prompt script."""
from __future__ import annotations

import re
import sys


def is_interactive() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


def ask(prompt: str, default: str | None = None) -> str:
    """Single-line ask; empty input keeps default. Never invents a default."""
    suffix = f" [{default}]" if default not in (None, "") else ""
    try:
        raw = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        return default or ""
    return raw or (default or "")


def ask_yes(prompt: str, default_yes: bool = True) -> bool:
    default = "Y" if default_yes else "n"
    ans = ask(prompt, default).lower()
    return ans not in ("n", "no")


def ask_multi(prompt: str, allowed: tuple[str, ...], default: list[str]) -> list[str]:
    """Comma-separated multi-select against `allowed`."""
    legend = "/".join(allowed)
    raw = ask(f"{prompt}（可多选，逗号分隔，{legend}）",
              ",".join(default) if default else None)
    if not raw:
        return list(default) or ["none"]
    alias = {"mcp": "agent_mcp", "agent-mcp": "agent_mcp",
             "否": "none", "无": "none", "不启用": "none"}
    picked: list[str] = []
    for token in re.split(r"[,，\s]+", raw):
        t = token.strip().lower()
        if not t:
            continue
        key = alias.get(t, t)
        if key in allowed and key not in picked:
            picked.append(key)
    if not picked:
        return list(default) or ["none"]
    if "none" in picked and len(picked) > 1:
        return ["none"]
    return picked


def split_csv(raw: str) -> list[str]:
    return [t.strip() for t in re.split(r"[,，\s]+", raw or "") if t.strip()]


PROMPT_SCRIPT = """\
EduEvidence 一次性两轮引导（固定语句，用户只答模式和问题）

—— 第一轮 ——
1) 研究问题（必填）
2) 执行增强（可多选，各附一句话简介）：
   [agent_mcp] Agent MCP — 多 CLI/多模型分工、独立子上下文、超时恢复（可选执行增强）
   [jev]       Jev — 轻量工具子集派发，适合把确定性小步交给受限工具面
   [semdecide] SemDecide — 语义决策辅助，只结构化上游意图，不改下游确定性路由
   [none]      均不启用 — 平台原生模式，零外部执行增强
3) 深度：
   [S]    S 快检 — 单点问题，最小检索面，直接给边界结论
   [M]    M 标准 — 常规采用/比较问题，标准证据到决策流程
   [L]    L 深研 — 高影响、有争议或要试点，完整深研与决策扩展
   [auto] 自动 — 单点→S，常规采用→M，高影响/争议/要试点→L，不确定取 M

—— 第二轮（仅增强开启时的增强项；背景深挖始终执行）——
· Agent MCP 开 → 角色 → CLI / 模型 授权表（只展示已扫描到的真实 CLI/模型）
· Jev 开 → 工具子集（search / fetch / validate / …）
· SemDecide 开 → 用途说明（只结构化上游意图）
· 背景智能深挖：按题目推断领域 Frame 骨架后，针对该题追问 3–6 个影响边界的问题
  （人群 / 干预 / 对照 / 主结果 / 情境），智能默认 + 一次确认，禁止编造。

—— 收尾 ——
摘要一次确认后无人值守。prefs 只记 enhancement / mcp·jev 映射 / depth /
open_browser / default_main_theme，不记研究问题。五主题全渲染，主报告只决定打开哪份。
"""
