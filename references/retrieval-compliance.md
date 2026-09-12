# Retrieval Compliance Policy（检索合规政策）

本条政策约束 EduEvidence 的一切外部检索与抓取行为。它服务于两件事：**研究的可复现性**（每条来源都能被第三方重新定位）与**对他方服务与作者的尊重**（不越权、不滥用、不掩盖出处）。违反本条政策的检索结果不得进入证据链。

## 1. 定位与适用范围

适用于 `retrieval/` 下的全部通道：

| 通道 | 类型 | 是否需 key |
|---|---|---|
| OpenAlex / Semantic Scholar / CrossRef | 学术元数据 API | 否 |
| AIHot | 行业动态源 | 否 |
| AgentSearch / ArXiv | 预印本检索 | 否 |
| DuckDuckGo | 通用网页回退 | 否 |
| Sciverse | 学术检索（含全文） | 是（`SCIVERSE_API_TOKEN`） |
| Tavily / Brave | 商业搜索 API | 是 |
| 抓取链（builtin / jina_reader / defuddle / markdown_new / raw_html） | 正文读取 | 否 |

## 2. 抓取前：robots 与访问边界

- **尊重 robots.txt**：目标站点在 robots.txt 中禁止抓取的路径不得作为抓取目标；需要该内容时改用其官方 API 或元数据记录，并在筛选中注明"仅元数据"。
- **不绕过访问控制**：登录墙、付费墙、验证码页面一律视为不可读内容。抓取链会在校验门中把这些页面判为无效（`is_login_page` / `is_captcha_page`），此时正确做法是回到检索阶段寻找开放版本（预印本、机构库、作者主页），**而不是尝试绕过**。
- **不伪造可读性**：`FETCH_FAILED` / `FETCH_PARTIAL` 的内容不得作为证据；不得由模型根据标题或摘要"补写"正文。
- **私有地址不外发**：指向本机/私网的目标只允许本地读取，绝不提交给第三方清洗服务（`retrieval/fetch.py` 的 `LOCAL_PROVIDERS` 约束）。

## 3. 限速与重试

- 检索按查询批次串行执行，每次 provider 尝试最多重试 1 次（`AuditedSearchExecutor(max_retries=1)`）；失败即记录并切换通道，不做无限重试。
- 单次运行的检索预算由 `SearchPlan.provider_budget` 限定；S/M/L 分级只影响预算，不影响协议。
- 超时：检索 12 秒、抓取 20 秒；超时按失败处理并进入降级链。
- 商用 API 通道按其配额与速率限制使用；配额耗尽是运营问题，不构成放宽其他通道约束的理由。

### Sciverse 通道附加约定

- 单次 `agentic-search` 的 `top_k` 上限 100，且同一篇论文最多返回约 3 个 chunk；`balanced` 模式服务端约截断至 50 条。
- `filters` 为**软过滤**语义：chunk 侧元数据缺失的文档不会被排除。按年份等条件过滤时，结论表述必须写"近似范围"；需要严格范围时改用 `meta-search` 的结构化字段并核对返回记录。
- `offset` / `limit` 以 **Unicode 码点**计（与 Python `len` 一致），不是字节；翻页使用返回的 `next_offset`。
- 引用必须回指论文本身（DOI 或 `unique_id`），**不得把 Sciverse 记为引用目标**——它是读取路径，不是来源。

## 4. 署名与引用

- 引用目标永远是被引文献本身（DOI / 正式 URL / 数据库标识），绝不是检索或清洗通道（`r.jina.ai`、`markdown.new`、Sciverse 等）。
- 作者、年份、标题、期刊按原文记录，不改写、不翻译、不合并同名作者。
- 使用的每个来源都要能给出可核验的 `source_location`；没有位置的记录标 `needs_manual_location` 进入人工筛选。
- 撤稿与更正：已引 DOI 通过 `scripts/retraction_watch.py` 定期核查，命中即移除其支撑作用并重新裁决。

## 5. 缓存与留存

- 抓取正文在 run workspace 的 `fetch/` 下保存（raw + clean + provenance + fallback_chain），用于复现与审计；该目录随 run 生命周期管理。
- 检索审计（`search-provenance.json` / `search-attempts.jsonl` / `source-screening.csv` / `exclusion-log.csv`）与 run 同寿命，用于证明"检索确实发生过、范围如何"。
- 不长期镜像第三方全文；需要长期复用时保存定位信息与哈希，而非内容副本。
- 私有项目、用户上传数据与本地运行历史一律不进入公共产物（提交包由 `scripts/skill_payload.py` 的显式白名单构建）。

## 6. 凭据处理

- API key 只从环境变量读取（`SCIVERSE_API_TOKEN` / `TAVILY_API_KEY` / `BRAVE_API_KEY`）；不写入仓库、不写入产物、不进日志。
- 错误信息只保留状态与简短描述，不携带 Authorization 头或 token 片段。
- 缺少 key 时通道静默失活并如实上报状态，不影响零配置通道与科学门。

## 7. 失败与例外

| 情形 | 处理 |
|---|---|
| 站点禁止抓取 | 退回元数据记录并标注；不得绕过。 |
| 付费墙 | 寻找开放版本；找不到则记 `needs_manual_location`。 |
| 配额耗尽 | 记录该次尝试；切换零配置通道继续。 |
| 合规与时效冲突 | 以合规为准；宁可结论标注"证据不足"。 |

## 8. 交叉引用

- 检索协议：`references/retrieval-protocol.md`（查询构造、来源分级、饱和规则）
- 来源有效性：`references/source-validity.md`
- 抓取与校验实现：`retrieval/fetch.py`、`retrieval/validate.py`
- Sciverse 通道：`docs/sciverse-api.md`

