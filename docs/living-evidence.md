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
