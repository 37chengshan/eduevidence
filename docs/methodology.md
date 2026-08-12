# EduEvidence 教育证据方法学

方法学层回答"如何把一条教育问题变成一份可信、可追溯、可复核的证据决策"。核心观点：**教育决策的可信度不来自模型更强，而来自方法学纪律**。本文档定义八角色协议、复杂度分级（Complexity Gate）与置信度规则化计算。

## 〇、V2 Research Engine 方法学升级

- **独立研究计数**：合成与置信度只在 Study 级计数（`independence_key`）；同一研究的 5 条 Finding = 1 个独立研究，绝不构成 5:1 投票。
- **三语义严格分离**：`Finding.effect_direction`（研究观察到什么）/ `EvidenceLink.relation_to_claim`（是否支持该 Claim）/ `EvidenceLink.decision_implication`（对当前决策的含义）永不混用；"支持负面 Claim"不会被画成正向教学效果。
- **V2 置信度政策（2026-08-12.v3）**：`0.30×方法质量 + 0.25×研究级一致性 + 0.20×Directness + 0.25×独立研究数 − 冲突罚分(仅独立正反研究并存) − 不确定性罚分`；High≥.72 / Moderate≥.45 / Low≥.20 / 其余 Insufficient。Directness 不再重复计权；分数是内部审计指数，不是概率。
- **KnowledgeGap 结构化**：缺口从图覆盖度推导（frame 请求的 outcome vs 图内实际测量），不是自由文本"未来工作"；任务表现 Finding 永远不能覆盖保持/迁移缺口。
- **方法学门槛**：usable Study 要求有效/部分接受来源、可解析身份、最新审计非 fail；任何新研究设计必须先通过证据奠基门。

## 一、八角色协议（Eight-Role Protocol）

EduEvidence 将完整证据流程拆成八个独立职责（Role），每个角色有明确任务、输入与产出。角色是"职责单元"，不是必须独立运行的进程。

| # | 角色（Role） | 任务 | 关键产出 |
|---|--------------|------|----------|
| 1 | Education Planner | 把模糊的教育问题结构化为研究问题与决策目标 | Education Research Frame |
| 2 | Evidence Retriever | 依据 Frame 的 scope 与 inclusion criteria 检索来源 | 候选来源列表（含 source_location） |
| 3 | Evidence Analyst | 从来源中抽取 Claim 级证据，按 schema 结构化 | Evidence Object（evidence_id） |
| 4 | Skeptic | 主动寻找负面结果、反驳证据、未发现与 confounder | Contradiction List、Knowledge Gap |
| 5 | Method Reviewer | 审计每篇研究的方法学质量，检查"任务完成≠学习" | Methodology Audit（PASS/CONCERN/FAIL） |
| 6 | Evidence Judge | 汇总证据、判定结论、输出 Verdict 与置信度 | Education Verdict + Confidence |
| 7 | Intervention Designer | 把 Verdict 落成最小可验证干预（默认偏向最小可验证 PILOT） | Teaching Intervention Plan |
| 8 | Evaluation Designer | 为试点设计评估方案，分离 Task vs Learning | Evaluation Plan |

### 1.1 角色数量 ≠ Agent 数量

- **角色是分工**：八角色定义的是"必须做满的八件事"，防止遗漏检索、反方证据或方法学审计。
- **Agent 是实现**：一个 Agent（一次模型调用）可以顺序承担多个角色；也可以一个角色由多个 Agent 并行承担（如多个检索器并行 Retrieve）。
- **两种映射示例**：
  - Single-Agent 模式：一个模型依次扮演全部 8 个角色，靠提示词切换视角；
  - Multi-Agent 模式：Education Planner / Retriever / Analyst 由轻量模型承担，Skeptic 与 Evidence Judge 由强推理模型承担，Intervention/Evaluation Designer 可再并行。

### 1.2 关键角色说明

- **Skeptic**：证据流程中最容易被省略、也最有价值的一环。Skeptic 的职责是主动**寻找、验证和记录**反方证据、null result 与替代解释：该研究是否有自选偏倚（self-selection）？效果是否来自 novelty effect？是否存在负面结果被丢弃？没有 Skeptic 的综述是"单边证据"。**禁止为形成"双边观点"虚构反方证据**；没有反方证据时明确输出 `NO CONTRADICTORY EVIDENCE FOUND`。
- **Method Reviewer**：不判断证据"说什么"，只判断证据"站不站得住"。核心铁律：**task performance 不得自动等同为 learning effect**——作业完成快不等于学会了。
- **Evidence Judge**：是所有角色的最终仲裁者，输出 `what_can_be_claimed` 与 `what_cannot_be_claimed` 两张清单，并明确"超出证据边界"的结论（exceeds_evidence_boundary）。

## 二、Complexity Gate：S/M/L 判级与执行路径

先给教育问题分级，再决定投入多少证据流程深度，避免"小题大做"或"大题浅做"。步骤命名统一采用完整 10 步工作流（`SKILL.md` §6 与 `docs/architecture.md` §1.2）：1 Frame / 2 Retrieve / 3 Fetch / 4 Validate / 5 Extract / 6 Challenge / 7 Audit / 8 Adjudicate / 9 Design（Applicability + Intervention + Evaluation）/ 10 Present；EvidenceFlow Core = Frame → … → Adjudicate，Decision Extension = Applicability → Intervention → Evaluation。

| 级别 | 判定条件（满足其一即升级） | 执行路径 |
|------|------------------------------|----------|
| **S（Small）** | 单门课程内的常规教学决策；现有证据充足；无高风险后果 | 快速路径：Frame → Retrieve（少量）→ Fetch/Validate（关键来源）→ Extract（≤5 条）→ Verdict；可跳过完整 Skeptic 与 Method Reviewer，用规则化置信度兜底 |
| **M（Medium）** | 跨课程/跨专业适用；存在正反两派证据；涉及评价体系变更 | 标准路径：Frame → Retrieve → Fetch/Validate → Extract → Challenge → Audit → Adjudicate，八角色全走一遍 |
| **L（Large）** | 全校/培养方案级决策；涉及学术诚信政策；证据高度冲突或缺失 | 深度路径：标准路径 + 系统化检索（含反向检索）+ 独立 Skeptic 与双人 Method Review + Intervention 与 Evaluation 设计强制产出 |

### 2.1 判级输入

- 决策影响范围（单班 / 单课 / 跨课 / 全校）；
- 决策后果严重度（学生成绩、学术诚信、培养质量）；
- 证据成熟度（是否已有高质量 RCT / meta-analysis）。

### 2.2 设计意图

Complexity Gate 保证：**S 级问题不烧钱**，**L 级问题不偷工**。默认门控为 M，输入信息不足时按上一级从严处理。

## 三、Confidence 规则化计算

置信度不是模型的"自我感觉"，而是可分解、可复核的规则化结果。Verdict 的 `confidence` 字段取值为 `High / Moderate / Low / Insufficient`。

### 3.1 计算公式

```
Confidence Score = Evidence Quality
                 + Consistency
                 + Directness
                 + Evidence Count
                 - Conflict Penalty
                 - Unsupported Penalty
```

| 分量 | 含义 | 取值说明 |
|------|------|----------|
| Evidence Quality | 证据质量 | 由各证据 `quality_score`（0-10）与 evidence_level（strong/moderate/weak/very_weak）聚合 |
| Consistency | 方向一致性 | 多条证据方向（support/contradict/neutral）一致的加分，方向分散的扣分 |
| Directness | 直接性 | 证据是否直接针对目标 learner/subject/tool/usage（D5_directness） |
| Evidence Count | 证据数量 | 证据条数越多越稳定，但设置上限避免"堆数量" |
| Conflict Penalty | 冲突惩罚 | Skeptic 找到的反驳证据/负面结果数量越多，惩罚越大 |
| Unsupported Penalty | 未支持惩罚 | status 为 UNSUPPORTED（缺 mandatory 字段）或 DOWNGRADE_CONFIDENCE 的对象占比越高，惩罚越大 |

### 3.2 阈值映射

| 得分区间 | 置信度 | 决策含义 |
|----------|--------|----------|
| 高分段 | **High** | 证据充分且一致，可支持 ADOPT 或确定性高的 PILOT |
| 中分段 | **Moderate** | 方向基本一致但有缺口，倾向 PILOT |
| 低分段 | **Low** | 证据薄弱或冲突明显，必须 PILOT 且设置严格 Stop Conditions |
| 不足段 | **Insufficient** | 证据缺失或方法论不过关，输出 INSUFFICIENT EVIDENCE，先补证据再决策 |

### 3.3 规则化设计的价值

1. **可复核**：任何第三方都能用同一公式从 evidence.jsonl 重新算出置信度，不依赖"模型感觉"。
2. **可诊断**：得分低时能精确指出是质量问题、冲突问题还是覆盖不足。
3. **可抑制幻觉**：Unsupported Penalty 让"编造来源、编造结论"的对象直接拉低置信度，从结构上惩罚幻觉。
4. **与 Verdict 联动**：置信度高低决定 recommended_action 的倾向（adopt / pilot / reject / insufficient_evidence）。

## 四、方法学铁律（Methodological Guardrails）

1. **任务完成 ≠ 学习**：task_completion 只计入 process metrics，不单独构成学习证据。
2. **短期 ≠ 长期**：Immediate 效应必须与 Retention、Transfer 分开报告。
3. **无对照组 ≠ 因果**：没有 control_group 或 randomization 的研究降级证据等级。
4. **负面结果必须收录**：Skeptic 检索到的 null/negative 结果计入 Consistency 与 Conflict Penalty。
5. **默认偏向最小可验证 PILOT**：Intervention Designer 默认产出最小可验证 Pilot；只有关键 Outcome 存在较强直接证据、风险可控且场景高度匹配时才允许 ADOPT（且必须附带 Evaluation Design）。

八角色协议、Complexity Gate 与规则化置信度共同构成 EduEvidence 的方法学骨架，是 Benchmark（docs/benchmark.md）中被 A/B 验证的核心变量。
