---
name: evidence-review
description: Traceable evidence review with mandatory counter-evidence and methodology gates.
---

# Evidence Review

Use for a question that needs a bounded, decision-grade evidence assessment.
Run `Frame → Retrieve → Extract → Challenge → Audit → Adjudicate → Applicability`.

The required outputs are a search plan and attempt log, validated sources, claim-level evidence links, a methodology audit, a decision boundary, and applicability limits. Search snippets are discovery metadata, never evidence.

When the user asks to continue autonomously, identify the next most decision-relevant evidence, or keep iterating until the evidence state reaches a bounded stopping condition, load `references/autoresearch.md`. Keep the public workflow unchanged: Evidence Autoresearch is a meta-layer over this review, not a fourth user-facing workflow. Preserve append-only evidence and the Single Writer rule.
