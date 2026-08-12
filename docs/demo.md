# 主 Demo：大一 C 语言课程能否使用生成式 AI 编程助手

Demo 的核心叙事：**"能更快完成作业"≠"编程学得更好"**。EduEvidence 通过证据检索、Skeptic 反驳与方法学审计，把一个看似"方便就该允许"的问题，收敛为一个带 Stop Conditions 的分阶段 PILOT。

## 一、演示问题与决策链路

- **输入问题**："大一 C 语言课程是否允许学生使用 GitHub Copilot 这类生成式 AI 编程助手？"
- **Frame 关键要素**：undergraduate_year_1、CS major、第一门编程课、授课 16 周、允许范围为"全程随意使用" vs "仅查错/无 AI 对照组"。
- **最终结论**：`PILOT`（非 ADOPT、非 REJECT）+ 阶段化 AI 使用规则 + 8 周评估方案。

## 二、Demo 高光点（必须让观众看见的五个瞬间）

### 高光 1：Completion Speed↑ ≠ Programming Learning↑

检索命中多篇研究：允许 Copilot 的实验组完成作业更快（completion_time 显著下降），但**同一批学生在无 AI 环境下的独立编程成绩没有提升甚至下降**。画面呈现：左侧时间轴（作业完成快 40%），右侧学习结果（retention/transfer 平或负）——一升一平的对照是全场第一印象。

### 高光 2：Immediate vs Retention vs Transfer

Evidence Matrix 中按时间维度拆列：

| 维度 | 观测结果 |
|------|----------|
| Immediate（当堂任务） | 完成速度与正确率↑ |
| Retention（4-8 周延迟测验） | 记忆保持无明显优势 |
| Transfer（无 AI 新任务） | 迁移能力下降（reduced_transfer、over_reliance） |

一句话高光：**"现在变快了，考试时变慢了"**——即时收益与长期学习收益必须分开计量。

### 高光 3：Skeptic 主动找负面结果

Skeptic 不顺着"允许"找支持，而是主动检索 null / negative 结果：ai_dependency、false_confidence、reduced_effort、academic_integrity_risk。界面上以红色"反驳卡片"弹出，随后 Evidence Matrix 相应列被标记为 CONFLICT。**这段是观众第一次意识到"这不是生成式咨询，是证据仲裁"。**

### 高光 4：Method Reviewer 指出"任务完成 ≠ 学习"

Method Reviewer 审计关键研究：对照组是否有 self-selection？作业正确率是否被当成"学会"的证据？审计输出 `task_vs_learning_guard: equates_task_with_learning = true`，将该研究标记 CONCERN 并降级。**规则被点名的时刻，就是方法学价值被看到的时刻。**

### 高光 5：最终 PILOT + 阶段化 AI 使用规则

Verdict = `PILOT`，置信度 `Moderate`（证据方向基本一致但 retention/transfer 有缺口）。随后给出阶段化规则：

- Phase 1（第 1-4 周）：**AI 禁用于编程，先打语法与算法基础**；允许用 AI 解释报错。
- Phase 2（第 5-8 周）：**作业允许 AI 辅助，但必须提交"AI 使用日志"与"逐行讲解"**。
- Phase 3（第 9-16 周）：**限时无 AI 测验**评估独立编程能力。
- 贯穿：Stop Conditions（若 retention/transfer 指标下滑即回退 Phase 1）+ 期末无 AI 环境代码考核。

## 三、180 秒时长结构表

| 时间段 | 阶段 | 画面要点 |
|--------|------|----------|
| 0-20s | 输入问题 | 用户输入"大一 C 语言能否用 AI 编程助手"；Ask 页展示问题与决策目标 |
| 20-45s | Frame | Frame 页结构化：learner / course / intervention / comparison / outcomes / scope |
| 45-75s | 检索 | Evidence 页逐条出现来源卡（source_id、年份、study_type、source_location），并行检索动效 |
| 75-110s | Evidence Matrix | 生成证据矩阵：按 outcome_type 分组、direction 着色、quality 标注 |
| 110-135s | Methodology + Skeptic | Skeptic 红色反驳卡弹出，Method Reviewer 审计栏标 CONCERN，证据降级 |
| 135-155s | Tribunal | Evidence Judge 输出 Verdict：supported / cannot / missing + Confidence 分解条 |
| 155-170s | Intervention + Evaluation | 阶段化 PILOT 规则 + 8 周评估设计（Retention/Transfer/无 AI 测验） |
| 170-180s | Benchmark | 收尾展示 B2 vs B3 vs B4 指标对比，说明"没有方法学就不会有刚才那套结论" |

## 四、UI 五页面设计

| 页面 | 核心组件 | 交互亮点 |
|------|----------|----------|
| Ask | 问题输入框、决策目标选择（evidence_review / teaching_decision / pilot_design / evaluation_design） | 一键示例填充、历史问题（Memory Bank） |
| Frame | Frame 表单（learner/course/intervention/comparison/outcomes/scope） | 自动抽取建议、Conflict 提示（问题太宽泛） |
| Evidence | 来源卡片流、Evidence Matrix、过滤（direction/quality/outcome_type） | 点击卡片展开原文 claim、悬停显示 source_location |
| Verdict | supported / cannot be claimed / missing 三栏 + Confidence 分解条形图 + recommended_action | 每项可反查证据；点击"超出证据边界"警告 |
| Action | 阶段化 PILOT 时间线、Stop Conditions、Evaluation Plan 卡片 | 导出 Research & Decision Pack 按钮 |

## 五、可视化优先级

按信息密度从高到低排序，画面资源有限时按此取舍：

1. **Evidence Matrix**（最高优先）：方向×结果维度矩阵，红绿着色，一眼看懂"哪里一致、哪里冲突"。
2. **Confidence 分解条**：Evidence Quality / Consistency / Directness / Count − Conflict − Unsupported 的规则化构成。
3. **Immediate vs Retention vs Transfer 对比**：三列柱状图，直击"短期收益 vs 长期学习"。
4. **Skeptic 反驳卡**：红色高亮，制造戏剧冲突，强化"主动找反方"。
5. **PILOT 阶段时间线**：Phase 1→2→3 与 Stop Conditions 的路径。
6. **来源卡元数据**：study_type、sample_size、education_level 小标签。
7. **Benchmark 对比尾图**：仅作收尾，不占主叙事。

原则：**让"证据的一致与冲突"优先可见，让"模型的输出过程"退到幕后**。可视化目标是让观众在 180 秒内复现推理，而不是看动画。

## 六、Demo 叙事一句话

> "更快完成 ≠ 学得更好；短期便利 ≠ 长期能力。EduEvidence 用证据、质疑与方法学审计，把教学决策从'感觉'变成'可追溯的 Pilot'。"
