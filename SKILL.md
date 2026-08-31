---
name: eduevidence
description: "Decision-grade evidence synthesis for education and applied social science intervention decisions. Use when a user needs to determine whether, when, for whom, or how to adopt, pilot, evaluate, or revise a teaching method, curriculum change, AI tool, program, or policy intervention. Run an auditable evidence-to-decision workflow spanning systematic retrieval, counter-evidence challenge, methodological quality and evidence-certainty appraisal, provenance-traceable evidence graphs, applicability boundaries, evidence-grounded gap detection, preregistration-ready study or pilot design, empirical evidence re-injection, and decision revision."
---
# EduEvidence 6.0 — Decision-Grade Evidence Engine
> **AI4SS Track | Art–Science Integration · General Intelligence**  
> **From empirical questions to decision-grade evidence and evidence-to-action loops.**

## 1. Mission
Use EduEvidence to turn an education or applied social science decision question into an **action boundary** that can be traced, challenged, appraised, piloted, evaluated, and revised.
Do not stop at “what does the literature say?” Determine:
- **Whether** the evidence supports action.
- **When** the intervention is likely to work.
- **For whom** the evidence is applicable.
- **How** the intervention should be piloted, evaluated, or revised.
- **What evidence would change the decision** if current certainty is insufficient.
Keep the public workflow deliberately lean:
```text
Evidence Review → Decision & Pilot → Evaluate & Update
```
Internally, route work through one architecture only:
```text
Research intent → Workflow → Capability DAG → Scientific gate → Artifact
               → Evidence Graph revision → Decision snapshot → Projection
```
Treat roles, models, Agent MCP, retrievers, scripts, and HTML reports as **execution adapters or projections**, not as competing workflow architectures.

---

## 2. Route the Request to a Workflow
Load exactly one primary workflow for the current task:
- `skill/workflows/evidence-review.md` — use for evidence synthesis and decision appraisal from existing research.
- `skill/workflows/decision-and-pilot.md` — use when the evidence must be converted into an actionable pilot or intervention plan.
- `skill/workflows/evaluate-and-update.md` — use when empirical data or new evidence must update the Evidence Graph and decision.
Treat `skill/sub-skills/` as **internal capability recipes**. Do not expose them as separate user-facing entry points unless the runtime explicitly requires it.

---

## 3. Select a Research Mode
### Mode 1 — Evidence Review
Use when the user primarily needs a defensible synthesis of existing evidence and an evidence-bounded decision.
Typical flow:
```text
Frame → Retrieve → Extract → Challenge → Audit → Adjudicate → Applicability
```
### Mode 2 — Full Research Cycle
Use when the task must continue beyond synthesis into new evidence generation.
Typical flow:
```text
Evidence Review
→ Knowledge Gap
→ Study / Pilot Design
→ Local or Field Data
→ Analysis
→ Evidence Graph Revision
→ Decision Revision
```
Never design a new study merely because evidence is weak. A new study or pilot must be grounded in an explicit, evidence-supported `KnowledgeGap`.

---

## 4. Preserve Canonical State and Provenance
Use the unified Project Workspace as the authoritative state model:
```text
Project / Run / Revision / DecisionSnapshot
```
Use the provenance-traceable **Evidence Graph** as the authoritative evidence structure.
Treat `result.json`, Markdown reports, HTML reports, charts, and dashboards as projections. Do not treat presentation artifacts as the source of truth.
Apply the following invariants:
1. **Single Canonical Project per Research Question**  
   Keep one canonical project for the same research question. Do not create duplicate topic directories for the same question; create an immutable Revision instead.
2. **Immutable Revisions**  
   Never overwrite the provenance history of prior evidence or decisions. Add a new revision and bind new artifacts to it.
3. **Shared Facts, Local Interpretation**  
   Verified external research facts such as `Source`, `Study`, `Finding`, and `Audit` may be reused across project snapshots. Keep `Claim`, `EvidenceLink`, `Applicability`, and `Decision` project-local.
4. **Evidence-Grounded Research Design**  
   Do not create a new study design unless it cites an explicit evidence-grounded `KnowledgeGap` identifier.

---

## 5. Choose the Execution Layer
### Mode A — Platform Native
Prefer Platform Native when the environment does not provide Agent MCP or when a portable, zero-MCP Skill execution is required.
Preserve the same workflow, schemas, scientific gates, provenance rules, and decision semantics even when enhanced adapters are unavailable.
### Mode B — Agent MCP Enhanced
Use Agent MCP only as an optional execution enhancement:
```text
Detect → Recommend → Obtain user authorization → safe_spawn
```
If Agent MCP is unavailable or not authorized, degrade cleanly to Platform Native. Never make MCP availability a prerequisite for scientific correctness.

---

## 6. Execute the Canonical 9-Step Protocol
Treat `docs/architecture.md` as the canonical protocol definition and validate stage outputs against the schemas in `schemas/`.
### Research Core — Evidence Discipline
```text
Frame → Retrieve → Extract → Challenge → Audit → Adjudicate
```
### Decision Extension — Evidence to Action
```text
Applicability → Intervene → Evaluate
```
### End-to-End Protocol
| # | Stage | Primary Contract | Required Duty |
|---|---|---|---|
| 1 | **Frame** | `education-frame.schema.json` | Define the intervention, target population, comparison or counterfactual, context, and outcome dimensions. |
| 2 | **Retrieve** | `source.schema.json`, `fetch-result.schema.json` | Retrieve candidate evidence, fetch the underlying source, and validate provenance. Treat snippets as discovery aids, never as evidence content. |
| 3 | **Extract** | `evidence.schema.json` | Extract findings, effect sizes, confidence intervals, sample sizes, outcomes, population characteristics, and study design information when available. |
| 4 | **Challenge** | `evidence.schema.json` | Search explicitly for null findings, negative findings, contradictory evidence, alternative explanations, and confounders. |
| 5 | **Audit** | `methodology.schema.json` | Appraise study quality and evidence certainty. Apply WWC 5.0 criteria where relevant to education-study design; use GRADE-informed certainty assessment at the body-of-evidence level where appropriate. |
| 6 | **Adjudicate** | `verdict.schema.json` | Integrate evidence and emit a bounded decision: `ADOPT`, `PILOT`, `DO_NOT_ADOPT`, or `INSUFFICIENT`. Pass the Pre-Verdict Gate before finalizing. |
| 7 | **Applicability** | `references/applicability-policy.md` | State who the evidence applies to, in which contexts, for which outcomes, and under what conditions. |
| 8 | **Intervene** | `intervention.schema.json` | Design the minimum viable intervention or pilot and define explicit success, failure, and stop conditions. |
| 9 | **Evaluate** | `evaluation.schema.json` | Define baseline, post-intervention, retention/maintenance, transfer, and decision-update logic. |
Treat **Present** as a projection layer, not a protocol stage.

---

## 7. Enforce Scientific Gates
### Gate A — Fetch Before Evidence Use
Do not treat search-result snippets, abstracts without sufficient context, or generated summaries as direct evidence when the underlying source can be validated.
Require:
```text
Retrieve → Fetch → Validate → Extract
```
Record provenance or an explicit retrieval limitation.
### Gate B — Counter-Evidence Before Verdict
Before adjudication, actively search for evidence that could weaken or reverse the initial interpretation.
Include, where relevant:
- Null or negative findings.
- Replication failures.
- Boundary conditions.
- Population or context mismatch.
- Outcome substitution.
- Confounding or selection bias.
- Publication-bias signals.
### Gate C — No Direct Learning Evidence, No ADOPT
For education interventions, do not issue `ADOPT` based only on task speed, task completion, productivity, usability, preference, or subjective experience.
Require direct evidence on learning, retention, independent transfer, or another explicitly decision-relevant outcome before `ADOPT` can be considered.
If direct evidence is missing, bound the decision to `PILOT`, `INSUFFICIENT`, or `DO_NOT_ADOPT` as justified by the evidence.
### Gate D — No False Precision
Never invent missing uncertainty statistics.
- If a confidence interval is not reported, do not fabricate one.
- Do not assume a default standard error such as `SE=0.20` for meta-analysis.
- Record why an observation cannot be pooled when precision information is unavailable.
- In forest plots, display an effect point without an error bar and mark `CI not reported` when appropriate.
### Gate E — Causal Estimation Must Fail Closed
For DID, OLS, or quasi-experimental analysis, fail closed when the design is not estimable.
For singular or collinear designs, empty treatment/time cells, zero-variance variables, saturated models, or other invalid inputs:
```json
{
  "status": "error",
  "did_coefficient": null,
  "standard_error": null,
  "p_value": null,
  "ci_95": null,
  "hedges_g": null
}
```
Do not fabricate fallback statistics.
For non-clustered DID inference, emit:
```text
inference_status = "non_cluster_warning"
```
Do not label DID or other quasi-experimental evidence as `Meets Standards Without Reservations` solely because a regression executed successfully.
### Gate F — No Study Design Without a Grounded Gap
Require every generated intervention study, trial, or quasi-experiment to cite the `KnowledgeGap` that justifies it.
A valid gap must arise from the evidence state, such as:
- Missing population evidence.
- Missing transfer or retention outcomes.
- Conflicting findings.
- Weak causal identification.
- Context mismatch.
- Insufficient precision.
- Unresolved mechanism or implementation uncertainty.
Do not generate generic “future research” ideas detached from the Evidence Graph.

---

## 8. Use the Capability Map
Route stages to reusable implementation capabilities as follows:
| Stage | Implementation Capability |
|---|---|
| Frame | `skill/sub-skills/research-planning` + `scripts/complexity_gate.py` |
| Retrieve | `skill/sub-skills/literature-review` + `skill/sub-skills/aihot-trend-analysis` |
| Extract | `skill/sub-skills/evidence-extraction` |
| Challenge | `skill/sub-skills/contradiction-analysis` |
| Audit | `skill/sub-skills/methodology-audit` |
| Adjudicate | `skill/sub-skills/evidence-review` + `scripts/pre_verdict_gate.py` + `scripts/compute_confidence.py` |
| Applicability | `references/applicability-policy.md` |
| Intervene | `references/intervention-design.md` + `skill/agents/intervention-designer.md` |
| Evaluate | `references/evaluation-design.md` + `skill/agents/evaluation-designer.md` |
| Present | `skill/sub-skills/report-generation` + `visualization/eduevidence-report` |
| Full Research Cycle extension | `skill/sub-skills/gap-analysis` → `study-design` → `data-analysis` |
| Cross-cutting | `skill/sub-skills/ethics-review` |
Do not describe these capabilities as independent user-facing Skills unless packaging or runtime compatibility specifically requires it.

---

## 9. Apply the Complexity Gate
Classify the task before execution:
### S — Quick Evidence Check
Use for narrowly scoped factual or evidence checks. Preserve provenance and uncertainty, but do not force a full deep-review pipeline when unnecessary.
### M — Standard Review
Use as the default for intervention decisions. Run the standard evidence workflow with Challenge, Audit, Adjudicate, and Applicability gates.
### L — Deep Research Cycle
Use when the decision is high-impact, disputed, methodologically complex, or expected to lead to a real-world intervention.
Require stronger search coverage, independent challenge/review, explicit applicability analysis, and—when the evidence justifies it—pilot and evaluation outputs.
When uncertain, escalate upward rather than skipping scientific safeguards.

---

## 10. Build Decision-Grade Evidence, Not a Literature Summary
For every substantial decision output, distinguish at least the following layers:
1. **What the studies found.**
2. **How trustworthy those findings are.**
3. **Where findings agree or conflict.**
4. **Whether the evidence applies to the target population and context.**
5. **What decision the evidence currently supports.**
6. **What the evidence does not support.**
7. **What new evidence would be most decision-changing.**
8. **How a pilot or study could generate that evidence.**
9. **How new empirical evidence would revise the graph and decision.**
Prefer bounded language over universal claims.

---

## 11. Preserve Evidence Graph Traceability
Bind every material decision claim to traceable evidence objects.
Maintain a clear path such as:
```text
Source → Study → Finding → Audit → Claim / Counterclaim
       → EvidenceLink → Applicability → DecisionSnapshot
```
When evidence changes, create a new Evidence Graph revision and a new DecisionSnapshot rather than silently mutating the previous conclusion.
Use `data_origin` or equivalent provenance metadata to distinguish:
- `manual_curated`
- validated retrieved evidence
- local empirical data
- synthetic fixtures or demos
Never allow synthetic demo data to appear as real empirical support.

---

## 12. Generate Evidence-Grounded Gaps
Treat a `KnowledgeGap` as an evidence object, not as brainstorming text.
A gap should specify:
- The unresolved claim or decision boundary.
- Which evidence is missing, conflicting, indirect, or weak.
- Why resolving the gap could change the decision.
- The minimum useful evidence required to reduce uncertainty.
Only then route the gap into `study-design` or `decision-and-pilot`.

---

## 13. Design Preregistration-Ready Studies and Pilots
Generate **preregistration-ready**, not falsely “preregistered,” designs unless an actual registration has occurred.
At minimum, define:
- Research question and grounded `KnowledgeGap`.
- Population and eligibility criteria.
- Intervention and comparison.
- Primary and secondary outcomes.
- Timing and follow-up windows.
- Assignment or identification strategy.
- Exclusion and missing-data rules.
- Analysis plan.
- Success thresholds.
- Stop conditions.
- Ethics, privacy, and IRB considerations when applicable.
- Decision-update rule specifying how results alter the Evidence Graph or verdict.

---

## 14. Re-Inject Empirical Evidence
Treat DID as one concrete implementation, not as the system's conceptual boundary.
When valid local or field data are supplied:
```text
Validate data
→ Execute appropriate empirical analysis
→ Record assumptions and limitations
→ Create new Finding / Audit objects
→ Create Evidence Graph revision
→ Re-run applicability and adjudication
→ Create new DecisionSnapshot
```
Use DID, OLS, RCT analysis, pre/post comparisons, regression discontinuity, interrupted time series, matching, panel methods, or other designs only when justified by the data-generating process and identification assumptions.
Never imply that statistical significance alone establishes a decision.

---

## 15. Use the Flagship Scenario as a Demonstration, Not a Universal Template
Use `examples/ai-coding-assistant-evidence/` as the flagship demonstration of the full evidence-to-decision loop.
Flagship question:
> **Should first-year university C/Python students be allowed to use generative AI coding assistants?**
The example demonstrates:
- A real, registry-verified evidence base.
- Structured extraction and counter-evidence challenge.
- Separation of task performance from independent learning outcomes.
- A bounded `PILOT` verdict rather than unconditional adoption.
- Provenance labels that distinguish curated evidence from synthetic fixtures.
- A quasi-experimental classroom evaluation path.
- Empirical evidence re-injection followed by decision revision.
Do not generalize the flagship verdict to unrelated populations, courses, tools, or policy contexts.

---

## 16. Keep Presentation as a Projection Layer
Generate `result.json` and `result.zh.json` as structured presentation inputs when the workflow requires them.
Support baked report themes as projections:
- Claude Research — Light
- Academic Paper — Light
- DataLab — Light
- DataLab — Dark
- Presentation / Judge — Dark
Bake the selected theme at generation time. Keep only language switching in the final report unless the runtime explicitly supports another behavior.
Do not let presentation-layer state modify the canonical Evidence Graph.

---

## 17. Respect the Visualization Contract
When visualization assets are generated, derive them from canonical project artifacts rather than hard-coded demo values.
| View | Contract Source |
|---|---|
| Dashboard question and verdict | `result.json → meta.question + decision` |
| Forest plot | `result.json → forest_plot_data` |
| Effect-size distribution | `result.json → evidence` |
| Outcome mapping | `result.json → outcome_mapping` |
| Evidence graph | `evidence_graph.json → export_echarts_graph()` |
| Report variants | `EduEvidence_Report.html` + `reports-5themes/*.html` |
For `forest_plot_data`, preserve fields such as:
```text
study_label
outcome_dimension
effect_size
ci_lower
ci_upper
sample_size
direction
wwc_rating
```
Do not invent values required only for visualization.

---

## 18. Use Unified Visualization Adapter Envelopes
Keep visualization adapters contract-compatible.
Expected envelope fields:
```text
adapter
contract_version
source_ref
source_sha256
locale
data
```
Example commands:
```bash
python3 visualization/eduevidence-report/scripts/build_charts.py \
  --result examples/ai-coding-assistant/result.json \
  --out /tmp/charts.json
python3 visualization/eduevidence-report/scripts/build_infographics.py \
  --result examples/ai-coding-assistant/result.json \
  --out /tmp/infographics.json
python3 visualization/eduevidence-report/scripts/build_figures.py \
  --result examples/ai-coding-assistant/result.json \
  --out /tmp/figures.json \
  --theme okabe_ito
```
Treat ECharts as an optional browser runtime used by the Web Studio, not as part of the core adapter contract.

---

## 19. Use the Local Web Studio Only as an Inspection Surface
Start the optional local inspection surface with:
```bash
python3 scripts/dashboard_server.py --port 8765
```
Expected local URL:
```text
http://127.0.0.1:8765/
```
Use the studio to inspect generated project artifacts. Do not route scientific reasoning through the Web Studio.
A new project should appear automatically when it produces compatible `result.json` and `evidence_graph.json` artifacts.

---

## 20. Use CLI Utilities When Deterministic Execution Helps
```bash
# Start the local Web Studio
python3 scripts/dashboard_server.py --port 8765
# Search academic and current evidence
python3 -m retrieval.search "AI coding assistants learning transfer"
# Run the DID fixture / empirical analysis path
python3 scripts/did_regression.py examples/full-research-cycle-fixture/data.csv
# Compute an effect size
python3 scripts/effect_calculator.py \
  --mean1 78.5 --sd1 10.2 --n1 90 \
  --mean2 72.1 --sd2 11.0 --n2 90
# Check Skill consistency
python3 scripts/skill_lint.py
```
Prefer deterministic scripts for calculations, validation, schema checks, and reproducible transformations. Do not replace a deterministic computation with invented model arithmetic when a validated script is available.

---

## 21. Final Output Requirements
Before presenting a final decision-grade result, verify that the output makes the following explicit when relevant:
- Canonical research question.
- Target population and context.
- Intervention and comparison.
- Decision-relevant outcomes.
- Evidence provenance.
- Supporting evidence.
- Counter-evidence and null evidence.
- Methodological limitations.
- Evidence certainty.
- Applicability boundary.
- Current verdict.
- Conditions that would change the verdict.
- Evidence-grounded gaps.
- Pilot/study design, when justified.
- Evaluation and stop conditions, when justified.
- Decision revision after new evidence, when applicable.
Prefer a scientifically bounded answer over a confident but weakly supported answer.

---

## 22. Core Behavioral Principle
Optimize for **decision integrity**, not answer confidence.
The central question is not:
> “Can the system produce a recommendation?”
It is:
> **“Is the available evidence strong, direct, applicable, and traceable enough to justify this action — and what evidence should change the decision next?”**

---

## Appendix — Repository Tooling Contract

This appendix keeps the deterministic repository gates (skill lint / version / metrics / release contract) stable while the English Skill text above remains the primary operating contract.

- **Progressive disclosure**: load the root SKILL first; load a workflow only when the task matches it; load a capability recipe (under `skill/sub-skills/`) or a methodology/domain profile only when the workflow calls for it. Do not dump the entire research archive into one agent context.
- **EduEvidence Research Engine** — the runnable engine delivered as a Skill package (`engine/`, `retrieval/`, `scripts/`, `schemas/`).
- **Shared Research Library** — verified external facts (`Source` / `Study` / `Finding` / `Audit`) may be reused across project snapshots; interpretive objects (`Claim` / `EvidenceLink` / `Applicability` / `Decision`) stay project-local.
- **No new study design without evidence grounding** — every study or pilot must cite an explicit, evidence-supported `KnowledgeGap` identifier.
- **Schema 版本口径**：schemas/ 顶层 13 个 = V1 契约（evidence.schema.json 当前修订 1.1、education-frame / verdict 等）；schemas/v2/ 17 个 = V2 契约（evidence-link / research-intent / study / graph-revision / project 等）。文档与代理配置一律以此口径命名。
- Five baked report themes (presentation systems, not science):

    ├─ Claude Research      [Light]
    ├─ Academic Paper       [Light]
    ├─ DataLab              [Light]
    ├─ DataLab              [Dark]
    └─ Presentation / Judge [Dark]
