---
name: methodology-audit
description: "Audits empirical studies against WWC 5.0, GRADE risk-of-bias frameworks, and social science pitfalls."
capability: methodology_appraisal
---

# Methodology Audit Skill (Methodology Tribunal)

## When to Use
Trigger before claim synthesis to evaluate threats to internal and external validity, applying methodological confidence scoring.

## Inputs
- `evidence.jsonl` + `fetch/` 原文
- `references/wwc_standards.md`、`references/grade_framework.md`、`references/social_science_pitfalls.md`

## Process
1. **WWC 5.0 Rating**: Tier 1 (meets standards without reservations — clean RCT, low attrition), Tier 2 (with reservations — QED with baseline equivalence), Tier 3 (correlational / promising).
2. **Social Science Pitfalls**: task performance ≠ genuine learning; short-term score ≠ retention (4+ weeks); AI-assisted performance ≠ independent transfer; correlation ≠ causation.
3. **GRADE Certainty**: High / Moderate / Low / Very Low at the body-of-evidence level.
4. **15-item checklist** in fixed order (control_group … dropout), each `met|partial|missing|not_applicable`.

## Output Contract
`methodology.json` per `schemas/methodology.schema.json`, including `task_vs_learning_guard.equates_task_with_learning`.

## Quality Gates
- [ ] 15 项齐全且仅用四值枚举。
- [ ] guard 结论明确。
- [ ] 审计只判"证据是否成立"，不判"证据说什么"。

## Anti-Patterns
- 用样本量大掩盖无对照；把相关性研究列入因果结论；缺项直接记 `met`。

## Worked Example
某准实验无前测等价性 → Tier 2 (with reservations) + `pre_test: missing`；其结论只可用于"提示可能"，不进强支持列。

## References
- `references/methodology-audit.md`、`references/tribunal-policy.md`、`skill/agents/method-reviewer.md`、`skill/task-briefs/audit.md`
