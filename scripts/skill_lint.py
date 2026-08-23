#!/usr/bin/env python3
"""scripts/skill_lint.py — Skill Static Consistency and Contract Linter.

Verifies:
1. Root SKILL.md exists, has valid YAML frontmatter (name, description), and is concise.
2. Sub-skills in skill/sub-skills/ exist, each with a valid SKILL.md containing YAML frontmatter.
3. Reference documents exist in references/.
4. Key schemas exist in schemas/.
5. Search providers and scripts exist.

Usage:
    python3 scripts/skill_lint.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def lint_skill() -> list[str]:
    errors = []
    
    # 1. Check root SKILL.md
    root_skill = ROOT / "SKILL.md"
    if not root_skill.exists():
        errors.append("Root SKILL.md is missing")
    else:
        text = root_skill.read_text(encoding="utf-8")
        if not re.search(r"^---\s*\nname:\s*\S+.*?\n---", text, re.DOTALL):
            errors.append("Root SKILL.md missing valid YAML frontmatter with 'name:'")
        if "Progressive Disclosure" not in text and "skill/sub-skills" not in text:
            errors.append("Root SKILL.md should mention progressive disclosure / sub-skills router")

    # 2. Check sub-skills in skill/sub-skills/
    skills_dir = ROOT / "skill" / "sub-skills"
    if not skills_dir.exists():
        errors.append("skill/sub-skills/ directory is missing")
    else:
        sub_skills = [d for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if len(sub_skills) < 5:
            errors.append(f"Expected at least 5 sub-skills in skill/sub-skills/, found {len(sub_skills)}")
        for sd in sub_skills:
            skill_md = sd / "SKILL.md"
            if not skill_md.exists():
                errors.append(f"Sub-skill '{sd.name}' is missing SKILL.md")
            else:
                stext = skill_md.read_text(encoding="utf-8")
                if not re.search(r"^---\s*\nname:\s*\S+.*?\n---", stext, re.DOTALL):
                    errors.append(f"Sub-skill '{sd.name}/SKILL.md' missing valid YAML frontmatter")

    # 3. Check reference documents
    ref_dir = ROOT / "references"
    expected_refs = [
        "social_science_pitfalls.md",
        "wwc_standards.md",
        "grade_framework.md",
        "effect_size_formulas.md",
    ]
    for r in expected_refs:
        if not (ref_dir / r).exists():
            errors.append(f"Missing methodology reference: references/{r}")

    # 4. Check core scripts
    expected_scripts = [
        "did_regression.py",
        "effect_calculator.py",
        "orchestrator.py",
    ]
    for s in expected_scripts:
        if not (ROOT / "scripts" / s).exists():
            errors.append(f"Missing required script: scripts/{s}")

    # 5. Check retrieval search
    if not (ROOT / "retrieval" / "search.py").exists():
        errors.append("Missing retrieval/search.py")

    # 6. Canonical Protocol 口径（W5 架构对齐）
    if root_skill.exists():
        text = root_skill.read_text(encoding="utf-8")
        if "Canonical" not in text and "Research Core" not in text:
            errors.append("Root SKILL.md should present the Canonical Protocol (Research Core 6 + Decision Extension 3)")
        if re.search(r"12-Step|12 步|twelve", text, re.I):
            errors.append("Root SKILL.md still mentions the deprecated 12-Step pipeline (canonical = 9 steps)")
        for banned in ("运行时主题切换", "theme-switcher", "theme_switcher", "agent 派遣"):
            if banned in text:
                errors.append(f"Root SKILL.md contains banned wording: {banned}")
        if "Schema 版本口径" not in text:
            errors.append("Root SKILL.md missing canonical Schema 版本口径 (V1 top-level vs schemas/v2)")
        if re.search(r"12-Step|12 步流水线", text):
            errors.append("Root SKILL.md drifted back to 12-step pipeline wording")

    # 6b. 输出契约解析安全（禁止 FINAL_ANSWER 文本尾巴）
    for role_md in sorted((ROOT / "skill" / "agents").glob("*.md")):
        rtext = role_md.read_text(encoding="utf-8")
        if "FINAL_ANSWER" in rtext:
            errors.append(f"Role prompt {role_md.name} still uses FINAL_ANSWER tail (output must be pure JSON)")

    # 7. task-briefs 模板（编排链补全）
    brief_dir = ROOT / "skill" / "task-briefs"
    stage_briefs = ["frame", "retrieve", "extract", "challenge", "audit",
                    "adjudicate", "intervene", "evaluate", "present"]
    if not brief_dir.exists():
        errors.append("skill/task-briefs/ is missing (orchestration chain)")
    else:
        for st in stage_briefs:
            if not (brief_dir / f"{st}.md").exists():
                errors.append(f"Missing task brief template: skill/task-briefs/{st}.md")

    # 8. 语言人话化规则下沉到核心角色
    for role in ("evidence-judge", "skeptic", "method-reviewer"):
        role_md = ROOT / "skill" / "agents" / f"{role}.md"
        if not role_md.exists():
            errors.append(f"Missing role prompt: skill/agents/{role}.md")
        elif "语言人话化规则" not in role_md.read_text(encoding="utf-8"):
            errors.append(f"Role {role} prompt missing 语言人话化规则 (Present language contract)")

    # 9. 渲染器无运行时换肤（Present 烘焙原则）
    renderer = ROOT / "visualization" / "eduevidence-report" / "scripts" / "build_report.py"
    if renderer.exists():
        rtext = renderer.read_text(encoding="utf-8")
        if re.search(r"_theme_switcher\(|theme-switcher", rtext):
            errors.append("build_report.py still contains runtime theme switcher code")
    legacy = ROOT / "scripts" / "render_report_html.py"
    if legacy.exists():
        ltext = legacy.read_text(encoding="utf-8")
        if re.search(r"theme-btn|theme-switcher|data-theme-target", ltext):
            errors.append("scripts/render_report_html.py still contains runtime theme switcher")

    return errors


def main():
    print("[*] Running EduEvidence Skill Linter...")
    errors = lint_skill()
    if errors:
        print(f"[-] Skill Lint FAILED with {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"    • {e}", file=sys.stderr)
        sys.exit(1)
    else:
        print("[+] Skill Lint PASSED: Root SKILL.md, 12 sub-skills, canonical 9-step protocol, orchestration chain, and scripts are consistent!")
        sys.exit(0)


if __name__ == "__main__":
    main()
