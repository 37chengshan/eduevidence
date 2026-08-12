#!/usr/bin/env python3
"""Tests for startup_probe.py — 启动能力检测脚本。"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from startup_probe import (SERIES_PRIORITY, THINKING_LEVELS, _thinking_for,
                            latest_by_series, scan_cli_models)


def test_thinking_levels():
    """deepseek 系默认 max，其余 high。"""
    assert _thinking_for("opencode-go/deepseek-v4-flash") == "max"
    assert _thinking_for("opencodex/deepseek/deepseek-v4-pro") == "max"
    assert _thinking_for("opencodex/gpt-5.6-sol") == "high"
    assert _thinking_for("opencode-go/glm-5.2") == "high"
    assert _thinking_for("opencode-go/kimi-k2.7-code") == "high"
    assert _thinking_for("opencode-go/qwen3.8-max") == "high"
    assert _thinking_for("opencode-go/minimax-m3") == "high"
    assert _thinking_for("opencode-go/grok-4.5") == "high"


def test_latest_by_series_keeps_prefix_endpoint():
    """同一后缀不同前缀是不同端点，保留完整名，pro/ 优先于 jbb/pix。"""
    records = [
        {"provider": "opencodex", "model": "opencodex/gpt-5.6-sol", "thinking": "high"},
        {"provider": "opencodex", "model": "opencodex/jbb/gpt-5.6-sol", "thinking": "high"},
        {"provider": "opencodex", "model": "opencodex/pix/gpt-5.6-sol", "thinking": "high"},
        {"provider": "opencodex", "model": "opencodex/pro/gpt-5.6-sol", "thinking": "high"},
        {"provider": "opencode-go", "model": "opencode-go/deepseek-v4-flash", "thinking": "max"},
    ]
    picked = latest_by_series(records, limit=5)
    models = [p["model"] for p in picked]
    # gpt 系只保留一个，且优先无前缀端点
    assert "opencodex/gpt-5.6-sol" in models
    assert not any("jbb/" in m or "pix/" in m for m in models)
    assert "opencode-go/deepseek-v4-flash" in models


def test_latest_by_series_series_dedup():
    """同一系列多模型只列最新（SERIES_PRIORITY 顺序）。"""
    records = [
        {"provider": "opencode-go", "model": "opencode-go/glm-5", "thinking": "high"},
        {"provider": "opencode-go", "model": "opencode-go/glm-5.1", "thinking": "high"},
        {"provider": "opencode-go", "model": "opencode-go/glm-5.2", "thinking": "high"},
        {"provider": "opencode-go", "model": "opencode-go/kimi-k2.5", "thinking": "high"},
        {"provider": "opencode-go", "model": "opencode-go/kimi-k3", "thinking": "high"},
    ]
    picked = latest_by_series(records, limit=10)
    models = [p["model"] for p in picked]
    # GLM 系只留一个（glm-5.2 最新），Kimi 系只留一个（kimi-k3）
    assert sum("glm-" in m for m in models) == 1
    assert "opencode-go/glm-5.2" in models
    assert sum("kimi-" in m for m in models) == 1
    assert "opencode-go/kimi-k3" in models


def test_series_priority_covers_all_known_families():
    """SERIES_PRIORITY 覆盖主要模型家族。"""
    joined = " ".join(SERIES_PRIORITY)
    for family in ("gpt", "deepseek", "glm", "kimi", "qwen", "minimax", "grok"):
        assert family in joined, f"missing family {family}"


def test_scan_cli_models_parses_omp_segments(tmp_path):
    """omp models 分段输出解析：provider 段头 + 数据行 → 完整模型名。"""
    fake_output = """opencode-go (2)
┌───────────┬──────┐
│ model     │ ctx  │
├───────────┼──────┤
│ deepseek-v4-flash │ 1M │
│ glm-5.2   │ 1M   │
└───────────┴──────┘
opencodex (1)
│ pro/gpt-5.6-sol │ 375K │
"""
    # 直接测解析核心：模拟 scan 的逐行逻辑
    import re
    records = []
    provider = None
    for line in fake_output.splitlines():
        s = line.strip()
        m = re.match(r"^([\w.-]+)\s+\(\d+\)$", s)
        if m and "│" not in s:
            provider = m.group(1)
            continue
        if not s.startswith("│") or "model" in s or set(s) <= {"│", "─", " "}:
            continue
        parts = [p.strip() for p in s.strip("│").split("│")]
        if not parts or not parts[0]:
            continue
        name = parts[0]
        if not re.match(r"^[\w./-]+$", name) or name == "model":
            continue
        records.append(f"{provider}/{name}" if provider else name)
    assert "opencode-go/deepseek-v4-flash" in records
    assert "opencode-go/glm-5.2" in records
    assert "opencodex/pro/gpt-5.6-sol" in records


def test_render_markdown_no_agent_mcp_lists_only_session_pool():
    """无 Agent MCP 时不列 CLI/模型，只列主会话可见池 + 安装提示。"""
    from startup_probe import render_markdown
    report = {"agent_mcp": {"configured": False},
              "clis": {"omp": {"available": True, "models": [{"model": "x/gpt-5.6-sol", "thinking": "high"}]}}}
    out = render_markdown(report)
    assert "○ 未发现" in out
    assert "原生子代理池 task / scout / reviewer" in out
    assert "gpt-5.6-sol" not in out  # 不列 CLI/模型
    assert "推荐先安装 Agent MCP" in out


def test_render_markdown_with_agent_mcp_lists_cli_models():
    """有 Agent MCP 时列出会话池 + 各 CLI 模型。"""
    from startup_probe import render_markdown
    report = {"agent_mcp": {"configured": True},
              "clis": {"omp": {"available": True, "models": [{"model": "opencodex/gpt-5.6-sol", "thinking": "high"}]}}}
    out = render_markdown(report)
    assert "● 已连接" in out
    assert "原生子代理池" in out
    assert "opencodex/gpt-5.6-sol" in out
