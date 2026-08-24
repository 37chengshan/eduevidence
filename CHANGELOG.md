# Changelog

所有显著变更均记录于此。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)；版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。


## [5.2.0] — 2026-08-24

> 可信度修复版：示例 provenance 纠偏 + 版本/口径单一权威（依据 docs/plans/v5.2-v6.0-iteration-plan.md）。

### 版本治理
- `engine/versions.py` 成为唯一版本权威；`engine/__init__.py` 的死值 2.0.0 改为 re-export。
- 新增 `scripts/check_version_consistency.py` 并纳入 CI：versions.py ↔ pyproject ↔ CHANGELOG 头条目 ↔ SKILL.md 标题一致性校验。

### 示例 provenance 纠偏（随本版后续提交补充）


## [5.1.1] — 2026-08-23

> 排版修复 + 五主题布局约束门（含手机端）。

### Judge（presentation）主题排版问题排查与修复
- 根因一（移动端/平板横向裁切）：`:root[data-theme="X"]`（特异性 0,2,0）压过基座
  `@media (max-width:980px)`（0,1,0）——presentation 的 `full-report-layout` 在 390px 仍为
  `230px 104px` 两列，内容列被挤到 104px；datalab/dark/presentation 的 `outcome-groups`
  `repeat(auto-fit,minmax(240px,1fr))` 内在尺寸爆炸，768px 平板第二列结果消失在视口外
  （shell scrollWidth 1025 > 768）。
- 修复范式：基座断点改 `minmax(0,1fr)` + 网格 item `min-width:0` 安全网；全部 5 主题
  `auto-fit` 轨道改 `minmax(min(Npx,100%),1fr)`；三主题 `report-page-brief`/`full-report-layout`
  自带 `@media ≤980` 覆写（同主题文件内，等特异性后声明生效）；`scope-grid`/`method-audit-grid`
  同样处理。
- 结果：18 份报告（3 示例 × 5 主题 + 3 主报告 + 13 篇示例）× 390/768/1280 × brief/full
  浏览器实测 114 项全部无溢出、无裁切。

### 展开动画「只有点击才触发」体验修复
- 根因：首屏卡片在页面加载瞬间即播完动画（用户未看到），滚动中又常被错过，感知为
  "只有点击才动"。`motion.js` 新增入场错峰：页面加载 1.5s 内命中的卡片按
  `140ms + (index%6)*130ms` 逐个播放入场（draw-in 可见）；滚动进入与点击重播立即执行；
  `prefers-reduced-motion`/无 JS 仍然静态可见。

### 五主题排版约束机制（skill + 脚本 + 测试）
- 新建 `scripts/lint_report_layout.py`：静态不变量审计（裸 1fr 轨道、无移动端覆写的双列
  grid、固定 px 最小值 auto-fit 均为违规）+ 可选浏览器级门（调 `check_mobile_layout.js`）。
- 新建 `visualization/eduevidence-report/scripts/check_mobile_layout.js`：零依赖 Node CDP
  实测（390/768/1280 × brief/full）：页面无横向溢出、可见 shell 无裁切、逃逸元素排除
  滚动容器/SVG 内部、画廊 reveal 契约（滚入全部 is-live）。
- 新建 `tests/test_report_layout_mobile.py`：静态门必跑；浏览器级门在有 Chrome+Node 时跑，
  否则 skip；reveal 契约静态断言。
- 文档：新增 `visualization/eduevidence-report/references/layout-constraints.md`（守则 + 教训 +
  验收清单）；`component-catalog.md` §10/§11 与 `report-generation` sub-skill §2.4 引用守则。

## [5.1.0] — 2026-08-22

> Present 层大改造：**AI 自由组合 Lieflat 图表 + 5 套主题文案排版优化（含展开动画）**。

### 数据驱动 Lieflat 画廊（AI 自由组合）
- 新增 `visualization/eduevidence-report/scripts/charts_data.py`：16 个提取器（meta.forest / evidence.ranked_effects / year_x_dimension / grouped_distribution / multidim_top / study_type & wwc_composition / outcomes.direction_counts & paired_counts & bipolar_axes / intervention.phase_weeks & activity_weights & phase_groups / decision.confidence_score / methodology.flag_rates / year_x_outcome_counts），数据不足返回 None + reason（镜像 Meaningful Visualization Gate），不编造单位。
- 重构 `lieflat_engine.py`：REGISTRY（17 个 type ↔ 目录编号 ↔ 提取器 ↔ 渲染器）+ `render_figure` 调度器，未知 type 显式报错；**删除全部硬编码演示数据与 SVG 内嵌 `<style>`**，改为 `lf-pop/lf-fade/lf-draw` 类 + `--motion-delay`（点阵 12ms / 条形 100ms）；SVG 最小字号 6.5px、数值 800、面积 sqrt。
- `build_figures.py`：学术图保持不变；Lieflat 部分只渲染 `resolve_visual_layout` 校验通过的条目，键用条目 chart_id。
- `build_report.py`：新增 `resolve_visual_layout`（新契约 `{chart_id, type, catalog_ref, title_zh/en, subtitle_zh/en, caption_zh/en, source, params}`；兼容旧 title/subtitle 双语共用并告警；未注册/缺双语/参数非法 → 丢弃 + 原因入 report_spec；全无效 → 确定性安全组合 forest + dot_cascade + bubble_almanac + tick_rows）；完整性门新增 `lieflat_data_bound`（渲染值逐一比对提取器 bundle）；`render_lieflat_gallery_brief` 重写（四件套卡片 + `data-lieflat`/`data-visual` + 图注 + 抑制清单）；`report_spec.json` 增加 `lieflat_gallery`。
- 新增 `schemas/visual-layout.schema.json`（目录原为空，正放新契约）。

### 展开动画对齐 skill 正本（图表 SVG 为主）
- `motion/motion.css`：新增 `data-lieflat` 区块——`.js-lf` 门控的 `lf-pop`（scale 0→1，cubic-bezier(.2,.7,.3,1.3)，500ms）/ `lf-fade`（900ms ease）/ `lf-draw`（dasharray 1，1s cubic-bezier(.4,0,.2,1)），`--motion-delay` stagger，reduced-motion 与 print 全关，无 JS 静态可见。
- `motion/motion.js`：`[data-lieflat]` 实现 mono-tokens `obsReveal` 语义——IntersectionObserver（threshold .3）滚入播放一次；点击重播（先清该 id 已登记 timer，防叠加）；`CSS.escape` 安全。
- `references/motion-system.md`：`chart-reveal` 写为固定模板角色，五主题不得另造动画逻辑。

### 5 套主题文案排版优化（设计个性全部保留）
- 文案：表头 meta 行规范为「模式：… · 生成时间：… · 证据 N 条 · 来源 N 个」（英文对应）；润色 `full_report_intro`、12 条 section leads、brief 各块 lead、`benchmark_note`；图表文案规范（标题写结论、副标题说清图例单位、来源行全大写）。
- 排版：中文优先字体栈（PingFang SC / Noto Sans CJK，academic 保留 Songti 衬线）；中文正文不加 letter-spacing；数字 `tabular-nums`；claude 标题 500 字重与 measure 收窄；academic 打印 8.5pt；datalab/datalab-dark 4 列 brief 网格 + 章头双栏 + 控件尺寸统一（暗版对比度 ≥4.5:1 复核）；presentation 裁决字号阶梯 + insight 内边距 + 金橙对比度复核。

### 夹具、测试与交付
- 修复 `examples/ai-coding-assistant` 夹具（决策叙述中的 E-xxx 引用 / null 残留 / overall_risk schema 键 → 语言门禁 0 问题）；三个示例项目 `visual_layout` 升级为新双语契约（50 篇示例展示 L20/G15/L14/F11/L15/L16 六种轮廓组合）。
- 新增 `tests/test_lieflat_composition.py`（提取器溯源、注册表拒绝、抑制、无演示值、schema、数据溯源门）；`test_build_report_html.py` 增补画廊卡片 / motion 定义唯一 / reveal 契约 / footer / meta 行；`test_build_figures.py` 按 layout 渲染。
- 全量 pytest 与 `skill_lint.py` 全绿；`rebake_all_5themes.py` 重烘焙 3 示例 × 5 主题（15 份，integrity 全 PASS）。

### 文档
- `skill/sub-skills/report-generation/SKILL.md` §2 重写为六步组合工作流；新增 `references/lieflat-composition.md`（注册表 + 契约 + 推荐组合 + 抑制规则）；更新 `component-catalog.md` / `full-report-outline.md` / 根 `SKILL.md` Present 行 / `docs/architecture.md` Present 管线。

## [5.0.0] — 2026-08-21

> v5 大迭代旗舰版（`ENGINE_VERSION = "5.0.0"`）。主题：**「SSOT 证据图谱 × 杀手级实证闭环 × Claude 本地控制台」**。

### 统一 SSOT 证据图谱引擎 (`engine/evidence_graph.py`)
- **7 大统一实体节点模型**：`PaperNode` (文献)、`EvidenceNode` (量化效应量 Hedges' g、WWC 5.0 评级)、`OutcomeNode` (5维社科分类)、`ClaimNode` (科学主张)、`RiskNode` (方法学陷阱)、`GapNode` (学术空白)、`DecisionNode` (四态裁决快照)
- **消除数据孤岛**：所有下游消费端（Tribunal 仲裁、HTML 报告、Web 控制台、GapLens）统一读取此 SSOT 图模型
- **ECharts 力导向图导出**：支持可视化拓扑导出与交互式路径追踪

### 50 篇真实学术文献杀手级 Demo (`examples/ai-coding-assistant-50/`)
- **核心命题**：“高校大一程序设计课程引入 AI 编程助手是否真正提升计算思维与独立编程能力？”
- **揭示社科核心悖论**：任务完成速度提升 $+0.64g$ vs 撤除 AI 后的独立闭卷期末考迁移赤字 $-0.28g$
- **WWC 5.0 脚手架依赖陷阱检测**：自动触发认知陷阱告警，裁决为 `PILOT` (限制性试点)
- **12周准实验因果闭环**：自动生成 12 周 DID 准实验设计，支持课堂 CSV 数据回注因果回归

### Claude 风格本地控制台 (`scripts/dashboard_server.py`)
- **浅色极简美学**：暖白底色 `#FAF9F6`、1px hairline 边框、`Instrument Serif` 衬线字体、呼吸感负空间
- **实时事件流 (SSE)**：基于 `engine/events.py` 的 EventBus 内存总线实时推送 9 阶段执行日志
- **Token 消耗与多模型成本矩阵**：实时比对 DeepSeek-V3/R1、Minimax 2.7、Claude 3.5 Sonnet 与 GPT-4o 成本
- **混合多渠道检索诊断台**：支持 4 大免配置学术渠道与 AIHot 动态趋势渠道实时测试

### 出版级 HTML 报告与图表重构
- **出版级效应量森林图 (Forest Plot SVG)**：直观展现速度提升 vs 迁移赤字的尖锐分歧
- **100% 数据一致性门控**：所有动态聚合与图表通过严苛校验，生成单文件 618KB 离线可用报告
- **三层白话信息架构**：一页白话结论 (30秒) ➔ 可视化概要 (3分钟) ➔ 完整证据档案 (可折叠)

### 外部 Skill 深度集成与安全补强
- **`skills/aihot-trend-analysis/`**：集成 AIHot 实时 AI/EdTech 技术趋势雷达
- **`skills/gap-analysis/`**：集成 BioGapLens 空白与矛盾透镜
- **`skills/ethics-review/`**：引入人类受试者与 IRB 研究伦理审查
- **`retrieval/corpus_store.py`**：内置 5 领域离线语料库，保障 100% 离线演示容灾
- **测试矩阵**：补齐 `tests/test_search.py`，全量 703 个 pytest 用例 100% 零错误通过

## [4.0.0] — 2026-08-14

> v4 正式版（`ENGINE_VERSION = "4.0.0"`）。主题：**「科艺融合 × 通用智能」——从教育证据引擎到社科证据决策平台**。

### EvidenceCore 领域泛化
- `domains/` 领域注册表：`eduevidence domain list|select|check`；education 为注册域（零新增逻辑路径，v3 行为不变）；policy 为 v4 首个自带契约域（decision_object/intervention/population/stakeholders 政策框架、5 类政策结果、12 项政策证据质量清单、5 篇政策方法学参考）
- `engine/evidencecore.py`：`DECISION_STATES`/`PROTOCOL_STEPS` 领域无关常量、`load_domain`（JSON Pointer 契约引用校验）、`validate_frame`（按域校验）

### 证据综合层（Evidence Synthesis）
- `engine/meta_analysis.py`：效应量提取、固定效应（inverse-variance）与随机效应（DerSimonian-Laird，Q/τ²/I²）双口径合并、森林图数据
- `engine/bias.py`：Egger 回归（stdlib 手写 t 分布 p 值）、Rosenthal fail-safe N
- `engine/robustness.py`：leave-one-study-out → robust/fragile 标签

### Living Evidence（活证据）
- `eduevidence living subscribe|refresh|status`：决策快照订阅 → 新证据（人工注入或 retriever 适配器）内容 hash 幂等入图 → 漂移报告（confirmed/changed/needs_review），绝不自动改判

### 内置证据库 + 离线初步裁决
- `benchmarks/evidence-library.json`（230 条：金标 209 + 示例 21）：`preliminary_verdict` 保守裁决（从不 adopt），无检索能力时可用

### LLM Judge 评估
- `eduevidence benchmark-judge run|report`：5 维 rubric（citation/outcome/scope/contradiction/decision）评审实证响应，与 heuristic 并列对照，披露同族模型独立性限制

### CI 与工程
- GitHub Actions 三作业并行：测试矩阵（3.10/3.12 + 重试）、schema-smoke（示例全量过契约）、upload 构建（SKILL.md 一致性 + 零泄漏 canary）
- 测试 612 → 681（69 个 v4 用例），education 域零回归
## [3.0.0] — 2026-08-14

> v3 正式版（`engine/versions.py` → `ENGINE_VERSION = "3.0.0"`）。v3 三大方向：**可信度收口**（每个结论收紧到可追溯、可反驳、可审计）、**实证 Benchmark**（Layer B 真实模型运行）、**闭环能力**（PILOT → 真实数据 → 再裁决）。

### 可信度收口（Credibility Tightening）

- **Evidence Matrix 三列化（P1-1）**：支持 / 反驳 / 中性证据分列呈现，混合列不再被静默统计（`77db8b5`、`303054e`）。
- **Pre-Verdict Gate 严格化（OPEN-1）**：`uncertain_claims` 必须绑定证据（`evidence_ids`），无绑定即校验失败（`77db8b5`）。
- **outcome_mapping 报告（OPEN-2）**：决策输出新增 outcome 映射报告，学习效果与任务表现显式区分（`77db8b5`）。
- **角色 prompt schema 契约（OPEN-4）**：八角色 prompt 内嵌 schema 契约与枚举值表，输出即契约（`352015a`）。
- **agent MCP 三态（OPEN-5）**：MCP 可用性三态检测，`install` 自动写入 env（`a735cf6`）。
- **检索层回归测试补强（P0-1）**：检索 / 校验层回归测试补强，并修复 dedupe stale-index 合并（`de741d0`）。
- **Source fallback 诚实化（P1-2）**：真实 DOI 解析判 tier1，否则 tier5 + incomplete，杜绝编造 canonical URL（`985239e`）。
- **fetch 基准站点标题无害化**：中文站点标题英文化 + 分类泛化（`d7f068b`）。

### 实证 Benchmark（Empirical Benchmark，Layer B）

- **benchmark_v3 harness**：真实模型调用 + run manifest 契约（`schemas/v3/run-manifest.schema.json`），SIMULATED 与 EMPIRICAL 严格区分（`26a1d1b`）。
- **gold-based evaluator**：对照 `benchmarks/annotations/gold-*.json` 计算六项指标，每条标注 `method: heuristic`，均值按 95% CI 报告（`26a1d1b`）。
- **30 金标补齐**：Q11–Q30 金标标注 + 一致性校验测试（`fced61c`）。
- **CliDriver(omp)**：`omp` CLI 执行后端（`--driver cli`），实证运行落地 `benchmarks/empirical/run-empirical-01`（`503abca`）。

### 闭环能力（Phase 2）

- **Decision-to-Outcome Loop（pilot）**：PILOT 试点结果回填 → redecide → 再裁决（`715fae7`）。
- **Multi-project library synthesis**：跨项目证据库综合 + `REPORT_CONTRACT_VERSION 3.0` + pilots 目录（`eb059fb`）。
- **CLI 新子命令**：`pilot` / `synthesize` / `benchmark`（`400b346`）。

### 交付与文档

- **HTML 报告可访问性与诚实性小修**（6.1–6.5，保持视觉风格）（`d54d23a`）。
- **文档统一**：Canonical Protocol 9 步（6+3）、Schema 13 个、方法论文档 11 篇、V2 contracts 17 个等数字口径修正（`5b0e886`、`907cd11`）。
- **版本基线**：`3.0.0`（`715fae7` 起 3.0.0-dev，`ee7ae79` 正式化）。
