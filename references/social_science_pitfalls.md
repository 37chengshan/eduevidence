# Social Science & Educational Research Pitfalls Checklist

> **Methodology Tribunal Core Audit Rule**
> When evaluating empirical claims in education, learning sciences, and educational technology, every study must be audited against these four foundational pitfalls. Failure to isolate these confounds results in immediate methodological confidence downgrading.

---

## 1. Task Performance != Genuine Learning (任务表现 != 概念习得)

- **The Threat**: An intervention (e.g., AI coding assistant, interactive hint system, intelligent tutor) allows students to complete learning tasks faster or with fewer syntax errors, but fails to build enduring conceptual mental models or deep problem-solving schema.
- **Audit Criteria**:
  - Does the study evaluate conceptual understanding beyond automated task completion?
  - Are assessment tasks distinct from the training tasks (avoiding near-transfer memorization)?
  - Is there evidence of cognitive offloading where the tool performed the task instead of the learner?
- **Decision Penalty**: If an outcome only measures in-task completion speed/accuracy without conceptual probing, classify outcome as  (never ).

---

## 2. Short-Term Score != Long-Term Retention (短期得分 != 长期保持)

- **The Threat**: Immediate post-tests administered right after tool use capture transient cognitive scaffolding and working memory activation. As scaffolding fades, learned gains frequently decay rapidly.
- **Audit Criteria**:
  - Was a delayed post-test administered at least 2 to 4+ weeks post-intervention?
  - Does the effect size persist or decay over the retention window?
  - Is there longitudinal follow-up across academic grading cycles?
- **Decision Penalty**: If only immediate post-test data is available without delayed retention, downgrade Evidence Tier and flag .

---

## 3. AI-Assisted Performance != Independent Transfer (辅助表现 != 独立迁移)

- **The Threat**: Measuring student proficiency while the AI/intervention tool is actively present conflates human capability with human-AI joint capability. True educational value requires independent transfer to solo, unassisted contexts.
- **Audit Criteria**:
  - Were post-tests and transfer tests conducted in an isolated, tool-free environment?
  - Can learners solve novel, isomorphic, and far-transfer problems independently?
  - Did the intervention foster tool dependency or autonomous mastery?
- **Decision Penalty**: Claims asserting student skill improvement based on tool-in-the-loop assessments must be rejected or marked as .

---

## 4. Correlation != Causal Pedagogical Efficacy (相关关系 != 因果实证)

- **The Threat**: High-performing, intrinsically motivated students voluntarily adopt AI tools or new learning methods at higher rates (Self-Selection Bias). Observing higher test scores among tool users reflects baseline ability, not treatment effect.
- **Audit Criteria**:
  - Is there true random assignment (RCT) or rigorous quasi-experimental control (DID, Propensity Score Matching, Regression Discontinuity)?
  - Was baseline equivalence established on pre-tests and demographic confounders?
  - Was overall and differential attrition tracked and within WWC standard thresholds?
- **Decision Penalty**: Observational correlational studies without causal identification strategies cannot receive WWC Tier 1/2 or support definitive  recommendations.
