# HTML Component Catalog（冻结版）

> 固定组件，不让 LLM 自由创建 DOM 结构（v5 方案 §36 / §10）。Report Spec 只能使用以下组件。避免：每次报告形态漂移、LLM 写坏 HTML、无意义组件、视觉风格漂移、可访问性失控、数据展示错误。

## 一、组件清单（22 个，冻结）

### Shell / 导航

| 组件 | 职责 | 实现 |
|---|---|---|
| `ReportShell` | 报告外壳：header / 内容 / footer，响应式容器 | HTML/CSS |
| `ThemeSwitcher` | 五主题切换（claude/academic/editorial/datalab/presentation）+ localStorage 持久化 | CSS variables + `data-theme` + Vanilla JS |
| `SectionNav` | 章节导航（桌面 sticky sidebar / 平板 top tabs） | HTML/CSS |

### 决策

| 组件 | 职责 |
|---|---|
| `DecisionCard` | 四态决策卡（ADOPT/PILOT/REJECT/INSUFFICIENT EVIDENCE），颜色编码 |
| `ConfidenceBadge` | High/Moderate/Low/Insufficient 徽标 |
| `OutcomeSummary` | Outcome Evidence Overview（Diverging Evidence Bar，方向/强度/不确定性） |

### 图表

| 组件 | 引擎 | 职责 |
|---|---|---|
| `InteractiveChart` | ECharts | 交互分析图（矩阵/趋势/分布） |
| `AcademicFigure` | Academic Figures | 出版级统计图（SVG/PNG/PDF，Okabe-Ito/Nature/Conservative） |
| `InfographicBlock` | AntV Infographic | 研究流程/裁决/干预/评价信息图（SVG） |

### 证据

| 组件 | 职责 |
|---|---|
| `EvidenceMatrix` | 主证据界面：Study/Population/Intervention/Outcome/Direction/Quality/Directness/Claim/Source + Filter/Search/Sort/Expand |
| `EvidenceRow` | 矩阵单行（可展开显示细节） |

### 裁决

| 组件 | 职责 |
|---|---|
| `TribunalView` | CAN CLAIM / CANNOT CLAIM / WHY 三段式 + Decision/Confidence/Missing Evidence |
| `MethodologyPanel` | small multiples + warning cards（5 维：Study Design/Sample/Measurement/Temporal/Directness） |
| `ConflictCard` | 冲突分析：正反证据冲突来源（样本/测量/课程/工具/设计） |
| `ClaimTrace` | ECharts Graph：Decision→Claim→Evidence→Source（点击穿透） |

### 行动

| 组件 | 职责 |
|---|---|
| `ApplicabilityCard` | For whom / which course / which outcome / conditions |
| `InterventionTimeline` | 纯 HTML/CSS Timeline（每步 Goal/AI Rule/Teacher/Student/Exit） |
| `EvaluationFlow` | Inline SVG：Baseline→Treatment/Control→Post→Retention→Transfer |

### 数据与溯源

| 组件 | 职责 |
|---|---|
| `BenchmarkPanel` | 四图：Citation Support / Unsupported Rate / Contradiction / Quality vs Cost |
| `SourceList` | 来源表（含 authority_level / canonical_url / source_location） |
| `ProvenancePanel` | Fetch Provenance：Original URL / Provider / Status / Fallback / Retrieved At（v3 §20） |
| `Footnote` | 报告脚注（模式/时间/版本） |

## 二、使用规则

1. 一个 Section 只用一个主组件；辅助组件（Footnote 等）不受限；
2. Report Spec 中 `component` 字段必须是上表名称，未知组件 → 渲染器报 `REPORT_INVALID`；
3. 组件 props 只控制展示（标题/排序/高亮），不能携带数据改写指令；
4. 图表组件必须携带 `summary_text`（无障碍非颜色编码摘要，v5 §26）。

## 三、数据一致性

- 所有组件只从 `result.json` 取数（经 `report-result.schema.json` 校验）；
- 图表数字 == result.json 数字（Scientific Integrity Gate，v5 §27）；
- 组件层禁止新增结论、禁止隐藏 contradiction、禁止捏造统计（v5 §60）。

## 四、自检清单

- [ ] 同一 report_spec 渲染五种主题，数据完全一致（v5 §49）
- [ ] 无 JS 时 Decision / Evidence summary / Matrix / Tribunal / Intervention / Sources 仍可读（v5 §28）
- [ ] ThemeSwitcher 持久化（localStorage），刷新后主题不变
- [ ] Provenance 只在 Sources & Provenance 面板展示，不出现在主证据界面（v3 §20）
