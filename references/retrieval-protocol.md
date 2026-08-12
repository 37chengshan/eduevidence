# Retrieval Protocol（检索协议）

## 1. 目的与定位

本协议是工作流第 2 步 Retrieve 的执行细则，回答三个问题：

1. **查什么**：从 EducationResearchFrame 构造覆盖正面与反方证据的查询词族；
2. **从哪查**：按来源分级（对齐 `source.schema.json` 的 `authority_level`）决定哪些来源可进入候选；
3. **查多少**：轮次、数量与饱和规则，避免检索不足或检索冗余。

检索的产出是 `sources.jsonl` 中状态为 `DISCOVERED` 的来源条目。**检索结果与摘要只是线索，
不是证据内容**（RULE 2）；只有通过 Fetch（步骤 3）与 Validate（步骤 4，见
source-validity.md）后才能进入 Evidence Extraction。

未经本协议规范检索的结论一律视为"证据链不完整"，不得进入 Tribunal。

## 2. 查询构造（教育 PICO 式转化）

### 2.1 从 Frame 提取三要素

每个查询必须覆盖 干预（Intervention）× 学习者（Population）× 结果（Outcome）三要素。
缺失任一要素的查询视为无效查询，不得执行。

| 要素 | 来源字段（education-framing.md） | 示例 |
| --- | --- | --- |
| 干预 I | `intervention.ai_tool` + `allowed_usage` | `GitHub Copilot`、`AI code completion`、`"代码补全"` |
| 学习者 P | `learner.education_level` + `major` + `prior_knowledge` | `undergraduate introductory programming`、`大一 编程入门` |
| 结果 O | `outcomes.primary` + `risk` | `independent problem solving`、`learning`、`transfer` |

### 2.2 查询词族规则

- 每个要素生成 2–3 个同义/近义表达（如 `AI assistant` / `AI code completion` / `LLM-based tutor`），
  组合成词族；词族间必须实际执行，禁止只跑一个代表性查询后"脑补"其余结果。
- AI 工具结论必须限定到**工具类型或版本**：`complete code generation` 与
  `code completion` 与 `explain errors only` 是三个不同的干预（冲突来源分类
  `tool`，见 tribunal-policy.md），不得混用一个查询。
- 语言覆盖：**中文查询与英文查询必须各至少 1 个**。国内高校场景的证据（如
  中文期刊、国内试点报告）只有中文检索才能发现；applicability-policy.md 要求
  地域标注，检索端必须提供两类地域的候选。
- 每个查询记录到来源条目的 `discovered_by` / `discovery_provider`，并保存查询串，
  保证可复现。

### 2.3 反方证据查询独立构造

正面证据与反方证据的查询**必须独立构造、独立执行**（RULE 4）。禁止把正面检索的
同一批结果"翻面"充当反方证据。反方查询模式见第 5 节。

## 3. 来源分级与可接受性

来源分级直接使用 `source.schema.json` 的 `authority_level` 枚举（Tier 1–5），
本协议不另设分级。**fetch provider 不能提升此值**——抓取渠道只改变读取路径，
不改变来源权威级别。

| 级别 | 含义 | 示例 | 可作 SUPPORTED 证据？ |
| --- | --- | --- | --- |
| `tier1_paper_doi` | 有 DOI 的同行评审论文（期刊/会议） | ACM/IEEE/Elsevier 论文 | ✅ 是 |
| `tier2_academic_database` | 学术数据库/预印本/机构知识库条目（无 DOI 但有稳定标识） | arXiv、SSRN、大学学位论文库 | ✅ 是（按 source-validity.md 预印本规则） |
| `tier3_professional_institution` | 专业机构报告与页面 | 大学教学中心、教育部、ACM/IEEE 官方综述 | ⚠️ 可作为背景与上下文，不作独立因果证据 |
| `tier4_news_secondary` | 新闻与二手来源 | 媒体报道、他人转述的研究解读 | ❌ 仅线索 |
| `tier5_general_web` | 一般网页 | 博客、无署名页面、厂商页面 | ❌ 仅线索；厂商声明禁止作证据 |

### 分级判定规则

| 编号 | 内容 |
| --- | --- |
| RP-01 | 每条候选来源必须标注 `authority_level`，禁止省略；无法判定时标 `tier5_general_web` 并说明。 |
| RP-02 | `tier4` / `tier5` 来源只能进入"线索池"，不得直接成为 Evidence 的绑定来源；如其中确有可核实的研究发现，必须回溯到其引用的原始 `tier1`/`tier2` 来源。 |
| RP-03 | 厂商/行业声明（如 Copilot 官方博客、AI 产品宣传页）**一律不得**作为独立证据，即使域名是 `.edu` / `.gov`（需核查内容是否厂商资助）。 |
| RP-04 | 无法回溯到原始来源的二手转述，不得进入 Evidence Matrix。 |

## 4. 检索轮次与饱和规则

### 4.1 最小轮次

| 轮次 | 内容 | 最小查询数 |
| --- | --- | --- |
| 第 1 轮 | 主体检索：按 2.2 词族执行正面证据检索 | 3–5 个查询 |
| 第 2 轮 | 反方检索：按第 5 节执行独立反方证据检索 | 3–5 个查询 |
| 第 3 轮（如需要） | 补漏检索：针对证据冲突、样本不匹配或 Frame 的 inclusion_criteria 定向补充 | 按缺口定 |

### 4.2 饱和与停止

- **饱和规则**：连续 3 个不同查询未发现任何新来源（去重后），视为达到检索饱和，可停止。
- **数量下限**：进入 Tribunal 前，独立研究/独立样本数量必须满足
  Pre-Verdict Gate 的 `Independent study/sample count checked` 项；不足时
  标注 `INSUFFICIENT_SOURCES`（见 SKILL.md 第 15 章），禁止强行裁决。
- **正反比例**：反方证据检索结果即使为零，也必须如实输出
  `NO CONTRADICTORY EVIDENCE FOUND`（skeptic-protocol.md SK-06），不得以"查过了没有"的模糊表述代替。

### 4.3 范围控制

- 检索范围由 Frame 的 `scope`（time_range / geography / study_types）与
  `inclusion_criteria` / `exclusion_criteria` 控制（education-framing.md）。
- 超出 `scope.time_range` 的经典研究可以保留作背景，但结论时效性按
  evidence-quality.md 的 D4/D5 评分，不得因"经典"而豁免。
- 检索结果命中排除标准（如样本为研究生、干预不足 2 周）的，直接排除并记录排除原因，
  不进入 Fetch。

## 5. 反方证据检索战术（RULE 4 执行细则）

Skeptic 的 9 项固定任务（skeptic-protocol.md）需要对应的独立查询模式。每项任务
至少执行一个针对性查询，查询方向与正面检索相反或正交：

| 任务 | 检索目标 | 查询模式示例 |
| --- | --- | --- |
| S-01 null result | 无显著差异研究 | `"no significant difference" AI coding assistant`；`copilot exam performance equivalent` |
| S-02 negative result | 效果更差的研究 | `AI code generation harms learning`；`ChatGPT 编程 能力下降` |
| S-03 相反方向 | 结论相反的研究 | `banning AI improves outcomes`；`限制 AI 使用 更好` |
| S-04 alternative explanation | 替代解释证据 | `practice time confound AI study`；`novelty effect AI education` |
| S-05 measurement mismatch | 测量错配案例 | `satisfaction measured as learning AI`（用于识别把 C2/C3 当 C1 的常见做法） |
| S-06 sampling bias | 自选/高动机样本 | `self-selection AI course study`；`volunteer bias` |
| S-07 novelty effect | 新奇效应衰减 | `novelty effect longitudinal AI tutor`；`long-term AI education study` |
| S-08 AI dependency | 撤除 AI 后表现 | `performance drop without AI`；`AI dependency students`；`withdrawal AI assessment` |
| S-09 超出范围 | 边界外推证据 | 针对目标 Frame 的特定维度组合检索（如 MOOC 场景、无教师支持场景） |

反方证据同样必须通过 Fetch + Validate + 方法学审查（methodology-audit.md）
后才能纳入裁判（skeptic-protocol.md SK-05）。检索到的反方候选若质量低于
`weak`（evidence-quality.md），按 SK-04 只保留最高质量 2 条。

## 6. 检索记录要求

| 字段（source.schema.json） | 要求 |
| --- | --- |
| `source_id` | 稳定命名，如 `S-2025-<firstauthor>` |
| `title` / `authors` / `year` / `doi` | 完整填写；DOI 缺失时标注"未找到 DOI" |
| `canonical_url` | 原始来源的规范 URL；抓取渠道 URL 不得冒充 |
| `authority_level` | 按第 3 节判定 |
| `discovered_by` / `discovery_provider` | 检索渠道与提供方 |
| `query`（扩展字段） | 命中该来源的查询串，保证可复现 |
| `status` | 初始为 `DISCOVERED`，后续按 source-validity.md 流转 |

## 7. 执行规则（必须遵守）

| 编号 | 内容 |
| --- | --- |
| RP-05 | 检索未执行（跳过 Retrieve 直接回答）即违反 RULE 1，流程无效。 |
| RP-06 | 三要素（I × P × O）任一缺失的查询不得执行。 |
| RP-07 | 中英双语各至少 1 个查询；仅单语检索视为检索不完整。 |
| RP-08 | 反方证据必须独立查询，禁止复用正面结果充当反方。 |
| RP-09 | snippet 与摘要不得直接作为证据内容（RULE 2）；检索阶段产物只能是线索。 |
| RP-10 | 厂商声明与二手转述不得作为独立证据（RP-03 / RP-04）。 |
| RP-11 | 达到饱和规则或数量下限后仍不足的，如实输出 `INSUFFICIENT_SOURCES`，禁止降低纳入标准凑数。 |
