---
name: evidence-extraction
description: "Extracts fine-grained claims, effect sizes (Hedges g), sample sizes, and methodology variables from validated full-text sources."
---
# Evidence Extraction Skill

## 1. When to Use
Trigger on fetched and validated source texts to perform claim-level feature and statistical extraction.

## 2. Process
1. **Statistical Extraction**:
   - Sample sizes (N_treatment, N_control).
   - Means and standard deviations (M1, SD1, M2, SD2).
   - Standardized effect size metric: compute Hedges' g, Cohen's d, or Odds Ratio.
   - 95% Confidence Intervals [CI_lower, CI_upper] and p-values.
2. **Methodology Extraction**:
   - Design type: RCT, Quasi-Experimental (DID, PSM, RDD), Correlational.
   - Outcome classification: Task Performance vs Conceptual Learning vs Delayed Retention.
3. **Output Contract**: Emit evidence objects per schemas/evidence.schema.json（V1 顶层契约，修订 1.1）into evidence.jsonl; 图谱层投射为 EvidenceLink 时用 schemas/v2/evidence-link.schema.json（V2 契约）。
