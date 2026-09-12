---
name: evidence-extraction
description: "Extracts fine-grained claims, effect sizes (Hedges g), sample sizes, and methodology variables from validated full-text sources."
capability: study_extraction + finding_extraction
---

# Evidence Extraction Skill

## When to Use
Trigger on fetched and validated source texts to perform claim-level feature and statistical extraction.

## Inputs
- `sources.jsonl`（全部 FETCH_VALID / 确认的 FETCH_PARTIAL）
- `fetch/` 清正文；必要时经 Sciverse `/content` 读取定位段落

## Process
1. **Statistical Extraction**: sample sizes (N_treatment, N_control); means/SDs; standardized effect size (Hedges' g, Cohen's d, Odds Ratio via `scripts/effect_calculator.py`); 95% CIs and p-values when reported.
2. **Methodology Extraction**: design type (RCT, quasi-experimental DID/PSM/RDD, correlational); outcome classification (task performance vs conceptual learning vs delayed retention).
3. **Locate precisely**: keep `source_location` (page/section/offset) so every claim can be re-opened.

## Output Contract
Evidence Objects per `schemas/evidence.schema.json` (V1 top-level, revision 1.1) into `evidence.jsonl`; graph projections use `schemas/v2/evidence-link.schema.json` (V2).

## Quality Gates
- [ ] 每行通过 evidence schema，枚举合法。
- [ ] 任务表现与学习效果记录分离。
- [ ] 缺失统计量保持缺失（禁止由显著性反推效应量）。
- [ ] 每条记录可定位回原文。

## Anti-Patterns
- 把 `relation_to_claim` 写到研究本体；把即测分数当保持/迁移；从摘要估算效应量。

## Worked Example
PNAS 2025 三臂 RCT → 三条 evidence：练习表现（task_performance, support）、独立考试（learning, contradict）、护栏组（learning, support），各带 N 与效应量。

## References
- `references/evidence-quality.md`、`references/effect_size_formulas.md`、`skill/task-briefs/extract.md`
