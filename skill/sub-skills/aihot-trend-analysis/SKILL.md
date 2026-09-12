---
name: aihot-trend-analysis
description: "Real-time horizon scanning and dynamic trend ingestion for emerging AI educational tools, model benchmarks, and EdTech releases via AIHot."
capability: literature_search (grey-literature channel)
---

# aihot-trend-analysis — Real-Time AI & EdTech Trend Ingestion

## When to Use
Triggered when an inquiry involves fast-moving generative AI tools (Cursor, Claude, Socratic LLM tutors, Copilot) where peer-reviewed literature may lag 6–18 months.

## Inputs
- `keyword`: target technology or pedagogy topic.
- `time_window` (optional): `24h` / `7d` / `30d`.
- `category` (optional): `EdTech` / `Agents` / `Reasoning` / `LLMs`.

## Process
1. Query the AIHot channel through `retrieval/search.py` (`AIHotProvider`).
2. Record every hit as grey literature with its publication time.
3. Route any factual claim that would enter the decision back through Retrieve → Fetch → Validate: trend items never bypass RULE 2.

## Output Contract
`SearchHit` objects tagged `provider: "aihot"` with grey-literature authority (`tier5_general_web`); they inform horizon scanning, not effect estimation.

```json
{
  "trend_items": [
    {
      "title": "Socratic tutoring framework evaluated across 10 universities",
      "url": "https://aihot.virxact.com/api/item/...",
      "summary": "Benchmark evaluation on novice retention and prompt scaffolding.",
      "category": "EdTech",
      "publish_time": "2026-08-15"
    }
  ]
}
```

## Quality Gates
- [ ] 每条 trend 项带 URL 与时间戳。
- [ ] 明确标注为灰来源，不进入效应量合成。

## Anti-Patterns
- 用产品博客宣称的效果当作实证证据；把版本发布日期当研究发表时间。

## Worked Example
关键词 "AI programming assistant" → 返回 30 天内的发布与基准报道，用于判断文献滞后期内是否出现新的风险信号。

## References
- `retrieval/search.py::AIHotProvider`、`references/retrieval-compliance.md`
