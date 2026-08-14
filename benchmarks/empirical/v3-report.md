# EduEvidence Benchmark Report (v3)

- run_id: run-20260814-031601
- mode: **EMPIRICAL**
- driver: cli | model: deepseek-v4-flash (deepseek-v4-flash) | temperature: 0.0
- tools: host agent tools | search_provider: host_tools | agent_mcp_used: False
- attempts: 60 total | failed: 0 | budget_stopped: 0
- notes: empirical run; see per-attempt artifacts
- cost: usage not metered by the cli/api driver (reported as 0.0 = NOT CAPTURED, not free)

| Baseline | n | outcome_sep | decision_cal | contra_recall | contra_precision | citation_recall | scope_cal | cost_usd |
|---|---|---|---|---|---|---|---|---|
| B2_standard_agent | 30 | 0.867+-0.124 | 0.567+-0.180 | 0.517+-0.120 | 0.230+-0.068 | 0.600+-0.128 | 0.633+-0.175 | 0.0 |
| B3_eduevidence_single | 30 | 0.967+-0.065 | 0.600+-0.178 | 0.500+-0.141 | 0.351+-0.106 | 0.500+-0.149 | 1.000+-0.000 | 0.0 |
