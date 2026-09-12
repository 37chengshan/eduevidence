---
name: evidence-review
description: "Synthesizes extracted claims and evidence nodes into the project Evidence Graph with meta-analysis pooling."
capability: claim_linking + evidence_synthesis
---

# Evidence Review Skill

## When to Use
Trigger to aggregate validated evidence nodes into the project's single source of truth (SSOT) Claim Graph and execute quantitative synthesis.

## Inputs
- `evidence.jsonl` + `methodology.json`
- 项目 Evidence Graph 当前 revision

## Process
1. **Evidence Graph State Machine**: build the directed graph of claims, sources, findings; determine claim status (SUPPORTED / CONTRADICTED / MIXED / UNCERTAIN).
2. **Meta-Analysis Pooling** (`engine/meta_analysis.py`): fixed-effect inverse-variance pooling and DerSimonian–Laird random-effects pooling; Cochran's Q, df, I².
3. **Publication Bias & Robustness** (`engine/bias.py` / `engine/robustness.py`): Egger regression, Rosenthal fail-safe N, leave-one-out sensitivity.
4. **Counting rule**: pool by independent **study**, never by finding count.

## Output Contract
Graph revision (append-only) plus synthesis artifacts; projections (`result.json`, HTML) are derived, never the source of truth.

## Quality Gates
- [ ] 按独立研究计数，非按 finding 计数。
- [ ] 异质性（I²、Q）与偏倚检验结果一并报告。
- [ ] 三个方向列未被合并隐藏。

## Anti-Patterns
- 同一研究的多个 outcome 当作多项独立证据；对不可合并的结果强行做标准化合并。

## Worked Example
8 来源 12 条发现 → 仅部分可合并；不可合并者以叙述式证据矩阵呈现并标注原因。

## References
- `references/evidence-quality.md`、`docs/evidence-synthesis.md`、`engine/meta_analysis.py`
