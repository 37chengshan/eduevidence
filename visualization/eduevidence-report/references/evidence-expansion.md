# Evidence Expansion Contract

Evidence is progressive disclosure, not a flat wall of prose.

## Compact matrix

Default columns:

```text
Evidence ID | Outcome | Effect | Quality | Claim | Source
```

`Effect` is derived from `evidence.effect_direction` (`positive / negative / null`). `relation_to_claim` is shown only as a secondary relationship note.

## Full expansion

When present, expose:

```text
study_id
sample_id
title
year
study_type
education_level
population
sample_size
intervention
comparison
outcome_measure
claim
effect
effect_direction
relation_to_claim
duration
method
strengths
limitations
confounders
quality_dimensions
quality_score
evidence_level
directness
applicability
confidence
status
extensions.claim_id
source_id
source_location
canonical_url
```

Missing fields are omitted. The renderer must not manufacture placeholders that could be mistaken for research data.

## Long text

Brief surfaces show an exact prefix excerpt. Clicking the native `<details>` control reveals the complete original string. The renderer may normalize whitespace but may not paraphrase, strengthen, weaken or translate the claim to create a shorter version.

## Source safety

Only `http` / `https` locations become links. Other source locations remain plain text.

## Print

Print mode exposes detail content and hides interactive summaries so scientific information is not lost in PDF/print export.
