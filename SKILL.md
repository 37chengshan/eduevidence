---
name: eduevidence
description: Use when a teaching or education decision — whether, when, and how to adopt a teaching method, tool, or AI-based intervention — must be grounded in research evidence rather than opinion. Covers any education question: teaching methods, AI tools, assessment, curriculum, and learning interventions, with structured evidence review, counter-evidence search, methodology audit, evidence tribunal, and actionable pilot design.
---

# EduEvidence — EduEvidence Research Engine (Evidence-Based Education Decision Skill)

**From Education Questions to Evidence-Based Decisions.**

EduEvidence is delivered as an **AI Agent Skill**; inside the Skill operates
the **EduEvidence Research Engine** — a persistent, auditable engine that
turns education questions into evidence-grounded decisions. Users experience
one Skill; the engine keeps research state in Projects/Runs instead of
reconstructing it from chat context or a monolithic result file.

## 1 Purpose

EduEvidence helps teachers, education researchers, and education administrators turn "should we adopt a teaching method or tool?" from an intuition-driven choice into a **traceable, challengeable, verifiable evidence decision process**. It does not generate answers for teachers — it shows what the evidence supports, what it cannot support, who it applies to, and how to pilot and verify it.

### 1.1 Research Engine architecture

```text
EduEvidence Skill
        ↓
Research Router
        ↓
Project Workspace
        ↓
Capability-first Research Planner
        ↓
Research Engine
├─ Evidence Review
├─ Retrieval / Fetch / Validation
├─ Evidence Graph
├─ Methodology
├─ Synthesis / Tribunal
├─ Knowledge Gap
├─ Study Design
├─ Dataset / Analysis
└─ Report Projection
        ↓
Project Evidence Graph
        ↓
DecisionSnapshot
        ↓
Visual Brief / Full Report / Markdown / future PPT
```

- **Project** = long-lived research project owning a versioned Project
  Evidence Graph. **Run** = one execution attempt/mutation inside a Project.
  **Revision** = one immutable scientific evidence state. **DecisionSnapshot**
  = an adjudication bound to a graph revision. Four concepts stay separate.
- **Project Workspace** lives under `~/.eduevidence/projects/PRJ-.../` with
  graph/, gaps/, study-designs/, datasets/, analyses/, decisions/,
  projections/, reports/ and runs/.
- **Evidence Graph** is the sole authoritative scientific state; `result.json`,
  localization packs, Markdown, HTML and charts are projections, never fact
  stores.
- **Shared Research Library** (`~/.eduevidence/library/`) reuses verified
  external facts (Source/Study/Finding/Audit) through immutable snapshot
  imports: research facts may be reused, interpretations (Claim/EvidenceLink/
  Applicability/Decision) stay Project-local, and a later library change never
  silently alters an existing Project's conclusions.
- Two Research Modes: **Evidence Review** (secondary-evidence research only)
  and **Full Research Cycle** (Evidence Review → Knowledge Gap → new study
  design → user data → analysis → new evidence → graph update → updated
  decision). Mode is recommended from a structured ResearchIntent and may be
  overridden by the user.
- **Scientific rule (frozen): No new study design without evidence grounding.** Any experiment/survey design must reference explicit,
  evidence-grounded KnowledgeGap IDs; the Research Router first verifies the
  Project has sufficient grounding, otherwise it runs at least a minimum
  Evidence Review to identify a defensible gap.
- The engine is an internal capability architecture — it is **not** a
  server application, and it never requires Agent MCP or a daemon.
  Native Core runs on Python stdlib only.

### 1.2 Startup flow (Skill-level, updated)

1. Detect an existing Project (resume) or create a new one (Project
   Workspace).
2. Produce a schema-valid ResearchIntent (`schemas/v2/research-intent.schema.json`).
3. Recommend Research Mode (Evidence Review vs Full Research Cycle) via the
   deterministic mode router.
4. Recommend depth (quick / standard / deep) from the complexity gate.
5. Discover scientific capabilities (SCP → local `references/` → native) and
   execution capabilities (Agent MCP → host subagents → sequential).
6. Request ONE explicit execution/theme confirmation (per §5.5).
7. Operate through Project/Run state (graph revisions), never through chat
   memory alone.

Static agent files become capability execution profiles: a fixed 8-role
topology is NOT required for every deep run; roles map to capabilities as
needed.

### 1.3 v3 capabilities (added in 3.0.0)

- **Decision-to-Outcome Loop**: a PILOT decision is not terminal. The CLI
  closes the loop — `eduevidence pilot register|import|analyze-link|redecide`:
  register a PilotRun bound to a DecisionSnapshot, import anonymized outcome
  data (PII columns are refused), link the analysis, then fold pilot evidence
  into a new graph revision and re-adjudicate, producing a new DecisionSnapshot
  plus a machine-readable diff. Student data stays local.
- **Empirical Benchmark (Layer B)**: `eduevidence benchmark run|eval|report`
  runs B0–B4 baselines with real model calls and gold-annotated evaluation
  (30 questions, Q01–Q30); every run records a full manifest (model,
  temperature, tools, usage, cost) and SIMULATED runs are never presented as
  model performance.
- **Cross-project synthesis**: `eduevidence synthesize` aggregates the Shared
  Research Library's verified facts into an outcome-level overview.

## 2 When to Use

EduEvidence addresses **any teaching/education decision that needs evidence**: whether to adopt a teaching method, tool, or AI intervention; how to introduce it; for whom it works; and how to verify its effect. Typical scenarios include (not limited to):

- **AI teaching tools**: Should first-year C programming students be allowed to use AI coding assistants? Is an AI tutor effective for calculus? Does an AI writing assistant harm independent writing skills?
- **Teaching methods**: Flipped classroom vs traditional lecture? Is project-based learning worth scaling? Peer assessment vs instructor grading?
- **Curriculum & assessment**: How to set formative assessment frequency? Online vs in-person effect differences?
- **Learning interventions**: Cognitive load management, motivation interventions, peer learning design.
- **Pilot design**: How to design a low-risk, evaluable teaching pilot?

Trigger signals: the question involves "whether to adopt / how to introduce / for whom it works / how to verify", and the answer should be based on research evidence rather than personal experience.

## 3 When Not to Use

- General "is AI teaching good or bad" discussion (no decision to ground in evidence).
- Ordinary Q&A unrelated to education decisions.
- Individual student diagnosis.
- Grade prediction.
- Full LMS construction.

## 4 Inputs

### Minimal input (required)

```yaml
education_question: string
```

### Structured input (optional; the more complete, the more precise the conclusion)

```yaml
education_question: "..."
learner:
  education_level: undergraduate_year_1
  major: computer_science
  prior_knowledge: first_programming_course
course:
  subject: C_programming
  type: lecture_lab
  duration: 16_weeks
intervention:
  ai_tool: generative_ai_coding_assistant
  allowed_usage: "explain_errors_only"
comparison: "no_ai"
target_outcomes: [independent_problem_solving, code_quality, ai_dependency]
constraints: "complete within 16 weeks, class of 60"
depth: standard          # quick | standard | deep
target: teaching_decision # evidence_review | teaching_decision | pilot_design | evaluation_design
```

## 5 Non-Negotiable Rules

These 8 rules are non-negotiable. **Violating any rule invalidates the process — roll back and fix before continuing**; any request to "skip a rule to save time/cost" must not be executed (see Chapter 15 Failure / Fallback).

**RULE 1 — Never reach a teaching conclusion without Retrieval / Evidence**
Every teaching conclusion must rest on a retrieved, validated evidence chain. If the user asks "skip the literature and answer directly", you must still complete Retrieve → Fetch → Validate → Extract (see Chapter 6).

**RULE 2 — Search snippets must never become SUPPORTED Evidence**
Search results and abstracts are leads, not evidence content. Evidence Extraction is allowed only after Fetching the source and passing Validate; on fetch failure, snippets must not be SUPPORTED Evidence (mark `FETCH_FAILED` / `UNSUPPORTED`).

**RULE 3 — Task Performance ≠ Learning**
Task performance ≠ learning; short-term scores ≠ long-term retention; AI-assisted performance ≠ no-AI transfer. Never equate task performance with learning evidence (see Chapter 10).

**RULE 4 — Independent Counter-Evidence Search is mandatory**
Every retrieval must include an independent counter-evidence search; the Skeptic must independently seek null / negative / contradictory evidence, AI dependency, reduced transfer, novelty effect, self-selection bias, and alternative explanations. Fabricating counter-evidence to create "both sides" is forbidden; when none exists, output `NO CONTRADICTORY EVIDENCE FOUND`.

**RULE 5 — Pre-Verdict Gate before Tribunal**
The Evidence Tribunal (Chapter 6, step 8) requires passing the 11-item Pre-Verdict Gate checklist (Chapter 11); failure of critical items forbids high-confidence verdicts — downgrade to PILOT / INSUFFICIENT as appropriate.

**RULE 6 — No Agent MCP spawn without user confirmation**
Agent MCP being available ≠ permission to use it. The Confirmation Gate (Chapter 9) is mandatory: **Scan first. Recommend second. Ask the user. Execute only after explicit confirmation.** If unconfirmed or rejected → fall back to Native Subagent Mode (or Sequential Mode if the host has no subagents).

**RULE 7 — Presentation must never modify Evidence / Verdict / Confidence**
Chart numbers must match result.json item by item; the presentation layer only changes how data is shown, never the data itself. Mismatch → `REPORT_INVALID`, publication blocked.

**RULE 8 — Final Verification before declaring done**
Before announcing DONE, pass the 9-item Final Verification checklist (Chapter 14); otherwise → `FINAL_VERIFICATION_FAILED`, do not declare completion.

## 5.5 Startup Confirmation (Step 0: one-time confirmation before research)

After the user inputs the research question, **present the following startup checklist and collect three choices at once before executing**. Never run without confirmation.

### Startup checklist template

```markdown
# EduEvidence Research Startup Confirmation

## 📌 Research question
「<user question>」

## 1️⃣ Complexity assessment (complexity gate)
Result: **<S/M/L>**
Basis: <single question single outcome | multiple studies 2-3 outcomes partial conflict | multiple outcomes multiple populations clear conflict needs implementation plan>

## 2️⃣ Research depth (pick one)
- [ ] quick   — quick path (Frame→Retrieve→Extract→Answer)
- [ ] standard — standard path (+ simplified Skeptic/Method Review)
- [ ] deep    — deep path (full 8 roles + Pre-Verdict Gate + cross-review) ← recommended here

## 3️⃣ Execution mode (pick one)
| Mode | Description | When |
|------|-------------|------|
| **A. Agent MCP Enhanced** (recommended) | multi-CLI + multi-model orchestration, cross-context + cross-review | deep research |
| B. Host native subagents | main session dispatches via its own subagents (same model pool) | no Agent MCP |
| C. Main session direct | single agent, no dispatch | quick/simple |

### Current session capability check
- Agent MCP: ● connected (spawn_agent available) / ○ not found
- **Models usable in this session (visible to the main session; listed in both cases)**:
  native subagent pool: task / scout / reviewer …
- **When Agent MCP is available**, additionally list each CLI + models (latest per family; thinking level is default, no confirmation needed):
  `omp`: gpt-5.6-sol(high) · deepseek-v4-flash(max) · glm-5.2(high) · kimi-k2.7(high) …
  `codex`: <actual scan> …
- **When Agent MCP is not found**: do not list CLI/models (those are Agent MCP model options); recommend installing Agent MCP (register spawn_agent in `~/.omp/agent/mcp.json` and restart the session to enhance); execute with the main session's native subagent pool.

> **Default model thinking levels (built into the main session, no user confirmation)**: deepseek family = `max`; gpt / claude / glm / kimi / qwen / minimax / grok families = `high`. Set thinking accordingly when dispatching subagents; do not ask item by item.
>
> **Model prefix = endpoint**: relay-injected models carry prefixes (`opencodex/gpt-5.6-sol`, `opencode-go/deepseek-v4-flash`, `jbb/gpt-5.6-luna`); same suffix different prefix = different endpoint. **Always dispatch with the full model name (with prefix)**; never strip or rename.

## 4️⃣ Report style (pick one)

```text
1. Claude Research      [Light]
2. Academic Paper       [Light]
3. DataLab              [Light]
4. DataLab              [Dark]
5. Presentation / Judge [Dark]
```

Internal theme keys: `claude` / `academic` / `datalab` / `datalab-dark` / `presentation`.

## ✅ Reply with three choices at once
1. Execution mode: A / B / C (A recommended)
2. CLI + models: e.g. `omp + gpt-5.6-sol(pro) + deepseek-v4-flash(standard)`
3. Report style: claude / academic / datalab / datalab-dark / presentation

After confirmation, execute fully automatically, produce HTML + Markdown, then open the browser and explain the results.
```

### Execution rules

- **All three choices required**: mode, CLI+models, style. Defaults when omitted (A / omp scan result / claude) with a note.
- After confirmation, **no more per-stage questions** — run fully automatically to Present (reporting step).
- depth=deep and mode A: Cross-Model Review (mode 2, §8.5) enabled by default unless the user explicitly wants the same model only.
- Final deliverables: `EduEvidence_Report.html` (single-file bilingual report) + Markdown research pack (agent-authored from the projection) + browser open + 3-5 sentence result summary.

## 6 Workflow Overview

Execute strictly in these 9 protocol steps (Research Core 6 + Decision Extension 3, canonical definition in docs/architecture.md); **each step's output must pass Schema validation before the next step**. Resource discovery (Chapter 7) and execution backend selection (Chapter 8) happen between steps 1–2; the Confirmation Gate (Chapter 9) completes before any delegation.

```text
1. Frame          Build the EducationResearchFrame (question/learner/course/intervention/comparison/outcomes/scope/inclusion-exclusion)
2. Retrieve       Retrieve literature & evidence; Fetch full/verifiable content; Validate source & content (snippet ≠ content, RULE 2; details: retrieval-protocol.md / source-validity.md)
3. Extract        Extract claim-level evidence (Evidence Object bound to Outcome)
4. Challenge      Skeptic protocol (fixed 9 checks)
5. Audit          Method Reviewer methodology audit (15-item checklist)
6. Adjudicate     Evidence Tribunal (must pass Pre-Verdict Gate first, Chapter 11)
7. Applicability  Applicability + intervention design + evaluation plan (For whom / minimum viable pilot / Evaluation Plan)
8. Intervene      Intervention design (minimum viable pilot + AI usage rules + stop conditions)
9. Evaluate       Evaluation plan (indicators + success threshold)

Reporting step (not counted in the 9-step protocol):
Present         Render the single-file bilingual HTML report + infographics + academic figures
```

**Hard rule: Search snippet ≠ Evidence.** Retrieve results are candidate leads only; Extract is allowed only after Fetch (real source content) and Validate (source & content checks pass).

**Every step must pass its Schema gate before the next**:

```text
Frame        → education-frame.schema.json
Retrieve     → source.schema.json
Fetch        → fetch-result.schema.json
Validate     → source.schema.json / fetch-result.schema.json
Extract      → evidence.schema.json
Challenge    → cross-model-review.schema.json (counter-evidence record)
Audit        → methodology.schema.json
Adjudicate   → verdict.schema.json
Design       → intervention.schema.json / evaluation.schema.json
Present      → report-result.schema.json (overall contract)
```

### Presentation (reporting step)

After research produces `result.json`, deterministic adapters render it into the user-facing layer (`visualization/eduevidence-report/`):

```text
result.json + result.zh.json (Chinese parallel data, produced directly by AI)
  ├─ build_charts.py       → ECharts specs (outcome overview / claim trace / benchmark)
  ├─ build_infographics.py → 4 infographic SVGs (EvidenceFlow / tribunal / intervention / evaluation)
  ├─ build_figures.py      → publication academic figures (SVG/PNG/PDF)
  └─ build_report.py       → EduEvidence_Report.html (single-file offline bilingual report)
```

- The report defaults to Chinese with one-click EN switch; two-layer structure: Visual Brief + Full Report (AI plans 5–7 dynamic chapters based on the research), one of five styles chosen at generation time.
- **Presentation only changes how data is shown, never the data** (RULE 7): chart numbers must match result.json item by item, otherwise `REPORT_INVALID` blocks publishing.
- Render command: `python3 visualization/eduevidence-report/scripts/build_report.py --result <result.json> --out REPORT.html`

## 7 Resource Discovery

- **SCP available → dynamic discovery**: use the Scientific Resource Capability Layer (SCP) as the science capability layer, discovering resources by capability (literature_search / scholar_metadata / web_fetch / pdf_extraction / document_conversion / citation_validation / statistical_analysis / meta_analysis / data_visualization, etc.).
- **SCP unavailable → fall back to local `references/`**: methodology documents (education-framing / outcome-taxonomy / evidence-quality / methodology-audit / skeptic-protocol / tribunal-policy / applicability-policy / intervention-design / evaluation-design / retrieval-protocol / source-validity) and native tools (Native Search / Smart Web Fetch / local parsers).
- **Never hard-code a resource inventory**: do not write any ecosystem's full list (e.g. SCP's Scientific Skills) into the Skill; route by capability priority, no global fixed order. Typical priority:

```text
Literature: SCP Skill / SCP Resource → Scholar Provider → Native Search
Web fetch:  Smart Web Fetch → Native / Local Parser
```

- **SCP and Agent MCP are orthogonal**: SCP chooses "which scientific capability", Agent MCP chooses "which CLI / Model / Agent executes" — never mix the two layers.

## 8 Execution Backend Selection

Assess complexity first, then choose the execution backend. Three tiers:

```text
Tier 1  Agent MCP Enhanced       multi-model multi-agent orchestration (user confirmation required, Chapter 9)
Tier 2  Host Native Subagents    host-native subagents
Tier 3  Sequential Main Agent    single agent, sequential
```

**Complexity gate (assess first, then topology):**

| Level | Criteria | Execution path |
|---|---|---|
| S | Single question, single outcome, few sources, no clear conflict | Frame → Retrieve → Fetch → Validate → Extract → Verify → Answer (single agent, no split) |
| M | Multiple studies, 2–3 outcomes, partial conflict, one independent check needed | Primary Analysis + Independent Check (max 2–3 roles in enhanced mode) |
| L | Multiple outcomes, multiple learner groups, clear evidence conflict, needs implementation plan | Full 8-role workflow (Planner / Retriever / Analyst / Skeptic / Method Reviewer / Judge / Intervention Designer / Evaluation Designer) |

**Selection flow:**

```text
does the task benefit from delegation?
  ├─ NO → Native (Tier 2 / Tier 3)
  └─ YES
       ↓
does the host session expose Agent MCP orchestration tools (spawn_agent etc.)?
  ├─ NO → Native (Tier 2 / Tier 3) — execute via host's own subagent mechanism
  └─ YES
       ↓
Mandatory Confirmation Gate (Chapter 9)
```

> **Agent MCP availability = `spawn_agent` and related MCP tools visible & callable in the current session** (e.g. `agent-mcp ● connected` in `~/.omp/agent/mcp.json`). Not an env var, not a port probe, not file existence. Check the session tool list before executing.

**Two spawn mechanisms (choose one after the gate passes):**

```text
Mechanism A  Agent MCP spawn: dispatch via the MCP tool spawn_agent to user-approved
             CLI+models, cross-context execution, results returned by MCP
             (multi_cli_dispatch / cross_model_review / memory_bank available).
Mechanism B  Host native subagents: the main agent dispatches via its own
             task/subagent tools; role split & model mapping identical to A,
             but without MCP enhancements.

Prefer A; if session tools are invisible or calls fail → B (same role mapping).
```

- Number of roles ≠ number of agents that must launch. Native Mode (Tier 2/3) runs the role protocols sequentially in a single agent.
- All three tiers share the same Scientific Protocol (Chapter 6); only execution differs.

## 8.5 Cross-Model Review Mode (optional, requires user confirmation)

Two review modes; confirm with the user before execution:

```text
Mode 1  Same-model sequential: the 8 roles run on the approved mapping
        (Skeptic/Judge use the strong model); no independent cross-review.
Mode 2  Cross-Model Review: after the same pipeline, an independent model
        from a DIFFERENT model family reviews raw_verdict independently
        (cross_model_review), outputting agreement + disagreement list;
        "same model different session" does NOT count as cross-review.
```

- Mode 2 requires confirming the independent reviewer model (must not be same family as the main mapping).
- The cross-review artifact follows `cross_model_review.schema.json` and is an optional Pre-Verdict Gate input.

## 9 Agent MCP Confirmation Gate

Final principle:

> **Scan first. Recommend second. Ask the user. Execute only after explicit confirmation.**

```text
user-approved CLIs (allowed_clis)
→ scan only those CLIs for currently available models (model_inventory)
→ build a recommendation table from Role Requirements
→ show the user: role / CLI / model / rationale / task
→ user explicitly confirms (approval)
→ only then spawn agents
```

- **No spawn without confirmation**: unconfirmed or rejected → `AGENT_MCP_APPROVAL_REQUIRED`, fall back to Native Subagent Mode (Tier 2); no host subagents → Sequential Mode (Tier 3).
- Scan only user-approved CLIs; never auto-traverse every agent CLI on the machine.
- **Never hard-code model names** (available models change); record only verifiable capability facts (reasoning / speed / cost / structured_output / context / tool_use / multimodal); unknown → `unknown`, never guess.
- The recommendation table also shows: role count, concurrency, Cross-Model Review on/off, Memory Bank on/off, Cost class (Unknown if not known).
- Independent reviewers should use different models, preferably different providers/families; never package "same model different session" as cross-model.
- **Re-confirmation required on**: new CLI, replaced model, new role, modified Role→Model mapping, significant token budget increase, new external provider.
- "Agent MCP installed" alone is not permission; after confirmation the same mapping holds for the run, no per-agent re-asking.

## 10 Evidence Rules

- Every evidence item binds to one Outcome (Outcome Taxonomy: learning / task performance / process / risk).
- **Evidence Contract core fields**: `source_id`, `study_id`, `sample_id`, `claim_id`, `claim`, `outcome_type`, `relation_to_claim`, `effect_direction`, `source_location`; `direction` is backward-compatible only, no longer core semantics. Missing any core field → mark `UNSUPPORTED`.
- **Task performance ≠ learning; short-term ≠ long-term retention; AI-assisted ≠ no-AI transfer** (RULE 3).
- The Skeptic must independently seek null / negative / contradictory evidence, AI dependency, reduced transfer, novelty effect, self-selection bias, alternative explanations (RULE 4). **Never fabricate counter-evidence for "both sides"**; when none exists, output `NO CONTRADICTORY EVIDENCE FOUND`.
- Run a Citation Audit before final report generation: Claim → Evidence ID → Source ID → Source Location → support relation → Outcome match → Scope check. Failures marked `UNSUPPORTED` or `DOWNGRADE_CONFIDENCE`.
- Quality scoring uses the five-dimension framework (D1 Study Design / D2 Sample Quality / D3 Measurement Validity / D4 Temporal Strength / D5 Directness, each 0–2, total 0–10).

## 11 Pre-Verdict Gate

Before the Evidence Tribunal (Chapter 6, step 8), pass this checklist (RULE 5):

```text
[ ] Research Frame valid              (education-frame schema)
[ ] Sources valid                     (source schema; Fetch / Validate done)
[ ] Evidence Schema valid             (evidence schema)
[ ] Source dedupe completed
[ ] Counter-evidence search completed (RULE 4)
[ ] Methodology audit completed       (15-item checklist)
[ ] Claim-Evidence Audit passed
[ ] Outcome mapping checked           (four-category Taxonomy)
[ ] Scope calibration checked         (evidence scope vs target context)
[ ] Independent study/sample count checked  (same study not double-counted as multiple evidence)
[ ] Deterministic confidence computed (compute_confidence.py, not model-generated)
```

**Critical-item failure forbids high-confidence verdicts**: downgrade to PILOT / INSUFFICIENT as appropriate; failure state is `PRE_VERDICT_FAILED` (Chapter 15).

## 12 Decision Rules

### Four-state decision matrix

| Decision | Requirement |
|---|---|
| **ADOPT** | Multiple key outcomes with strong direct evidence; risk controlled; context matches |
| **PILOT** | Positive evidence, but long-term / transfer / risk still unclear |
| **REJECT** | Stable negative effect on key outcomes, or risk clearly outweighs benefit |
| **INSUFFICIENT EVIDENCE** | Too few sources, weak directness, weak design, unexplained conflict |

Every PILOT / ADOPT recommendation requires an Evaluation Plan; every recommendation passes Applicability Analysis.

### Rule-based Confidence (not model-generated)

```text
Evidence Quality + Consistency + Directness + Evidence Count
- Conflict Penalty - Unsupported Penalty
→ High | Moderate | Low | Insufficient
```

- Final confidence is computed deterministically by `scripts/compute_confidence.py`, overriding any model value.
- Numeric scores are for internal comparison only; never marketed as "scientific probability".

## 13 Output Contract

The final output is a **Research & Decision Pack**: structured data artifacts plus a two-layer presentation report.

```text
Structured data artifacts (Schema-validated per step):
  frame.json       research frame (learner/course/intervention/comparison/outcomes/scope/inclusion-exclusion)
  sources.jsonl    source list (verifiable locations + fetch provenance)
  evidence.jsonl   claim-level evidence (relation_to_claim / effect_direction / decision_relation)
  methodology.json methodology audit (15-item checklist + task-vs-learning guard)
  raw_verdict.json LLM verdict (supported/uncertain/contradicted + evidence boundary)
  final_verdict.json deterministic-confidence verdict (compute_confidence overrides model values)
  intervention.json teaching intervention (minimum viable pilot + AI usage rules + stop conditions)
  evaluation.json  evaluation plan (baseline/post/retention/transfer + success threshold)
  result.json      aggregated results (outcomes aggregated by effect_direction; stable claim_ids)
  result.zh.json   Chinese parallel version
  artifact_manifest.json  artifact consistency (result hash / renderer / git commit)

Presentation (same data, two views):
  EduEvidence_Report.html  single-file offline bilingual (Visual Brief + Full Report,
                           5-7 dynamic chapters, one of five styles at generation time)
  RESEARCH.md              Markdown research pack (agent-authored projection view)
```

Every structured artifact (Frame / Evidence / Methodology / Verdict / Intervention / Evaluation) must pass its JSON Schema (`schemas/*.schema.json`); verify with `scripts/validate_schema.py`.

## 14 Final Verification

Before declaring DONE, pass this checklist (RULE 8):

```text
[ ] result.json Schema pass           result.json passes Schema validation
[ ] Evidence Trace complete           Claim → Evidence → Source fully traced
[ ] Verdict uses deterministic confidence
[ ] HTML data integrity pass          presentation matches result.json item by item
[ ] No unsupported high-confidence claim
[ ] zh/en structure valid             bilingual structure valid
[ ] report rendered successfully
[ ] provenance saved                 (run manifest / trace)
[ ] no REPORT_INVALID
```

All pass → declare **DONE**; any failure → `FINAL_VERIFICATION_FAILED`, fix before declaring completion.

## 15 Failure / Fallback

On these states, **never force a high-confidence recommendation**; label honestly and give next steps:

```text
INSUFFICIENT_SOURCES     too few sources; suggest more retrieval or mark insufficient_evidence
UNSUPPORTED_CLAIM        claim cannot bind to a reliable source; mark UNSUPPORTED and downgrade
CONFLICT_UNRESOLVED      pro/con conflict unexplained; stay uncertain, do not force a ruling
SCOPE_MISMATCH           evidence scope does not match target context; annotate and narrow
METHODOLOGY_TOO_WEAK     study design too weak to support the conclusion
NEEDS_USER_CONTEXT       missing learner/course/intervention info; request before continuing
TOOL_FAILURE             retrieval or tool failure; report honestly, never fabricate sources
FETCH_FAILED             source fetch failed; snippet must not be SUPPORTED Evidence (RULE 2)
PRE_VERDICT_FAILED       Pre-Verdict Gate failed; no Tribunal or downgraded verdict
REPORT_INVALID           presentation inconsistent with data; publishing blocked
FINAL_VERIFICATION_FAILED Final Verification failed; no completion declaration
```

**Execution backend fallback chain**:

```text
Agent MCP (confirmed) → Native Subagent Mode → Sequential Main Agent
```

- Agent MCP unavailable / unconfirmed / rejected → Native (Tier 2); no host subagents → Sequential (Tier 3).
- Resource fallback: SCP unavailable → local `references/` and native tools (Chapter 7).
- Any fallback keeps the Scientific Protocol (Chapter 6) and Non-Negotiable Rules (Chapter 5).

## 16 Human-in-the-Loop

EduEvidence is a **teaching-decision aid**, not a replacement for teachers' or institutions' final decisions. It never auto-decides on high-stakes assessment, student discipline, individual psychological judgments, or major student educational opportunities. Core positioning: research & decision support.

## 17 References

- Methodology documents (`references/`): education-framing / outcome-taxonomy / evidence-quality / methodology-audit / skeptic-protocol / tribunal-policy / applicability-policy / intervention-design / evaluation-design / retrieval-protocol / source-validity
- Data contracts (`schemas/`): education-frame / source / fetch-result / evidence / cross-model-review / methodology / verdict / intervention / evaluation / report-result
- Deterministic logic (`scripts/`): validate_schema / evidence_score / evidence_matrix / claim_audit / compute_confidence / benchmark_v3 / benchmark_evaluator / render_report
- Docs (`docs/`): architecture / methodology / benchmark / demo / reproducibility / install-guide / open-source-references / V3_REVIEW_2026-08-14
- Engine v3 modules (`engine/`): pilot (Decision-to-Outcome Loop) / meta_synthesis (cross-project synthesis) / tribunal / library / graph_store
- Real-research anchor examples (`examples/`):
  - Kazemitabaar et al. (2023, CHI) — AI Code Generators on Novice Learners: task completion ↑ 1.15×, correctness ↑ 1.8×, but one-week retention showed no significant difference → **task performance ≠ retention/learning**
  - Marzuki et al. (2024, Smart Learn. Environ.) — ChatGPT formative feedback positively affected undergraduate academic writing → writing-scenario supporting evidence
  - Bastani et al. (2025, PNAS) — unguarded GPT Base students scored 17% lower on the independent exam; guardrailed GPT Tutor eliminated the negative effect → **tool-design guardrails determine the direction of the learning effect**
  - Lee et al. (2025, ACL) — GPT-4 interactive homework raised engagement without harming learning → feasibility evidence for homework scenarios
