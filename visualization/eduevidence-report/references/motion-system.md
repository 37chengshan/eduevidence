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
- `chart-reveal` — `[data-lieflat]` gallery cards follow the Lieflat mono-tokens `obsReveal` contract. **This is a fixed template role; the five themes must not invent alternative chart animation logic.**

`chart-reveal` contract (implemented in `motion/motion.css` + `motion/motion.js`):

- Elements carry `lf-pop` / `lf-fade` / `lf-draw` classes plus an inline `--motion-delay` variable (dot matrices stagger 12 ms, bars 100 ms — the 8–15 ms / 80–130 ms token ranges).
- Curves are the mono-tokens family: `lf-pop` scale 0→1 with `cubic-bezier(.2,.7,.3,1.3)` 500 ms; `lf-fade` 900 ms ease; `lf-draw` dasharray 1 with `cubic-bezier(.4,0,.2,1)` 1 s.
- Reveal runs once when the card scrolls into view (IntersectionObserver, threshold .3), gated by the `.js-lf` root class; clicking the card replays the reveal after clearing that card's registered timers (no animation stacking).
- Without JS, or under `prefers-reduced-motion: reduce`, or in print, every element stays static and fully visible — motion never hides evidence.

Constraints:

- Motion never changes numbers, evidence direction, ordering, adjudication, or chart scale.
- Every reveal runs at most once per element (except explicit user-requested replay via click on `[data-lieflat]`).
- `prefers-reduced-motion: reduce` disables nonessential animation.
- Print disables all animation and exposes detail content.
- Five visual themes may alter layout and surfaces, but must not invent new motion behaviors.
