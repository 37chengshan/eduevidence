---
name: gap-analysis
description: "Identifies population, measurement, and methodological gaps in the Evidence Graph and diagnoses cross-study empirical contradictions using BioGapLens PICO taxonomy."
---

# gap-analysis — Research Gap Discovery & Contradiction Lens Sub-Skill

## When to Use
Triggered after Evidence Extraction and Meta-Analysis (between Step 8 and Step 9) to ensure that trial designs are strictly grounded on verified empirical gaps rather than generic templates.

## Execution Rules
1. **Measurement & Retention Gap Audit**: If evidence only measures immediate task speed (OutcomeDimension: PROCEDURAL_EFFICIENCY), flag a missing delayed unassisted retention gap.
2. **Population Heterogeneity Audit**: Check if studies exclusively evaluate elite CS majors or introductory cohorts; flag advanced algorithmic transfer gaps.
3. **Contradiction Lens**: When studies report divergent effect directions ($g > +0.3$ vs $g < -0.1$), isolate the moderating variable (e.g. Socratic scaffolding vs unguided copy-pasting).

## Output Contract (`GapNode` list written directly to SSOT `EvidenceGraph`)
```json
{
  "gap_id": "GAP-RETENTION-001",
  "gap_type": "Measurement/Retention Gap",
  "description": "Lack of 12-week longitudinal retention data measuring unassisted transfer in CS1.",
  "target_outcome": "Delayed Unassisted Problem Solving",
  "recommended_trial_design": "12-Week Cluster Randomized Trial with 4-week delayed post-test without AI access"
}
```
