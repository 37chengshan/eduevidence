# Sciverse 检索通道（API 契约存档）

本条记录 EduEvidence 接入 Sciverse 开放平台所用的最小契约，依据官方 `openapi.yaml` **v0.14.2**（`opendatalab/Sciverse-Agent-Tools`）整理。目的是让检索链在**没有网络**时也能被复核：字段名、错误码、限制与语义都在这里，代码变更需同步更新本文件。

## 1. 基本信息

| 项 | 值 |
|---|---|
| Base URL | `https://api.sciverse.space` |
| 鉴权 | `Authorization: Bearer <SCIVERSE_API_TOKEN>`（HTTP Bearer） |
| Token 来源 | 控制台 Tokens 页；同账号可通用于 Sciverse / DianShi / SeqStudio 已开通能力 |
| 实现 | `retrieval/sciverse.py`（stdlib-only） |
| 通道类型 | key-based 学术通道，在 `MultiSearchRouter.academic_key_providers` 中优先于零配置学术通道 |
| 无 token 行为 | 通道静默失活（`SCIVERSE_UNAVAILABLE`），零配置通道继续工作 |

## 2. 使用的四个端点

### 2.1 `POST /meta-search` — 结构化元数据检索

用于 Source 级命中：标题、作者、摘要、期刊、年份、DOI。

- 请求（所用子集）：`collection`（papers/authors/sources）、`query`（BM25）、`filters_advanced[]`（`{field, operator, value}`）、`page`、`page_size`（≤50）。
- 响应：`results[]`（注意是 `results`，不是 `hits`）、`total_count`、`page`、`page_size`、`total_pages`、`next_cursor`。
- 关键字段：`unique_id`（元数据全局唯一 ID，**始终存在**）、`doc_id`（全文内容哈希 sha256，**仅当存在全文**）、`is_content_accessible`、`doi`、`author[].name`、`publication_published_year`、`publication_venue_name_unified`。
- 过滤操作符：`FILTER_OP_EQ/NE/GT/GTE/LT/LTE/IN/NIN/CONTAINS/MATCH/MATCH_PHRASE`；`doi` 用 `EQ`（服务端去 `doi.org` 前缀并转小写后精确匹配）。
- 排序与加权：`sort_by_year`（`auto` 在带 query 时保留相关性排序）、`freshness_boost` / `impact_boost` / `language_affinity`（`NONE|MILD|STRONG`，仅在 query 非空时生效；加权生效时**不支持深翻页**）。

### 2.2 `POST /agentic-search` — 自然语言语义检索（RAG）

用于 chunk 级**定位子**：

- 请求：`query`（1–200 字最佳）、`top_k`（1–100）、`mode`（`fast` ~200ms / `balanced` ~600ms / `quality` ~2–4s）、可选 `filters`、`source_types`（`web` / `pdf`）。
- 响应：`hits[]`，每条含 `chunk_id`、`doc_id`、`score`、`title`、`offset`（**Unicode 码点**，可直接作为 `/content` 的 offset）、`page_no`、`source_type`、`chunk`、`abstract`。
- **限制**：`balanced` 模式服务端约截断至 50 条；同一篇论文最多返回约 3 个 chunk，因此高 `top_k` 需要足够多的不同论文。
- **软过滤语义**：`filters` 在召回阶段与语义检索同时下推，但 chunk 侧元数据缺失的文档不会被排除（按年份过滤时，缺年份的 chunk 仍可能返回）。结论表述必须写"近似范围"；需要严格范围时改用 `meta-search` 的结构化过滤并核对返回记录。
- 唯一的硬过滤字段是 `doc_id`（命中绝不越出给定集合；去重后上限默认 1000）。

### 2.3 `GET /content` — 按码点区间读原文

把 chunk 定位子扩展为可抽取的正文：

- 参数：`doc_id`（必填）、`offset`（默认 0）、`limit`（默认 4096，服务端上限 524288，超出静默钳制）。
- **必须显式传 `offset`**：省略时服务端返回整篇全文并忽略 `limit`。
- 响应：`text`、`bytes_returned`（UTF-8 字节数，仅供参考）、`next_offset`（下一段起始码点，翻页用它而非字节数）、`more`。
- 单位：`offset` / `limit` 均以 **Unicode 码点**计，与 Python `len` 一致，不是字节。

### 2.4 `POST /meta-paper-relations` — 引用 / 被引 / 相关工作

用于引文链审计（`SearchQuery.purpose = citation_chain`）：

- 请求：`unique_id`（**不是 doc_id**）、`relation`（`CITATIONS` 被引 / `REFERENCES` 参考文献 / `RELATED_WORKS`）、`page`、`page_size`（≤200）。
- 响应：`items[]`（`id` / `id_type` / `title`）、`total_count`、`page`、`page_size`、`total_pages`。
- 方向语义：`CITATIONS` 是"谁引用了我"，`REFERENCES` 是"我引用了谁"，两者相反。
- **上限**：关系数超 10000 返回 `429`；`page × page_size` 超 10000 返回 `400`。两种情况改用 `meta-search` 的 `references_unique_id` 反查（支持深翻页与任意排序）。
- `total_count` 只统计库内命中，与论文自身 `citation_count` 可能有约 ±1% 差异。

## 3. 错误处理与状态映射

`retrieval/sciverse.py` 把 HTTP 与网络异常统一映射为**定型状态**，绝不把异常抛进检索管道：

| HTTP / 情形 | 状态 | 管道行为 |
|---|---|---|
| 200 | `ok` | 正常解析 |
| 401 / 403 | `SCIVERSE_UNAUTHORIZED` | 记录尝试，切换其他通道 |
| 400 / 404 / 429 | `SCIVERSE_BAD_REQUEST` | 同上（429 视为配额/上限耗尽） |
| 502 / 503 / 5xx | `SCIVERSE_UPSTREAM_ERROR` | 同上 |
| 超时 / DNS / TLS | `SCIVERSE_NETWORK_ERROR` | 同上 |
| 未配置 token | `SCIVERSE_UNAVAILABLE` | 通道失活，不产生请求 |

错误信息只保留服务端 `ApiError.message` 或状态描述，**不携带 Authorization 头或 token 片段**。

## 4. 在证据链中的位置（RULE 2 的机器化）

```text
/meta-search      → Source 级命中（DOI → https://doi.org/<doi>；无 DOI 则标记 needs_manual_location）
/agentic-search   → chunk 定位子（doc_id + offset）→ 写入 chunks.jsonl，标注 discovery_only_requires_content_fetch
/content          → 按定位读原文 → 经 retrieval/validate.py 校验门 → 才可进入 Extract
/meta-paper-relations → 引文链记录（写入审计导出，供筛选与饱和判断）
```

要点：**chunk 不是证据**。它是发现线索；只有 `/content` 读到的正文通过校验门（长度、错误页、登录页、验证码、标题匹配等）之后，才允许被抽取为 Evidence Object。这条纪律由 `retrieval/fetch.py::fetch_sciverse_content()` 实现，产出与 `FetchResult` 同形，下游零改动。

引用目标永远是论文本身（DOI / `unique_id`），**不是 Sciverse** —— 它是读取路径，不是来源。

## 5. 配置

```bash
export SCIVERSE_API_TOKEN=sv-...        # 必需；未设置时通道失活
# 可选：指向测试环境
export SCIVERSE_BASE_URL=https://api.sciverse.space
```

宿主侧如已安装官方 Skill / MCP，可作为**补充**而非替代（本仓库的实现不依赖它）：

```bash
npx skills add https://sciverse.space
# 或 MCP server
npm install -g sciverse-mcp-server
export SCIVERSE_API_TOKEN=sv-...
```

## 6. 验证

```bash
# 契约与降级行为（离线，mock HTTP）
python -m pytest tests/test_sciverse_channel.py -q

# 真实连通冒烟（需 token）
python - <<'PY'
from retrieval import sciverse as s
print('available:', s.available())
print('meta:', s.meta_search('generative AI coding assistants learning outcomes', limit=3).status)
r = s.agentic_search('unguarded GPT-4 access harms independent exam performance', top_k=3)
recs = s.chunk_records(r)
print('chunks:', len(recs))
if recs:
    c = s.read_content(recs[0]['doc_id'], offset=recs[0]['offset'], limit=600)
    print('content:', c.status, len(c.data.get('text') or ''))
PY
```

## 7. 合规

配额、限速、缓存与署名规则统一见 `references/retrieval-compliance.md`（§3 Sciverse 附加约定）。规范漂移时以官方 `openapi.yaml` 为准，并同步更新本文件与 `references/retrieval-protocol.md`。

