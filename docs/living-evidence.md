# 活证据工作流（Living Evidence）

> **证据不是一次性产物，而是持续修订的决策状态。** EduEvidence vNext 把活证据扩展为两类更新：新证据到来时被动/订阅式更新，以及由当前 KnowledgeGap 主动选择“下一条最值得寻找的证据”。

## 一、三条相互区分的闭环

```text
Evidence Autoresearch
Gap → bounded search experiment → GraphRevision → Decision drift → next Gap

Decision-to-Outcome
Decision → Pilot → Data → Analysis → GraphRevision → DecisionSnapshot

Skill Autoresearch
repository hypothesis → candidate → protected eval → keep/revert
```

前两条改变现实研究 Project；第三条只改变研究系统候选代码，绝不能碰真实用户 Project。

## 二、试点数据回注

1. **注册 PilotRun**：PILOT DecisionSnapshot 绑定试点运行记录。
2. **导入结果数据**：匿名化结果导入；PII 列在导入时拒绝或要求去标识。
3. **分析链接**：AnalysisRun 必须 validated；不可估计时 fail closed。
4. **原子图更新**：项目本地 Source + Study + Finding + Audit + Claim/Link 在受控 GraphRevision 中提交；旧 Revision 不覆盖。
5. **再裁决**：基于新 Revision 产生新的 DecisionSnapshot/diff。新数据不要求强行改变 action；certainty/applicability/boundary 改变也是有效 revision。

## 三、文献订阅与增量刷新

`engine/living.py` 保留现有语义：

```text
DecisionSnapshot subscription
→ incremental evidence
→ content-hash dedupe
→ GraphRevision n+1
→ drift report
→ review / maintain / revise
```

搜索结果摘要仍只用于发现，必须通过 fetch/provenance/validation/extraction 才能进入证据状态。

## 四、主动 Evidence Autoresearch

Living Evidence 不再只依赖预先写死的 query terms。需要主动继续研究时：

```text
Project + current GraphRevision + DecisionSnapshot
→ derive grounded KnowledgeGaps
→ conceptual DVI ranking
→ select ONE decision-relevant Gap
→ ONE bounded ResearchStrategy
→ validated evidence append or no-gain/negative-search memory
→ re-adjudicate
→ repeat until bounded stop
```

详细规则见 `references/autoresearch.md`。

关键边界：

- DVI 只输出 HIGH/MEDIUM/LOW 和可解释 drivers，不伪装成 EVPI/EVSI。
- Validated Evidence append-only，不因不利于当前 verdict 而删除。
- No-gain ResearchIteration 不制造 GraphRevision。
- 同一 Gap 的失败策略会轮换，避免重复撞同一路径。
- Search saturation 需要连续低收益 + strategy diversity exhaustion。
- 只有 HIGH-DVI、decision-material、仍 unresolved、secondary search saturated 且伦理/可行性允许，才可进入 `EMPIRICAL_EVIDENCE_NEEDED`；随后仍必须通过现有 StudyDesign grounding gate。

## 五、Single Writer

主动检索可以并行，但 canonical state transition 串行：

```text
parallel workers
→ staging artifacts
→ schema/provenance/scientific gates
→ Single Writer
→ GraphRevision
```

Subagent 不直接写 GraphRevision、DecisionSnapshot、KnowledgeGap persistent state、StudyDesign 或 PilotRun。

## 六、跨项目活证据

- Shared Research Library 保存经核验的外部事实快照；事实可复用，解释保持 project-local。
- `engine/meta_synthesis.py` 对库修订做只读 outcome-level projection，不替代项目 Decision。
- Evidence Autoresearch 的 ResearchIteration memory 保持 project-local，避免一个项目的失败搜索直接变成另一个项目的事实。

## 七、自动化保障

- `CI / schema-smoke`：当前完整 example packs 通过原有 schema 契约。
- `Autoresearch Gates`：检查科学宪法、S/M/L orchestration、Single Writer、vNext schemas、wheel subpackages 和 benchmark partition contract。
- `autoevolve-nightly`：仅在显式配置外部 Agent/Evaluator 后运行，branch-only；绝不自动 merge/release/deploy。
- Evidence/Decision 与 Skill evolution 权限物理分离。

## 八、更新节奏

| 层级 | 触发 | 结果 |
|---|---|---|
| Project passive refresh | 新文献/订阅证据 | GraphRevision + drift |
| Project active research | HIGH-value KnowledgeGap | bounded ResearchIteration(s) |
| Project empirical | grounded saturated Gap | Pilot/Data → GraphRevision |
| Library | 新核验事实快照 | Library revision |
| Skill evolution | 维护者/定时 opt-in | autoresearch branch candidate |
| Release | 人工确认 | main/release |

结论不是终点；**可追溯、可挑战、可更新且有停止条件的决策过程**才是 EduEvidence 的长期状态。
