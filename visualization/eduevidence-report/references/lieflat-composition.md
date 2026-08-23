# Lieflat Composition — 注册表、契约与推荐组合

EduEvidence 的 Lieflat 画廊是**数据驱动的手作图表组合**：上游 AI 按数据形状自由选型（只能选注册表内图型），渲染器从 `result.json` 提取真实数据渲染成主题化内联 SVG。AI 不直接写数值——所有数字经 `scripts/charts_data.py` 提取器出数，完整性门 `lieflat_data_bound` 逐值核对溯源。

> 上游规范 = `visualization/lieflat-charts/`（Lupi 正本 + mono-tokens）。本文件只记录 EduEvidence 特有规则。

## 1. 注册表（type ↔ 目录编号 ↔ 数据形状 ↔ 提取器）

| `type` | 目录编号 | 数据形状 | 提取器（scripts/charts_data.py） |
|---|---|---|---|
| `forest_plot` | FOREST-PLOT (publication figure) | 逐研究 Hedges' g + 95% CI（meta.forest 或 evidence.effect_size） | `meta.forest` |
| `dot_cascade` | L2 Dot Cascade | 逐研究效应量排序（g + N） | `evidence.ranked_effects` |
| `bubble_almanac` | L9 Bubble Almanac | 年份 × 结果维度，气泡面积 ∝ 研究数 | `evidence.year_x_dimension` |
| `jitter_strip` | G15 Jitter Strip | 分组逐条 g 分布（每点一篇研究） | `evidence.grouped_distribution` |
| `parallel_coordinates` | L20 Parallel Coordinates | 同一批研究跨 g / N / 质量 / 年份 | `evidence.multidim_top` |
| `hundred_field` | L14 Hundred Field | 100% 构成（单位 = 1 篇研究，总数 ≤100） | `evidence.study_type_composition` |
| `tick_donut` | F4 Tick Donut | 100% 构成（100 ticks ∝ 份额） | `evidence.wwc_composition` |
| `tick_rows` | F5 Tick Rows | 各结果正向/负向/零效应计数（每点 1 条证据） | `outcomes.direction_counts` |
| `rung_bars` | F1 Rung Bars | 各结果方向计数（每格 1 条证据，竖排） | `outcomes.direction_counts` |
| `paired_rungs` | F6 Paired Rungs | 每结果正负两列对比 | `outcomes.paired_counts` |
| `brand_spectrum` | L7 Brand Spectrum | 双极维度：位置 = （正向 − 负向）÷ 方向计数 | `outcomes.bipolar_axes` |
| `barcode_lollipop` | L3 Barcode Lollipop | 16 周 × 阶段归属（柱高 = 阶段序号，无逐日数据不伪造） | `intervention.phase_weeks` |
| `launch_fan` | L1 Launch Fan | 干预阶段与活动权重（权重 = 活动条数） | `intervention.activity_weights` |
| `dotty_matrix` | L8 Dotty Matrix | 阶段 × 网格 × 活动（每点 = 1 项活动，强度均匀） | `intervention.phase_groups` |
| `tick_gauge` | F11 Tick Gauge | 单值 0–100%（决策置信度） | `decision.confidence_score` |
| `ballot_tally` | L15 Ballot Tally | 各方法学检查项独立计票（每 tick = 1 条审计结论） | `methodology.flag_rates` |
| `matrix_heat` | L16 Matrix Heat | 年份 × 结果维度 × 计数 | `evidence.year_x_outcome_counts` |

未注册 `type` → 该条被丢弃并写入 `report_spec.json` 的 `visualization_decisions.lieflat_gallery.rejected`，**不静默回退**。M1/M2 地图与 B1–B3 交互大图不进入 EduEvidence 默认画廊。

## 2. `visual_layout` 条目契约

写入 `result.json` 与 `result.zh.json` 的 `visual_layout`（两份文件条目完全相同，双语文本内嵌于每条）：

```json
{
  "chart_id": "lieflat-dot-cascade.svg",
  "type": "dot_cascade",
  "catalog_ref": "L2 Dot Cascade",
  "title_zh": "16 篇写作实证的效应量梯队级联",
  "title_en": "Ranked effect-size cascade of 16 writing studies",
  "subtitle_zh": "按 g 降序 · 圆点高度 ∝ |g| · 顶部数字 = g · 悬停读样本量",
  "subtitle_en": "Sorted by g · dot height ∝ |g| · top number = g · hover for sample size",
  "caption_zh": "梯队数值来自 evidence.effect_size.value 与 sample_size。",
  "caption_en": "Cascade values from evidence.effect_size.value and sample_size.",
  "source": "evidence.ranked_effects",
  "params": {"limit": 12}
}
```

规则：

- `chart_id` 唯一；缺省 = `lieflat-<type>.svg`；与学术图键（`outcome-comparison.svg` 等）冲突时自动加 `lieflat-` 前缀。
- `type` 必须在注册表内；`catalog_ref` 写错只告警并采用注册表值。
- `title/subtitle/caption` 双语齐备（旧式 `title/subtitle` 双语共用被兼容但告警）。
- `params` 白名单：`forest_plot{max_studies}`、`dot_cascade/jitter_strip/parallel_coordinates{limit}`、`launch_fan{max_items}`、`tick_rows/rung_bars/paired_rungs/brand_spectrum{outcomes:[…]}`。未知键或类型错误 → 条目被丢弃并记录原因。
- 标题写结论不写图型名；副标题把图例/单位说清（`·` 分隔）；来源行由渲染器按 `SOURCE · CATALOG_REF` 全大写输出。
- 每图一个独立结论，总数 ≤6，形状不重复；schema 见 `schemas/visual-layout.schema.json`。

## 3. 数据不足抑制（Meaningful Visualization Gate 镜像）

- 类目 <3、无 CI、无 phase 周区间、无年份、无 audit_items 等 → 该图抑制，原因写入 `report_spec.json` 的 `lieflat_gallery.suppressed`，报告 Brief 中以 `lieflat-suppressed` 块解释「为什么不画」。
- `visual_layout` 缺失或全无效 → 确定性安全组合 `forest_plot + dot_cascade + bubble_almanac + tick_rows`（同样经提取器出数，数据不足仍逐图抑制），画廊不空。
- 大样本 → top-N 截断 + `<title>` 悬停读数；不加欺骗性交互。
- 暗色主题 → SVG 底色 = 主题 `card_bg`，对比度 ≥4.5:1；浅/暗同图同结构仅换色。
- 无 JS / reduced-motion / 打印 → 图表静态完整可见（motion 模板的 `data-lieflat` 规则覆盖）。

## 4. 三个示例项目的推荐组合样例

- **ai-coding-assistant-50（50 篇，数据最全）**：`parallel_coordinates`（L20 跨维度）+ `jitter_strip`（G15 分布）+ `hundred_field`（L14 设计构成）+ `tick_gauge`（F11 置信度）+ `ballot_tally`（L15 审计计票）+ `matrix_heat`（L16 年份×维度）——六种轮廓全不重复。
- **highschool-math-ai-tutor（16 篇）**：`forest_plot` + `brand_spectrum`（L7 提速 vs 留存）+ `barcode_lollipop`（L3 四阶段）+ `launch_fan`（L1 活动权重）+ `paired_rungs`（F6 正负对比）。
- **esl-academic-writing-ai（16 篇）**：`forest_plot` + `dot_cascade`（L2 梯队）+ `bubble_almanac`（L9 年历）+ `tick_rows`（F5 方向分布）+ `dotty_matrix`（L8 阶段点阵）。

## 5. 渲染层不变式

- 渲染器只吃提取器 bundle；`lieflat_engine.render_figure(type, bundle, theme, meta)` 未知 type 抛错。
- SVG 内无 `<style>`；动画 = `lf-pop/lf-fade/lf-draw` 类 + `--motion-delay` 内联变量（点阵 12ms、条形 100ms stagger），由 `motion/motion.css` 定义曲线（quarticOut 族）。
- 卡片四件套：结论式标题（700）+ 副标题（图例，`·` 分隔）+ 图 + 全大写加字距来源行；图注可选。
- SVG 最小字号 6.5px；数值字重 800；面积编码用 sqrt；计数轴整数刻度。
