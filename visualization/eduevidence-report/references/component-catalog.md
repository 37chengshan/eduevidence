# HTML Component Catalog（结果层冻结组件）

> LLM 可以规划章节和选择已有组件，但不能自由编写影响证据语义的 DOM / chart 逻辑。组件固定，章节组合动态。

## 1. Shell / 导航

| 组件 | 职责 |
|---|---|
| `ReportShell` | 单文件离线报告外壳 |
| `GeneratedThemeMarker` | 显示生成时选择的五种视觉系统之一 |
| `LanguageSwitcher` | 中文 / English 切换 |
| `PageSwitcher` | Visual Brief / Full Report 一级分页 |
| `FullReportReader` | 左 TOC + 右完整报告阅读器 |
| `CollapsibleTOC` | 读取动态 5–7 章 outline；sticky / active / collapse |
| `FullChapter` | AI 规划后的章节容器，只组合语义模块，不修改研究数据 |

## 2. 决策 / 摘要

| 组件 | 职责 |
|---|---|
| `DecisionHero` | Decision / Confidence / strongest claim / uncertainty / risk / action |
| `ConfidenceBadge` | High / Moderate / Low / Insufficient |
| `VisualBriefBlock` | 摘要页高价值模块容器；不是完整报告章节 |
| `KeySourceCards` | 摘要页只显示少量关键来源 |

## 3. Outcome / Visualization

| 组件 | 引擎 | 职责 |
|---|---|---|
| `OutcomeSeparation` | HTML/CSS | Task / Learning / Retention / Transfer / Risk 构念分离 |
| `EvidenceBalance` | SVG/ECharts | 基于 `effect_direction` 的正向/负向/零效应比较；只有 Gate 通过才渲染 |
| `LieflatGalleryCard` | 内联 SVG（charts_data + lieflat_engine） | AI 组合的数据驱动 Lieflat 图卡：结论式标题 + 副标题（图例 `·` 分隔）+ 主题化 SVG + 全大写来源行 + 可选图注；`data-lieflat` / `data-visual` 属性供 motion 与测试定位 |
| `LieflatSuppressed` | HTML | 数据不足时列出被抑制图型与原因（镜像 Meaningful Visualization Gate） |
| `InteractiveChart` | ECharts | 有信息增益的交互分析图 |
| `AcademicFigure` | Academic Figures | 出版级静态图（outcome-comparison / benchmark / forest，保持主题无关） |
| `InfographicBlock` | SVG / AntV | 流程、干预、评价等语义图 |
| `VisualizationSuppressed` | HTML | 数据不足时解释为什么不画图 |

Lieflat 图卡只渲染 `resolve_visual_layout` 校验通过的 `visual_layout` 条目；每个条目经注册表（`references/lieflat-composition.md`）提取器出数，未注册 type 显式报错。完整性门 `lieflat_data_bound` 逐值核对数值溯源。

## 4. Evidence / progressive disclosure

| 组件 | 职责 |
|---|---|
| `EvidenceMatrix` | 6 列主视图：Evidence ID / Outcome / Effect / Quality / Claim / Source |
| `EvidenceRow` | 单条 Evidence 摘要 |
| `ExpandableEvidence` | 展开 study/sample/design/intervention/comparison/effect/quality/source 等完整字段 |
| `QualityMeter` | 仅表达已有 quality_score |
| `SafeSourceLink` | 只允许 http / https 可点击 URL |

Outcome/Matrix 的主方向使用 `effect_direction`。`relation_to_claim` 只作为次级 Claim relation 显示。

## 5. Adjudication / methodology / trace

| 组件 | 职责 |
|---|---|
| `TribunalView` | Supported / Uncertain / Contradicted / Missing Evidence |
| `ExpandableTribunalClaim` | 长裁决文本和 Evidence IDs 渐进展开 |
| `MethodologyPanel` | compact status surface |
| `ExpandableMethodology` | 展开每项 methodology note |
| `ConflictCard` | 去重后的冲突/异质性解释 |
| `ClaimTrace` | Claim → Evidence → Outcome → Effect → Quality → Source |

## 6. Applicability / intervention / evaluation

| 组件 | 职责 |
|---|---|
| `ApplicabilityCard` | Suitable / not suitable / conditions / boundary |
| `EvidenceToAction` | Evidence → Applicability → Decision → Guardrails → Stop → Evaluation |
| `InterventionTimeline` | 教学试点阶段 |
| `EvaluationFlow` | Baseline → Post → Retention → Transfer |
| `StopConditionBlock` | 失败/停止条件 |

## 7. Sources / provenance

| 组件 | 职责 |
|---|---|
| `SourceList` | Source ID / original title / year / authority / location |
| `ExpandableSource` | canonical URL / source location / fetch metadata |
| `ProvenancePanel` | 只显示真实存在的 fetch metadata；空 fetch 不生成空表 |
| `Footnote` | 模式 / 版本 / integrity 状态 |

## 8. Motion Template

| 组件 | 职责 |
|---|---|
| `MotionTemplate` | 统一 section/stagger/bar/trace/flow/detail/page/toc 动画 |
| `ChartReveal` | `data-lieflat` 图卡的 mono-tokens reveal：滚入视野（threshold .3）播一次 + 点击重播（timer 清理）+ reduced-motion 降级 + 无 JS 静态可见 |

动画由 `motion/motion.css` + `motion/motion.js` 固化。五种主题不得创建不同的科学/数据动画逻辑，`chart-reveal` 为固定模板角色（见 `references/motion-system.md`）。

## 9. Dynamic Report Planner

AI 不创建新组件，而是把固定语义模块组合成 5–7 个章节：

```text
decision · scope · retrieval · outcomes · evidence · quality
conflicts · trace · applicability · intervention · evaluation · sources
```

规则：

1. 第一章包含 `decision`。
2. 最后一章包含 `sources`。
3. 全部模块覆盖且每个恰好一次。
4. AI 可以自由命名章节和合并中间模块。
5. Invalid outline → safe six-chapter fallback。

章节之外的**图表计划**由 AI 写入 `visual_layout`（每图一个独立结论、≤6 张、形状不重复），渲染器只执行注册表校验通过的条目；数值一律由提取器从 `result.json` 出数（`references/lieflat-composition.md`）。

## 10. 五种主题共用组件，不共用排版

同一组件在五种主题中可以改变：

- 宽度和列布局。
- 卡片/横线/面板策略。
- TOC 外观。
- Brief 模块网格。
- 表格密度。
- 标题尺度和章节节奏。

不能改变：

- Evidence / Claim / Verdict / Confidence。
- `effect_direction`。
- 数据数量。
- 页面功能与 Evidence 展开能力。
- Meaningful Visualization Gate。

**排版守则（硬性，见 `references/layout-constraints.md`）**：主题规则特殊性高于基座断点——
凡 ≥2 列含 px 最小值的 `grid-template-columns`，主题必须自带 `@media (max-width:980px)` 覆写；
轨道用 `minmax(0,1fr)` 或 `minmax(min(Npx,100%),1fr)`，禁止裸 `1fr` 与固定 px 最小值 auto-fit。
改动后跑 `scripts/lint_report_layout.py`（静态 + 浏览器级 390/768/1280 × brief/full）。

## 11. 自检

- [ ] 同一 result 生成五种主题，数据与章节内容覆盖完全一致。
- [ ] 五种主题的首屏、Brief 排版、TOC、正文宽度、章节 surface 明显不同。
- [ ] Visual Brief / Full Report 都可切换。
- [ ] 5–7 章 TOC 自动读取 outline。
- [ ] 无 JS 时核心研究内容仍存在于 HTML。
- [ ] 打印只输出完整报告并暴露 detail 内容。
- [ ] Outcome visual 使用 `effect_direction`，不是 Claim support。
- [ ] `lint_report_layout.py` PASS：五主题静态不变量 + 浏览器级（390/768/1280 × brief/full）无溢出、reveal 生效。
- [ ] 手机（390px）与平板（768px）实测：无横向滚动、无裁切、图表完整、点击重播动画正常。
