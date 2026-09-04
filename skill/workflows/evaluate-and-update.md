---
name: evaluate-and-update
description: Re-inject validated outcome data into an evidence graph and re-adjudicate.
---

# Evaluate & Update

Use when pilot or field data exists. Validate provenance and missingness before analysis, fail closed when inference is not estimable, commit a graph revision, then produce a new decision snapshot and a decision diff.

For autonomous/living refreshes, preserve prior revisions and treat the newly re-adjudicated decision as a candidate update until the applicable review/human gate accepts it. New evidence does not need to flip the action; unchanged action with changed certainty, applicability, or boundary is a valid revision.
