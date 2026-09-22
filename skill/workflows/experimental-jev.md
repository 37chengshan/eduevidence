---
name: experimental-jev
description: Optional Jev / SemDecide Tier-0 acceleration overlay. Modes 0 standard / 1 jev-mcp / 2 semdecide / 3 hybrid. Fail-closed. Never replaces Pre-Verdict Gate or Skeptic.
---

# Experimental Jev Overlay

Use only when the run explicitly enables `--experimental` (or `EDU_EXPERIMENTAL_JEV=<mode>`).
This is an **acceleration overlay** on the scientific protocol — not a fourth workflow,
not a substitute for scientific gates, and not a source of evidence.

Default without the flag: **mode 0 standard** (existing large-model pipeline only).

## Modes

| Mode | Name | Backing | When |
|---:|---|---|---|
| 0 | standard | host large model only | default; no experimental flag |
| 1 | jev-mcp | `integrations/jev/` → FreeJev or Vercel AI Gateway `typesafe-ai/jev` (urllib) or documented MCP (`https://freejev.org/mcp`, `npx -y @jkudish/jev-mcp`) | Tier-0 typed judgments, fast & cheap |
| 2 | semdecide | `integrations/semantic_decide.py` → `semdecide is / filter / choose` | Unix-pipeline predicates, filtering, routing |
| 3 | hybrid | 1 + 2 together | screen/rerank/extract/classify/verify via Jev; local predicates via SemDecide |

Enable:

```bash
# resolve mode + detect backends (no network judgment yet)
python3 integrations/jev_mcp.py --experimental 3
python3 integrations/semantic_decide.py --experimental 3

# user confirmation gate (writes ~/.eduevidence/jev_mcp_approval.json)
python3 integrations/jev_mcp.py --experimental 3 --approve

# host CLI (documented entry; flag turns the overlay on for the run)
eduevidence run --question "..." --run-id <id> --experimental 3
```

Secrets live only in `~/.eduevidence/env` — never in the repository, never on argv.

| Provider | Env | Decide endpoint | MCP (documented only) |
|---|---|---|---|
| `freejev` | `FREEJEV_API_KEY`, `JEV_PROVIDER=freejev` | `https://freejev.org/api/v1/decide` | `https://freejev.org/mcp` |
| `vercel` (default) | `AI_GATEWAY_API_KEY` or `TYPESAFE_API_KEY`, `JEV_PROVIDER=vercel` | Vercel AI Gateway System One | `npx -y @jkudish/jev-mcp` |

**FreeJev `request_id` is an idempotency key — never retry the same `request_id`.**
On timeout / 5xx / unknown outcome, fail-closed escalate this call to the large
model. A deliberate re-ask must use a **new** `request_id` and its own provenance row.

## Non-negotiable boundaries

1. **Fail-closed.** Any Jev `JEV_INVALID_RESPONSE` / `JEV_PROVIDER_ERROR`, and any
   SemDecide exit **2 / 3 / 4** (plus `SEMDECIDE_UNAVAILABLE` / `SEMDECIDE_TIMEOUT`),
   escalates to the large model (or a human). Never invent, never silently
   accept, never force a binary on an uncertain probability.
2. **FreeJev `request_id` 不重试.** Same `request_id` is never resent; escalate instead.
2. **Does not replace `scripts/pre_verdict_gate.py`.** Stage Adjudicate still runs the
   Pre-Verdict Gate before any verdict is final.
3. **Does not replace Skeptic.** Stage Challenge still executes all nine fixed checks
   (`skill/sub-skills/contradiction-analysis`). `claim_verify` may pre-triage claims only.
4. **Does not replace methodology audit / tribunal / outcome separation.**
5. **Snippet ≠ evidence (RULE 2).** `content_screen` / `semantic_rerank` operate on
   discovery material only. Only fetched, validated content enters Extract.
6. **Verbatim extract only.** `field_extract` returns regex-matched substrings chosen by
   Jev — never model-authored field values. `review` / `not_found` are not extraction.
7. **Approval gate.** Network Tier-0 calls require
   `~/.eduevidence/jev_mcp_approval.json` (tools hash + provider + model). Missing or
   mismatched approval → `JEV_APPROVAL_REQUIRED`, escalate.

## Nine-stage mapping (`engine/workflows.py::SCIENTIFIC_STAGE_IDS`)

| # | Stage | Mode 1 / 3 Jev Tier-0 | Mode 2 / 3 SemDecide | Still mandatory (never skipped) |
|---:|---|---|---|---|
| 1 | Frame | — | `choose` optional route for domain/frame vocabulary (uncertain → planner) | Frame schema; no intervention advice before framing |
| 2 | Retrieve | `content_screen` (pre-context injection/substance/relevance); `semantic_rerank` (discovery order); `classify_check` (inclusion pre-triage) | `filter` on candidate JSONL; `is` for cheap exclusion predicates | Search plan + counter-evidence queries; Fetch/Validate gate; provenance export |
| 3 | Extract | `field_extract` (verbatim n / effect / CI candidates); `classify_check` (outcome type pre-label) | `is` for task-vs-learning guard pre-check | Evidence Objects schema; outcome separation; finding ≠ study merge ban |
| 4 | Challenge | `claim_verify` **assist only** (claim↔evidence relation triage) | `is` for "is there a contradiction signal?" assist | **All nine Skeptic checks**; `NO CONTRADICTORY EVIDENCE FOUND` rule |
| 5 | Audit | `claim_verify` assist on claim support | `is` for checklist pre-filter | Methodology audit + `task_vs_learning_guard` |
| 6 | Adjudicate | — (Tier-0 must not score final verdict) | — | Four-state verdict; confidence breakdown; **`scripts/pre_verdict_gate.py`** |
| 7 | Applicability | `classify_check` optional population/context tags | `choose` optional applicability bounds | Population / conditions / exclusions / uncertainty stated |
| 8 | Intervene | — | — | Intervention design gates (`intervention_design`) |
| 9 | Evaluate | — | — | Evaluation design + data validation (`evaluation_design`, `data_validation`) |

Projection (report render) stays outside the nine stages and outside this overlay.

## Capability ↔ tool

Registered in `engine/capabilities.py` (experimental set; resolve with
`capability_registry(include_experimental=True)` or `experimental_capability_registry()` —
omitted from the default scientific registry because Tier-0 is not role-owned work):

| capability_id | Tool | Mode |
|---|---|---|
| `content_screen` | `jev_mcp.screen` | 1, 3 |
| `semantic_rerank` | `jev_mcp.rerank` | 1, 3 |
| `field_extract` | `jev_mcp.extract` | 1, 3 |
| `classify_check` | `jev_mcp.classify` | 1, 3 |
| `claim_verify` | `jev_mcp.verify` | 1, 3 |

SemDecide wrappers (`integrations/semantic_decide.py`) support stages without new
capability IDs: `is` / `filter` / `choose`.

## Fail-closed matrix

Aligned with `integrations/semantic_decide.py` (`EXIT_MEANINGS`, `ESCALATE_EXIT_CODES`,
`requires_llm_escalation`, `escalate_plan`) and `integrations/jev/gateway.py` status codes.

| Signal | Meaning | Action |
|---|---|---|
| Jev `JEV_INVALID_RESPONSE` | typed answer / `answers` envelope missing or malformed | escalate to large model; mark `review` |
| Jev `JEV_PROVIDER_ERROR` | transport / HTTP 401, 403, 429, 529, 5xx | escalate this call only; record attempt |
| FreeJev `request_id` failure/timeout | idempotent decide attempt already keyed | **do not retry same `request_id`**; escalate / new id only |
| `JEV_APPROVAL_REQUIRED` | no/wrong approval file | do not call network; escalate / ask user to approve |
| `JEV_UNAVAILABLE` | no key and no MCP path | mode 0 standard pipeline |
| SemDecide exit `0` | `true/selected/match` | semantic result usable |
| SemDecide exit `1` | `false/no match` | usable; `filter` exit 1 is **not** an escalation by itself |
| SemDecide exit `2` | `invalid input` | repair input and re-run, or hand the whole decision to the large model |
| SemDecide exit `3` | `uncertain` | escalate to large model / human; never force true/false |
| SemDecide exit `4` | `provider failure` | degrade to large model for this call only; record the attempt |
| `SEMDECIDE_UNAVAILABLE` | binary missing / spawn failed | escalate (`requires_llm_escalation`) |
| `SEMDECIDE_TIMEOUT` | CLI timed out | escalate (`escalate=ESCALATE_TO_LLM`) |
| Screen `block` / `review` | injection or low trust | do not enter context; discard or human review |
| Extract `review` / `not_found` | provisional or absent value | not an extracted field; large model re-extract |
| Classify `review` | low confidence / margin | large model re-label |
| Verify `review` / `unknown` | low confidence / invalid | large model claim check; never auto-adopt |

## Degradation path

```
mode 3 hybrid
  ├─ provider key + approval             → Tier-0 screen/rerank/extract/classify/verify
  │    (FreeJev: FREEJEV_API_KEY + JEV_PROVIDER=freejev; request_id never retried)
  ├─ semdecide on PATH                   → is/filter/choose
  ├─ exit 2/3/4 / SEMDECIDE_TIMEOUT
  │    / JEV_INVALID_RESPONSE / JEV_PROVIDER_ERROR
  │                                    → large model for THAT call (fail-closed)
  ├─ Jev unavailable                     → SemDecide only (mode 2 slice)
  ├─ semdecide unavailable               → Jev only (mode 1 slice)
  └─ both unavailable / no --experimental → mode 0 standard (Platform Native)
```

Scientific gates do not degrade: Pre-Verdict Gate, Skeptic nine checks, methodology
audit, and the four-state tribunal always run on the host path.

## Acceptance checklist

- [ ] `--experimental <mode>` recorded on the run; mode 0 when absent.
- [ ] Approval file present and `tools_hash` matches before any gateway call.
- [ ] Every Tier-0 result stored with `status` / `confidence` / `escalate` provenance.
- [ ] All SemDecide exit 2/3/4, `SEMDECIDE_UNAVAILABLE`, and `SEMDECIDE_TIMEOUT` rows
      show an escalation record (no silent coercion). `filter` exit 1 alone is not escalated.
- [ ] FreeJev calls never reuse a `request_id` for retry; each attempt is one shot.
- [ ] Stage 4 Challenge still has the nine Skeptic checks + explicit contradiction statement.
- [ ] Stage 6 Adjudicate still ran `scripts/pre_verdict_gate.py` before finalising.
- [ ] A/B metrics logged per `docs/j-ev-experimental.md` (speedup口径 + quality gates).
- [ ] No secrets in artifacts (`AI_GATEWAY_API_KEY` / `TYPESAFE_API_KEY` / `FREEJEV_API_KEY`);
      keys only from `~/.eduevidence/env` / process env.

## Minimal example

```bash
export EDU_EXPERIMENTAL_JEV=3   # or pass --experimental 3 to the host CLI
python3 integrations/jev_mcp.py --experimental 3 --approve
eduevidence run --question "Should first-year CS students use generative AI coding assistants?" \
  --run-id ai-cs1-jev --experimental 3
# Scientific path unchanged: Frame → Retrieve → Extract → Challenge → Audit → Adjudicate → Applicability
# Tier-0 only pre-screens, re-ranks, extracts verbatim fields, pre-labels, pre-verifies claims.
```
