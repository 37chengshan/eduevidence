---
name: data-analysis
description: "Runs deterministic statistical regression (DID/OLS) on user-uploaded classroom and field datasets to re-inject local empirical evidence."
capability: data_validation + data_analysis
---

# Data Analysis Skill

## When to Use
Trigger when the user imports empirical classroom or survey data (CSV/XLSX) from an active field trial or pilot deployment.

## Inputs
- 数据集 + 采集溯源（谁、何时、从哪个人群、何种同意）
- 预先注册的分析计划（不得在看到数据后修改）

## Process
1. **Data Ingestion & Cleaning**: profile columns, check missingness, identify Treatment and Post indicators; the provenance/hash/missingness gate runs before analysis.
2. **Deterministic DID Regression** (`scripts/did_regression.py`): Y = β0 + β1·Treat + β2·Post + δ·(Treat×Post) + ε; report δ, SE, t, p and Hedges' g (`scripts/effect_calculator.py`).
3. **Fail closed**: when the design is not estimable (no baseline, no control, attrition beyond tolerance) return `ANALYSIS_NOT_ESTIMABLE` — never fabricate p-values or silently substitute a weaker estimator.
4. **Graph Re-adjudication**: add a local Evidence Node (`EVD-LOCAL-*`), commit a new revision, re-run the tribunal.

## Output Contract
`analysis-run` + `dataset-manifest`; the graph revision carries the local node; the decision diff is produced by the update workflow.

## Visualization Sync
- `result.json` → `forest_plot_data`: one entry with `study_label` "Local Field Trial (DID)", outcome dimension from the trial, effect size = Hedges' g, CI bounds from the regression.
- `result.json` → `evidence`: one evidence object whose `relation_to_claim` follows the sign of δ.
- `evidence_graph.json`: re-export after adding the `EVD-LOCAL-*` node.

## Quality Gates
- [ ] 溯源、哈希、缺失率在分析前记录。
- [ ] 分析严格按预注册计划执行。
- [ ] 本地结果作为"一项研究"并入，不覆盖既有证据。

## Anti-Patterns
- 事后改阈值；把不显著说成无效果；用本地单点结果推翻既有证据体。

## Worked Example
两班前后测数据 → DID δ=+0.21（不显著）：报告为"本地未复现"，不改变原裁决方向，仅下调适用性置信。

## References
- `scripts/did_regression.py`、`references/evaluation-design.md`、`skill/workflows/evaluate-and-update.md`
