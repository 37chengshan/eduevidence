---
name: report-generation
description: "Renders 5 baked-theme single-file bilingual HTML reports, executive Visual Briefs, and Markdown reports, powered by Lieflat Charts editorial visualization standards and AI-composed, data-driven chart galleries."
---
# Report Generation Skill

## 1. When to Use
Trigger at the completion of a research cycle (Step 9: Present stage) to deliver visual dossiers, decision briefs, and publication-grade reports.

## 2. Lieflat Charts Editorial Standards Integration
All statistical figures, evidence matrices, and causal trajectories follow the **Lieflat Charts Editorial Codex** (`visualization/lieflat-charts/`). Chart galleries are **AI-composed but data-driven**: the upstream AI writes a chart plan (`visual_layout`), and the deterministic renderer extracts every number from `result.json` via `scripts/charts_data.py`. **The AI never writes numeric values into the layout** — values are un-tamperable and always traceable.

### 2.1 Six-Step Chart Composition Workflow
1. **判数据形状。** 看 `result.json` 的数据长什么样（效应量 g+CI / 年份×维度 / 方向计数 / 阶段周区间 / 置信度单值 / 审计状态……），形状是选图的主键。
2. **按 catalog 审计候选。** 在 `visualization/lieflat-charts/catalog.md` 按数据形状召回候选，至少比较 3 个并写下淘汰理由（语义契合、单位诚实、标签容纳、阅读速度、本批次是否重复）。Glance 系只在 Lupi/Basics 不适配或用户明确要求快读时进入候选。
3. **锁定注册表 `type`。** 只能选 `visualization/eduevidence-report/references/lieflat-composition.md` 注册表内的图型（type ↔ 目录编号 ↔ 数据形状 ↔ 提取器）；**未注册 type 会显式报错并被丢弃，不存在静默回退**。
4. **写 `report_outline` + `visual_layout`。** 每张图承担一个独立结论；总数 ≤6 张；同一批形状不重复（不堆同类环/条/点阵）；每张图写清 `type / catalog_ref / title_zh+en / subtitle_zh+en / caption_zh+en / source / params`，副标题写清图例与单位；主题色系由烘焙主题锁定，布局不得换色。
5. **渲染。** 运行 `build_report.py`（或 `scripts/rebake_all_5themes.py`）——渲染器对每个条目走注册表提取器：数据不足 → 该图抑制并记录原因（镜像 Meaningful Visualization Gate）；全部无效 → 确定性安全组合（forest_plot + dot_cascade + bubble_almanac + tick_rows）。
6. **按 Lieflat skill 第八节自检**（面积 sqrt、最小字号 6.5/5.5px、数值 800、reveal 滚入播放 + 点击重播 + reduced-motion、卡片四件套齐全、数值与视觉成正比）。

### 2.2 数据契约：AI 写计划，渲染器出数
- `visual_layout` 条目 = 图型 + 目录编号 + 双语文案 + 数据源参数。**数值一律由 `scripts/charts_data.py` 的提取器从 `result.json` 读出**，渲染器只接收提取器 bundle——被篡改的数值天然不被采用，完整性门 `lieflat_data_bound` 逐值核对溯源。
- 50 篇级大样本 → 提取器 top-N 截断 + SVG `<title>` 悬停读数，不加欺骗性交互。
- 中文长类目 → 按决策树选横排图（F5/F1/F6 系），L2 cascade 类目名 ≤4 字约束保留。

### 2.3 5 Theme Palettes Adaptive Binding (Zero-CDN Guarantee)
Every chart is rendered as **pure self-contained inline SVG** following the baked report theme's color system:
- **`claude` (智库典雅)** ➔ **Lieflat Palm (暖棕)**: `#FAF7F2` paper base, `#B8694A` terracotta, `#5E8A6A` forest green, `#C99A4A` amber.
- **`academic` (学术顶刊)** ➔ **Lieflat Mono / Nature (学术黑白灰)**: `#FFFFFF` paper base, `#0F172A` ink black, Okabe-Ito colorblind-safe accents.
- **`datalab` (数据科学)** ➔ **Lieflat Porcelain (瓷青)**: `#F8FAFC` slate base, `#0284C7` sky blue, `#10B981` emerald.
- **`datalab-dark` (极客终端)** ➔ **Lieflat Wire Dark (暗黑高对比)**: `#0B0F17` terminal black, `#38BDF8` neon cyan, `#F59E0B` amber.
- **`presentation` (法庭终裁)** ➔ **Lieflat Judicial Gold (朱金)**: `#140A08` dark ochre, `#F59E0B` gold, `#F24D29` brand orange.

Dark themes draw on the theme's `card_bg`; text contrast is checked against the theme palette (≥4.5:1 for body/labels). The chart structure is identical across light/dark — only colors change.

### 2.4 排版守则（五主题统一约束）
五个烘焙主题的排版必须通过 `scripts/lint_report_layout.py`（静态不变量 + 浏览器级
390/768/1280 × brief/full 实测）：轨道 `minmax(0,1fr)` / `minmax(min(Npx,100%),1fr)`、
主题自带移动端媒体覆写、禁止裸 `1fr` 与固定 px 最小值 auto-fit、表格外包 `overflow-x:auto`。
详见 `visualization/eduevidence-report/references/layout-constraints.md`；合入前重烘焙 15 份报告
并跑 `tests/test_report_layout_mobile.py`。

## 3. Outputs
1. **5 Baked Report Themes**: `claude` / `academic` / `datalab` / `datalab-dark` / `presentation`.
   - Theme is chosen **at generation time**; single-file offline self-contained (zero CDN).
   - In-document bilingual switching (`lang-toggle`, `result.json` / `result.zh.json`).
2. **AI-Composed Lieflat Gallery**: registry-validated, extractor-driven inline SVG charts per `visual_layout` (entry contract and registry in `references/lieflat-composition.md`), plus unchanged publication figures (forest plot, outcome × direction, benchmark).
3. **Bilingual result pack**: `result.json` / `result.zh.json`.

## 4. Web Studio Sync
The Local Web Studio (`scripts/dashboard_server.py`) serves the baked HTML reports and Lieflat figures directly.
