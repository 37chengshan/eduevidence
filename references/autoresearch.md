# Evidence Autoresearch

Use this reference for bounded autonomous evidence acquisition inside an existing EduEvidence Project.

## Loop

`GraphRevision + DecisionSnapshot + KnowledgeGaps → rank DVI → choose ONE gap → ONE falsifiable strategy → bounded execution → validate staging evidence → single-writer graph commit or no-gain log → re-adjudicate → next gap`.

## Hard rules

- A KnowledgeGap must already be grounded in the Evidence Graph.
- DVI is an ordinal HIGH/MEDIUM/LOW prioritization heuristic, never EVPI/EVSI or a probability.
- Run one primary research hypothesis per ResearchIteration.
- Validated evidence is append-only whether supportive, contradictory, neutral, or null.
- A no-gain iteration creates ResearchIteration memory but no GraphRevision.
- Negative search results may only state that no eligible evidence was found within the recorded search scope.
- Stop on resolved gap, loss of decision sensitivity, budget exhaustion, saturation, tool blockage, user stop, or need for new empirical evidence.
- Literature → Pilot requires HIGH DVI + decision materiality + unresolved gap + search saturation + ethical/operational feasibility.
- New decision outputs created by autonomous refresh remain candidate decisions until an appropriate human/review gate accepts them.

## CLI

```text
eduevidence research auto step --project <id>
eduevidence research auto step --project <id> --outcome-file <validated-staging.json>
eduevidence research auto status --project <id>
eduevidence research auto stop --project <id>
```

Without an execution artifact, `step` emits the selected GapPriority and ResearchStrategy and stops at `awaiting_execution`; it never fabricates search results.
