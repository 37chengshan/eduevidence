#!/usr/bin/env python3
"""report_copy_policy_guard.py — teaching-vocabulary ban for the policy copy pack."""
from __future__ import annotations

from typing import Any

#: Teaching / education-research vocabulary banned from the policy pack.
TEACHING_WORDS_ZH = (
    "教学", "学习者", "目标学习者", "学习指标", "学习效果", "学习结果", "学习过程",
    "学习能力", "学习收获", "学习动机", "学习 /", "AI 干预", "AI干预", "教师",
    "课程情境", "教育阶段", "教学决策", "教学行动", "教学干预",
    "任务表现 ≠ 学习效果", "任务表现≠学习效果", "保持测试", "迁移测试", "独立学习",
)
TEACHING_WORDS_EN = (
    "AI intervention", "Target learners", "Learning metrics", "Learning effect",
    "Learning outcome", "Teaching intervention", "Teaching decision", "Teaching action",
    "learning gain", "student learning",
)


def iter_strings(node, path="$"):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from iter_strings(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from iter_strings(value, f"{path}[{index}]")
    elif isinstance(node, str):
        yield path, node


def assert_policy_copy_clean(files: dict[str, Any]) -> None:
    """Policy pack must not contain teaching vocabulary (fail-clear)."""
    hits = []
    for name, data in files.items():
        for path, text in iter_strings(data):
            for word in TEACHING_WORDS_ZH:
                if word in text:
                    hits.append(f"{name} {path}: {word!r} in {text!r}")
            lowered = text.lower()
            for phrase in TEACHING_WORDS_EN:
                if phrase.lower() in lowered:
                    hits.append(f"{name} {path}: {phrase!r} in {text!r}")
    if hits:
        raise AssertionError(
            "policy copy pack contains teaching vocabulary:\n  " + "\n  ".join(hits)
        )
