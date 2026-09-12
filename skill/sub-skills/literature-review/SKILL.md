---
name: literature-review
description: "Executes multi-source academic and web retrieval across OpenAlex, Semantic Scholar, CrossRef, AIHot, AgentSearch, Sciverse, and user-configured providers."
capability: literature_search + counter_evidence_search + source_fetch + source_validation
---

# Literature Review Skill

## When to Use
Trigger after research intent is established to gather candidate empirical studies, peer-reviewed papers, and verified grey literature.

## Inputs
- `frame.json`（检索边界、纳排标准）
- 检索预算（S/M/L 决定）与可选 key：`SCIVERSE_API_TOKEN` / `TAVILY_API_KEY` / `BRAVE_API_KEY`

## Process
1. **Plan first** — 写 `SearchPlan`（core / expansion / **counter_evidence**），经 `retrieval/audit.py` 执行并导出审计四件套。
2. **Zero-Config Academic Providers**: OpenAlex (250M+ works with DOIs), Semantic Scholar (graph citations + abstracts), CrossRef (DOI registry), AIHot (real-time AI/EdTech feed), AgentSearch / ArXiv.
3. **Key-based academic channel**: Sciverse (`SCIVERSE_API_TOKEN`) — `/meta-search` 产出 Source 级命中；`/agentic-search` 产出 chunk 定位子，必须经 `/content` 读原文并过校验门，定位写入 `chunks.jsonl`。
4. **Configured web providers**: Tavily, Brave.
5. **Fetch & Validation**: 候选 URL 走 `retrieval/fetch.py` 降级链并由 `retrieval/validate.py` 校验；严格拒绝 snippet 幻觉。
6. **Compliance**: 遵守 `references/retrieval-compliance.md`（robots / 限速 / paywall / 署名与缓存）。

## Output Contract
- `sources.jsonl`（`schemas/source.schema.json`）+ `fetch/`（raw + clean + provenance + fallback_chain）
- 审计导出：`search-provenance.json` / `search-attempts.jsonl` / `source-screening.csv` / `exclusion-log.csv`
- Sciverse 定位：`chunks.jsonl`（`locator_state=discovery_only_requires_content_fetch`）

## Quality Gates
- [ ] 反方查询独立构造且计数 > 0。
- [ ] 每条来源为 FETCH_VALID 或经确认的 FETCH_PARTIAL。
- [ ] 无 DOI/URL 记录标 `needs_manual_location`，未伪造定位。
- [ ] 排除记录写明原因。

## Anti-Patterns
- 用支持证据的检索式找反证；把 abstract 当证据内容；为凑数填充无关来源。

## Worked Example
`python scripts/search_provenance.py "first-year CS generative AI coding assistant" --out runs/x/provenance --concept "AI coding assistant"` → 审计四件套 + 候选来源表，随后逐条 fetch/validate。

## References
- `references/retrieval-protocol.md`、`references/retrieval-compliance.md`、`references/source-validity.md`、`skill/task-briefs/retrieve.md`
