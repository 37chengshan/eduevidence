# What Works Clearinghouse (WWC 5.0) Standards Quick Reference

> **What Works Clearinghouse (IES / US Dept of Education) Standards Version 5.0**
> The WWC rating system evaluates the strength of causal evidence produced by an evaluation study.

---

## 1. Study Design & Rating Hierarchy

| Rating | Study Design Criteria | Key Requirements |
|---|---|---|
| **Tier 1: Meets WWC Standards Without Reservations** | Randomized Controlled Trial (RCT) | - True random assignment at student/classroom level<br>- Low overall (<20%) & differential (<5%) attrition<br>- Zero confounding factors |
| **Tier 2: Meets WWC Standards With Reservations** | Quasi-Experimental Design (QED) or High-Attrition RCT | - Baseline equivalence established (Hedges' g <= 0.05 without statistical adjustment, or 0.05 < g <= 0.25 with covariate adjustment)<br>- Causal identification (DID, Propensity Score, Fixed Effects) |
| **Tier 3: Promising Evidence** | Correlational with Statistical Controls | - Statistically controlled regression/matching<br>- Baseline covariates included |
| **Tier 4: Demonstrates a Rationale** | Theoretical / Logic Model | - Well-specified logic model with research grounding |
| **Does Not Meet Standards** | Confounded / Flawed Design | - Severe baseline imbalance (g > 0.25)<br>- Single unit of assignment (N=1 cluster)<br>- Post-treatment intervention changes |

---

## 2. Baseline Equivalence Thresholds
- **Satisfied Equivalence**: Baseline difference |g| <= 0.05 -> No adjustment required.
- **Conditional Equivalence**: 0.05 < |g| <= 0.25 -> Statistical adjustment (covariate/ANCOVA/DID) required.
- **Failed Equivalence**: |g| > 0.25 -> Study does NOT meet WWC standards; cannot establish causal attribution.

---

## 3. Attrition Model (Boundary Standard)
- Overall Attrition Rate (Ao) and Differential Attrition Rate (Ad = |At - Ac|).
- Liberal vs Conservative Attrition Boundary: High differential attrition (>5%) even with low overall attrition introduces severe attrition bias.
