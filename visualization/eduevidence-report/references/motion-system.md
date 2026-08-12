# Motion System

EduEvidence motion is a fixed presentation template, not per-report decoration.

Allowed roles:

- `section-enter` — one-shot section/chapter reveal.
- `stagger-enter` — evidence/tribunal/source groups reveal in reading order.
- `bar-grow` — meaningful comparison bars grow from zero once.
- `quality-grow` — inline quality meters grow once.
- `trace-reveal` — Claim → Evidence → Source chains reveal in order.
- `flow-reveal` — Evidence-to-Action nodes and arrows reveal in order.
- `detail-expand` — native `<details>` content receives a short opacity/translate reveal.
- `page-transition` — Visual Brief / Full Report switch uses a short page reveal.
- `toc-active` — active chapter changes color/border only.

Constraints:

- Motion never changes numbers, evidence direction, ordering, adjudication, or chart scale.
- Every reveal runs at most once per element.
- `prefers-reduced-motion: reduce` disables nonessential animation.
- Print disables all animation and exposes detail content.
- Five visual themes may alter layout and surfaces, but must not invent new motion behaviors.
