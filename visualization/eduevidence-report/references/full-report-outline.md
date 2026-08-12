# Full Report Outline

EduEvidence HTML contains two top-level views in one offline file:

1. **Visual Brief** — default, scan-first, preserves the existing visual summary experience.
2. **Full Report** — audit-first, desktop uses a collapsible sticky TOC and continuous report body.

The Full Report chapter order is fixed:

1. 执行摘要与最终裁决 / Executive decision
2. 研究问题、范围与决策标准 / Research question, scope & decision criteria
3. 检索策略与证据选择 / Retrieval strategy & evidence selection
4. Outcome Separation 与总体证据地图 / Outcome separation & evidence map
5. 完整 Evidence Matrix / Full evidence matrix
6. Methodology / Evidence Quality Audit
7. 反证、冲突与不确定性分析 / Conflict & uncertainty analysis
8. Evidence Tribunal 与 Claim Trace
9. 适用性与外推边界 / Applicability & extrapolation boundary
10. Evidence-to-Action 与教学干预 / Evidence-to-action & intervention
11. 评价方案与停止条件 / Evaluation & stop conditions
12. 来源、Provenance 与附录 / Sources, provenance & appendix

## Visual insertion rules

A chapter may include a chart or semantic visual only when it adds information beyond the adjacent text/table. Sparse states such as `1 support / 0 contradict / 0 neutral` stay as badges/text. Every meaningful visual must have an interpretation caption explaining what the reader should take from it.

## Progressive disclosure

Evidence, methodology audit items, tribunal claims and sources default to compact summaries and expose full traceable detail through accessible native `<details>/<summary>` controls. Print mode must not lose the hidden evidence content.
