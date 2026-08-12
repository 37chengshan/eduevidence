# Education Research Framing（教育研究框架）

## 1. 为什么先 Frame 再回答

教育问题的答案高度依赖上下文：同一个干预（例如"允许学生使用 AI 编程助手"）
在一个班级是脚手架，在另一个班级可能变成依赖源。脱离 Frame 直接回答，
等于把某篇论文的结论盲目套用到一个未必匹配的课堂。因此本框架规定：

- **任何最终教学建议都必须由一个完整的 EducationResearchFrame 推导而来。**
- Frame 不完整时，只能给出"需要补充哪些信息"的中间反馈，禁止生成最终建议。

### 执行规则（必须遵守）

| 规则编号 | 内容 |
| --- | --- |
| FR-01 | 回答教育问题前，先输出 EducationResearchFrame；缺失任一必填字段则框架不完整。 |
| FR-02 | 框架完整前，禁止输出最终教学建议（含"建议允许/不允许""建议调整策略"等结论性语句）。 |
| FR-03 | 框架内不得出现"待定""TBD""占位符"；未知信息应明确标注 `unknown + 如何获取`。 |
| FR-04 | Frame 与证据（Evidence）必须一起呈现：先 Frame，再 Evidence，最后结论。 |

## 2. EducationResearchFrame 字段清单

### question（研究问题）

- 用一句话表述，必须包含"干预 × 学习者 × 结果"三要素。
- 示例：`"在 Python 入门课中，允许使用 AI 代码补全是否会影响学生的独立编程能力？"`

### decision_target（决策目标）

- 本次回答要支持的具体决策，例如"是否允许某工具""是否采用某教学法""是否调整某门课的评分规则"。
- 一个 Frame 只服务一个 decision_target；多目标请拆分为多个 Frame。

### learner（学习者）

- `education_level`：小学 / 初中 / 高中 / 大学本科（大一…大四）/ 研究生 / 成人 / 职业培训。
- `major`：专业或院系背景（如计算机、非计算机、人文社科），影响先前经验假设。
- `prior_knowledge`：目标技能的前测水平描述（如"未系统学过编程，仅会打字与上网"）。
- `special_characteristics`：特殊特征（如高年级占比、性别比例、民族/语言差异、学习障碍、班内基础两极分化）。

### course（课程）

- `subject`：学科（如 C 语言、数据结构、线性代数）。
- `course_type`：课程类型（必修/选修、理论/实验/混合、项目制、MOOC）。
- `duration`：课程总时长（如 16 周、一学期 48 学时、两周集训营）。

### intervention（干预）

- `teaching_method`：教学方法（讲授、翻转课堂、项目式、同伴教学等）。
- `ai_tool`：具体 AI 工具及版本（如 GitHub Copilot v1.x、ChatGPT GPT-4o、Cursor；未指定版本视为不完整）。
- `allowed_usage`：允许的使用方式（禁止使用 / 仅解释报错 / 局部生成须注释 / 完全放开）。
- `frequency`：使用频率（每节课几次、每周上限）。
- `duration`：干预持续时长（如 4 周、一整个学期）。

### comparison（对照组）

- 与什么比较：无 AI 传统教学 / 无 AI 但加强练习 / 不同 AI 策略。
- 若缺失对照，只能得到描述性结果，不能得到因果结论。

### outcomes（结果）

- `primary`：主要结果，通常是"学习效果"类指标（见 outcome-taxonomy.md），一个为佳。
- `secondary`：次要结果（任务表现、学习过程指标）。
- `risk`：风险指标（AI 依赖、学术诚信风险等），必须至少列出并监控一项。

### context（情境）

- `teacher_support`：教师支持程度（有无助教、教师是否懂 AI、答疑频次）。
- `class_size`：班级规模（20 人小班 / 100 人大班 / 2000 人 MOOC）。
- `online_or_offline`：线上 / 线下 / 混合。

### scope（证据检索范围）

- `time_range`：文献时间范围（如 2015–2025，AI 教育研究时效性强，优先近 3 年）。
- `geography`：地域范围（国内 / 欧美 / 全球；注意文化差异）。
- `study_types`：纳入的研究类型（RCT、准实验、观察性、质性）。

### inclusion_criteria / exclusion_criteria（纳入/排除标准）

- 纳入标准示例：`样本为本科编程入门课；干预与 AI 工具相关；报告至少一个学习结果指标。`
- 排除标准示例：`仅报告满意度或工具使用时长；样本为研究生及以上；干预时长不足 2 周。`

### success_condition（成功条件）

- 判断"该干预值得继续/推广"的可操作标准，例如：
  `"迁移测试成绩无显著下降（效应量 -0.1 以内）且 AI 依赖风险指标不升高，即可继续试点。"`

## 3. 示例 Frame：大一C语言课是否允许使用AI编程助手

```
question: 在大一 C 语言程序设计必修课中，允许学生使用 AI 编程助手
          （自动补全 + 完整代码生成）是否会影响其独立编程能力与课堂作业诚信？
decision_target: 决定该课程本学期的 AI 使用政策（禁止 / 受限允许 / 放开）
learner:
  education_level: 大学本科一年级
  major: 非计算机专业（电子信息类）
  prior_knowledge: 无编程基础；高中信息课仅接触 Office；前测 0-1 道题可独立完成
  special_characteristics: 班内基础差异大，约 30% 学生畏难、倾向直接抄答案
course:
  subject: C 语言程序设计
  course_type: 必修、含 2 学时/周实验课
  duration: 16 周（一学期）
intervention:
  teaching_method: 讲授 + 上机实验 + 每周编程作业
  ai_tool: GitHub Copilot（指定版本）+ 课堂专用受限账号（无登录历史）
  allowed_usage: 待评估——本次回答的决策对象
  frequency: 每周作业 1 次，实验课 2 学时
  duration: 8 周（试点阶段）
comparison: 同期不启用 AI 的平行班（同教材同教师）
outcomes:
  primary: 期末独立编程题得分（无 AI 环境考试）
  secondary: 作业正确率、完成时间、课堂参与度
  risk: 脱离 AI 后能否独立改错；作业代写检测；学生对 AI 的依赖自评
context:
  teacher_support: 1 名教师 + 1 名研究生助教；教师已通过 AI 工具培训
  class_size: 约 60 人 / 班
  online_or_offline: 线下实验课 + 线上提交作业
scope:
  time_range: 2019–2025
  geography: 国内高校 + 欧美本科入门编程课研究
  study_types: RCT、准实验、有对照的前后测研究
inclusion_criteria: 本科入门编程课；干预涉及代码补全/生成类 AI；报告学习或迁移指标
exclusion_criteria: 仅报告"学生满意度"或"使用时长"；干预不足 2 周；样本为研究生
success_condition: 8 周试点后，独立编程题得分与对照班无显著差异（下降不超 5%），
                  且 AI 依赖风险指标不高于对照组，则允许受限使用；否则维持禁止。
```

## 4. 框架使用顺序

1. 用户提出教育问题 → 先把问题翻译成 `question + decision_target`。
2. 逐一核对全部字段；缺信息时向用户提问或标注 `unknown + 获取途径`。
3. 字段齐全后，才允许检索证据、构建 Evidence Matrix。
4. 最后基于 Frame 输出建议，并明示该建议仅对该 Frame 有效（见 applicability-policy.md）。
