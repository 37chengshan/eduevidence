---
name: data-analysis
description: "Runs deterministic statistical regression (DID/OLS) on user-uploaded classroom and field datasets to re-inject local empirical evidence."
---
# Data Analysis Skill

## 1. When to Use
Trigger when the user imports empirical classroom or survey data (CSV/XLSX) from an active field trial or pilot deployment.

## 2. Process
1. **Data Ingestion & Cleaning**:
   - Profile columns, check missingness, identify Treatment and Post indicators.
2. **Deterministic DID Regression**:
   - Run Difference-in-Differences OLS: Y = beta0 + beta1*Treat + beta2*Post + delta*(Treat*Post) + epsilon.
   - Calculate treatment effect delta, standard error, t-statistic, p-value, and Hedges' g.
3. **Graph Re-adjudication**:
   - Generate local Evidence Node (EVD-LOCAL-*) and re-run tribunal to update decision snapshot.

## 3. Visualization Sync
Append the local trial result to the project's visualization contract so the Data Visualization page reflects it without hard-coding:
- result.json → forest_plot_data: one entry with study_label "Local Field Trial (DID)", outcome_dimension from the trial outcome, effect_size = Hedges' g, ci_lower/ci_upper from the regression CI.
- result.json → evidence: one evidence object with relation_to_claim derived from the DID delta sign.
- evidence_graph.json: re-export after adding the EVD-LOCAL-* node.
