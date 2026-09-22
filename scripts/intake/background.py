"""Frame skeleton inference + 3–6 boundary questions (never fabricate)."""
from __future__ import annotations

import re
from typing import Any, Callable

from intake.constants import (
    CONTEXT_CUES,
    FRAME_SLOTS,
    OUTCOME_CUES,
    POP_CUES,
    SLOT_LABELS,
)
from intake.prompts import ask, ask_yes


def infer_frame_hints(question: str, domain: str = "education") -> dict[str, Any]:
    """Propose Frame boundary hints from the question text only.

    Anything not stated in the question stays absent. Never fabricate.
    """
    hints: dict[str, Any] = {"domain": domain, "confirmed": False}
    text = question or ""
    low = text.lower()
    for cue in POP_CUES:
        if cue.lower() in low:
            hints["population"] = cue
            break
    for cue in OUTCOME_CUES:
        if cue.lower() in low:
            hints["primary_outcome"] = cue
            break
    for cue in CONTEXT_CUES:
        if cue in text or cue.lower() in low:
            hints["context"] = cue
            break
    m = re.search(r"(AI[\w\s一-鿿]{0,20}(?:工具|助手|tutor|copilot|编程)|"
                  r"(?:翻转|项目式|同伴)教学|AI\s*编程助手)", text, re.I)
    if m:
        hints["intervention"] = m.group(0).strip()
    if re.search(r"是否|影响|对比|比较|vs|与.*比|是否允许|该不该", text):
        hints["comparison"] = "business as usual / 未使用该干预的常规做法"
    return hints


def boundary_questions(inferred: dict[str, Any]) -> list[tuple[str, str, str | None]]:
    """3–6 boundary questions: (slot, prompt, default)."""
    questions: list[tuple[str, str, str | None]] = []
    for slot in FRAME_SLOTS:
        questions.append((slot, f"  · {SLOT_LABELS[slot]}", inferred.get(slot)))
    return questions[:6]


def collect_frame_hints(question: str, *, domain: str = "education",
                        interactive: bool,
                        printer: Callable[[str], None] = print) -> dict[str, Any]:
    """Infer skeleton; when interactive, ask 3–6 boundary Qs + one confirm."""
    inferred = infer_frame_hints(question, domain=domain)
    frame_hints = dict(inferred)
    if not interactive:
        frame_hints["confirmed"] = False
        return frame_hints

    printer("—— 背景智能深挖（Frame 边界，智能默认 + 一次确认；缺失不编造）——")
    printer(f"  领域骨架：{domain}")
    for slot, prompt, default in boundary_questions(inferred):
        label = default if default is not None else "（未从题目推出，留空）"
        raw = ask(prompt, label if default is not None else "")
        if raw and not raw.startswith("（"):
            frame_hints[slot] = raw
        elif default is not None:
            frame_hints[slot] = default
        # else: leave absent — never fabricate
    printer("  Frame 边界摘要：")
    for slot in FRAME_SLOTS:
        printer(f"    {slot}: {frame_hints.get(slot) or '—'}")
    frame_hints["confirmed"] = ask_yes("  确认以上边界？(Y/n)", True)
    return frame_hints
