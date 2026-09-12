---
name: study-design
description: "Generates pre-registered quasi-experimental DID and RCT trial designs to fill identified knowledge gaps."
capability: study_design + measurement_design
---

# Study Design Skill

## When to Use
Trigger when the Evidence Graph yields MIXED, UNCERTAIN, or INSUFFICIENT outcomes — converting knowledge gaps into actionable empirical protocols. **A new design requires an explicit evidence-grounded KnowledgeGap ID.**

## Inputs
- `GapNode`（`GAP-*`）+ claim 状态
- 目标人群、可用课时、伦理审查结论

## Process
1. **Trial Specification**: sampling frame; cluster randomization or matched control classes; 4-phase rollout — baseline pre-test (W1), treatment exposure (W2–W9), immediate post-test (W10), 4-week delayed transfer test (W14).
2. **Pre-Registration Manifest**: power calculation (e.g. N > 120 for power ≥ 0.80 at g = 0.35); primary/secondary instruments; stopping rules; pre-specified regression model.
3. **Measurement plan**: hand over to evaluation design so thresholds are fixed before enrolment.

## Output Contract
StudyDesign + measurement plan validated against the grounded-study gate (`scripts/complexity_gate.py` + engine study-design checks). "Few papers found" alone never authorises a pilot.

## Quality Gates
- [ ] 设计引用显式 KnowledgeGap ID。
- [ ] 功效计算与停止规则齐备。
- [ ] 包含无 AI 的延迟迁移测量。
- [ ] 伦理审查已通过。

## Anti-Patterns
- 因"文献少"直接开研究；事后补功效计算；把即测当作迁移。

## Worked Example
GAP-RETENTION-001 → 12 周集群随机设计：W1 前测 / W10 即测 / W14 无 AI 迁移测，N≈160，预先注册分析模型。

## References
- `engine/study_design.py`、`references/intervention-design.md`、`skill/sub-skills/ethics-review/SKILL.md`
