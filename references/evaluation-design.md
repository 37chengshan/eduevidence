# Evaluation Design（评价设计）

## 1. 目的与核心区分

评价设计回答：**试点是否成功？** 评价必须同时区分两组维度，禁止混为一谈：

```
即时效果（immediate）  ≠  保持（retention）  ≠  迁移（transfer）
任务表现（task performance, C2）  ≠  学习（learning, C1）
```

任何"成功"判定必须说明它来自哪个维度。只用任务表现定成功 → 无效评价。

## 2. EvaluationPlan 字段

| 字段 | 说明 |
| --- | --- |
| `research_question` | 与 Frame.question 一致的一句话问题 |
| `groups` | `treatment`（试点组）与 `comparison`（对照/基线组）的定义与人数 |
| `baseline` | 前测内容与时间点（无 AI 环境，测 C1 基线） |
| `post_test` | 干预结束时的即时后测（仍按阶段 AI 政策执行） |
| `retention_test` | 结课后 2–4 周的延迟测验（无 AI） |
| `transfer_test` | 新题型/新环境/无 AI 的迁移任务 |
| `process_metrics` | 学习过程数据（C3：engagement、help_seeking、cognitive_load 等） |
| `learning_metrics` | 学习效果数据（C1：knowledge_gain、independent_problem_solving 等） |
| `risk_metrics` | 风险数据（C4：ai_dependency、over_reliance、academic_integrity_risk） |
| `analysis_plan` | 统计方法、效应量与置信区间、多重比较控制 |
| `success_threshold` | 判定成功的预注册阈值（必须同时看学习与风险） |
| `stop_conditions` | 立即终止/回退的阈值（与 intervention-design.md 一致） |

## 3. 测量时间轴（推荐模板）

| 时间点 | 测量 | 维度 |
| --- | --- | --- |
| T0（试点前） | 前测（无 AI）：语法知识 + 独立编程题 + 学习动机问卷 | C1 基线、C3 |
| T1（每阶段末） | 阶段小测、AI 使用日志、求助行为记录 | C2、C3、C4 |
| T2（第 8 周末） | 后测：即时独立编程测验 + 满意度/依赖自评 | C1（即时）、C2、C4 |
| T3（+2~4 周） | 保持测验（无 AI，新题但同难度） | C1/retention |
| T4（+2~4 周内） | 迁移任务（新题型或换语言，无 AI） | C1/transfer、C4 |

## 4. 指标绑定规则

- `learning_metrics` 只收 C1 指标；`process_metrics` 只收 C3；`risk_metrics` 只收 C4；
  C2（任务表现）单列，不得混入 learning_metrics。
- 每条数据记录格式：`指标名（类别）— 时间点 — 组别 — 值/变化`。
- 缺失 retention/transfer 测量的评价报告不得包含"长期有效""能迁移"字样。

## 5. 分析与成功判定

### 5.1 analysis_plan（示例）

- 主要比较：treatment vs comparison 在 T2 的 C1 后测差；效应量 Cohen's d 与 95% CI。
- 保持与迁移：T3、T4 两组差异（若 T2 有差异但 T3/T4 消失 → 即时红利假象）。
- 风险联动：C1 提升的同时检查 C4 是否上升；上升则成功判定需打折。
- 多重比较：涉及多个学习指标时做 Bonferroni 或 FDR 校正。
- 缺失值：报告 dropout 率；> 20% 需做敏感性分析。

### 5.2 success_threshold（示例）

成功 = 以下**全部**满足：

1. T2 无 AI 独立测验：treatment 不显著低于 comparison（d ≥ -0.1）；
2. T3 保持测验：无显著差异（d ≥ -0.15）；
3. T4 迁移测验：treatment 不显著低于 comparison（d ≥ -0.2）；
4. C4 风险指标不高于 comparison（ai_dependency 无上升）；
5. 代写命中率 ≤ 5%。

> 注意：允许阈值用"不显著低于对照"而不是"显著高于"，因为目标常是"在不损害学习的
> 前提下获得效率红利"，高估是更危险的错误。

## 6. 常见陷阱与检查

| 陷阱 | 检查 |
| --- | --- |
| 只用 AI 环境成绩定成功 | 必须有无 AI 的 post/retention/transfer 测量 |
| 后测即用训练题 | 后测、保持、迁移必须与训练题不同 |
| 无基线对照 | T0 必须测量，否则不能归因 |
| 只报平均分不报方差 | 报告分布与效应量，警惕少数人拉高均值 |
| 实验组额外获得辅导 | 记录辅导时间，作为 confounder 控制 |

## 7. 评价示例（C 语言 4 阶段试点）

```
research_question: 8 周分阶段 AI 使用政策是否影响大一 C 语言学生
                   的独立编程能力、保持、迁移与 AI 依赖？
groups:
  treatment: 试点班 60 人（4 阶段政策）
  comparison: 平行班 60 人（全程禁止 AI，同教材同教师）
baseline: T0 无 AI 前测（语法知识 20 题 + 独立编程 3 题），两组基线可比性卡方检验
post_test: T2 无 AI 独立编程测验（新题 4 道，覆盖指针/数组/函数）
retention_test: T3（+3 周）同难度新题 4 道（无 AI）
transfer_test: T4 用 C++ 实现链表反转（无 AI，教师未教过该语法）
process_metrics: 上机活跃时长、求助 AI 次数、Phase2/3 越界使用次数、NASA-TLX
learning_metrics: T2/T3/T4 得分（C1）；T2 与 T0 差 = knowledge_gain
risk_metrics: 撤除 AI 后独立完成率、代写检测率、依赖自评（4 题量表）
analysis_plan: 独立样本 t 检验 + Cohen's d；risk 指标做秩和检验；
               T3/T4 为关键检验（防即时红利假象）；FDR 校正
success_threshold:
  - T2 d ≥ -0.1 且 T3 d ≥ -0.15 且 T4 d ≥ -0.2（treatment 不低于 comparison）
  - C4 无上升（依赖自评与撤除后完成率不劣于 comparison）
  - 代写命中率 ≤ 5%
stop_conditions:
  - 任意阶段无 AI 独立题正确率低于基线 15% 连续 2 周
  - 越界使用完整代码生成比例 > 40%
  - 代写命中率 > 10%
```

## 8. 报告最小清单

评价报告必须包含：测量时间轴、各组人数与 dropout、每条指标的组间差（含效应量与
置信区间）、retention 与 transfer 结果、C4 风险结果、对照 success_threshold 的逐条判定。
