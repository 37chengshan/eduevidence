---
name: decision-and-pilot
description: Convert a bounded evidence decision into a reversible, measurable pilot.
---

# Decision & Pilot

Use only after an Evidence Review has produced an auditable decision snapshot. Add `Intervene` with a minimal pilot, explicit stop conditions, owner, population, and outcome measures. A pilot is not an adoption claim.

When this workflow is reached from Evidence Autoresearch, require the bridge in `references/autoresearch.md`: the KnowledgeGap is HIGH-DVI and decision-material, remains unresolved, bounded secondary search is saturated, and the empirical study is ethically/operationally feasible. Then still pass the existing grounded StudyDesign gate; "few papers found" alone never authorizes a pilot.

## When this workflow applies

- The review reached `PILOT` (or `ADOPT` with conditions) and the decision must become something a team can actually run.
- The user asks for an intervention plan, a rollout, a phased adoption, a stop rule, or "what would we do next week".
- A bounded empirical gap must be closed before the institution can move further.

Not for: producing the review itself (`evidence-review.md`), analysing data that already exists (`evaluate-and-update.md`), or recommending institution-wide deployment — that is an adoption claim this workflow is designed to prevent.

## Prerequisites

1. A completed, schema-valid `final_verdict.json` that passed the Pre-Verdict Gate. A pilot design without a review is a guess with extra steps.
2. An applicability statement — the pilot population must sit inside the supported population.
3. If the pilot closes an empirical gap: an explicit evidence-grounded KnowledgeGap ID. No KnowledgeGap, no study design.

## Runbook

| # | Stage | Role | Input | Artifact | Gate |
|---|---|---|---|---|---|
| 1–7 | (inherit the review) | — | prior run | `final_verdict.json` + `applicability.json` | the review's own gates must be green |
| 8 | Intervene | intervention-designer | verdict + frame | `intervention.json` | `schemas/intervention.schema.json`; minimal reversible pilot, not a deployment plan |
| 8b | (grounding check) | — | `intervention.json` | KnowledgeGap reference | `scripts/complexity_gate.py` + grounded StudyDesign gate |
| 9 | Evaluate | evaluation-designer | `intervention.json` + verdict | `evaluation.json` | `schemas/evaluation.schema.json`; task vs learning separated, retention and transfer present |

### Stage 8 — Intervene

Design the minimum viable pilot: phased rollout with explicit usage rules and guardrails, an owner, the participating population, and the evidence it aligns to. Every phase needs a **stop condition** (including a harm/risk stop) and a decision point — weeks, not quarters. Resist scope creep: a pilot that cannot be stopped cheaply is not a pilot.

### Stage 8b — Grounding check

A design may proceed only when it answers a real, unresolved gap that the review identified and the evidence cannot close. If the gap is already answered by existing evidence, the correct output is an applicability-bounded decision, not a new trial.

### Stage 9 — Evaluate

Define the measurement plan: baseline, immediate post-test, retention, and transfer, plus process and risk indicators. Success thresholds must be pre-registered; failure and stop thresholds are equally mandatory. Make the analysis plan explicit enough that `scripts/did_regression.py` can execute it on the returned data without further decisions.

## Failure handling and fallbacks

| Failure | Handling |
|---|---|
| `NEEDS_USER_CONTEXT` | Ask for population, duration, staffing, and constraints; never invent an operating context. |
| `INSUFFICIENT_EVIDENCE` | Stop here and return to the review — a pilot cannot substitute for missing evidence about safety or harm. |
| `SCOPE_MISMATCH` | Shrink the pilot population until it sits inside the supported population. |
| No grounded KnowledgeGap | Do not design the study; report what evidence would be needed instead. |
| Ethics review unresolved | Block the pilot; see `skill/sub-skills/ethics-review/SKILL.md`. |

## Human hand-off points

- Before the pilot design is accepted: the course owner confirms feasibility, staffing, and time budget.
- Before enrolment: ethics/IRB review where human participants or personal telemetry are involved.
- Before every phase transition: the stop-condition check is a human decision, not an automatic continuation.

## Resuming and updating

Pilot outcome data returns through `reference/` and is re-injected by the `evaluate-and-update` workflow, which commits a new Evidence Graph revision and a new decision snapshot. Never edit a pilot's success threshold after seeing the data.

## Minimal example

```bash
eduevidence project create --question "Unguarded AI coding assistance in CS1" --domain education   # policy / other registered domains work identically
eduevidence project show --project PRJ-... # confirm the decision snapshot
eduevidence study design --project PRJ-... --gap GAP-RETENTION-001 # grounded design
# write intervention.json (phases + stop conditions) and evaluation.json (thresholds)
eduevidence pilot register --project PRJ-... --decision DEC-... --title "Phased CS1 pilot"
```

## Acceptance checklist

- [ ] The pilot traces to a schema-valid verdict and an applicability boundary.
- [ ] Every phase has an owner, a duration, a stop condition, and a decision point.
- [ ] Guardrails and usage rules are explicit (what participants may and may not do).
- [ ] Evaluation separates task performance from learning and includes retention + transfer.
- [ ] Success and failure thresholds were set before enrolment.
- [ ] The KnowledgeGap reference exists, or the workflow exited without a study design.
- [ ] Nothing in the output claims adoption, deployment, or proven benefit.
