---
name: eduevidence-report
description: EduEvidence HTML 结果层渲染 Skill。把校验过的 result.json 渲染为五种差异化主题的单文件离线双层 Evidence Report：第一页是可视化摘要，第二页是 AI 规划的 5–7 章完整报告。只选择展示与组织方式，绝不修改 Evidence / Claim / Verdict / Confidence。
---

# eduevidence-report — HTML 结果层渲染 Skill

> **研究逻辑保持确定性，视觉表达与报告组织可以智能化。LLM 可以选择怎样讲清楚，但不能改变数据、证据和 Verdict。**

## When to Use

- EduEvidence Research 完成后，需要把 `result.json` / `result.zh.json` 渲染为可交互、可追溯、可离线展示的 HTML Evidence Report。
- 需要五种 HTML 风格之一：`claude` / `academic` / `datalab` / `datalab-dark` / `presentation`。其中明确区分 Light / Dark。
- 需要“快速看懂”与“完整审查”同时存在，而不是二选一。
- 教师阅读、研究审查、论文附录、答辩演示、公开分享。

## 不可变约束

只能：

```text
选择展示方式 · 规划 5–7 章目录 · 合并/排列语义模块
选择 chart · 格式化显示 · 增加 interaction · 渐进展开
```

不能：

```text
修改 Evidence · 修改 Claim · 修改 Verdict · 修改 Confidence
修改 effect_direction · 删除 Contradiction · 新增 Research Conclusion
为了图表更好看编造数据 · 重新搜索
```

## 数据流水线

```text
result.json + result.zh.json
  ↓ JSON Schema Validation
  ↓ Claim-Evidence-Source Integrity Check
  ↓ Scientific Integrity Gate
  ↓ Theme Selection（五种生成时主题）
  ↓ Report Outline Planner（AI 规划 5–7 章）
  ↓ Visual Brief Planner
  ↓ Full Report Module Mapping
  ↓ Meaningful Visualization Gate
  ↓ Component Router
  ↓ Bilingual Rendering
  ↓ Motion Template
  ↓ Accessibility / Print / Scientific Visual Audit
  ↓ 单文件 FINAL report.html
```

## 双层报告结构

最终 HTML 永远包含两个一级分页，分页逻辑和内容契约在五种主题中保持一致：

```text
[ 可视化摘要 / Visual Brief ] [ 完整报告 / Full Report ]
```

默认进入“可视化摘要”。切换不刷新页面。

### Page 1 — Visual Brief

目标：2–5 分钟内看懂研究结论，不把完整研究文本平铺出来。

推荐只保留 4–6 个高价值模块：

```text
Decision Hero
Outcome Separation / meaningful Evidence Balance
Evidence Tribunal
Evidence-to-Action
Key Sources
（必要时增加一项最关键的主题特定可视化）
```

Evidence / Methodology / Source / 长 Claim 通过 `<details>` 渐进展开。Visual Brief 不应重新变成“12 个章节的缩略版”。

### Page 2 — Full Report

桌面：左侧可折叠 sticky TOC + 右侧完整报告。移动端：目录折叠为顶部/抽屉式导航。滚动时高亮当前章节。

完整报告**不是固定 12 章**。AI 根据研究内容规划 **5–7 章**。目录应像真实研究报告，而不是模板填空题。

#### Report Outline Planner

上游 AI 应尽量写入：

```json
{
  "report_outline": {
    "chapters": [
      {
        "key": "decision",
        "title_zh": "……",
        "title_en": "……",
        "lead_zh": "……",
        "lead_en": "……",
        "modules": ["decision", "scope"]
      }
    ]
  }
}
```

约束：

- 总章节数必须为 5–7。
- 第一章必须包含 `decision`。
- 最后一章必须包含 `sources`。
- 下列语义模块必须全部出现且每个只出现一次：

```text
decision
scope
retrieval
outcomes
evidence
quality
conflicts
trace
applicability
intervention
evaluation
sources
```

- AI 可以自由合并模块、重命名章节、决定中间章节顺序。
- 例如 `retrieval + quality` 可以合并，`applicability + intervention` 可以合并，`conflicts + trace` 可以合并。
- 若 AI 产出的 outline 缺模块、重复模块、少于 5 章或多于 7 章，渲染器回退到安全的 6 章默认结构。
- 章节名称应针对当前研究问题写，不要机械使用“第 3 章：检索策略”之类的模板标题。

## 必须保留的研究内容

“动态章节”只意味着组织自由，不意味着内容可以丢失。Full Report 必须能完整承载：

- Decision / confidence / evidence boundary。
- Research question / scope / learner / course / comparison / outcome definitions。
- Retrieval / inclusion / exclusion / provenance（仅展示真实存在的数据，不伪造 PRISMA 数字）。
- Outcome Separation。
- 完整 Evidence Matrix。
- Methodology / Evidence Quality Audit。
- Counterevidence / conflicts / uncertainty。
- Evidence Tribunal。
- Claim → Evidence → Source Trace。
- Applicability / extrapolation boundary。
- Intervention / guardrails / stop conditions。
- Evaluation / retention / transfer / independent assessment。
- Sources / DOI / canonical URL / source location / provenance。

## Evidence 展开契约

Evidence Matrix 默认只显示：

```text
Evidence ID | Outcome | Effect | Quality | Claim | Source
```

注意：主表和 Outcome 可视化使用 `effect_direction`：

```text
positive / negative / null
```

`relation_to_claim` / `direction` 表示“这条证据是否支持某个 Claim”，不能拿它冒充 Outcome 的好坏方向。一个研究可以“support 一个负面结论”，因此 `support ≠ positive effect`。

展开 Evidence 时，存在什么就显示什么，不发明缺失字段：

- study_id / sample_id / title / year。
- study type / education level / population / sample size。
- intervention / comparison / outcome measure。
- claim / effect / effect_direction / relation_to_claim。
- duration / method / strengths / limitations / confounders。
- quality dimensions / quality score / evidence level。
- directness / applicability / confidence / status。
- Claim ID / Source ID / source location / canonical URL。

## 方法学与裁决展开

- Methodology 默认使用 compact status surface；每个审计项点击后展开完整 note。
- 中文模式把 `control_group`、`randomization`、`retention_test`、`transfer_test` 等稳定 taxonomy 翻译成中文。
- Tribunal 默认四类：Supported / Uncertain / Contradicted / Missing Evidence。
- Visual Brief 每类最多先显示少量重点，剩余内容继续展开。
- Full Report 保留完整裁决文本和 Evidence IDs。

## 五主题系统

开始生成报告时，如果用户尚未指定主题，必须先明确询问，并把明暗属性直接标出来：

```text
请选择报告视觉风格：
1. Claude Research      [Light]
2. Academic Paper       [Light]
3. DataLab              [Light]
4. DataLab              [Dark]
5. Presentation / Judge [Dark]
```

同一份内容、同一分页逻辑、同一 5–7 章 outline、同一 Evidence 数据，五个主题必须在 **UI 结构层明显不同**，不能只换颜色。

| theme | 定位 | 结构差异 |
|---|---|---|
| `claude` | Claude Research [Light] | 暖色研究阅读器；高留白；细窄目录；正文约 760–900px；数据区适度突破 |
| `academic` | Academic Paper [Light] | 论文/期刊；serif；正式横线；窄正文；目录像论文导航；print-first |
| `datalab` | DataLab [Light] | 浅色分析工作台；宽屏；Decision/Outcome 主导的 Brief；TOC/章节面板化；证据筛选密度高 |
| `datalab-dark` | DataLab [Dark] | 与 DataLab Light 共用信息架构的深色分析工作台；适合长时间审查、证据矩阵和方法学检查 |
| `presentation` | Presentation / Judge [Dark] | 深色高对比；Decision 首屏最强；Brief 卡片网格；Full Report 为评审面板 |

### 响应式与报告宽度约束

所有主题必须遵守同一套阅读器响应式规则：

- 页面使用 `width: 100%` + `max-width`，最大宽度只限制超宽屏阅读，不得把正文做成固定宽度。
- 浏览器缩窄时，header、Visual Brief、Full Report、表格与可视化必须连续压缩；不得出现依赖桌面固定像素宽度的横向溢出。
- `report-shell`、`brief-block`、`full-report-layout`、`full-report-content` 都必须允许 `min-width: 0` / `width: 100%` 的收缩路径。
- 宽数据表桌面端可横向滚动；移动端优先卡片化或纵向布局，关键 Evidence 字段不能因为 overflow 被永久隐藏。
- 980px 以下 Full Report 目录进入单列/折叠模式；720px 以下所有双列/四列关键阅读组件降为单列。
- 目录展开时可以占用左侧栏；目录收起后必须**真正退出网格布局**，右侧 Full Report 解除常规正文 `max-width` 限制并占满当前主题允许的可用宽度，只保留一个可访问的“展开目录”按钮。
- 目录收起不能只是隐藏链接而继续保留 48px / 240px 空栏。
- 移动端交互按钮和 `<summary>` 必须有足够触控面积，长标题、Source、Claim、URL 必须允许换行。

五主题允许不同：

```text
首屏构图
Brief 模块排列
正文最大宽度
TOC 宽度与 active 样式
卡片/横线/面板策略
数据区突破宽度
表格密度
章节标题尺度与节奏
```

五主题禁止不同：

```text
Evidence / Claim / Verdict / Confidence
章节内容覆盖范围
分页逻辑
Evidence 展开字段
Meaningful Visualization Gate
Motion 语义
科学完整性规则
```

运行 `build_report.py` 时通过 `--theme` 指定；交互终端未指定时先询问用户，非交互环境默认 `claude`。最终 HTML 内只保留中文 / English 切换，不提供五主题换皮按钮。

## Meaningful Visualization Gate

数据存在不等于必须画图。

- `1 / 0 / 0` 之类稀疏状态用 Badge / text，不放大成图。
- Outcome chart 必须使用 `effect_direction`。
- Evidence Balance 只有样本和非零格足够时才显示。
- Benchmark 只有真实、可比较、经验性数据才显示。
- 单一 PASS / FAIL 用状态组件。
- 多项 methodology audit 用状态矩阵。
- Claim → Evidence → Source 用 trace visual。
- 阶段流程用 timeline / semantic flow。
- 每个有意义的可视化后必须说明“这意味着什么”。
- 所有显示阈值都是 presentation heuristic，不得写成科学显著性标准。

## Motion Template

动画不是每份报告临时写，而是固定模板：

```text
motion/motion.css
motion/motion.js
references/motion-system.md
```

允许：`section-enter / stagger-enter / bar-grow / quality-grow / trace-reveal / flow-reveal / detail-expand / page-transition / toc-active`。

要求：

- 一次进入视口只触发一次。
- 不改变数据顺序、数值、方向、chart scale。
- `prefers-reduced-motion` 自动关闭非必要动画。
- 打印关闭动画并展示完整 detail 内容。
- 五主题共享同一 motion 行为，不能各自发明炫技动画。

## 双语规则

- 中文模式翻译稳定 UI / taxonomy / flow label。
- AI、RCT、DOI、Evidence ID、Claim ID、Source ID 可以保留英文缩写。
- 原始英文论文标题保留原文，并标注“原文标题”。
- 渲染层不能凭空翻译缺失的自由文本；若 `result.zh.json` 无对应中文，保留原文并明确标识。

## Static-first / Offline

JS 失败时，HTML 仍必须读得到：Decision、Outcome summary、Evidence、Tribunal、Intervention、Sources。ECharts 只能作为增强层，不允许留下空白 320px 图框。

## Scientific Integrity Gate

自动/人工检查重点：

```text
Chart number == result.json
Table number == result.json
Outcome direction == evidence.effect_direction
No hidden contradiction
No missing-source high-confidence claim
No axis distortion
No false precision
No generated certainty
No unsupported annotation
```

失败 → `REPORT_INVALID`，禁止发布。

## References

- `references/full-report-outline.md`：5–7 章动态报告规划与语义模块覆盖。
- `references/evidence-expansion.md`：Evidence 渐进展开规范。
- `references/bilingual-style.md`：双语 UI / taxonomy 规范。
- `references/motion-system.md`：固定动画模板。
- `references/component-catalog.md`：结果层组件目录。
- `themes/*.css`：五种结构差异化 UI 模板。
- `motion/motion.css` / `motion/motion.js`：共享动画模板。
- `scripts/build_report.py`：确定性 HTML 组装入口。
