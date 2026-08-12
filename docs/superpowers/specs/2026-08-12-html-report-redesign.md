# EduEvidence HTML Report Redesign

Date: 2026-08-12
Status: Implemented in HTML report generator
Scope: `visualization/eduevidence-report/` and the demo report data needed to validate the redesigned renderer

## 1. Goal

Redesign the final EduEvidence HTML report so that it is not merely a styled data dump, but a readable, presentation-ready evidence report with strong information hierarchy, meaningful visualization, bilingual delivery, and five genuinely differentiated visual systems.

The final report must preserve:

- Single-file offline HTML output.
- Chinese / English switching inside the generated report.
- Static-first rendering: the report remains fully readable without ECharts.
- Existing evidence traceability and 12-section research-report structure.
- Five visual styles.

The redesign must additionally provide:

- More whitespace, rhythm, and visual breathing room.
- Clear decision-first storytelling.
- Meaningful visualization instead of chart-for-chart's-sake rendering.
- Better visual treatment of tabular data.
- Stronger competition/demo readability without turning the report into a flashy dashboard.
- Clearer Evidence → Decision → Action narrative.

## 2. Theme Selection Model

The five styles remain, but theme selection moves primarily to report-generation time.

Interactive CLI execution should ask the user to select one of five report styles unless a theme is supplied explicitly.

Supported command-line behavior:

```text
--theme claude
--theme academic
--theme editorial
--theme datalab
--theme presentation
```

Interactive prompt:

```text
Choose report visual style / 请选择报告视觉风格
1. Claude Research      [Light]
2. Academic Paper       [Light]
3. DataLab              [Light]
4. DataLab              [Dark]
5. Presentation / Judge [Dark]
```

Automation and CI must never block on the prompt: explicit `--theme` or a deterministic default must remain available.

The generated report retains Chinese / English switching. Theme switching inside the final HTML is no longer the primary UX requirement. The selected theme is treated as a report-design decision rather than a cosmetic skin.

## 3. Five Differentiated Visual Systems

The five themes must differ in layout grammar, density, typography, hierarchy, table treatment, chart sizing, section rhythm, and first-screen composition—not just colors.

### 3.1 Claude Research

Purpose: default long-form research reading and polished delivery.

Characteristics:

- Warm neutral background.
- Restrained terracotta accent.
- Large whitespace.
- Low-contrast borders.
- Sparse cards.
- Bookish serif headings + clean sans-serif UI.
- Comfortable reading width distinct from full-width data surfaces.
- Calm, quiet hierarchy.
- Evidence and decisions emphasized through spacing and typography rather than saturation.

### 3.2 Academic Paper

Purpose: formal research-paper / review-report reading and printing.

Characteristics:

- Paper-like white background.
- Serif-heavy typography.
- Numbered sections and stronger document structure.
- Minimal decorative cards.
- Footnote/source emphasis.
- Compact but readable figures.
- Tables styled closer to academic publishing conventions.
- Excellent print CSS and grayscale legibility.

### 3.3 DataLab [Light]

Purpose: researcher inspection and evidence analysis in a bright analytical workspace.

Characteristics:

- Wide responsive workspace with a maximum width rather than a fixed page width.
- Decision and Outcome dominate the Visual Brief; Tribunal and Evidence-to-Action form the secondary paired row.
- Strong filtering and table affordances.
- Evidence Matrix becomes a first-class analytic surface.
- Compact but readable cards and controls.
- Numeric alignment and data scanning prioritized.
- Visual encodings embedded directly into tables where appropriate.

### 3.4 DataLab [Dark]

Purpose: the same analytical information architecture as DataLab Light, optimized for prolonged dark-mode evidence review.

Characteristics:

- Same content hierarchy, pagination, evidence semantics, and interactions as DataLab Light.
- Dark surfaces use restrained contrast rather than pure black/white extremes.
- Evidence Matrix, methodology audit and source trace remain high-density but readable.
- Charts with white SVG backgrounds remain visually separated from the dark workspace.
- This is a distinct generation-time theme, not a runtime light/dark toggle.

### 3.5 Presentation / Judge

Purpose: competition review, live demo, and rapid comprehension.

Characteristics:

- Strong decision-first first screen.
- Larger typography and fewer simultaneous details.
- Three product differentiators highlighted clearly:
  1. Outcome Separation
  2. Evidence Tribunal
  3. Evidence-to-Action
- High-value charts larger; secondary detail progressively disclosed.
- Evidence traceability remains accessible but does not dominate the first screen.
- Designed so a reviewer can understand the project's value in roughly 30 seconds and follow the full evidence story in a short demo.

## 4. Global Information Architecture

The report should no longer feel like 12 equal-weight cards placed one after another.

The intended reading rhythm is:

```text
Decision
  ↓
Core Evidence
  ↓
Why the Evidence Disagrees
  ↓
Method / Data Detail
  ↓
Applicability
  ↓
Intervention
  ↓
Evaluation
  ↓
Sources / Provenance
```

The existing 12 report sections remain available, but their visual weight and grouping change.

Use three visual levels:

1. Narrative sections — narrow/comfortable reading width.
2. Decision surfaces — emphasized but restrained.
3. Data surfaces — wider breakout regions for tables, matrices, and charts.

## 5. First Screen / Decision View

The first screen must prioritize meaning rather than raw counts.

Required information:

- EduEvidence product identity.
- Research question.
- Recommended decision: ADOPT / PILOT / REJECT / INSUFFICIENT EVIDENCE.
- Confidence.
- One concise decision rationale.
- Strongest supported conclusion.
- Most important uncertainty or contradiction.
- Main risk.
- Recommended next action.
- Lightweight evidence snapshot only when counts are informative.

Large KPI tiles must not be used simply because a numeric field exists.

Bad example:

```text
Support: 1
Contradict: 0
Neutral: 0
```

This should render as concise semantic text or a small status component, not as a large chart or three oversized KPI cards.

## 6. Meaningful Visualization Gate

Every visualization must pass a relevance gate before rendering.

A visualization should render only when all relevant conditions are satisfied:

1. There is a real comparison, trend, distribution, relationship, or process to show.
2. There are enough meaningful data points to justify visual encoding.
3. The chart communicates the result faster or more accurately than text/table alone.
4. Compared values belong to compatible concepts and units.
5. The chart does not imply precision or significance beyond the evidence.
6. The visualization is not merely duplicating a table without adding interpretive value.

### 6.1 Suppression Rules

Do not render a chart when:

- Only one meaningful non-zero data point exists.
- The chart would mostly display zeros.
- The sample size is too small for the visual to add information.
- The data is categorical status better represented by badges/state cells.
- The data is simulated benchmark output that could be misread as empirical model superiority.
- A compact table or sentence communicates the same information more clearly.

Suppressed charts should not leave fixed-height blank containers.

### 6.2 Fallback Representations

When a chart is suppressed, use one of:

- Semantic summary text.
- Status badge.
- Inline bar / progress encoding inside a table cell.
- Compact mini-summary.
- No visualization at all.

The renderer must prefer no chart over a meaningless chart.

## 7. High-Value Visualization Types

The report should concentrate on a small set of visualizations that explain EduEvidence's unique reasoning model.

### 7.1 Outcome Separation

Show distinctions among relevant outcome categories, such as:

- Task performance.
- Learning.
- Retention.
- Transfer.
- Independent problem solving.
- AI dependency.

Goal: make it visually obvious that improved task completion is not automatically evidence of learning.

Render only categories present in the actual evidence/result.

### 7.2 Evidence Balance

Render only when there is sufficient evidence density.

Prefer a representation that combines:

- Outcome.
- Direction: support / contradict / neutral.
- Quality.

Avoid simple 1/0/0 count charts.

### 7.3 Claim → Evidence → Source Trace

Provide an explicit trace path:

```text
Claim
  ↓
Evidence ID
  ↓
Outcome + Direction + Quality
  ↓
Source ID
  ↓
Original source / DOI / canonical URL
```

The visualization must supplement, not replace, accessible text and links.

### 7.4 Evidence Tribunal

Visually distinguish:

- Supported.
- Uncertain.
- Contradicted.
- Missing evidence.

The goal is to communicate adjudication structure, not decorate four lists.

### 7.5 Evidence-to-Action

Visualize the decision loop:

```text
Evidence
  ↓
Applicability
  ↓
Decision / Pilot
  ↓
Guardrails
  ↓
Stop Conditions
  ↓
Evaluation
  ↓
Retention / Transfer / Other Target Outcomes
```

The diagram should expose why EduEvidence is more than a literature-summary agent.

## 8. Table Visualization Strategy

"Visualize table data" does not mean adding a chart beside every table.

Tables themselves should become visual analytic components.

### 8.1 Evidence Matrix

The matrix should prioritize these fields visually:

```text
Evidence ID
Outcome
Direction
Quality
Claim
Source
```

Secondary fields remain accessible but should not force an unreadable 11-column first view.

Recommended behavior:

- Search.
- Direction filter.
- Outcome filter.
- Expandable row detail.
- Direction chip / visual state.
- Quality represented numerically plus a restrained inline visual bar where useful.
- Source trace link.
- Claim text readable without horizontal scanning across excessive columns.

DataLab may expose more columns by default; other themes should prioritize a readable reduced view.

### 8.2 Methodology Audit

Use state cells / status matrix rather than gratuitous charts.

### 8.3 Sources / Provenance

Prefer readable provenance states and direct traceability over source-count charts.

Charts of source authority distribution should render only with enough sources to make the distribution meaningful.

## 9. Bilingual Requirements

Chinese / English switching remains in every generated HTML report.

Requirements:

- No Chinese hardcodes in English rendering.
- All UI labels must route through language dictionaries.
- `<html lang>` updates when language switches.
- Theme-independent content structure remains parallel between EN and ZH.
- IDs, enums, URLs, numbers, evidence relationships, source relationships, and array structure must remain equivalent across languages except for explicitly translatable text fields.
- Buttons should expose appropriate accessibility state such as `aria-pressed` where relevant.
- Static SVG titles / descriptions must be bilingual or language-aware.

## 10. Static-First and ECharts Behavior

The report must remain fully usable if ECharts is unavailable.

Rules:

- Static SVG / HTML is the primary representation.
- ECharts is an enhancement layer only.
- Dynamic chart mount containers start hidden/collapsed.
- A chart container becomes visible only after successful ECharts initialization.
- No empty 320px chart areas.
- No content or conclusion may exist only in the interactive chart.

## 11. Layout and Breathing Room

Increase breathing room through hierarchy rather than indiscriminate padding.

Required principles:

- Distinguish reading width from data width.
- Use fewer full-border cards.
- Use spacing to separate conceptual stages.
- Avoid placing every paragraph inside a boxed component.
- Allow data tables and figures to break out wider than prose.
- Preserve generous line-height and paragraph measure.
- Reduce badge proliferation.
- Use consistent section rhythm.
- Give charts independent titles, captions, and interpretation summaries.
- Avoid visual noise from repeated borders, shadows, pills, and decorative metrics.

## 12. Chart Interpretation Contract

Every displayed chart must answer a specific question.

Each chart requires:

- A human-readable title.
- The question or comparison it represents.
- A concise interpretation sentence.
- The underlying data source / field reference when appropriate.
- A meaningful empty/suppressed state.

A chart must not exist solely because a chart spec was generated.

## 13. Demo Data Policy

Review the current `examples/ai-coding-assistant/` demo data because renderer quality cannot compensate for meaningless demo visualizations.

Files in scope include:

- `result.json`
- `result.zh.json`
- `chart_specs.json`
- `infographics.json`
- generated `EduEvidence_Report.html`

Rules:

- Do not fabricate additional evidence simply to make charts look richer.
- If the demo data cannot support a meaningful chart, suppress the chart.
- If the demo can naturally expose richer relationships already present in evidence, update derived chart specs accordingly.
- The demo should showcase Outcome Separation, evidence disagreement, traceability, and Evidence-to-Action wherever the actual result supports them.

## 14. Accessibility and Responsive Design

Required improvements:

- Correct document language state.
- Keyboard-accessible controls.
- Visible focus states.
- ARIA labels for filters and controls.
- Semantic table headers.
- Accessible chart title/summary fallback.
- Color must never be the only carrier of direction/status.
- Mobile layout must reflow rather than simply shrink desktop tables.
- Print layout must avoid clipping wide tables and figures.

## 15. Scientific Integrity Constraints

UI polish must not weaken scientific integrity.

The renderer must not:

- Label unexecuted checks as PASS.
- Present simulated benchmark data as empirical model performance.
- Infer significance from tiny counts.
- Use visual scale or area to exaggerate weak differences.
- Treat neutral evidence as contradiction.
- Fabricate provenance or measurement data.

Visual integrity statuses must reflect only checks actually performed.

## 16. Implementation Boundaries

Primary files expected to change:

- `visualization/eduevidence-report/scripts/build_report.py`
- `visualization/eduevidence-report/themes/claude.css`
- `visualization/eduevidence-report/themes/academic.css`
- `visualization/eduevidence-report/themes/editorial.css`
- `visualization/eduevidence-report/themes/datalab.css`
- `visualization/eduevidence-report/themes/presentation.css`
- visualization helper scripts only where required
- renderer-focused tests
- demo-derived chart specs/data only where scientifically justified

Do not change the core evidence methodology merely to make the HTML prettier.

Do not alter the local-only competition brief or its ignore rule.

## 17. Testing Requirements

Implementation is not complete until targeted tests cover at least:

1. Theme argument selection.
2. Interactive theme selection path without breaking non-interactive use.
3. Five themes produce clearly distinct theme/layout markers.
4. EN/ZH language switching and no known Chinese hardcodes in English UI.
5. Meaningful Visualization Gate suppresses tiny/mostly-zero charts.
6. Meaningful datasets still produce expected visualizations.
7. No blank ECharts mount when ECharts is absent.
8. Evidence Matrix reduced/readable default representation.
9. Static fallback contains all critical conclusions.
10. Bilingual structural parity for IDs, URLs, numbers, enums, and evidence/source relationships.
11. Mobile/print CSS presence and key behavior.
12. Existing report-generation smoke path remains functional.

After targeted tests, run the full suite with:

```text
python3 -m pytest -q
```

Then regenerate the demo HTML and inspect the generated artifact for:

- first-screen hierarchy,
- theme differentiation,
- bilingual UI,
- chart suppression,
- table readability,
- static fallback,
- print/mobile layout,
- evidence traceability.

## 18. Acceptance Criteria

The redesign is accepted when all of the following are true:

- The user chooses one of five visual styles before generation, unless a theme is passed explicitly.
- The five styles are recognizably different without looking only at color.
- The generated HTML preserves Chinese / English switching.
- The report feels spacious and intentionally designed.
- Tiny 1/0-style datasets do not generate meaningless charts.
- Charts appear only when they add interpretation value.
- Table data receives meaningful visual encoding where useful.
- Evidence Matrix is readable without requiring immediate full-width horizontal scanning.
- Outcome Separation, Evidence Tribunal, and Evidence-to-Action are visually understandable.
- No ECharts dependency is required for core readability.
- No blank dynamic chart regions remain when enhancement is unavailable.
- English mode contains no known Chinese UI hardcodes.
- Scientific-integrity labels describe only checks actually performed.
- The demo report showcases EduEvidence's differentiation without fabricating evidence.
- Full automated tests pass after the redesign.
