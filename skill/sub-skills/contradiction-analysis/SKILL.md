---
name: contradiction-analysis
description: "Mines adversarial claims, conflicting effect directions, and boundary condition qualifiers."
capability: counter_evidence_search (skeptic side)
---

# Contradiction Analysis Skill

## When to Use
Trigger during evidence synthesis when studies on the same Claim ID show conflicting directions (SUPPORTS vs CONTRADICTS) or high heterogeneity.

## Inputs
- `evidence.jsonl`（含方向标签）
- `frame.json`（判断是否 scope overreach）

## Process
1. **Adversarial Mining (Skeptic)**: identify confounders (teacher training, dosage, novelty); evaluate boundary conditions (does it fail for novices vs experts?).
2. **Directional Separation**: strictly separate supporting / contradicting / neutral — never blend them into one "mixed" bucket.
3. **Heterogeneity Attribution**: map conflict to subgroup variation, dosage thresholds, or outcome instrument differences.
4. **Nine fixed checks** per `skill/agents/skeptic.md`; absence of counter-evidence yields the standard statement, never invented sources.

## Output Contract
`skeptic.json` — `skeptic_findings[]` (`check` / `status` / `detail` / `related_evidence_ids`), `contradictory_evidence_found`, `no_contradictory_evidence_statement`, `threats_to_validity`.

## Quality Gates
- [ ] 九项检查齐全。
- [ ] 每条 found 绑定证据或来源。
- [ ] 标准语句与布尔标志语义一致。

## Anti-Patterns
- 把三列合并成"总体看有效"；为了显得严谨而虚构反证。

## Worked Example
同一 claim 下出现 g=+0.48（无护栏练习）与 g=−0.17（独立考试），归因到 outcome 测量差异与护栏配置，而非取平均。

## References
- `references/skeptic-protocol.md`、`skill/agents/skeptic.md`、`skill/task-briefs/challenge.md`
