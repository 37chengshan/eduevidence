# EduEvidence Demo 分镜 / 录屏脚本

> 对应 `docs/demo.md`（核心 180s 叙事 + 可选扩展幕 X/Y，合计约 250s）。画面元素全部锚定
> `examples/ai-coding-assistant/EduEvidence_Report.html` 的真实 Section / 元素。
> 录屏准备：Chrome 打开 `file://…/examples/ai-coding-assistant/EduEvidence_Report.html`，
> 窗口宽度 ≥1280，缩放 100%，主题默认 `claude`。

---

## 总览

| 时间 | 幕 | 页面位置 | 目标 |
|------|----|----------|------|
| 0-20s | 开场 + 决策结论 | 报告头部 + 01 Executive Decision | 5 秒回答"结论是什么" |
| 20-45s | 结果对照 | 02 结果证据概览 | 高光 1：任务快 ≠ 学得好 |
| 45-75s | 证据矩阵 | 03 Evidence Matrix + 筛选 | 高光 2：Immediate vs Retention vs Transfer |
| 75-110s | 反方 + 方法学 | 04 Tribunal + 05 Methodology | 高光 3/4：Skeptic 反驳卡、CONCERN 降级 |
| 110-135s | 追溯链 | 06 Conflict + 07 主张-证据追溯 | 每个结论可追溯 |
| 135-155s | 行动方案 | 09 Intervention + 10 Evaluation | 高光 5：PILOT 阶段化 |
| 155-170s | 信息图收束 | 04/09/10 内嵌 SVG | 设计语言统一 |
| 170-180s | 主题 + 收尾 | 头部生成主题徽标（claude）+ 12 Sources | 生成前选定主题、溯源完整 |
| 180-220s | 幕 X：Decision-to-Outcome 闭环 | CLI（`eduevidence pilot …`）+ `pilots/` + `decisions/` | 决策 → 试点 → 数据 → 再裁决，闭环可追溯 |
| 220-250s | 幕 Y：实证 Benchmark | `benchmarks/empirical/run-empirical-01/` + `v3-report.md` | Layer B 真实执行，SIMULATED / EMPIRICAL 明确区分 |

---

## 分镜 1（0:00-0:20）开场：第一屏必须回答决策

- **画面**：报告头部标题（问题原文）+ 01 Executive Decision 卡片。
- **操作**：无滚动。停留 8 秒。
- **旁白**："大一 C 语言课能不能用生成式 AI 编程助手？EduEvidence 的第一屏直接给出答案：PILOT——试点，不是全面放开。置信度 Moderate，来源 3 个，证据最充分的是知识获得，最不确定的是保持效果。主要风险：任务表现提升不等于学习能力提升。"
- **验证点**：KPI 网格 6 项（决策/置信度/最充分/最不确定/主要风险/来源数）全部可见；决策卡左缘为 PILOT 琥珀色。

## 分镜 2（0:20-0:45）结果对照：Completion Speed↑ ≠ Learning↑

- **画面**：02 结果证据概览——结果类型表 + 分歧条形图 + 图 1 学术图。
- **操作**：滚动到 02 节。指向 `completion_time` 行（支持 1）。
- **旁白**："证据矩阵按结果类型拆开：完成速度有支持证据；但独立问题解决这一行同时有支持与反驳——E-004 显示无护栏的 GPT 访问让独立考试成绩下降 17%。"
- **验证点**：表内数字与 result.json 一致（5 行：knowledge_gain 1/0/0、retention 0/0/1、independent_problem_solving 1/1/1、completion_time 1/0/0、assignment_score 1/0/0）；条形图反驳系列为负向红色。

## 分镜 3（0:45-1:15）证据矩阵：即时 vs 保持 vs 迁移

- **画面**：03 Evidence Matrix。
- **操作**：展开"筛选/搜索"；在搜索框输入 `retention` → 1 行；清空；方向筛选选"反驳" → 1 行（E-004）。
- **旁白**："矩阵可以按方向、结果、关键词过滤。留到最后的反驳证据是 E-004：同一批学生练习时快 48%，独立考试却差 17%。这就是'现在变快了，考试时变慢了'。"
- **验证点**：搜索 `guardrail` 命中 3 行；方向"反驳"命中 1 行；清空后恢复 7 行。

## 分镜 4（1:15-1:50）反方 + 方法学审计

- **画面**：04 证据裁决 → 05 Methodology Audit。
- **操作**：滚动到 04。停留 CAN CLAIM / UNCERTAIN / CANNOT CLAIM 三栏 8 秒；滚动到 05，指向 `measurement_validity=partial` 与"任务 vs 学习护栏"。
- **旁白**："裁决分三栏：可以主张——AI 确实提升训练期任务表现；尚不能主张——大学一年级真实学习效果没有直接研究；被反驳的主张——'AI 总是提升学习'。方法学审计点名了关键问题：练习成绩被当成'学会了'的证据，这是任务 vs 学习的混淆。"
- **验证点**：04 三栏各 ≥1 条；05 `overall CONCERN` 徽标 + 15 个审计项状态表；"任务 vs 学习护栏"说明含 "+48-127% practice performance 与 -17% independent exam 并存"。

## 分镜 5（1:50-2:15）追溯链：结论 → 证据 → 来源

- **画面**：06 Conflict Analysis → 07 主张-证据追溯。
- **操作**：滚动到 07。指向 Claim 4 的 E-004 链接 `S-2025-bastani`（PNAS 原文链接可点击）。
- **旁白**："结论为什么分歧？因为结果分离、工具设计、人群三个维度不同。每条主张都能穿透到证据、再到可验证的原始来源——这是可追溯的证据链，不是生成式问答。"
- **验证点**：07 静态树 7 条 Claim 全部 SUPPORTED，每条含方向徽标 + 证据 ID + 来源链接（3 个唯一来源）。

## 分镜 6（2:15-2:40）行动方案：PILOT 阶段化

- **画面**：09 教学干预 → 10 评价方案。
- **操作**：滚动到 09，指向 Phase 1→4 的 AI 规则变化；滚动到 10，指向成功阈值。
- **旁白**："结论落到行动：8 周分阶段试点。Phase 1 禁止生成、允许解释；Phase 3 允许部分生成但强制推理痕迹；Phase 4 无 AI 迁移考核。停止条件写死：迁移成绩下滑超阈值即回退。成功阈值：独立解题不劣于对照，否则任务表现再好也不算成功。"
- **验证点**：09 四个 Phase 块各含 AI 规则/活动/结果检查；10 含基线/后测/保持/迁移 + 3 类指标 + 成功阈值。

## 分镜 7（2:40-3:00）信息图 + 主题 + 溯源收尾

- **画面**：04 EvidenceFlow 协议 SVG + 09 干预时间线 + 10 评价流程 → 头部生成主题徽标（claude）→ 12 来源与溯源。
- **操作**：快速滚动展示 3 张信息图；回到头部，指出当前主题为生成前选择的 `claude`（`claude`[Light] / `academic`[Light] / `datalab`[Light] / `datalab-dark`[Dark] / `presentation`[Dark] 五选一，最终 HTML 不提供主题切换，五种主题以 `reports-5themes/` 独立文件预览）；滚动到 12，展示来源表与 Fetch 溯源。
- **旁白**："研究流程、裁决、干预、评价全部有统一风格的信息图，离线可用、不依赖任何 CDN。主题在生成前从五种中选定，最终 HTML 只保留中英文切换。最后是来源与抓取溯源——每条证据的来源、获取方式、时间都可查。"
- **验证点**：4 张信息图内嵌 SVG 渲染正常；头部仅中英文切换（无主题切换 UI）、主题徽标显示生成时选定的主题；12 节来源表 3 行 + Fetch 溯源表头完整。

## 分镜 8（3:00-3:40）幕 X：Decision-to-Outcome 闭环（可选扩展）

> 本幕起画面切换到终端 + 文件视图（脱离 HTML 报告）：锚定 `eduevidence pilot` CLI 输出
> 与项目工作区 `~/.eduevidence/projects/PRJ-…/pilots/PIL-*.json`、`decisions/*.json`。

- **画面**：终端（`pilot register / import / redecide` 输出）+ `pilots/PIL-*.json` 与 `decisions/*.json` 双栏对照。
- **操作**：
  1. 回到报告头部 01 决策卡，指出 `PILOT`——闭环的起点正是这张 DecisionSnapshot；
  2. 运行 `eduevidence pilot register --decision <snapshot_id> --title "C 语言 8 周试点" --start … --end … --condition guardrailed --sample 60 --design <design_id> --outcome independent_problem_solving --outcome retention` → 输出新 `PIL-…`；打开 `pilots/PIL-*.json`，指向 `decision_snapshot_id` 与 `status: "registered"`；
  3. 运行 `eduevidence pilot import --pilot PIL-… --file outcomes.csv`：先演示含 `姓名/学号` 列的 CSV 被 PII 门拒绝（报错 `PII columns detected and refused`），再导入去标识化 CSV → 输出 `imported …`，`status` → `data_imported`（可选：`analyze-link` → `analyzed`）；
  4. 运行 `eduevidence pilot redecide --pilot PIL-… --claim <claim_id> --outcome transfer --measure … --effect … --relation …` → 终端打印 `new decision: <DEC-…> <action> <confidence>` 与 `diff:` 片段；打开 `decisions/` 下的新 DecisionSnapshot 与 `pilots/PIL-*.json` 的 `redecide` 块，指出 action / confidence 的变化即 diff 的内容。
- **旁白**："PILOT 不是终点，而是下一轮证据的起点。决策快照注册成试点；试点产出 CSV 结果，PII 列在导入口就被拒绝，学生数据留在本地；分析结果回流证据图、提交新图版本，裁决器重跑一遍，输出一张带机器可读 diff 的新决策快照——action 变了还是置信度变了，一比对就知道。这就是 Decision-to-Outcome 闭环：从决策出发，回到决策。"
- **验证点**：`pilots/PIL-*.json` 与 `decisions/*.json` 路径锚定；状态机按 `registered → data_imported → analyzed → adjudicated` 流转；PII 列（name/student/学号/姓名/email/…）被拒报错可见；redecide 后 `decisions/` 出现新快照、`pilots/` 记录 `redecide.diff` 含 action/confidence 变化；`schemas/v3/pilot-outcome.schema.json` 校验通过。

## 分镜 9（3:40-4:10）幕 Y：实证 Benchmark（Layer B，可选扩展）

- **画面**：`benchmarks/empirical/run-empirical-01/` 目录（manifest + per-attempt JSON）→ `benchmarks/empirical/v3-report.md`。
- **操作**：
  1. 打开 run 目录的 `manifest.json`，指向 `run_mode: "empirical"`、`environment`（`model_family`（deepseek-v4-flash，经 omp 执行）/ `model_version` / `temperature` / `tools` / `search_provider` / `driver`）与 `baselines`、`repeats`（≥3），逐次 token / latency / cost 在 `attempts` 里；
  2. 打开 `v3-report.md`：先让观众看到顶部模式横幅（EMPIRICAL，非 SIMULATED），再指向指标表（每格 `均值±95% CI`，带 `n` 列）；
  3. 指向报告脚注中 SIMULATED 的声明，读一句"Layer A 是固定种子的确定性模拟，只能验证管线可运行，不能当性能证据"。
- **旁白**："Benchmark 分两层：Layer A 是确定性模拟，产物必须标注 SIMULATED，只能验证框架可运行；Layer B 才是性能证据——本场演示用 omp 驱动 deepseek-v4-flash 真实执行，每次运行记录模型家族、版本、温度、工具集、检索 provider，重复 ≥3 次，指标按均值±95% CI 报告。页面上所有数字就是 v3-report.md 的原样输出，我们不做任何夸大。"
- **验证点**：manifest 含 `run_mode=empirical` + 环境（模型家族/版本、temperature、tools、search_provider、driver）+ `baselines` + `repeats≥3` + `attempts` 逐次 token/latency/cost；`v3-report.md` 顶部横幅明确 EMPIRICAL、脚注明确 SIMULATED 不得作为性能证据；指标表为 `mean±CI95` 且带 `n`；演示台词与报告数字完全一致（不新增、不修饰）。

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
