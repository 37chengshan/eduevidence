# Intervention Design（干预设计）

## 1. 最小可验证试点原则

**不允许"直接全面部署"**。任何新的 AI 使用政策必须先做小规模、有时间上限的试点：

- 范围小：1–2 个班（或 ≤ 120 人），覆盖目标 learner 的代表性子集；
- 周期短：4–12 周，有明确结束节点；
- 目标明确：只验证一个 decision（如"是否允许某种 AI 用法"）；
- 全程测量：试点期间必须采集 C1/C2/C3/C4 指标（见 outcome-taxonomy.md）；
- 有出口：达到 stop_conditions 立即暂停或回退。

> 试点不是"试试看"，而是带有预先注册假设与退出条件的受控实验。

## 2. TeachingIntervention 字段

| 字段 | 说明 |
| --- | --- |
| `decision` | 本干预要支撑的决策（必须与 Frame 的 decision_target 一致） |
| `target_learners` | 试点对象（班级、层次、先验水平） |
| `learning_goals` | 2–3 条可测量的学习目标（绑定 C1 指标） |
| `pilot_duration` | 试点总时长与各阶段时长 |
| `phase_1/2/3` | 阶段化设计：每阶段的 目标 / AI 用法 / 教师角色 / 学生任务 |
| `ai_usage_policy` | 每阶段允许与禁止的 AI 用法（允许使用逐条列出） |
| `teacher_role` | 教师在各阶段做什么（讲解、监督、反馈） |
| `student_role` | 学生各阶段的任务与责任 |
| `reflection_requirement` | 学生需提交的反思（如每周解释自己的解题思路、标注 AI 使用部分） |
| `assessment` | 过程评估与结果评估的测量方式与时间点 |
| `risk_control` | 风险指标清单与监控频率 |
| `stop_conditions` | 触发暂停/回退的具体阈值条件 |

## 3. 示例：C语言课 4 阶段试点（8 周，2 个班各 60 人）

### 阶段总览

| 阶段 | 时间 | 主题 | AI 用法 |
| --- | --- | --- | --- |
| Phase 1 | 第 1–2 周 | Independent Foundation | 禁止使用 AI |
| Phase 2 | 第 3–4 周 | Explain Don't Solve | 允许解释报错，禁止生成代码 |
| Phase 3 | 第 5–6 周 | Structured Collaboration | 允许局部生成，必须解释关键逻辑 |
| Phase 4 | 第 7–8 周 | Transfer Check | 无 AI 新任务（评估迁移） |

### Phase 1 Independent Foundation（禁止完整代码生成）

- **目标**：学生独立掌握 顺序/分支/循环 三大语法，形成基础能力基线。
- **AI 用法**：实验课全程禁用 AI；作业同样禁用。
- **教师角色**：逐个检查上机基础操作；对卡壳学生给提示不给代码。
- **学生任务**：独立完成 4 个基础编程作业；提交时附上思路草稿。
- **评估**：第 2 周末基线测验（无 AI），记录 `independent_problem_solving` 基线。

### Phase 2 Explain Don't Solve（允许解释报错）

- **目标**：学习"读错误信息 + 定位问题"的诊断技能。
- **AI 用法**：仅允许粘贴报错信息让 AI 解释错误含义；**禁止**让 AI 给出修复代码或完整解决方案。
- **教师角色**：抽查学生是否越界使用；示范"报错解读 → 自己改"的流程。
- **学生任务**：每道错题先自行尝试 15 分钟，再使用"解释报错"通道。
- **评估**：记录 help_seeking 比例与无 AI 诊断小测。

### Phase 3 Structured Collaboration（允许局部生成须解释关键逻辑）

- **目标**：在受控范围内体验协作式开发，同时保持理解责任在学生。
- **AI 用法**：允许 AI 生成**局部代码片段**（单个函数体）；但提交时必须在每个 AI 生成处
  标注，并用自然语言解释该段的关键逻辑（如"为什么用指针传参"）。
- **教师角色**：批改时重点检查"AI 标注 + 解释"是否真实，随机抽问解释。
- **学生任务**：完成 2 个综合作业（数组、函数、指针应用），附 AI 使用清单。
- **评估**：记录 `code_quality`、`reflection_requirement` 完成率。

### Phase 4 Transfer Check（无AI新任务）

- **目标**：检验迁移能力与依赖程度（对应 C1/transfer 与 C4/ai_dependency）。
- **AI 用法**：全禁 AI；任务为**新题型/新语言环境**（如改用 C++ 实现同样算法）中的全新题目，
  与训练题不重复。
- **教师角色**：监考式无 AI 测验；统计 AI 撤除后的表现对比。
- **学生任务**：完成迁移测验 + 依赖自评问卷。
- **评估**：`transfer_test` 成绩与 Phase 1 基线对比；C4 指标报告。

### 阶段公共字段

- `ai_usage_policy`（汇总）：Phase1 禁用；Phase2 仅报错解释；Phase3 局部生成+强制解释；
  Phase4 禁用。所有阶段禁止用 AI 完成整份作业或生成答案文本。
- `reflection_requirement`：每阶段结束提交 200 字反思，回答"我用了 AI 吗？用了哪一步？
  删掉 AI 我还能做吗？"。
- `risk_control`：每周汇总 C4 指标（ai_dependency / over_reliance / false_confidence）。
- `stop_conditions`（任一触发即暂停，退回上一阶段或中止试点）：
  1. 无 AI 独立题正确率连续 2 周低于 Phase 1 基线 15% 以上；
  2. 代写检测命中率 > 10%；
  3. 超过 40% 学生在 Phase 2 越界使用完整代码生成；
  4. 学生虚假自信自评（高自信 + 低实绩）比例超过 30%。

## 4. 试点执行规则

| 编号 | 规则 |
| --- | --- |
| ID-01 | 试点必须预先写明 stop_conditions 并在每阶段检查，禁止事后补写。 |
| ID-02 | 每个阶段结束做一次 mini-evaluation（≤ 20 分钟），数据进 Evidence Matrix。 |
| ID-03 | 试点期间禁止同时调整教材、教师、工具等多变量；一次只变 AI 用法。 |
| ID-04 | 试点结果无论正负都需走 skeptic-protocol.md 的 9 项检查后再决定是否扩大。 |
| ID-05 | 全面部署只有在试点满足 success_condition 且适用性分析（applicability-policy.md）通过后才能讨论。 |
