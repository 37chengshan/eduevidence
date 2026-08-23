---
name: aihot-trend-analysis
description: "Real-time horizon scanning and dynamic trend ingestion for emerging AI educational tools, model benchmarks, and EdTech releases via AIHot."
---

# aihot-trend-analysis — Real-Time AI & EdTech Trend Ingestion Sub-Skill

## When to Use
Triggered when an educational or social science research inquiry involves fast-moving generative AI tools (e.g. Cursor, Claude 3.5, Socratic LLM tutors, Copilot) where peer-reviewed academic literature may have a 6-18 month publication lag.

## Input Requirements
- `keyword`: Target technology or pedagogy topic (e.g. `"AI programming assistant"`, `"Socratic coding tutor"`).
- `time_window`: Optional lookup horizon (`"24h"`, `"7d"`, `"30d"`).
- `category`: `"EdTech"`, `"Agents"`, `"Reasoning"`, `"LLMs"`.

## Output Contract
Returns structured `SearchHit` objects tagged with `provider: "aihot"` and `tier: 5` (grey literature / technical trend), providing zero-day context before empirical trials are designed.

```json
{
  "trend_items": [
    {
      "title": "OpenAI Socratic Tutoring Framework Evaluated Across 10 Universities",
      "url": "https://aihot.virxact.com/api/item/...",
      "summary": "Benchmark evaluation on novice cognitive retention and prompt scaffolding.",
      "category": "EdTech",
      "publish_time": "2026-08-15"
    }
  ]
}
```
