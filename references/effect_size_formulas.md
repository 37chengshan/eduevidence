# Effect Size Formulas & Statistical Reference

> **Standardized Mean Differences (Cohen's d, Hedges' g) & Difference-in-Differences (DID)**

---

## 1. Standardized Mean Difference: Cohen's d and Hedges' g

Given Treatment Group (n1, mean1, sd1) and Control Group (n2, mean2, sd2):

### Pooled Standard Deviation (s_pooled):
s_pooled = sqrt(((n1 - 1)*sd1^2 + (n2 - 1)*sd2^2) / (n1 + n2 - 2))

### Cohen's d:
d = (mean1 - mean2) / s_pooled

### Hedges' g (Small-Sample Bias Correction J):
J(df) = 1 - (3 / (4 * (n1 + n2 - 2) - 1))
g = J(df) * d

### Variance and Standard Error of g:
Var(g) = (n1 + n2)/(n1 * n2) + (g^2) / (2 * (n1 + n2))
SE(g) = sqrt(Var(g))
95% CI(g) = [g - 1.96 * SE(g), g + 1.96 * SE(g)]

---

## 2. Difference-in-Differences (DID) Regression Model

For panel/classroom trial data across pre- and post-periods:
Y_ist = beta0 + beta1 * Treat_i + beta2 * Post_t + delta * (Treat_i * Post_t) + epsilon_ist

- beta1: Baseline difference between treatment and control cohorts.
- beta2: Shared secular trend over time.
- delta: The causal DID treatment effect parameter ((Y_T_post - Y_T_pre) - (Y_C_post - Y_C_pre)).
