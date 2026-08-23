#!/usr/bin/env python3
"""startup_probe.py — Skill 启动能力检测（SKILL.md §5.5 启动清单动态填充）。

只探测【主会话看不到的信息】：
  1. Agent MCP 配置状态（MCP 工具可见性以会话内为准）
  2. 各 CLI 当前可用的模型（按 provider 段解析，保留前缀端点；系列只列最新）

【不探测】宿主原生子代理池——主会话模型自己就能直接看见（task/scout/reviewer 等）。

⚠️ 模型名=完整端点：中转站注入的模型名带 provider 段前缀（如 opencodex/pro/gpt-5.6-sol、
opencode-go/deepseek-v4-flash），同一后缀不同前缀是不同端点。派发时必须使用完整模型名。

用法：
    python3 scripts/startup_probe.py             # JSON 输出
    python3 scripts/startup_probe.py --markdown  # 输出启动清单的"当前会话能力检测"段
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# 各 CLI 的探测命令（存在才列）
CLI_PROBES: dict[str, list[str]] = {
    "omp": ["omp", "models"],
    "codex": ["codex", "--help"],
    "claude": ["claude", "--version"],
    "opencode": ["opencode", "--version"],
    "grok": ["grok", "--version"],
    "kimi": ["kimi", "--version"],
}

# 各系列"最新模型"显示顺序（按系列去重，只列最新）
# 档位：旗舰（FLAGSHIP）= 复杂推理/裁决；基础（BASE）= 检索/抽取/结构化
SERIES_PRIORITY = [
    # OpenAI 系
    "gpt-5.5", "gpt-5.6-sol", "gpt-5.6-luna", "gpt-5.6-terra",
    # Anthropic 系
    "claude-opus-5", "claude-fable-5", "claude-sonnet-5",
    # DeepSeek 系
    "deepseek-v4-pro", "deepseek-v4-flash", "ds-flash",
    # GLM 系
    "glm-5.3", "glm-5.2", "glm-5.1",
    # Kimi 系
    "kimi-k3", "kimi-k2.7",
    # 其余
    "qwen3.8-max", "qwen3.7-plus",
    "minimax-m3", "minimax-m2.7",
    "grok-4.5",
]

# 档位标注（展示用；不写死路由，路由以用户授权为准）
MODEL_TIERS = {
    # 旗舰（strong / independent）
    "gpt-5.5": "FLAGSHIP", "gpt-5.6-sol": "FLAGSHIP",
    "claude-opus-5": "FLAGSHIP", "claude-fable-5": "FLAGSHIP",
    "glm-5.3": "FLAGSHIP", "deepseek-v4-pro": "FLAGSHIP", "kimi-k3": "FLAGSHIP",
    # 基础（fast）
    "ds-flash": "BASE", "deepseek-v4-flash": "BASE",
    "gpt-5.6-luna": "BASE", "gpt-5.6-terra": "BASE",
    "claude-sonnet-5": "BASE", "glm-5.2": "BASE", "glm-5.1": "BASE",
    "kimi-k2.7": "BASE",
}

# 模型默认思考等级（主会话内置知识，无需用户确认）
THINKING_LEVELS = {
    "deepseek-v4-flash": "max",
    "deepseek-v4-pro": "max",
    "ds-flash": "max",
    "gpt-5.5": "high",
    "gpt-5.6-sol": "high",
    "gpt-5.6-luna": "high",
    "gpt-5.6-terra": "high",
    "claude-opus-5": "high",
    "claude-fable-5": "high",
    "claude-sonnet-5": "high",
    "glm-5.3": "high",
    "glm-5.2": "high",
    "glm-5.1": "high",
    "kimi-k3": "high",
    "kimi-k2.7": "high",
    "qwen3.8-max": "high",
    "qwen3.7-plus": "high",
    "minimax-m3": "high",
    "minimax-m2.7": "high",
    "grok-4.5": "high",
}

# 前缀端点：同一后缀不同前缀是不同端点，保留完整名
KNOWN_PREFIXES = ("pro/", "jbb/", "pix/", "pixgrok/", "opencode-go/", "deepseek/", "combo/")


def detect_agent_mcp_tools() -> dict:
    """探测 Agent MCP 配置状态（最终以会话内 spawn_agent 工具可见性为准）。"""
    mcp_json = Path.home() / ".omp" / "agent" / "mcp.json"
    configured = False
    if mcp_json.exists():
        try:
            cfg = json.loads(mcp_json.read_text())
            configured = "agent-mcp" in cfg.get("mcpServers", {})
        except json.JSONDecodeError:
            configured = False
    return {
        "configured": configured,
        "config_path": str(mcp_json) if mcp_json.exists() else None,
        "note": "最终以会话内 spawn_agent 工具可见性为准",
    }


def scan_cli_models(cli: str) -> list[dict]:
    """扫描 CLI 模型列表，返回 [{provider, model(完整名), thinking}]。

    解析 omp 风格分段输出：
        opencode-go (25)      <- provider 段
        │ gpt-5.6-luna ...    <- 段内模型（可能带 pro/ jbb/ 前缀）
    完整模型名 = provider + "/" + 段内名（段内无前缀时即 provider 内模型）。
    """
    probe = CLI_PROBES.get(cli)
    if not probe or shutil.which(probe[0]) is None:
        return []
    try:
        out = subprocess.run(probe, capture_output=True, text=True, timeout=15)
    except (subprocess.SubprocessError, OSError):
        return []

    records: list[dict] = []
    provider: str | None = None
    for line in (out.stdout + out.stderr).splitlines():
        s = line.strip()
        # provider 段头：`opencode-go (25)` / `opencodex (18)`
        m = re.match(r"^([\w.-]+)\s+\(\d+\)$", s)
        if m and "│" not in s and "┌" not in s and "└" not in s:
            provider = m.group(1)
            continue
        # 数据行：`│ model-name  │ ...`
        if not s.startswith("│") or "model" in s or set(s) <= {"│", "─", " "}:
            continue
        parts = [p.strip() for p in s.strip("│").split("│")]
        if not parts or not parts[0]:
            continue
        name = parts[0]
        if not re.match(r"^[\w./-]+$", name) or name in ("model",):
            continue
        full = f"{provider}/{name}" if provider else name
        records.append({
            "provider": provider or "?",
            "model": full,
            "thinking": _thinking_for(full),
        })
    return records


def _thinking_for(model: str) -> str:
    level = "high"
    for key, lv in THINKING_LEVELS.items():
        if key in model:
            level = lv
            break
    return level


def _series_family(model: str) -> str:
    """模型所属系列族（用于去重）：取已知系列前缀的根。"""
    for fam in ("gpt", "deepseek", "glm", "kimi", "qwen", "minimax", "grok", "hy"):
        if fam in model:
            return fam
    return model.split("/")[-1].split("-")[0]


def latest_by_series(records: list[dict], limit: int = 8) -> list[dict]:
    """按系列去重，各系列只列最新（含前缀端点）。"""
    picked: list[dict] = []
    seen_families: set[str] = set()
    for ref in SERIES_PRIORITY:
        matches = [r for r in records if ref in r["model"]]
        if not matches:
            continue

        def rank(r: dict) -> int:
            m = r["model"]
            if "pro/" in m:
                return 1  # pro 路由档
            if "jbb/" in m:
                return 2
            if "pix/" in m or "pixgrok/" in m:
                return 3
            return 0  # 默认端点（含 provider 前缀但无路由后缀）优先

        matches.sort(key=rank)
        chosen = matches[0]
        fam = _series_family(chosen["model"])
        if fam in seen_families:
            # 例外：deepseek 系列同时保留 pro 与 flash（档位不同，都是常用选择）
            if not (fam == "deepseek" and
                    all("flash" not in p["model"] for p in picked)):
                continue
        seen_families.add(fam)
        picked.append(chosen)
        if len(picked) >= limit:
            break
    return picked


def probe_all() -> dict:
    report = {
        "agent_mcp": detect_agent_mcp_tools(),
        "clis": {},
        "note_native_pool": "宿主原生子代理池由主会话直接可见（task/scout/reviewer），无需探测",
        "note_prefix": "模型名含 provider 前缀=完整端点，派发必须使用完整名",
    }
    for cli in CLI_PROBES:
        records = scan_cli_models(cli)
        report["clis"][cli] = {
            "available": bool(records) or shutil.which(CLI_PROBES[cli][0]) is not None,
            "models": latest_by_series(records) if records else [],
        }
    return report


def render_markdown(report: dict) -> str:
    am = report["agent_mcp"]
    lines = ["### 当前会话能力检测", ""]
    lines.append(
        "- Agent MCP：" + ("● 已连接（spawn_agent 可用，以会话内工具可见性为准）"
                           if am["configured"] else "○ 未发现") + "")
    lines.append("")
    # 当前会话可用模型（主会话直接可见，两种情况都列出）
    lines.append("- **当前会话可用模型（主会话直接可见）**：原生子代理池 task / scout / reviewer …")
    lines.append("")
    if am["configured"]:
        lines.append("- **Agent MCP 可用，追加 CLI + 模型**（不同系列各列最新；思考等级默认值；完整名=端点）：")
        for cli, info in report["clis"].items():
            if not info["available"]:
                lines.append(f"  `{cli}`: （未检测到）")
                continue
            if not info["models"]:
                lines.append(f"  `{cli}`: （模型列表待扫描）")
                continue
            items = " · ".join(f"`{m['model']}`({m['thinking']})" for m in info["models"])
            lines.append(f"  `{cli}`: {items}")
    else:
        lines.append("- Agent MCP 未发现：不列出 CLI/模型（那是 Agent MCP 的模型选项），推荐先安装 Agent MCP")
        lines.append("  （`~/.omp/agent/mcp.json` 注册 spawn_agent 后重启会话即可增强）；当前用主会话原生子代理池执行。")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Skill 启动能力检测")
    parser.add_argument("--markdown", action="store_true", help="输出启动清单的检测段")
    args = parser.parse_args()

    report = probe_all()
    if args.markdown:
        print(render_markdown(report))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
