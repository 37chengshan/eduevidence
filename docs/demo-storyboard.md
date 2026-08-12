# EduEvidence Demo 分镜 / 录屏脚本

> 对应 `docs/demo.md`（180s 叙事结构）。画面元素全部锚定
> `examples/ai-coding-assistant/EduEvidence_Report.html` 的真实 Section / 元素。
> 录屏准备：Chrome 打开 `file://…/examples/ai-coding-assistant/EduEvidence_Report.html`，
> 窗口宽度 ≥1280，缩放 100%，主题默认 `claude`。

---

## 总览

| 时间 | 幕 | 页面位置 | 目标 |
|------|----|----------|------|
| 0-20s | 开场 + 决策结论 | 报告头部 + 01 Executive Decision | 5 秒回答"结论是什么" |
| 20-45s | 结果对照 | 02 Outcome Evidence Overview | 高光 1：任务快 ≠ 学得好 |
| 45-75s | 证据矩阵 | 03 Evidence Matrix + 筛选 | 高光 2：Immediate vs Retention vs Transfer |
| 75-110s | 反方 + 方法学 | 04 Tribunal + 05 Methodology | 高光 3/4：Skeptic 反驳卡、CONCERN 降级 |
| 110-135s | 追溯链 | 06 Conflict + 07 Claim-Evidence Trace | 每个结论可追溯 |
| 135-155s | 行动方案 | 09 Intervention + 10 Evaluation | 高光 5：PILOT 阶段化 |
| 155-170s | 信息图收束 | 04/09/10 内嵌 SVG | 设计语言统一 |
| 170-180s | 主题演示 + 收尾 | 头部 ThemeSwitcher + 12 Sources | 五主题、溯源完整 |

---

## 分镜 1（0:00-0:20）开场：第一屏必须回答决策

- **画面**：报告头部标题（问题原文）+ 01 Executive Decision 卡片。
- **操作**：无滚动。停留 8 秒。
- **旁白**："大一 C 语言课能不能用生成式 AI 编程助手？EduEvidence 的第一屏直接给出答案：PILOT——试点，不是全面放开。置信度 Moderate，来源 3 个，证据最充分的是知识获得，最不确定的是保持效果。主要风险：任务表现提升不等于学习能力提升。"
- **验证点**：KPI 网格 6 项（决策/置信度/最充分/最不确定/主要风险/来源数）全部可见；决策卡左缘为 PILOT 琥珀色。

## 分镜 2（0:20-0:45）结果对照：Completion Speed↑ ≠ Learning↑

- **画面**：02 Outcome Evidence Overview——结果类型表 + 分歧条形图 + Figure 1 学术图。
- **操作**：滚动到 02 节。指向 `completion_time` 行（支持 1）。
- **旁白**："证据矩阵按结果类型拆开：完成速度有支持证据；但独立问题解决这一行同时有支持与反驳——E-004 显示无护栏的 GPT 访问让独立考试成绩下降 17%。"
- **验证点**：表内数字与 result.json 一致（5 行：knowledge_gain 1/0/0、retention 0/0/1、independent_problem_solving 1/1/1、completion_time 1/0/0、assignment_score 1/0/0）；条形图反驳系列为负向红色。

## 分镜 3（0:45-1:15）证据矩阵：即时 vs 保持 vs 迁移

- **画面**：03 Evidence Matrix。
- **操作**：展开"筛选/搜索"；在搜索框输入 `retention` → 1 行；清空；方向筛选选"反驳" → 1 行（E-004）。
- **旁白**："矩阵可以按方向、结果、关键词过滤。留到最后的反驳证据是 E-004：同一批学生练习时快 48%，独立考试却差 17%。这就是'现在变快了，考试时变慢了'。"
- **验证点**：搜索 `guardrail` 命中 3 行；方向"反驳"命中 1 行；清空后恢复 7 行。

## 分镜 4（1:15-1:50）反方 + 方法学审计

- **画面**：04 Evidence Tribunal → 05 Methodology Audit。
- **操作**：滚动到 04。停留 CAN CLAIM / UNCERTAIN / CANNOT CLAIM 三栏 8 秒；滚动到 05，指向 `measurement_validity=partial` 与"任务 vs 学习护栏"。
- **旁白**："裁决分三栏：可以主张——AI 确实提升训练期任务表现；尚不能主张——大学一年级真实学习效果没有直接研究；被反驳的主张——'AI 总是提升学习'。方法学审计点名了关键问题：练习成绩被当成'学会了'的证据，这是任务 vs 学习的混淆。"
- **验证点**：04 三栏各 ≥1 条；05 `overall CONCERN` 徽标 + 15 个审计项状态表；"任务 vs 学习护栏"说明含 "+48-127% practice performance 与 -17% independent exam 并存"。

## 分镜 5（1:50-2:15）追溯链：结论 → 证据 → 来源

- **画面**：06 Conflict Analysis → 07 Claim-Evidence Trace。
- **操作**：滚动到 07。指向 Claim 4 的 E-004 链接 `S-2026-bastani`（PNAS 原文链接可点击）。
- **旁白**："结论为什么分歧？因为结果分离、工具设计、人群三个维度不同。每条主张都能穿透到证据、再到可验证的原始来源——这是可追溯的证据链，不是生成式问答。"
- **验证点**：07 静态树 7 条 Claim 全部 SUPPORTED，每条含方向徽标 + 证据 ID + 来源链接（3 个唯一来源）。

## 分镜 6（2:15-2:40）行动方案：PILOT 阶段化

- **画面**：09 Teaching Intervention → 10 Evaluation Plan。
- **操作**：滚动到 09，指向 Phase 1→4 的 AI 规则变化；滚动到 10，指向成功阈值。
- **旁白**："结论落到行动：8 周分阶段试点。Phase 1 禁止生成、允许解释；Phase 3 允许部分生成但强制推理痕迹；Phase 4 无 AI 迁移考核。停止条件写死：迁移成绩下滑超阈值即回退。成功阈值：独立解题不劣于对照，否则任务表现再好也不算成功。"
- **验证点**：09 四个 Phase 块各含 AI 规则/活动/结果检查；10 含基线/后测/保持/迁移 + 3 类指标 + 成功阈值。

## 分镜 7（2:40-3:00）信息图 + 主题 + 溯源收尾

- **画面**：04 EvidenceFlow 协议 SVG + 09 干预时间线 + 10 评价流程 → 头部主题切换 → 12 Sources & Provenance。
- **操作**：快速滚动展示 3 张信息图；回到头部，依次点击 Academic / Presentation 主题（观察配色切换）；滚动到 12，展示来源表与 Fetch Provenance。
- **旁白**："研究流程、裁决、干预、评价全部有统一风格的信息图，离线可用、不依赖任何 CDN。五种主题一键切换。最后是来源与抓取溯源——每条证据的来源、获取方式、时间都可查。"
- **验证点**：4 张信息图内嵌 SVG 渲染正常；主题切换改变 `data-theme` 且 localStorage 持久化；12 节来源表 3 行 + Fetch Provenance 表头完整。

---

## 可运行演示产物清单

| 产物 | 路径 | 验证命令 |
|------|------|----------|
| 单文件离线报告 | `examples/ai-coding-assistant/EduEvidence_Report.html`（59.5KB） | 浏览器直接打开，断网可读 |
| 可视化决策记录 | `examples/ai-coding-assistant/report_spec.json` | 完整性门 status=PASS |
| ECharts 规格 | `examples/ai-coding-assistant/chart_specs.json` | charts=2 + benchmark 面板 |
| AntV 信息图 | `examples/ai-coding-assistant/infographics.json` | workflow/tribunal/intervention/evaluation 4 张 SVG |
| 学术图 | `examples/ai-coding-assistant/figures/` | figure_data.json + SVG/PNG/PDF |
| 源数据 | `examples/ai-coding-assistant/result.json` | 7 证据 / 3 来源 / PILOT / Moderate |

## 复现命令（一次生成全部演示产物）

```bash
cd ~/edu
python3 visualization/eduevidence-report/scripts/build_charts.py \
  --result examples/ai-coding-assistant/result.json \
  --out examples/ai-coding-assistant/chart_specs.json
python3 visualization/eduevidence-report/scripts/build_infographics.py \
  --result examples/ai-coding-assistant/result.json \
  --out examples/ai-coding-assistant/infographics.json
python3 visualization/eduevidence-report/scripts/build_figures.py \
  --result examples/ai-coding-assistant/result.json \
  --out-dir examples/ai-coding-assistant/figures --export-png
python3 visualization/eduevidence-report/scripts/build_report.py \
  --result examples/ai-coding-assistant/result.json \
  --out examples/ai-coding-assistant/EduEvidence_Report.html
```
