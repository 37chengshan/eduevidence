# 效应量合成 · 发表偏倚 · 稳健性检验 —— 方法学说明

> EduEvidence 证据合成层的方法学补充说明（v4）。核心立场：**合成产出的是
> 可复核的方向性结论，而不是被包装成统计权威的数字** —— 引擎只聚合证据中
> 真实存在的信息，绝不外推或编造效应量。

## 一、效应量合成（Effect-Size Synthesis）

1. **方向性聚合 + 独立研究计数**：合成在 Study 级投票，不以 Finding 条数计权
   （`independence_key` 去重：同一研究的 5 条 Finding 只算 1 个独立研究）。
   判定语义（`engine/synthesis.py`）：仅支持 → `supported`；仅反驳 →
   `refuted`；正反独立研究并存 → `contested`；无决定性可用研究 →
   `insufficient`。
2. **效应量是报告元数据，不是计算原料**：研究如实报告效应量（如 Cohen's d、
   OR）时，其方向与显著性进入 Finding 的方向判定；未报告效应量的研究（如
   质性案例）被如实降级为"感知/态度发现"，绝不按经验猜测补一个数字。
3. **效应量合成（v4 已实现，engine/meta_analysis.py）**：固定效应（inverse-variance）
   与随机效应（DerSimonian-Laird，Q/τ²/I²）双口径合并 + 森林图数据。合并结果是辅助证据
   （synthesis report），**不替代**方向判定——教育证据异质性大，主裁决仍以方向一致性与
   独立研究覆盖为准，规则化置信度公式（0.30 质量 + 0.25 一致性 + 0.20 直接性 + 0.25 独立研究数
   − 冲突罚 − 未支持罚）不变。

## 二、发表偏倚（Publication Bias）

1. **Skeptic 反方检索**：八角色协议中 Skeptic 的职责是主动寻找、验证并记录
   null / negative 结果与替代解释；没有反方证据时明确输出
   `NO CONTRADICTORY EVIDENCE FOUND`，禁止虚构"双边观点"。
2. **负面结果强制收录**：检索到的 null / negative 计入一致性分量与冲突罚分
   （任一反对采纳的证据即触发 0.15 冲突罚），偏倚不会让结论"看起来更稳"。
3. **来源分层与降级**：来源按真实身份分层（DOI 可解析判 tier1，否则 tier5 +
   incomplete），检索/验证全链路留痕。发表偏倚无法根除、只能被暴露 —— 报告
   如实呈现证据缺口与检索范围，供决策者自行判断。

## 三、稳健性检验（Robustness Checks）

1. **leave-one-study-out 敏感性（v4 已实现，engine/robustness.py）**：逐次剔除单一
   独立研究后重算合并效应；方向翻转或 CI 跨零 → 标签 fragile，否则 robust。
2. **置信度扰动**：对质量 / 一致性 / 直接性 / 数量四个分量做 ± 一档权重扰动，
   检查阈值边界（High≥.72 / Moderate≥.45 / Low≥.20）附近的判定稳定性。
3. **跨模型交叉评审**：Draft Verdict 在终审前由独立模型（不同模型/CLI）复核，
   契约见 `schemas/cross-model-review.schema.json`；不一致项进入
   `disagreements / required_revision`，属 v4 可信度方向进行中能力。

## 四、边界声明

- 合成与稳健性检验是**审计指数**（内部纪律），不是概率或统计显著性声明；
- 任何数值（效应量、置信度分数）都可从 `evidence.jsonl` 复算，不依赖模型"感觉"；
- 方法学纪律的完整定义见 `docs/methodology.md` 与 `docs/architecture.md`。
