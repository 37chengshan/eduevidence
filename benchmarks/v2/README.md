# V2 Benchmark

V2 benchmark cases live under `benchmarks/v2/` and cover the Research Engine
contract dimensions. The existing `benchmarks/questions.jsonl` (V1) is kept
unchanged for historical comparability.

Metric functions live in `benchmarks/evaluator/v2_graph_metrics.py`. They are
**deterministic software/contract metrics** — they measure whether the engine
produced a spec-conformant graph, not whether a research conclusion is
scientifically correct. Human/gold research annotation is required only for
content-level evaluation (e.g. whether a Finding's direction was extracted
correctly from a real paper); the metric functions themselves never judge
research content.

## Deterministic software/contract metrics

- `study_identity_accuracy` — Study ids/independence keys preserved and
  deduplicated correctly.
- `independent_evidence_counting_accuracy` — 5 Findings from one Study count
  as 1 independent study (never 5:1 voting).
- `claim_link_semantics_accuracy` — `relation_to_claim` /
  `decision_implication` / `effect_direction` are never conflated.
- `graph_traceability` — Claim → EvidenceLink → Finding → Study → Source
  resolves completely.
- `projection_integrity` — projection counts match graph entity counts and
  projection never mutates the graph.
- `dataset_provenance_completeness` — dataset hash, privacy classification
  and deidentification status are recorded before analysis.

## Fixture caveat

`examples/full-research-cycle-fixture/data.csv` is synthetic; its scores are
**not** scientific performance evidence. See that fixture's README.
