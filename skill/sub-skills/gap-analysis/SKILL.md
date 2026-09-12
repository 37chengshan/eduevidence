---
name: gap-analysis
description: "Identifies population, measurement, and methodological gaps in the Evidence Graph and diagnoses cross-study empirical contradictions."
capability: knowledge_gap_detection
---

# gap-analysis — Research Gap Discovery & Contradiction Lens

## When to Use
Triggered after evidence extraction and meta-analysis, before study design: trial designs must be grounded on verified empirical gaps, never on generic templates.

## Inputs
- Evidence Graph（含 claim 状态与 outcome 维度）
- 矛盾诊断（方向冲突、异质性来源）

## Process
1. **Measurement & Retention Gap Audit**: if evidence only measures immediate task speed, flag the missing delayed unassisted retention measurement.
2. **Population Heterogeneity Audit**: check whether studies cover only elite CS majors or introductory cohorts; flag advanced-transfer gaps.
3. **Contradiction Lens**: when directions diverge (g > +0.3 vs g < −0.1), isolate the moderating variable (e.g. scaffolded vs unguided use).
4. **Priority**: rank gaps by decision-materiality so study design is not spent on immaterial questions.

## Output Contract
`GapNode` list written directly to the SSOT Evidence Graph, each with `gap_id`, `gap_type`, `description`, `target_outcome`, `recommended_trial_design`.

```json
{
  "gap_id": "GAP-RETENTION-001",
  "gap_type": "Measurement/Retention Gap",
  "description": "Lack of 12-week longitudinal retention data measuring unassisted transfer in CS1.",
  "target_outcome": "Delayed Unassisted Problem Solving",
  "recommended_trial_design": "12-week cluster randomized trial with 4-week delayed post-test without AI access"
}
```

## Quality Gates
- [ ] 每个 gap 绑定具体未满足的测量/人群/方法维度。
- [ ] gap 与决策材料性关联，而非"文献少"。
- [ ] 不把"论文数量少"当作研究缺口。

## Anti-Patterns
- 用"研究不足"概括一切；把已有证据能回答的问题标成缺口。

## Worked Example
现有证据多为即测任务表现 → 产出 GAP-RETENTION-001，约束后续 StudyDesign 必须包含无 AI 的延迟后测。

## References
- `engine/gap_lens.py`、`engine/gaps.py`、`references/scientific-invariants.md`
