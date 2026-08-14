# 活证据工作流（Living Evidence）

> v3 Decision-to-Outcome Loop 与 v4 迭代节奏的方法学说明。核心观点：
> **证据不是一次性产物，而是随试点数据持续更新的活证据** —— 每次试点运行
> 都会产生新的证据图修订，决策随证据一起演化。

## 一、什么是活证据

传统综述产出"定格"的结论；EduEvidence 把证据流程接成回路：
PILOT 决策 → 真实数据 → 分析 → 图更新 → 再裁决 → 新决策。教育干预的效果
只有回到真实课堂才能被确认，活证据工作流让每次试点都成为一次"证据体检"。

## 二、闭环流程（engine/pilot.py）

1. **注册 PilotRun**：PILOT 决策（DecisionSnapshot）绑定试点运行记录
   （`schemas/v3/pilot-outcome.schema.json`）。
2. **导入结果数据**：匿名化试点结果导入；**PII 列（姓名 / 学号 / 邮箱 / 电话）
   在导入时被拒绝**，学生数据永远留在本地。
3. **分析链接**：AnalysisRun 状态须为 `validated`，否则返回
   `ANALYSIS_INVALID` 且证据图保持不变。
4. **原子图更新**（engine/update.py）：项目本地 Source + Study + Findings +
   MethodologyAudit + Claims/Links 在**单个图修订（revision）**内一次提交，
   绝不分条提交；修订不可变、可追溯。
5. **再裁决**：tribunal 基于含试点证据的新修订重新裁决，产出新
   DecisionSnapshot 与机器可读 diff，旧决策保留完整追溯链。

## 二·补 v4 文献订阅与漂移（engine/living.py）

v4 把活证据从"试点数据回填"扩展到"**文献级持续监控**"：

1. **订阅决策**：`eduevidence living subscribe --decision <DEC> --term <检索词>`
   将某个 DecisionSnapshot 与其检索式绑定（`schemas/v4/living-subscription.schema.json`）。
2. **增量刷新**：`eduevidence living refresh --subscription <SUB>` 注入新证据
   （人工/agent 提供 evidence JSONL，或 retriever 适配器对接真实检索层）；
   新证据按内容 hash 幂等去重后**单次图修订**提交。
3. **漂移报告**：tribunal 重裁决后产出 `project/living/drift/<DRF>.json`
   （`schemas/v4/drift-report.schema.json`）：新旧决策 diff + 新证据摘要 +
   **建议动作 confirmed / changed / needs_review**。引擎**绝不自动改判**——
   改判必须由人走再裁决门。
4. **失败可恢复**：若刷新中途失败（图已提交但订阅未记账），重试同一证据
   会按图内实体幂等跳过并恢复 hash 记账（review P1-1）。

数据流：DecisionSnapshot + 订阅 → 增量证据 → 图 revision n+1 → 漂移报告 →
人决策（改判/维持/补充检索）。

## 三、跨项目活证据

- **Shared Research Library**：经核验的外部事实以不可变快照导入，事实可复用、
  解释留在项目内；
- **meta_synthesis**（`engine/meta_synthesis.py`）：把一个库修订的已核验事实
  聚合为 outcome 级概览（正向 / 负向 / 零效应 + 独立研究键），只读投影、不改库。

## 四、自动化保障（CI）

- `schema-smoke`：三 pack 的活证据产物（verdict / evidence / intervention /
  methodology / frame / evaluation / result）全量过 schema，契约漂移即失败；
- `upload-build`：SKILL.md 一致性 + 零泄漏检查，保证发布包与仓库同步；
- 活证据产物始终以 schema 契约形式落盘，可审计、可复算。

## 五、更新节奏

| 层级 | 更新频率 | 触发 |
|------|----------|------|
| 研究级（Project） | 每次试点 | PILOT 数据回填 → 再裁决 |
| 库级（Library） | 快照导入 | 新核验事实入库 |
| 发布级（Upload） | 每次发布 | CI upload-build |

活证据工作流是 v4「可信度 × 通用智能」路线的引擎侧支撑：结论不是终点，
持续可验证的决策过程才是。
