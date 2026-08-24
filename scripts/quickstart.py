#!/usr/bin/env python3
"""quickstart — 30 分钟上手引导器（plan F1）。

把"跑自己的研究问题"压缩成一条命令：

    python3 scripts/quickstart.py "大一 C 课程该不该允许学生用 AI 编程助手？"

流程：
1. 进程内调用 orchestrator.main(["run", ...]) 创建 run workspace
   （确定性阶段本地执行，LLM 阶段产出任务简报；无子进程、无 shell）；
2. 读取 state.json，找出待完成的外部 agent 阶段；
3. 在 run 目录生成 NEXT_STEPS.md —— 每个待办阶段的精确命令、对应
   sub-skill 简报位置、完成后的一键裁决/渲染/引用核验命令。

Stdlib only。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import orchestrator as orch  # noqa: E402

# 外部 agent 阶段 → sub-skill 简报（SKILL.md Canonical Protocol 对应）
STAGE_BRIEFS = {
    "frame": ("skill/sub-skills/research-planning", "education-frame.schema.json"),
    "retrieve": ("skill/sub-skills/literature-review", "source.schema.json"),
    "extract": ("skill/sub-skills/evidence-extraction", "evidence.schema.json"),
    "challenge": ("skill/sub-skills/contradiction-analysis", "evidence.schema.json"),
    "audit": ("skill/sub-skills/methodology-audit", "methodology.schema.json"),
}


def newest_run_dir() -> Path:
    runs_dir = ROOT / "runs"
    candidates = sorted((p for p in runs_dir.iterdir() if p.is_dir()),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise SystemExit("no run workspace found after orchestrator run")
    return candidates[0]


def build_next_steps(run_dir: Path, question: str, depth: str) -> str:
    state_path = run_dir / "state.json"
    pending: list[tuple[str, str]] = []
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        for stage, info in (state.get("stages") or {}).items():
            status = info.get("status") if isinstance(info, dict) else info
            if status != "completed":
                brief, schema = STAGE_BRIEFS.get(stage, ("skill/sub-skills/", "schemas/"))
                pending.append((stage, brief + "（产物须过 " + schema + "）"))

    lines = [
        "# NEXT STEPS — 把这个 run 跑完",
        "",
        "- 研究问题：" + question,
        "- 复杂度：" + depth + "　- run 目录：`" + str(run_dir) + "`",
        "- 原则：**LLM 阶段由你的 AI Agent 按 brief 执行并落盘 schema 合法工件；"
        "确定性阶段（audit/adjudicate/present）本地一条命令完成。**",
        ""]
    if pending:
        lines += ["## 待完成的外部 agent 阶段", ""]
        for stage, brief in pending:
            lines += ["### " + stage,
                      "- 简报：`" + brief.split("（")[0] + "`",
                      "- 完成后重跑：`eduevidence resume --run-id " + run_dir.name + "`",
                      ""]
    else:
        lines += ["## 全部阶段已完成 ✓", ""]
    lines += [
        "## 收尾（证据→决策→交付）",
        "",
        "- 确定性裁决：`eduevidence adjudicate --project <run_dir>`",
        "- 五主题报告烘焙：`bash scripts/bake_pack.sh <pack_dir>`",
        "- 引用核验：`python3 scripts/citation_check.py --pack <pack_dir> --write-back`",
        "",
        "## 可信度自检",
        "",
        "- 引用逐条核验报告：`benchmarks/doi-audit/report.md` 与包内 `citation_check.md`",
        "- 报告头徽章标注 data_origin；synthetic 演示不得当作实证引用",
        ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", help="你的教育研究问题")
    parser.add_argument("--depth", default="standard",
                        choices=["quick", "standard", "deep", "S", "M", "L"])
    parser.add_argument("--dry-run", action="store_true", help="只初始化，不推进阶段")
    args = parser.parse_args()

    t0 = time.time()
    argv = ["run", "--question", args.question, "--depth", args.depth]
    if args.dry_run:
        argv.append("--dry-run")
    rc = orch.main(argv)
    if rc not in (0, None):
        raise SystemExit("orchestrator run rc=" + str(rc))
    run_dir = newest_run_dir()
    (run_dir / "NEXT_STEPS.md").write_text(
        build_next_steps(run_dir, args.question, args.depth), encoding="utf-8")

    print("\n✅ run 已创建：" + str(run_dir) + f"（{time.time()-t0:.1f}s）")
    print("📋 下一步清单：" + str(run_dir / "NEXT_STEPS.md"))
    print("   把其中的外部 agent 阶段交给你的 AI Agent；确定性阶段按清单本地执行。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
