# Task Brief — stage: retrieve（角色：evidence-retriever）

## 目标
按 Frame 的 scope 与 inclusion criteria 检索支持证据与独立反方证据；只检索，不下结论。
Fetch/Validate 是 Retrieve 内部强制 gate（RULE 2：snippet ≠ 证据内容）。

## 前置输入
- `frame.json`（检索边界、纳排标准）
- 复杂度等级对应的检索预算（S/M/L）

## 产出
- `sources.jsonl`：每行一个 Source Object（source_id / title / canonical_url / authority_level），
  经 `retrieval/validate.py` 校验；抓取内容存 `fetch/`（raw + clean + provenance + fallback_chain）。
- 检索审计导出（`scripts/search_provenance.py`）：`search-provenance.json`、`search-attempts.jsonl`、
  `source-screening.csv`、`exclusion-log.csv`；Sciverse 通道命中另写 `chunks.jsonl`（定位子）。

## 执行规则
- **反方证据必须独立构造查询**（`purpose=counter_evidence`），不得复用支持证据的检索式。
- 先写 `SearchPlan` 再执行；每条查询、每次 provider 尝试、每个排除决定都要留痕。
- 来源权威等级可验证（DOI/期刊/机构），禁止编造 canonical URL；无 DOI 且无 URL 的记录标 `needs_manual_location`，
  进入人工筛选，不得伪造定位。
- **snippet/abstract 只是发现线索**：必须经 `retrieval/fetch.py` 抓取并通过 `retrieval/validate.py` 才可作为证据内容。
- Sciverse 通道（`SCIVERSE_API_TOKEN`）：`/agentic-search` 返回的是 chunk 定位子，必须经 `/content` 读原文并过校验门。
- 检索合规见 `references/retrieval-compliance.md`（robots、限速、paywall、署名与缓存政策）。

## 质量门
- [ ] `sources.jsonl` 每行通过 `schemas/source.schema.json`。
- [ ] 审计导出四件套齐全，且反方查询计数 > 0。
- [ ] 每条进入证据链的来源都有 FETCH_VALID 或经规则确认的 FETCH_PARTIAL。
- [ ] 排除记录写明原因，人工筛选项显式标注。

## 失败模式与回退
| 失败 | 处理 |
|---|---|
| `SEARCH_NO_RESULT` | 放宽词族、切换 provider，或记录 negative-search record；不得静默降低证据标准。 |
| `FETCH_FAILED` | 走 provider 降级链；链尽则弃用该来源并回退到检索。 |
| `FETCH_PARTIAL` | 需规则或人工确认后才可进入抽取。 |
| `SOURCE_INVALID` | 弃用并寻找替代来源。 |
| `SOURCE_DUPLICATE` | 合并同一论文的镜像 URL，保留最高权威等级条目。 |

## 语言与呈现契约
筛选理由与排除原因用人话表述；来源标题保留原文，不改写、不翻译。

## 交接说明
`sources.jsonl` + `fetch/` 是 Extract 的唯一输入；snippet 不得作为抽取依据随链传递。
