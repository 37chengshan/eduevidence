# Method Card — the discipline of a decision-grade review

Normal research retrieval: find papers, quote them. EduEvidence: **plan the search, record every attempt, screen sources, and search counter-evidence as a mandatory query**.

```text
SearchPlan (explicit queries, incl. counter_evidence)
  → provider attempts (all failures logged)
  → screening table + exclusion log
  → fetch + validation gate (snippet ≠ evidence)
  → methodology audit (WWC-style)
  → adjudication capped by Pre-Verdict Gate
  → applicability boundary
  → decision snapshot (immutable)
```

Machine-checkable artifacts:

- Planned-search provenance export: `retrieval/audit.py` + `scripts/search_provenance.py`;
- Fetch validation gate: `retrieval/validate.py`;
- Deduplication must keep one Study per duplicate, never two: `retrieval/dedupe.py`;
- Independent Study counting (never Finding counting): `scripts/evidence_score.py`;
- Confidence policy: `engine/versions.py` + `scripts/compute_confidence.py`;
- Fail-closed statistics: `scripts/did_regression.py` returns `status=error` and null coefficients rather than fake SE/p-values.
