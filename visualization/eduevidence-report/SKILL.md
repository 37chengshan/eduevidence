---
name: eduevidence-report
description: EduEvidence HTML 结果层渲染 Skill。把校验过的 result.json 通过冻结的 Component Catalog 渲染为五种主题的单文件离线 HTML Evidence Report（Interactive HTML + AntV Infographic + Academic Figures 三管线）。只选择展示方式，绝不修改数据/证据/Verdict。
---

# eduevidence-report — HTML 结果层渲染 Skill

> **研究逻辑保持确定性，视觉表达可以智能化。LLM 可以选择怎样展示，但不能改变数据、证据和 Verdict。**（v5 方案 §1）

## When to Use

- 一次 EduEvidence Research 完成后，需要把 `result.json` 渲染为可交互、可追溯、可离线展示的 HTML Evidence Report
- 需要五种 HTML 主题（claude / academic / editorial / datalab / presentation）之一
- 需要导出 Academic Figures（SVG/PDF/PNG）或 AntV Infographic（SVG）
- 教师阅读 / 论文附录 / 答辩演示 / 公开分享

## 核心约束（v5 方案 §7）

只能：

```text
选择展示方式 · 排列 Section · 选择 chart · 格式化显示 · 增加 interaction
```

不能：

```text
修改 Evidence · 修改 Claim · 修改 Verdict · 修改 Confidence
删除 Contradiction · 新增 Research Conclusion · 重新搜索
```

## 数据流水线（v5 方案 §8）

```text
result.json
  ↓ JSON Schema Validation (report-result.schema.json)
  ↓ Claim-Evidence Integrity Check
  ↓ Visualization Planner → report_spec.json
  ↓ Chart Spec Validation (chart-spec.schema.json)
  ↓ Renderer（确定性）
  ↓ report.html
  ↓ Scientific Visual Audit
  ↓ Web UX Audit
  ↓ FINAL report.html
```

## 固定 Component Catalog（v5 方案 §36）

```text
ReportShell ThemeSwitcher SectionNav
DecisionCard ConfidenceBadge OutcomeSummary
InteractiveChart AcademicFigure InfographicBlock
EvidenceMatrix EvidenceRow
TribunalView MethodologyPanel ConflictCard
ClaimTrace
ApplicabilityCard InterventionTimeline EvaluationFlow
BenchmarkPanel SourceList ProvenancePanel
```

Report Spec 只能使用以上组件——固定目录防止每次报告形态漂移、LLM 写坏 HTML、可访问性失控（§10）。

## 五主题系统（§3-10）

同一份 result.json + 同一套 Component Catalog，生成报告前选择视觉系统。五种主题允许改变 Typography、页面宽度、章节节奏、卡片策略、表格密度、首屏构图和数据面板布局，但不得改变证据语义、数字或裁决结果：

| theme | 定位 | 默认 |
|---|---|---|
| `claude` | Claude Warm Research（温暖/安静/高留白/编辑感） | ✅ DEFAULT |
| `academic` | Academic Paper（纯白/高密度/论文式编号） | 论文导出 |
| `editorial` | Editorial Journal（强 Typography/长文章/信息图穿插） | 公众传播 |
| `datalab` | Data Lab（高密度/Filter 强/交互优先） | 深度查看 |
| `presentation` | Presentation / Judge（深色/高对比/强首屏/答辩路径） | 答辩演示 |

实现：运行 `build_report.py` 时通过 `--theme` 指定；交互终端未指定时先询问用户，非交互环境默认 `claude`。主题写入生成 HTML 的 `data-theme`，报告内部只保留中文 / English 切换，不再提供五主题换皮按钮。Academic Figure **不随 HTML 主题改变**（§39）。

## Visualization Router（§34）

```text
interactive_analysis     -> ECharts
statistical_publication  -> Academic Figures
process_or_story         -> AntV Infographic
simple_structure         -> HTML/CSS/SVG
```

## 输出（§64）

```text
report.html                    单文件离线（CSS/JS/ECharts/数据全部 inline，无 CDN）
infographics/*.svg             研究流程/裁决/干预/评价信息图
figures/*.svg|png|pdf          出版级统计图（Okabe-Ito/Nature/Conservative）
report_spec.json               可视化决策记录
```

## Scientific Integrity Gate（§27 / §60）

自动检查：

```text
Chart number == result.json · Table number == result.json
No hidden contradiction · No missing-source high-confidence claim
No axis distortion · No false precision · No generated certainty
No unsupported annotation
```

失败 → `REPORT_INVALID`，禁止发布。统计结果（误差/p-value）只能来自分析结果，**禁止自己根据图形猜显著、自己发明 p-value**（§60）。

## 静态降级（§28）

JS 即使失败，HTML 仍应显示：Decision / Evidence summary / Evidence table / Tribunal / Intervention / Sources。图表加 `<noscript>` 或对应静态 Summary。

## Failure Handling

- `REPORT_INVALID`：数据完整性检查失败，禁止发布，rerun render
- 主题缺失：回退默认 `claude`，不中断
- 图表数据缺失：显示静态 Summary + 标注，不显示空图
- ECharts 不可用（离线/禁用 JS）：静态表格与 Summary 完整可用

## References

- `references/`（v5 方案 §6）：report-information-architecture / chart-selection / evidence-visualization / scientific-integrity / design-system / accessibility / demo-mode
- `schemas/`：report-result.schema.json / report-spec.schema.json / chart-spec.schema.json
- `templates/`：report.html（+ 主题 CSS）
- `scripts/`：build-report.py / validate-report.py / audit-claims.py / bundle-report.py
