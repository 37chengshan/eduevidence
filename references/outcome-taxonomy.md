# Outcome Taxonomy（学习结果分类）

## 0. 三条核心不等式（必须遵守）

```
任务完成 ≠ 学习          （Task completion ≠ Learning）
短期 ≠ 长期保持          （Short-term ≠ Long-term retention）
AI协助 ≠ 无AI迁移        （Performance with AI ≠ Transfer without AI）
```

这三条是解读任何教育研究证据的默认假设。任何声称"AI 有效/无效"的结论，
必须先说明它测量的是哪一类 Outcome，否则结论不可采信。

## 1. 四类 Outcome 与指标清单

### C1 学习效果（Learning Effects）——回答"学到了什么"

| 指标 | 说明 | 测量示例 |
| --- | --- | --- |
| `knowledge_gain` | 知识增量 | 前后测知识题得分差 |
| `concept_understanding` | 概念理解深度 | 概念解释题、错误概念辨识 |
| `retention` | 长期保持 | 结课 2–4 周后的延迟测验 |
| `transfer` | 迁移到新情境 | 换语言/换题型/无 AI 环境的新任务 |
| `independent_problem_solving` | 独立解题能力 | 闭卷、无 AI 环境中完成新题 |

> 这是 primary outcome 的首选来源。判断"是否允许用 AI"主要看 C1。

### C2 任务表现（Task Performance）——回答"任务做得怎样"

| 指标 | 说明 | 测量示例 |
| --- | --- | --- |
| `completion_time` | 完成时间 | 从开始到通过所有测试的时间 |
| `accuracy` | 正确率 | 测试通过率、题面覆盖率 |
| `code_quality` | 代码质量 | 可读性、结构、命名、冗余度 |
| `assignment_score` | 作业/考试成绩 | 常规评分（含 AI 参与环境） |

> C2 最容易测量，也最容易误导：用 AI 当然快而准。C2 改善**不能**推断出 C1 改善。

### C3 学习过程（Learning Process）——回答"学习如何发生"

| 指标 | 说明 | 测量示例 |
| --- | --- | --- |
| `engagement` | 投入度 | 上机活跃时长、任务尝试次数 |
| `motivation` | 动机 | 自评量表、课程留存率 |
| `cognitive_load` | 认知负荷 | NASA-TLX、学后疲劳自评 |
| `help_seeking` | 求助行为 | 求助 AI vs 求助教师/同伴的比例 |
| `metacognition` | 元认知 | 能否解释自己的思路、是否先规划再动手 |

### C4 风险指标（Risk Indicators）——回答"代价是什么"

| 指标 | 说明 | 测量示例 |
| --- | --- | --- |
| `ai_dependency` | AI 依赖 | 无 AI 条件下完成任务的能力降幅 |
| `over_reliance` | 过度依赖 | 求助 AI 的频率/比例、跳过思考步骤的行为 |
| `reduced_effort` | 努力下降 | 思考时间缩短、照抄输出 |
| `reduced_transfer` | 迁移下降 | 无 AI 新题得分低于对照组 |
| `academic_integrity_risk` | 学术诚信风险 | 代写检测、抄袭代码比例 |
| `false_confidence` | 虚假自信 | 高估自身能力而低估对 AI 的依赖 |

## 2. 证据绑定规则（每条证据必须绑定一个 Outcome）

### 规则（必须遵守）

| 编号 | 内容 |
| --- | --- |
| OT-01 | 每条证据/数据必须标注其 Outcome 类别与具体指标名，格式：`Outcome = C1/knowledge_gain`。 |
| OT-02 | 未标注 Outcome 的结论一律视为不可验证，不得进入 Evidence Matrix。 |
| OT-03 | 一项测量只能属于一类 Outcome；例如"用 AI 时的完成时间"属 C2，不能同时当作 C1。 |
| OT-04 | 结论中使用哪个指标，就必须声明该指标属于哪类，禁止跨类互换表述。 |
| OT-05 | 若证据只覆盖 C2，则结论只能谈任务表现，禁止外推为"学习效果得到改善"。 |
| OT-06 | 涉及 AI 工具的结论，必须同时报告至少一项 C1（学习）与至少一项 C4（风险）。 |

### 证据绑定示例

```
证据 1（实验组比对照组提交更快）：
  Outcome = C2/completion_time → 结论：AI 提高了任务效率。
  ✗ 不得改写为"AI 提高了学习效果"。

证据 2（四周后无 AI 独立测试两组无差异）：
  Outcome = C1/independent_problem_solving → 结论：短期任务效率优势未转化为独立能力。

证据 3（对照前测后均无下降，实验组无 AI 时错误明显增多）：
  Outcome = C4/ai_dependency → 结论：存在依赖风险，需限制使用方式。
```

## 3. 结果解读矩阵（Outcome 组合怎么解读）

| C2（任务表现） | C1（学习/迁移） | C4（风险） | 建议解读 |
| --- | --- | --- | --- |
| 上升 | 上升 | 无风险 | 正面证据，可考虑推广 |
| 上升 | 持平 | 无风险 | 工具可作效率提升，但勿声称"学得更快" |
| 上升 | 持平 | 有风险 | 效率红利伴随依赖，需设计防依赖策略 |
| 上升 | 下降 | — | **危险信号**：成绩好但没学会，优先查 C4 |
| 持平/下降 | 上升 | 无风险 | 慢但扎实，视课程目标取舍 |
| 上升 | 上升 | 有风险 | 需长期跟踪 retention/transfer 再下结论 |

## 4. 最小报告要求

任何"AI 使用政策"相关结论至少包含：

1. 一个 C1 指标（知识/理解/保持/迁移/独立解题）；
2. 一个 C4 指标（依赖或诚信）；
3. 明确区分"有 AI 时表现"与"无 AI 时表现"。

缺少以上任一 → 结论降级为"待验证假设"。
