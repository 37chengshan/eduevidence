# 外部开源项目：最终定位与本地实施映射

> 本文档明确 EduEvidence 引用的每个外部开源项目的**定位**（运行依赖 / 可选增强 / 方法或设计参考）、**本地实施映射**（对应仓库中的具体文件与行为）与**开源许可**，并给出与本项目 MIT LICENSE 的兼容性结论。
>
> 原则：**哪些是运行依赖、哪些是可选增强、哪些只是方法/设计参考**，不夸大任何依赖关系。

## 分类口径

| 分类 | 含义 |
|---|---|
| 运行依赖 | 项目正常出结果所必需；缺失则流程中断或降级 |
| 可选增强 | 非必需；缺失时行为不中断（有本地 fallback） |
| 参考实现 / 风格借鉴 | 不调用、不打包、不复制上游代码；仅借鉴方法、设计或视觉风格 |

本项目核心设计：**零第三方运行时依赖**（`pyproject.toml` 的 `dev` 仅含 pytest；核心为 Python 3.10+ 标准库）。所有"增强层"均为可选，缺失时自动降级，行为不中断。

---

## 1. EduEvidence（本项目）

- **仓库**：`https://github.com/37chengshan/eduevidence`
- **定位**：主项目（Domain + EvidenceFlow + Contracts + Renderer）
- **许可**：MIT（`LICENSE`，Copyright (c) 2026 EduEvidence Contributors）
- **本地映射**：仓库本体；无外部依赖。

---

## 2. Agent MCP

- **上游**：`https://github.com/37chengshan/agent-mcp`
- **定位**：可选高级执行后端（Optional Advanced Execution Backend）——fast models collect / strong models reason / independent models verify。
- **用途**：多 CLI 派发、Cross-Model Review（独立模型交叉审核）、Memory Bank。
- **本地实施映射**：`integrations/agent_mcp.py`（含 `safe_spawn()`、`cross_model_review()`、`build_memory_store_call()` 等）。EduEvidence **只做「检测 → 调用 → fallback」**，不迁移上游的 queue / resume / steer / memory / verify / daemon / multi-CLI routing 实现（见 `docs/agent-mcp-enhanced-mode.md`）。Agent MCP 是**直接安装的外部工具**，从不随 EduEvidence 分发或复制。
- **降级契约**：未安装 / daemon 不可达 → `AGENT_MCP_UNAVAILABLE`，退化为 Platform Native Mode（单 Agent 串行执行 8 角色协议）；已安装但模型表未获用户确认 → `AGENT_MCP_APPROVAL_REQUIRED`，禁止 spawn。
- **许可**：上游仓库**未声明许可文件**（GitHub 无 LICENSE 元数据）。EduEvidence 不复制其任何代码、不将其代码打包进本仓库，仅通过已安装的 MCP daemon 接口调用 → **参考实现/直接调用，无代码复制**；不产生本项目的许可义务。
- **兼容性**：不影响 MIT 分发；使用前建议用户自行确认上游许可条款。

---

## 3. Smart Web Fetch（自身 fetch 层设计）

- **上游参考**：`https://github.com/Kim-Huang-JunKai/smart-web-fetch`（MIT，Copyright (c) 2026）
- **定位**：Fetch Reliability Reference / 可选工具。解决"URL 已找到、正文获取失败"，**不是 Search 的替代品**。
- **本地实施映射**（Skill 本地确定性层，随 `install.sh` 的 `SKILL_PAYLOAD` 分发 `retrieval/` 与 `integrations/`）：
  - `retrieval/fetch.py` —— 降级链 `builtin → jina_reader → defuddle（本地提取）→ markdown_new → raw_html → FETCH_FAILED`；每级尝试立即 Validate（captcha / 登录页 / 过短正文继续降级），记录 Fetch Provenance（`original_url` 保留、`resolved_url` 取真实跳转、provider 记录）。
  - `retrieval/validate.py` —— SSRF 防护：私有 / 回环 / 链路本地 / CGNAT / 保留段 / 本地主机名一律不得进入第三方清洗服务（URL 路径中的 DOI "10." 前缀不影响判定）。
  - `integrations/smart_web_fetch.py` —— 集成包装：私有 URL 只走本地 provider；公开 URL 才允许完整降级链；`fetch_summary()` 提供来源溯源摘要。
  - 已吸收上游思路：multi-provider fallback、validation、provenance、private-network protection（全部为自研实现，无代码复制）。
- **Search 与 Fetch 的边界（重要）**：EduEvidence 的 fetch 层是 **Skill 内的本地确定性层**；**Search 是宿主能力**（宿主 web_search / SCP `literature_search` / Scholar Provider，见 `SKILL.md` 第 7 章 Resource Discovery 能力路由）。Skill 不内置搜索引擎；`RULE 2` 规定 Search snippet 不得直接成为 SUPPORTED Evidence，必须经 Fetch + Validate 通过后方可进入证据抽取。
- **许可**：上游参考 MIT；本地实现为原创代码（MIT 本项目）→ 兼容，无冲突。

---

## 4. Jina AI Reader

- **上游**：`https://github.com/jina-ai/reader`
- **定位**：Web → clean LLM-readable content（第三方 HTTP 清洗服务，`https://r.jina.ai/<url>`）。
- **用途**：Smart Web Fetch 降级链的第 2 级（`jina_reader` provider）。
- **本地实施映射**：`retrieval/fetch.py` 的 `_fetch_jina_reader()` —— 仅构造前缀 URL 的 HTTP 包装调用；`validate.py` 将其列为 `WRAPPER_PROVIDERS`（包装类 provider，URL 重写是设计使然，不参与 resolved-vs-original 严格比对）；私有 URL 被 SSRF 防护拦截，绝不发送到该服务。
- **许可**：**Apache-2.0**（LICENSE：Copyright 2020-2024 Jina AI Limited）。EduEvidence 只做 HTTP 服务调用，不包含、不复制其代码 → 兼容。
- **兼容性**：MIT 项目调用 Apache-2.0 服务/API 不产生再分发义务。

---

## 5. Defuddle

- **上游**：`https://github.com/kepano/defuddle`
- **定位**：local main-content extraction（HTML → 去 navigation/sidebar/script → 正文）。
- **用途**：文档承诺的 fallback 能力——`retrieval/fetch.py` 降级链第 3 级 `defuddle` provider。
- **本地实施映射**：`retrieval/fetch.py` 的 `_MainTextExtractor` / `extract_main_text()` —— **自研的 stdlib `html.parser` 实现**（跳过 script/style/nav/header/footer/aside，优先 `<main>/<article>` 正文，失败回退全页清洗），**不调用 Defuddle 库、不复制其代码**；仅沿用其"本地主内容提取"方法与命名。本地 provider，私有 URL 可安全使用。
- **许可**：上游 **MIT**（Copyright (c) 2025 Steph Ango）。本地实现为原创代码 → 兼容，无冲突。

---

## 6. Microsoft MarkItDown

- **上游**：`https://github.com/microsoft/markitdown`
- **定位**：File ingestion reference——PDF / DOCX / PPTX / XLSX → Markdown。**不要拿它替代网页搜索**。
- **用途**：文档承诺的 fallback 能力（本地文件/文档摄入方向的设计参考）；**不是**网页 fetch 链的组成部分（网页降级链中的 `markdown_new` 是 `https://markdown.new/` 第三方网页清洗服务，与 MarkItDown 无关）。
- **本地实施映射**：当前仓库**未打包、未调用** MarkItDown；仅在文档中作为文件摄入能力的方向性参考（`fetch-result.schema.json` / `source.schema.json` 的 `fetch_provider` 枚举预留 `pdf_parser`，供未来文档摄入扩展）。→ **参考实现，无代码复制，非运行依赖**。
- **许可**：上游 **MIT**（Copyright (c) Microsoft Corporation）→ 兼容，无冲突。

---

## 7. Apache ECharts

- **上游**：`https://github.com/apache/echarts`
- **定位**：可选交互可视化增强（Interactive Visualization Enhancement）。
- **用途**：结果概览（diverging bar）/ 主张-证据追溯（graph）/ 基准面板（composite）的交互分析。
- **本地实施映射**：
  - `visualization/eduevidence-report/scripts/build_charts.py` → `chart_specs.json`（ECharts option 格式的 spec，**只是数据规格，不含 ECharts 代码**）。
  - `build_report.py` 生成单文件 HTML：内置 `mountChart()` 增强器，**仅当 `window.echarts` 存在时才挂载图表**；无 JS / 无 ECharts 时静态 HTML/SVG 内容完整可读（静态优先设计，空容器不占位）。
  - `--vendor-echarts <本地 echarts.min.js>` 为可选内联参数，由用户自备本地副本。
- **许可**：**Apache-2.0**。EduEvidence 不打包、不复制 ECharts 代码；生成的 spec 为原创数据 → 兼容，无冲突。

---

## 8. AntV Infographic

- **上游**：`https://github.com/antvis/Infographic`
- **定位**：风格参考（Style Reference）——EvidenceFlow / Tribunal / Intervention / Evaluation 四张信息图的可选视觉方向。
- **本地实施映射**：`visualization/eduevidence-report/scripts/build_infographics.py` → `infographics.json` —— **确定性 AntV 风格 SVG**（纯 Python + 手写 SVG 模板，**不调用 AntV runtime、不包含 AntV 代码**）。项目内已实现确定性的本地 SVG 信息图；AntV 仅作视觉风格参考。
- **许可**：上游 **MIT**（Copyright (c) 2025 AntV）→ 兼容，无冲突。

---

## 9. Academic Figures Skill（可选参考）

- **上游**：SkillHub `https://skillhub.cn/skills/academic-figures` / ClawHub `https://clawhub.ai/docsor1212/academic-figures`
- **定位**：Optional Publication Figure Enhancement（出版级学术图的可选增强）。
- **本地实施映射**：`visualization/eduevidence-report/scripts/build_figures.py` —— 纯 Python / matplotlib 的 **deterministic publication fallback**（SVG 为纯标准库；PNG/PDF 导出在 matplotlib 可用时可选）。**不是** "build_figures.py 就是 academic-figures"；正确表述为：内置出版图渲染器 + 可选 academic-figures 增强。
- **许可**：SkillHub/ClawHub 分发渠道未提供可验证的仓库 LICENSE → **参考实现/风格借鉴，无代码复制**；不影响 MIT 分发。

---

## 10. UI/UX Pro Max Skill（可选参考）

- **上游**：`https://github.com/nextlevelbuilder/ui-ux-pro-max-skill`
- **定位**：Development-time UI/UX QA（设计系统 / 响应式 / 排版 / 无障碍 / 最终 UX 审计）——**不是最终运行时依赖**。
- **本地实施映射**：无运行时集成；仅开发/审查阶段用于 UI 质量检查。
- **许可**：上游 **MIT**（Copyright (c) 2024 Next Level Builder）→ 兼容，无冲突。

---

## 11. SCP（Scientific Skill 生态对齐，可选参考）

- **上游**：`https://github.com/InternScience/scp`
- **定位**：Scientific Skill / SCP ecosystem 对齐（`SKILL.md` 第 5.4 节：按 capability 动态发现科学资源，如 literature_search / web_fetch / pdf_extraction / citation_validation 等）。
- **本地实施映射**：能力路由设计参考（`SKILL.md` 第 7 章 Resource Discovery：按 capability 动态发现科学资源，如 literature_search / web_fetch / pdf_extraction / citation_validation 等）；SCP 可用则动态发现，不可用则 fallback 到本地 `references/` + 原生工具（Native Search / Smart Web Fetch / 本地解析器）。**不硬编码资源清单**；与 Agent MCP 正交（SCP 选"用什么能力"，Agent MCP 选"由谁执行"）。
- **许可**：上游 **MIT** → 兼容，无冲突。

---

## 许可检查结论

### 本项目许可

- **MIT License**（`LICENSE`，Copyright (c) 2026 EduEvidence Contributors）——宽松许可，允许使用、复制、修改、分发（含商用），需保留版权与许可声明。

### 引用项目许可汇总

| 项目 | 定位 | 许可 | 代码复制？ |
|---|---|---|---|
| Agent MCP | 可选执行后端（直接安装调用） | **未声明** | 否（仅调用 MCP daemon） |
| Smart Web Fetch | Fetch 可靠性参考 | MIT | 否（自研实现） |
| Jina AI Reader | 网页清洗服务（HTTP 调用） | Apache-2.0 | 否（仅服务调用） |
| Defuddle | 本地正文提取方法参考 | MIT | 否（自研 stdlib 实现） |
| Microsoft MarkItDown | 文件摄入方向参考 | MIT | 否 |
| Apache ECharts | 可选交互可视化 | Apache-2.0 | 否（仅生成 option spec） |
| AntV Infographic | 信息图风格参考 | MIT | 否（手写 SVG） |
| Academic Figures Skill | 出版图可选增强参考 | 未声明（渠道分发） | 否 |
| UI/UX Pro Max Skill | 开发期 UI/UX QA | MIT | 否 |
| SCP | 科学能力层对齐 | MIT | 否 |

### 兼容性结论

1. **MIT ↔ MIT**：本项目（MIT）与 Smart Web Fetch、Defuddle、MarkItDown、AntV、UI/UX Pro Max、SCP（均为 MIT）直接兼容。
2. **MIT ↔ Apache-2.0**：Jina AI Reader、Apache ECharts 为 Apache-2.0。Apache-2.0 与 MIT 均为宽松许可且相互兼容；本项目**不包含、不复制、不修改再分发**上游代码（仅 HTTP 服务调用 / 生成数据规格），不触发 Apache-2.0 的再分发义务。
3. **未声明许可项目**（Agent MCP、Academic Figures Skill）：本项目**无代码复制**（仅接口调用 / 方法参考 / 风格借鉴），不纳入再分发范围，故不产生许可义务；已在对应条目标注"参考实现/风格借鉴，无代码复制"。用户若直接使用 Agent MCP 上游工具，请自行确认其许可条款。
4. **结论：无许可冲突。** 本项目 MIT LICENSE 与所有引用的开源项目许可兼容，可安全开源分发。
