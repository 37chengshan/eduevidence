---
name: evidence-review
description: Traceable evidence review with mandatory counter-evidence and methodology gates.
---

# Evidence Review

Use for a question that needs a bounded, decision-grade evidence assessment.
Run `Frame → Retrieve → Extract → Challenge → Audit → Adjudicate → Applicability`.

The required outputs are a search plan and attempt log, validated sources, claim-level evidence links, a methodology audit, a decision boundary, and applicability limits. Search snippets are discovery metadata, never evidence.

When the user asks to continue autonomously, identify the next most decision-relevant evidence, or keep iterating until the evidence state reaches a bounded stopping condition, load `references/autoresearch.md`. Keep the public workflow unchanged: Evidence Autoresearch is a meta-layer over this review, not a fourth user-facing workflow. Preserve append-only evidence and the Single Writer rule.

## When this workflow applies

- A decision question can be answered from **existing** research — across any field: teaching methods, curriculums, AI tools, policies, programmes, clinical or organisational practice, cultural or media interventions.
- The user needs to know what the evidence supports, what it cannot support, for whom, and under which conditions.
- The user explicitly asks for a review, synthesis, appraisal, or an evidence-bounded recommendation.

Not for: designing a new study or pilot (use `decision-and-pilot.md`), re-injecting field data into an existing decision (use `evaluate-and-update.md`), or a quick literature list with no decision target.

The **domain** changes the frame vocabulary, not the protocol. `education` frames populations as learner/course; `policy` frames them as decision object/population/stakeholders; other domains register their own frame contract under `domains/`. Every stage below is domain-independent.

## Prerequisites

1. A research question plus the decision it feeds — if the decision target is missing, run the `frame` stage before anything else.
2. A run workspace (`eduevidence run --question "..."`) so every artifact has a durable home; do not carry state in chat.
3. A Complexity Gate level (S/M/L) from `scripts/complexity_gate.py`; it fixes the retrieval breadth, not the protocol.

## Runbook

| # | Stage | Role | Input | Artifact | Gate |
|---|---|---|---|---|---|
| 1 | Frame | research-planner | user question | `frame.json` | the selected domain's frame schema (`domains/<id>/manifest.json` → `frame_schema`); no intervention advice before framing completes |
| 2 | Retrieve | evidence-retriever | `frame.json` | `sources.jsonl` + `fetch/` | `schemas/source.schema.json`; Fetch/Validate gate inside Retrieve (RULE 2) |
| 3 | Extract | evidence-analyst | `sources.jsonl` + `fetch/` | `evidence.jsonl` | `schemas/evidence.schema.json`; outcome separation (task ≠ learning) |
| 4 | Challenge | skeptic | `evidence.jsonl` | `skeptic.json` | all 9 fixed checks executed; no fabricated counter-evidence |
| 5 | Audit | method-reviewer | `evidence.jsonl` + fetched text | `methodology.json` | `schemas/methodology.schema.json`; `task_vs_learning_guard` present |
| 6 | Adjudicate | evidence-judge | all of the above | `raw_verdict.json` → `final_verdict.json` | `schemas/verdict.schema.json`; Pre-Verdict Gate before finalising |
| 7 | Applicability | evidence-judge | `evidence.jsonl` + verdict | `applicability.json` | supported population, conditions, exclusions and uncertainty stated |

Execute the stages in order. A stage may be delegated to a sub-agent, a script, or the host model itself — the artifact and its gate are what count, never which adapter produced it.

### Stage 1 — Frame

Produce the PICO-style frame with decision target, scope, and inclusion/exclusion criteria, using the vocabulary of the selected domain (education: learner/course; policy: decision object/population/stakeholders). Ask the user only for inputs that cannot be inferred (target population, intervention variant, comparison, primary outcome); never invent defaults for them. Emit the suggested complexity level alongside the frame.

### Stage 2 — Retrieve

Write an auditable search plan (`SearchPlan`) with core, expansion, and **independent counter-evidence** queries, then execute it through `scripts/search_provenance.py` so attempts, screening decisions and exclusions are exported. `Fetch`/`Validate` are mandatory gates inside this stage: a snippet or abstract is a discovery aid; only fetched, validated content can be extracted from. Zero-config channels (OpenAlex / Semantic Scholar / CrossRef / AIHot / AgentSearch) work without keys; Sciverse (`SCIVERSE_API_TOKEN`) adds citation-grade retrieval with `doc_id`/`offset` provenance, and its chunk hits must be expanded through `/content` before use.

### Stage 3 — Extract

Extract claim-level Evidence Objects with effect sizes, CIs, sample sizes, outcome type and source location. Keep `relation_to_claim` on the link, never on the study. Do not merge task-performance and learning outcomes into one record.

### Stage 4 — Challenge

Run the nine fixed checks: null results, negative results, contradictory findings, alternative explanations, measurement mismatch, sampling bias, novelty effect, AI dependency, scope overreach. If nothing is found, state `NO CONTRADICTORY EVIDENCE FOUND` — absence of counter-evidence is a finding, not a gap to fill with invented sources.

### Stage 5 — Audit

Appraise each study against the methodology checklist and WWC 5.0 / GRADE-informed criteria. The auditor judges whether the evidence stands, never what it says. Record the `task_vs_learning_guard` verdict explicitly.

### Stage 6 — Adjudicate

Integrate frame, evidence matrix, skeptic findings and methodology audit into one of four states — `ADOPT` / `PILOT` / `REJECT` / `INSUFFICIENT EVIDENCE` — with `what_can_be_claimed` / `what_cannot_be_claimed` and a confidence breakdown. Run `scripts/pre_verdict_gate.py` **before** the verdict is treated as final; a critical failure caps confidence and forbids a high-confidence adoption claim.

### Stage 7 — Applicability

State who the evidence applies to, in which contexts, for which outcomes, under which conditions, and where it stops. A positive average effect never transfers automatically.

## Failure handling and fallbacks

| Failure | Handling |
|---|---|
| `SEARCH_NO_RESULT` | Broaden terms, switch discovery provider, or record a negative-search record — never lower the evidence bar silently. |
| `FETCH_FAILED` | Run the provider degradation chain; if it is exhausted, discard the source and return to Retrieve. |
| `FETCH_PARTIAL` | Require rule or human confirmation before extraction; never reconstruct missing text from memory. |
| `SCHEMA_INVALID` | Block the stage, repair the artifact, re-run the gate; do not advance. |
| `METHODOLOGY_TOO_WEAK` | Keep the study in the matrix but strip its support role. |
| `CONFLICT_UNRESOLVED` | Stay uncertain; do not force adjudication. |
| `INSUFFICIENT_EVIDENCE` | Emit `INSUFFICIENT EVIDENCE` with the specific evidence that would change the decision. |

## Human hand-off points

- After Frame, when population / intervention / comparison / outcome inputs are missing (`NEEDS_USER_CONTEXT`).
- After Challenge, when counter-evidence is absent, thin, or directly contradicts the working conclusion.
- After Adjudicate, before the decision is used for a real change in practice, curriculum, policy or operations.

## Resuming and updating

Resume with `eduevidence resume --run-id <id>`: the workspace continues from the first stage whose artifact is missing or schema-invalid. Evidence is append-only — a correction adds a new revision and a new decision snapshot; never overwrite an earlier one. To refresh the same question later, run the `evaluate-and-update` workflow so the change lands as a decision diff rather than a silently rewritten report.

## Minimal example

```bash
eduevidence run --question "Should first-year CS students use generative AI coding assistants?" --run-id ai-cs1
python scripts/search_provenance.py "first-year CS generative AI coding assistant learning outcomes" \
  --out runs/ai-cs1/provenance --concept "AI coding assistant"
eduevidence status --run-id ai-cs1
eduevidence gate --run-id ai-cs1
eduevidence report --run-id ai-cs1 --theme claude
```

The shipped reference result for this exact question is `examples/ai-coding-assistant-evidence/` — read its `frame.json` → `sources.jsonl` → `evidence.jsonl` → `skeptic.json` → `methodology.json` → `verdict.json` chain to see what a completed review looks like.

## Acceptance checklist

- [ ] Frame passes its schema and states scope plus inclusion/exclusion criteria.
- [ ] Search plan shows core, expansion and independent counter-evidence queries with attempts and exclusions exported.
- [ ] Every extracted finding traces to fetched, validated content — no snippet-only evidence.
- [ ] All nine skeptic checks ran; the contradiction statement is explicit either way.
- [ ] Methodology audit separates task performance from learning and records the guard verdict.
- [ ] Verdict is one of the four states, carries its confidence breakdown, and passed the Pre-Verdict Gate.
- [ ] Applicability states population, conditions, outcome limits and uncertainty.
- [ ] Reports and exports are projections of the stored artifacts, not a new source of truth.
