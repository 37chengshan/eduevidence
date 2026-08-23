---
name: evidence-review
description: "Synthesizes extracted claims and evidence nodes into the project Evidence Graph with meta-analysis pooling."
---
# Evidence Review Skill

## 1. When to Use
Trigger to aggregate all validated evidence nodes into the project's single source of truth (SSOT) Claim Graph and execute quantitative synthesis.

## 2. Process
1. **Evidence Graph State Machine**:
   - Construct directed graph of Claims, Sources, and Findings.
   - Determine claim status: SUPPORTED, CONTRADICTED, MIXED, or UNCERTAIN.
2. **Meta-Analysis Pooling**:
   - Fixed-effect inverse-variance pooling and DerSimonian-Laird random-effects pooling.
   - Cochran's Q, degrees of freedom, and I^2 heterogeneity index.
   - Egger regression and Rosenthal Fail-Safe N publication bias checks.
   - Leave-one-out study sensitivity analysis.
