# Applicability Analysis（适用性分析）

## 1. 目的

裁判庭（tribunal-policy.md）得出"结论可以成立"之后，还需回答最后一个问题：
**这个结论能用在我的场景吗？** 适用性分析把结论从其原研究情境映射到目标情境，
明确边界，避免盲目照搬。

## 2. 核心原则

```
证据只对其检验过的  learner × course × outcome × tool × context  组合严格成立；
组合中任一维度变化，成立强度都要降级。
```

## 3. 七问检查（Applicability Check）

对每条可成立结论逐一回答七个问题：

| 问题 | 检查内容 | 判定输出 |
| --- | --- | --- |
| For whom? | 原研究学习者与目标学习者是否一致（层次/专业/先验/特征）？ | 一致 / 部分一致 / 不一致 |
| Which course? | 学科、课程类型、时长、难度是否匹配？ | 一致 / 部分一致 / 不一致 |
| Which outcome? | 结论的 Outcome 与你的目标结果是否同类（见 outcome-taxonomy.md）？ | 同类 / 相关但不同类 / 不同类 |
| What conditions? | 班级规模、线上线下、教师支持是否可比？ | 可比 / 部分可比 / 不可比 |
| How long? | 干预时长与研究时长是否可比（短期结论不宜外推到长期）？ | 可比 / 更长 / 更短 |
| What teacher support? | 你能否提供与研究相当的教师/助教支持？ | 具备 / 需额外投入 / 不具备 |
| What AI usage policy? | 你能执行的 AI 使用规范（allowed_usage）是否与研究一致？ | 可执行 / 需调整 / 不可执行 |

## 4. 输出结构

```yaml
applicability:
  conclusion: <被评估的可成立结论>
  suitable_for:
    - <明确匹配的组合，如: 大一 C 语言、代码补全型工具、线下小班、有助教、8 周试点>
  not_suitable_for:
    - <明确不匹配的组合及其原因>
  required_conditions:
    - <要落地该结论必须具备的条件，如: 需要 AI 使用日志、需要受限账号>
  teacher_requirements:
    - <教师所需能力与投入，如: 教师需掌握工具配置、需每周答疑 2 小时>
  student_prerequisites:
    - <学生的先决条件，如: 需先完成顺序/分支/循环三大语法单元>
  usage_constraints:
    - <可执行的使用边界，如: 禁止完整代码生成、实验课外使用需登记>
  risk_factors:
    - <落地后需监控的风险，如: 依赖指标上升、代写行为增加>
```

## 5. 执行规则

| 编号 | 规则 |
| --- | --- |
| AP-01 | 七问中任一"不一致"，必须在输出中显式降级结论置信度或缩小 suitable_for 范围。 |
| AP-02 | `not_suitable_for` 不允许留空偷懒；即使无明确证据，也需列出"未验证的组合"作为待验证项。 |
| AP-03 | `usage_constraints` 必须与 Frame 的 `intervention.allowed_usage` 一致，不得凭空放宽。 |
| AP-04 | `risk_factors` 必须与 Frame 的 `outcomes.risk` 对应；新增风险需说明依据。 |
| AP-05 | 若目标场景与研究场景差异过大（如工具类型不同），即使原研究是 `strong`，也只能给 `moderate` 或 `low` 的外推置信度。 |

## 6. 示例：把"Copilot 提高作业正确率"结论应用到另一所学校

```
conclusion: "Copilot 可提高 AI 环境下大一 C 语言作业正确率（C2/accuracy）"
           ——原研究: 线下小班 60 人、有助教、8 周、受限账号 + 使用日志。

applicability:
  suitable_for:
    - 线下实验课、班级 ≤ 80 人、有助教、有 AI 使用日志监控的同类课程
    - 能提供与 8 周相当的试点期的课程
  not_suitable_for:
    - 2000 人 MOOC（无教师监控，日志缺失）
    - 纯线上自学课程（无对照班与监督）
    - 要求学生"先独立完成再求助"的作业模式（与研究的使用方式冲突）
  required_conditions:
    - 为每个学生配置可审计的受限 AI 账号
    - 保留每周作业的无 AI 独立版本以跟踪 C1
  teacher_requirements:
    - 教师须完成工具使用培训
    - 助教每周 2 学时答疑，负责核查使用日志
  student_prerequisites:
    - 学生已掌握指针之前的语法基础（实验内容不超过研究覆盖范围）
  usage_constraints:
    - 仅允许代码补全与报错解释；禁止完整代码生成
    - 实验课内使用，课外使用需登记
  risk_factors:
    - 每周跟踪 C4/ai_dependency；若独立题正确率连续 2 周下降则触发暂停
```
