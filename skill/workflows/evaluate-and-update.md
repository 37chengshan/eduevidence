---
name: evaluate-and-update
description: Re-inject validated outcome data into an evidence graph and re-adjudicate.
---

# Evaluate & Update

Use when pilot or field data exists. Validate provenance and missingness before analysis, fail closed when inference is not estimable, commit a graph revision, then produce a new decision snapshot and a decision diff.

For autonomous/living refreshes, preserve prior revisions and treat the newly re-adjudicated decision as a candidate update until the applicable review/human gate accepts it. New evidence does not need to flip the action; unchanged action with changed certainty, applicability, or boundary is a valid revision.

## When this workflow applies

- Pilot, field, or survey data has been collected and must now update the decision.
- New literature or a retraction changes what the existing decision can rest on.
- A scheduled Living Evidence refresh fires and must feed a decision diff.

Not for: running the original review (`evidence-review.md`) or designing the pilot that produced the data (`decision-and-pilot.md`).

## Prerequisites

1. The dataset plus its collection provenance: who collected it, when, from which population, under which consent.
2. The prior decision snapshot and the pilot's pre-registered thresholds — they must not be revised now.
3. Confirmation that the analysis plan was fixed before the data arrived.

## Runbook

| # | Stage | Role | Input | Artifact | Gate |
|---|---|---|---|---|---|
| 1 | Validate data | (deterministic) | raw dataset | `dataset-manifest` | provenance, hash, and missingness checked before any analysis |
| 2 | Analyse | evaluation-designer / `data-analysis` | manifest + analysis plan | `analysis-run` | fail closed when not estimable; never fabricate p-values |
| 3 | Merge | (deterministic) | analysis + prior graph | new Evidence Graph revision | append-only; prior revisions preserved |
| 4 | Re-adjudicate | evidence-judge | revised graph | new decision snapshot | verdict schema + Pre-Verdict Gate re-run |
| 5 | Diff | (deterministic) | old vs new snapshot | `decision-diff` | every change states which evidence caused it |

### Step 1 — Validate before analysing

Profile the dataset for missingness, attrition, and provenance. `provenance/hash/missingness before analysis` is a hard gate: an undocumented dataset is not evidence, and a treatment/control label that cannot be verified is not a comparison.

### Step 2 — Analyse under the pre-registered plan

Run the fixed plan — for the standard classroom case, Difference-in-Differences via `scripts/did_regression.py`, with Hedges' g via `scripts/effect_calculator.py`. If the design is not estimable (no baseline, no control, attrition beyond tolerance), the correct output is `ANALYSIS_NOT_ESTIMABLE`, not a weaker statistic presented as if it were the plan.

### Step 3 — Commit a revision, never an overwrite

A local finding enters the graph as a new node (`EVD-LOCAL-*`) and a new graph revision. Existing sources, findings, and prior decisions stay untouched — the Single Writer rule applies to the commit.

### Step 4 — Re-adjudicate against the whole body of evidence

Local data is one study among many. Re-run the four-state decision over the complete evidence set; a single favourable classroom result never outvotes a body of contrary evidence, and a null local result does not erase positive evidence elsewhere.

### Step 5 — Publish a decision diff

The deliverable is the diff: what changed in action, confidence, applicability, or boundary, and which evidence moved each one. Unchanged action with changed uncertainty is a real result and should be reported as such.

## Failure handling and fallbacks

| Failure | Handling |
|---|---|
| `ANALYSIS_NOT_ESTIMABLE` / `ANALYSIS_CAPABILITY_UNAVAILABLE` | Fail closed: report the design limitation; never substitute a weaker estimator silently. |
| Missingness above tolerance | Report attrition explicitly; downgrade certainty rather than dropping participants silently. |
| Thresholds changed post-hoc | Stop; the change is a protocol deviation and must be recorded, not absorbed. |
| New evidence contradicts on method only | Keep the finding, strip its support role (methodology gate). |
| Retraction of a cited source | Run `scripts/retraction_watch.py`, remove the source's support, re-adjudicate. |

## Human hand-off points

- Before analysis: data owner confirms consent and de-identification.
- Before the new decision is effective: the review/human gate accepts or rejects the candidate update (`living` refresh).
- When the diff changes a stop condition: the course owner decides whether the pilot continues.

## Resuming and updating

Autonomous refreshes create candidate updates only. Living Evidence subscriptions keep prior revisions and surface each refresh as a diff for acceptance; nothing overwrites a published decision. Repeated no-change refreshes are recorded, not re-announced.

## Minimal example

```bash
eduevidence data ingest --project PRJ-... --file pilot-results.csv
eduevidence analyze --project PRJ-... --outcome retention --design did
eduevidence adjudicate --project PRJ-... # new decision snapshot + diff
eduevidence living status --project PRJ-... # scheduled refresh state
```

## Acceptance checklist

- [ ] Dataset provenance, hashing, and missingness recorded before analysis.
- [ ] Analysis followed the pre-registered plan; non-estimable designs failed closed.
- [ ] A new graph revision was committed; no prior revision was modified.
- [ ] Re-adjudication used the full evidence set, not the local data alone.
- [ ] The decision diff states each change and the evidence that caused it.
- [ ] Any retracted source was removed from the support structure.

