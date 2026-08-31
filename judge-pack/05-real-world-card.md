# Real-world Card — real literature, real portability, honest boundaries

## Flagship (real literature)

`examples/ai-coding-assistant-evidence/` — 8 registry-verified sources (CrossRef/DataCite audit trail `benchmarks/doi-audit/report.md`), 12 evidence rows, engine-computed Moderate confidence, five baked report themes.

## Policy portability (not an education-hardcoded prompt)

- Domain registry: `domains/manifest.json` (education vs policy);
- Policy frame rejects `learner`/`course` leaks: `tests/test_policy_portability.py`;
- Projects can carry `domain=policy`: `engine/project.py`, `schemas/v2/project.schema.json`.

## Honest boundary (status report)

Implemented and machine-checkable:

- Canonical protocol + Projection split, version SSOT (`engine/versions.py` → 6.0.0), green CI contract;
- Audited retrieval + counter-evidence queries, durable control plane, immutable artifacts, judge-pack export;
- Report H1 sizing reduced across all five themes (`visualization/eduevidence-report/assets/base.css`, five theme files, `tests/test_report_layout_mobile.py`).

External / pending (not claimed as released):

- Full 30-question B2-vs-B3 same-model comparison requires real model budget; a recorded bounded run is `benchmarks/empirical/omp-dsflash-max-smoke/`.
- Living-evidence classroom re-injection awaits real anonymized outcome data (`docs/plans/STATUS.md` F2).
- Publication/contest channels are external actions and remain out of scope of this repository change.
