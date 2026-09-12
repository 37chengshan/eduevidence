---
name: ethics-review
description: "Evaluates trial designs, intervention protocols, and human-subject data collection against IRB and research ethics standards (education and other applied domains)."
capability: (engine-level gate; no deterministic capability)
---

# ethics-review — Research Ethics & IRB Compliance

## When to Use
Triggered before finalising any quasi-experimental / DID field trial design involving human student cohorts, classroom telemetry, or control-group assignment.

## Inputs
- `intervention.json` / study-design 草案（阶段、人群、对照、数据采集范围）
- 数据采集清单（分数、日志、提示词、遥测）

## Process — Ethical Audit Checklist
1. **Control Group Harm Prevention**: the control group must not be deprived of essential learning opportunities (use delayed crossover or active alternatives).
2. **Participant Privacy & Telemetry Protection**: pseudonymise prompts, interaction logs, and outcome records; comply with the applicable regime (FERPA / GDPR or the domain's equivalent).
3. **Informed Consent & Voluntary Participation**: opt-out without academic penalty.
4. **Algorithmic Bias & Equity Check**: audit whether the tool introduces grading bias or accessibility barriers for underrepresented groups.
5. **Data Retention**: state what is stored, where, and for how long; commercial LLM endpoints must not retain prompts.

## Output Contract
Ethics review record attached to the study design; a non-passing review blocks the pilot.

```json
{
  "ethics_status": "APPROVED_WITH_CONDITIONS",
  "irb_tier": "Exempt / Expedited Educational Research (Category 1)",
  "privacy_safeguards": ["Anonymized student IDs", "Zero prompt retention on commercial LLM endpoints"],
  "equity_protections": "Provide universal campus lab access to eliminate hardware disparities."
}
```

## Quality Gates
- [ ] 对照组的可接受替代方案已给出。
- [ ] 采集字段清单与去标识方式明确。
- [ ] 退出机制不产生学业惩罚。
- [ ] 设备/网络差异导致的公平性问题被处理。

## Anti-Patterns
- 以"教改豁免"跳过伦理审查；保留可回指到个人的提示词日志；用"照常上课"掩盖对照组机会剥夺。

## Worked Example
12 周准实验含对照班 → APPROVED_WITH_CONDITIONS：延迟交叉 + 匿名 ID + 关闭端点日志留存 + 统一机房访问。

## References
- `references/evaluation-design.md`、`references/social_science_pitfalls.md`、`skill/task-briefs/intervene.md`
