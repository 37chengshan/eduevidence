# Chart Selection Catalog — AI 选图与表格边界

本目录是 EduEvidence 报告生成阶段的**自包含选图控制面**。AI 可以根据 `result.json` 的数据形状自由组合图表，但只能从运行时注册表中选择；AI 负责“选什么、为什么”，确定性渲染器负责“从哪里取数、怎么画”。

> 核心原则：**图负责模式识别，表负责精确核验。** 不为了“更像数据产品”把所有表格图表化，也不了“严谨”把所有模式藏在大表里。

## 1. Table vs. chart policy

### 必须保留表格 / 展开详情的内容

- `EvidenceMatrix`：Evidence ID / Outcome / Effect / Quality / Claim / Source。
- `SourceList`：来源标题、年份、authority、canonical location。
- `MethodologyPanel` / methodology details：审计项的原始判断与备注。
- `ClaimTrace`：Claim → Evidence → Outcome → Effect → Quality → Source 的精确链路。
- 任何用户需要逐行复核、复制、引用或追溯的记录。

这些是审计面，不属于“可视化失败”。图表可以总结它们，但不能替代它们。

### 优先使用图表的内容

- 效应量及 CI 的横向比较。
- 研究/证据在年份、结果维度、设计簻型上的分布。
- 正向 / 负向 / 零效应的构成或两极差异。
- 干预阶段、活动数量与时间分布。
- 单值置信度和方法学检查构成。
- 多维研究特征的模式发现。

### 不画图的情况

- 数据不足以形成至少一个诚实的视觉关系。
- 维度单位不可比较或把不同 outcome 合并会制造假结论。
- 只有一条记录且图表没有比文本/表格增加信息。
- 缺失值会迫使渲染器填 `0`、补 CI、补趋势或推断因果方向。

此时输出 `VisualizationSuppressed` / `LieflatSuppressed` 和原因，比凑图更正确。

## 2. AI selection protocol

对每个准备表达的**独立结论**执行：

1. **识别数据形状**：g+CI、排序 g+N、年份×维度、逐条分布、100% 构成、方向计数、双极轴、阶段周区间、单值置信度、审计票数等。
2. **召回候选**：从下表中找语义匹配且提取器有数据的候选。通常比较至少 3 个；如果有效候选本来只有 1–2 个，不得为了满足数量硬凑不合适图型。
3. **逐项比较**：语义契合、单位诚实、标签容纳、阅读速度、移动端适配、与本批次图型是否重复、数据是否达到 Meaningful Visualization Gate。
4. **记录淘汰原因**：例如“需要 CI，但当前只有点估计”“类别名过长，不适合竖排”“与上一张同为方向计数，信息重复”。
5. **选择 ≤6 张**：每张图必须承担不同结论，优先轮廓多样性而非数量；同一数据形状不要堆多个近似图。
6. **只写计划，不写数值**：AI 只写 `type / catalog_ref / title_zh+en / subtitle_zh+en / caption_zh+en / source / params`。所有数值由 `charts_data.py` 提取。
7. **让渲染器最终裁决可画性**：注册表未收录、参数非法或数据不足时显式拒绝/抑制，不允许 AI 绕过。

## 3. Registered chart catalog

| `type` | `catalog_ref` | 数据形状 / extractor source | 最适合表达 | 避免使用 |
|---|---|---|---|---|
| `forest_plot` | FOREST-PLOT (publication figure) | g + 95% CI · `meta.forest` | 多研究效应与不确定性、零线关系 | 无 CI 时不要伪造区间 |
| `dot_cascade` | L2 Dot Cascade | 排序 g + N · `evidence.ranked_effects` | 效应量梯队、快速看排序与差距 | outcome/单位不可比时不要混排 |
| `bubble_almanac` | L9 Bubble Almanac | 年份 × 维度 × 研究数 · `evidence.year_x_dimension` | 时间覆盖与研究密度 | 没有年份或二维结构时不用 |
| `jitter_strip` | G15 Jitter Strip | 分组逐研究 g · `evidence.grouped_distribution` | 分布、离散度、异常点 | 只有聚合均值时不用 |
| `parallel_coordinates` | L20 Parallel Coordinates | g / N / 质量 / 年份 · `evidence.multidim_top` | 同一批研究的多维差异 | 维度单位/缩放无法解释时不用 |
| `hundred_field` | L14 Hundred Field | 研穵类型 100% 构成 · `evidence.study_type_composition` | 离散单位组成、研究设计结构 | 总数过大且单位点失去意义时慎用 |
| `tick_donut` | F4 Tick Donut | WWC 100% 构成 · `evidence.wwc_composition` | 少类别质量/等级份额 | 类别过多或精确比较更重要时不用 |
| `tick_rows` | F5 Tick Rows | outcome 方向计数 · `outcomes.direction_counts` | 长类目下的正/负/零分布 | 样本点太少且文本更清楚时不用 |
| `rung_bars` | F1 Rung Bars | outcome 方向计数 · `outcomes.direction_counts` | 紧凑方向计数比较 | 长中文类目或移动端拥挤时优先 tick_rows |
| `paired_rungs` | F6 Paired Rungs | 正/负成对计数 · `outcomes.paired_counts` | 每 outcome 正负直接对照 | 需要展示大量 null 时不优先 |
| `brand_spectrum` | L7 Brand Spectrum | 双极位置 · `outcomes.bipolar_axes` | “收益 ↔ 风险/退化”的方向张力 | 不得把 claim support 当正效应 |
| `barcode_lollipop` | L3 Barcode Lollipop | 周次 × 阶段 · `intervention.phase_weeks` | 干预阶段时间安排 | 没有真实周区间时不补时间点 |
| `launch_fan` | L1 Launch Fan | 阶段 × 活动权重 · `intervention.activity_weights` | 阶段工作量/活动构成 | “活动条数”不是强度时须在副标题说明 |
| `dotty_matrix` | L8 Dotty Matrix | 阶段 × 活动点阵 · `intervention.phase_groups` | 阶段结构和活动密度 | 不得把点数解释成效果大小 |
| `tick_gauge` | F11 Tick Gauge | 0–100% 单值 · `decision.confidence_score` | 已存在的决策置信度 | 不得从证据数量自行计算 confidence |
| `ballot_tally` | L15 Ballot Tally | 方法学检查计票 · `methodology.flag_rates` | 审计通过/风险项概览 | 不替代方法学原始备注 |
| `matrix_heat` | L16 Matrix Heat | 年份 × outcome × count · `evidence.year_x_outcome_counts` | 二维覆盖、证据空白和聚集区 | count 不代表效果强弱，标题需避免误导 |

## 4. Recommended candidate families

同一“问题”先在家族内比较，再跨家族避免重复：

- **效应与不确定性**：`forest_plot` / `dot_cascade` / `jitter_strip` / `parallel_coordinates`。
- **证据分布与覆盖**：`bubble_almanac` / `matrix_heat` / `hundred_field` / `tick_donut`。
- **结果方向**：`tick_rows` / `rung_bars` / `paired_rungs` / `brand_spectrum`。
- **干预结构**：`barcode_lollipop` / `launch_fan` / `dotty_matrix`。
- **决策与方法学摘要**：`tick_gauge` / `ballot_tally`。

示例：如果目标是“不同 outcome 的正负证据差异”，先比较 `tick_rows`、`rung_bars`、`paired_rungs`、`brand_spectrum`；如果类目长且要保留 null，通常 `tick_rows` 更合适；如果核心是两极张力，`brand_spectrum` 更快；如果只想看正负并排，`paired_rungs` 更直接。

## 5. Composition constraints

- 一份报告最多 6 张 AI-composed 图；少而准优先于填满 6 张。
- 每图对应一个明确问题或结论，不允许仅因“有数据”就画。
- 同一批次避免重复轮廓：例如已经用 `tick_rows` 讲方向分布，就不要再用 `rung_bars` 重复同一事实，除非第二张回答的是不同问题。
- 五种主题共享同一个 `visual_layout` 科学结构；主题只能改变版式、色板、表格密度和阅读节奏，不能改变数据、结论、图型含义或 Meaningful Visualization Gate。
- 报告中的 `EvidenceMatrix`、`SourceList`、方法学详情和 `ClaimTrace` 始终保留可审计入口。
- 图表数据必须通过 `lieflat_data_bound`；任何 AI 写入的数值都不进入渲染数据面。

## 6. Output contract example

```json
{
  "type": "paired_rungs",
  "catalog_ref": "F6 Paired Rungs",
  "title_zh": "迁移与保持结果呈现更明显的正负分化",
  "title_en": "Transfer and retention outcomes show the clearest directional split",
  "subtitle_zh": "每格 = 1 条已提取证据 · 正向与负向并列",
  "subtitle_en": "1 cell = 1 extracted finding · positive and negative shown side by side",
  "caption_zh": "仅展示已记录的 effect_direction，不根据 claim relation 推断方向。",
  "caption_en": "Uses recorded effect_direction only; claim relation never determines effect direction.",
  "source": "outcomes.paired_counts",
  "params": {}
}
```

AI 选择图型后，仍由 `references/lieflat-composition.md`、`schemas/visual-layout.schema.json`、`charts_data.py` 与 `lieflat_engine.REGISTRY` 共同执行机械校验。
