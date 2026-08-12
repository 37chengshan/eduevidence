# Full Report Outline

EduEvidence HTML contains two top-level views in one offline file:

1. **Visual Brief** — default, scan-first, preserves the visual summary experience.
2. **Full Report** — audit-first, desktop uses a collapsible sticky TOC and continuous report body.

## Dynamic 5–7 chapter rule

The Full Report is **not** a frozen 12-chapter document. An upstream AI should organize the research into **5–7 chapters** based on the actual evidence story.

The renderer works with semantic modules rather than fixed chapters:

```text
decision
scope
retrieval
outcomes
evidence
quality
conflicts
trace
applicability
intervention
evaluation
sources
```

The AI may merge and reorder middle modules and write research-specific chapter titles. Examples:

- `retrieval + quality` → “证据从哪里来，以及它们有多可信”
- `outcomes + evidence` → “效率提升背后的学习结果分化”
- `conflicts + trace` → “为什么证据冲突，以及哪些主张仍可成立”
- `applicability + intervention` → “从适用边界到有护栏试点”

Constraints:

- 5–7 chapters total.
- First chapter contains `decision`.
- Last chapter contains `sources`.
- Every semantic module appears exactly once.
- No evidence, contradiction, methodology audit or source provenance may be dropped by chapter merging.
- If an AI outline is invalid, the renderer falls back to a safe six-chapter grouping.

## Optional `report_outline`

```json
{
  "report_outline": {
    "chapters": [
      {
        "key": "decision",
        "title_zh": "结论与研究边界",
        "title_en": "Decision and Research Boundary",
        "lead_zh": "先明确可以得出什么结论，再解释为什么。",
        "lead_en": "State what can be concluded before explaining why.",
        "modules": ["decision", "scope"]
      }
    ]
  }
}
```

## Visual insertion rules

A chapter may include a chart or semantic visual only when it adds information beyond adjacent text/table. Sparse states such as `1 support / 0 contradict / 0 neutral` stay as badges/text. Every meaningful visual must have an interpretation caption explaining what the reader should take from it.

Outcome visuals must encode `effect_direction` (`positive / negative / null`), not `relation_to_claim`. Evidence can support a claim that an intervention caused a harmful outcome; therefore `support` is not equivalent to a positive effect.

## Progressive disclosure

Evidence, methodology audit items, tribunal claims and sources default to compact summaries and expose full traceable detail through accessible native `<details>/<summary>` controls. Print mode must not lose the hidden evidence content.

## Five themes, one content contract

The same Visual Brief / Full Report structure, dynamic outline and evidence content are rendered through five clearly differentiated layout templates:

- Claude Research — calm research reader.
- Academic Paper — journal/paper layout.
- Editorial — long-form magazine layout.
- DataLab — analytical workbench.
- Presentation / Judge — review/presentation layout.

Theme differences may include header composition, Brief grid, TOC appearance, body width, chapter surfaces, table density and data breakout width. Themes may not change evidence semantics or chapter content coverage.
