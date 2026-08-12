# Failure Matrix — EduEvidence 失败状态与处理矩阵

> 对应 `SKILL.md` §Failure Handling（Phase 33）。**核心原则：出现以下任一状态时，
> 禁止强行生成高确定性建议；如实标注失败状态，执行处理动作，输出对应降级状态，
> 再决定是否继续流程。** 每条状态都可以被确定性逻辑检测/触发（见"检测点"），
> 行为约束由 `tests/test_skill_behavior.py`（Scenario A–G）离线验证，不依赖 LLM。

## 速查表

| 失败状态 | 触发条件 | 处理动作 | 输出状态 |
|---|---|---|---|
| `INSUFFICIENT_SOURCES` | 来源数量/直接性/研究设计强度不足，无法支撑结论 | 补充检索或标注 insufficient_evidence；拒绝 ADOPT | `INSUFFICIENT` 或 `PILOT`（有积极证据时） |
| `UNSUPPORTED_CLAIM` | 结论无法绑定到可验证来源（缺 evidence/source/location，或证据与结论方向矛盾） | Citation Audit 标记 `UNSUPPORTED`，降级或丢弃该结论 | 结论降级/不输出；`confidence` 被惩罚 |
| `CONFLICT_UNRESOLVED` | 正反证据冲突且无法用方法学/样本/场景差异解释 | 保持不确定，不强行裁决；冲突计入 penalty | `INSUFFICIENT` / 结论标注"冲突未解决" |
| `SCOPE_MISMATCH` | 证据适用范围与目标场景不匹配（学习者/课程/干预/Outcome） | 缩小结论边界；Audit 标记 `DOWNGRADE_CONFIDENCE` | 结论范围收窄，置信度降级 |
| `METHODOLOGY_TOO_WEAK` | 研究设计过弱（D1–D5 质量不足），不能支撑结论 | 不作为支持证据使用 | 该证据不计入支持；`INSUFFICIENT` |
| `NEEDS_USER_CONTEXT` | 缺少学习者/课程/干预/Outcome 等最小输入 | 先请求用户补充，再继续 | 流程暂停，输出待补充问题清单 |
| `TOOL_FAILURE` | 检索或工具调用异常（异常/超时/权限） | 如实报告，不编造来源；重试或换工具 | `TOOL_FAILURE` 记录，不产生 Evidence |
| `FETCH_FAILED` | 网页抓取全链失败（含降级链耗尽、SSRF 拦截） | 不重试同一 URL；回 Discovery 找替代来源 | `FETCH_FAILED`，跳过抽取，来源缺失 |
| `AGENT_MCP_APPROVAL_REQUIRED` | Agent MCP 已安装但模型表未确认（允许的 CLI/模型组合未获用户确认） | 不得 spawn；先与用户确认模型表；未安装则退化为 Platform Native Mode | 不派发任何 agent；`platform_native` 降级 |
| `REPORT_INVALID` | 展示层数据与 result.json 不一致（Schema 校验失败 / Claim 绑定失败 / 数字不一致 / 完整性门 FAIL） | 禁止发布，修复数据后重跑渲染 | 不产出报告文件，退出码非 0 |
| `PRE_VERDICT_FAILED` | 裁决前门失败：verdict Schema 校验失败 / Cross-Model Review 缺失或不合格 / 方法学审查未过 | 修复裁决前置产物后重新执行前门 | 不输出裁决（Verdict 缺失） |

## 各状态详述

### 1. INSUFFICIENT_SOURCES

- **触发条件**：证据数量不足、直接性差（D5 低）、研究设计弱（D1–D4 低）、或冲突无法解释，
  使规则化 confidence 达不到 High/Moderate。
- **检测点**：`scripts/compute_confidence.py` / `scripts/evidence_score.py` → `confidence == "Insufficient"`（或 `Low`）。
- **处理动作**：提示用户补充检索；或按四态矩阵输出 `INSUFFICIENT`；若存在积极证据但长期效果/迁移/风险不明，
  降级为 `PILOT`（必须附 Evaluation Plan）。
- **输出状态**：`INSUFFICIENT` / `PILOT`；禁止 `ADOPT`。
- **测试**：`test_g_adopt_refused_when_confidence_insufficient`、`test_g_empty_evidence_never_yields_adopt`。

### 2. UNSUPPORTED_CLAIM

- **触发条件**：结论无法绑定可靠来源——claim 无 `evidence_ids`、证据缺失、
  evidence 缺 `source_id`/`source_location`、或证据方向与结论矛盾（`contradict`）。
- **检测点**：`scripts/claim_audit.py` → `audit_claims()` 返回 `status == "UNSUPPORTED"`；
  同时 `confidence` 的 Unsupported Penalty（`min(0.20, 0.05 × n)`）生效。
- **处理动作**：降级或丢弃该结论；不得把无来源证据写进报告。
- **输出状态**：该 claim 不进入最终报告；`confidence` 下降。
- **测试**：`test_a_skipping_evidence_cannot_produce_supported_conclusion`、
  `test_f_fabricated_evidence_without_source_is_rejected`、
  `test_e_counter_evidence_is_detected_and_priced_in`。

### 3. CONFLICT_UNRESOLVED

- **触发条件**：支持与反对证据并存，且无法用研究设计、样本、场景差异解释分歧。
- **检测点**：`evidence_score.consistency_score` < 1.0 且存在 `contradict` 方向 →
  Conflict Penalty `0.15` 计入 confidence。
- **处理动作**：保持不确定，不强行裁决（"stay_uncertain_do_not_force_adjudication"）；
  在 Conflict Analysis 中如实呈现分歧。
- **输出状态**：confidence 受罚；裁决倾向 `INSUFFICIENT`；结论标注"冲突未解决"。
- **测试**：`test_e_counter_evidence_is_detected_and_priced_in`。

### 4. SCOPE_MISMATCH

- **触发条件**：证据的适用范围（applicability.scope）不覆盖 claim 声称的范围
  （如证据只覆盖"编程作业任务表现"，结论却声称"提升整体学习效果"）；
  或 claim 的 `outcome_type` 与证据不一致。
- **检测点**：`scripts/claim_audit.py` → issue "claim scope ... exceeds source scope" /
  "outcome mismatch" → `status == "DOWNGRADE_CONFIDENCE"`。
- **处理动作**：缩小结论边界到证据覆盖的范围；任务表现 ≠ 学习效果、短期 ≠ 长期保持。
- **输出状态**：结论范围收窄，置信度降级。
- **测试**：`tests/test_claim_audit.py`（`test_downgrade_on_scope_exceed`、
  `test_downgrade_on_outcome_mismatch`）。

### 5. METHODOLOGY_TOO_WEAK

- **触发条件**：研究设计质量过低——五维评分（D1 研究设计 / D2 样本 / D3 测量效度 /
  D4 时间强度 / D5 直接性）不足，或方法学审查（15 项清单）未通过。
- **检测点**：`evidence_score.quality_score()` → `quality_level` ∈ {`weak`, `very_weak`}；
  Method Reviewer 清单存在 FAIL。
- **处理动作**：该证据不作为支持使用（"do_not_use_as_support"）；必要时在报告中标注方法学局限。
- **输出状态**：证据从支持池移除；confidence 相应降低。
- **测试**：`tests/test_evidence_score.py`（`test_quality_levels` 等）。

### 6. NEEDS_USER_CONTEXT

- **触发条件**：缺少最小输入——`education_question` 缺失，或学习者/课程/干预/目标 Outcome 信息不足，
  无法构建 Education Research Frame。
- **检测点**：Frame 构建校验（`schemas/education-frame.schema.json`）失败。
- **处理动作**：先请求用户补充信息再继续，不猜测默认值。
- **输出状态**：流程暂停；输出待补充问题清单（人机协作，Human-in-the-Loop）。

### 7. TOOL_FAILURE

- **触发条件**：检索或工具调用异常（provider 超时、网络异常、权限错误、内部错误）。
- **检测点**：异常被 `handle_tool_failure` 捕获 → `TOOL_FAILURE`；
  不产生任何 Evidence 对象。
- **处理动作**：如实报告失败（不编造来源）；按需重试或更换工具。
- **输出状态**：`TOOL_FAILURE` 记录；该步骤产出为空，流程不假装成功。
- **测试**：`test_f_tool_failure_reported_without_evidence`。

### 8. FETCH_FAILED

- **触发条件**：网页抓取全链失败——内置/Jina Reader/Defuddle/Markdown.new 全部失败，
  或降级链被 SSRF 防护中断（如重定向到私网地址）。
- **检测点**：`retrieval/failures.py` → `classify_fetch()` 返回 `FETCH_FAILED`；
  `recovery_plan()` 的 `retry == False`。
- **处理动作**：**不无限重试同一 URL**；回 Discovery 找同一论文/事实的替代来源；
  抓取结果无内容时不进入 Evidence 抽取。
- **输出状态**：`FETCH_FAILED` 标注；该来源缺失；如有人伪造无来源证据，
  Citation Audit 必然拒绝（`UNSUPPORTED`）。
- **测试**：`test_f_fetch_failure_marks_state_and_never_extracts`、
  `test_f_partial_fetch_requires_confirmation_before_extraction`。

### 9. AGENT_MCP_APPROVAL_REQUIRED

- **触发条件**：Agent MCP 已安装且 daemon 可达，但**模型表未确认**——允许派发的
  CLI/模型组合尚未获得用户确认。
- **检测点**：`gate_agent_mcp_spawn(installed=True, model_table_confirmed=False)`
  → `AGENT_MCP_APPROVAL_REQUIRED`（`tests/test_skill_behavior.py` Scenario B）。
- **处理动作**：**不得 spawn 任何 agent**；先与用户确认模型表；
  若未安装则输出 `AGENT_MCP_UNAVAILABLE` 并退化为 Platform Native Mode
  （单 Agent 串行执行 8 角色协议，行为不中断）。
- **输出状态**：`spawn_calls == []`；模式为 `platform_native`；Cross-Model Review
  降级为 `native_self_review`（无 `spawn_call`）。
- **测试**：`test_b_installed_without_model_table_confirmation_blocks_spawn`、
  `test_b_unavailable_degrades_to_native_self_review`。

### 10. REPORT_INVALID

- **触发条件**：展示层与数据层不一致——result.json/result.zh.json Schema 校验失败、
  Claim-Evidence-Source 审计失败、图表数字与 result.json 不一致、
  完整性门（`no_axis_distortion` 等）FAIL。
- **检测点**：`visualization/eduevidence-report/scripts/build_report.py` 的前置门
  → 输出 `REPORT_INVALID — ...` 并返回退出码 2。
- **处理动作**：**禁止发布报告**；修复数据后重跑渲染（"block_publish_rerun_render"）。
- **输出状态**：不产出报告 HTML；流程显式失败。
- **测试**：`tests/test_build_report_html.py`（`test_integrity_fails_when_numbers_tampered` 等）。

### 11. PRE_VERDICT_FAILED

- **触发条件**：裁决前门失败——Verdict 未通过 `schemas/verdict.schema.json` 校验、
  或 Cross-Model Review 缺失/不合格、或方法学审查未完成即尝试出裁决。
- **检测点**：`scripts/validate_schema.py` 对 verdict 的校验；Cross-Model Review
  状态非 `READY` 且未降级确认。
- **处理动作**：修复裁决前置产物（补充独立审核、修正 verdict 字段）后重新执行前门；
  不得带着失败的前门输出裁决。
- **输出状态**：不输出裁决（Verdict 缺失）；流程停在 Adjudicate 步骤之前。

## 与 SKILL.md §Failure Handling 的映射

| SKILL.md 状态 | 矩阵状态 |
|---|---|
| INSUFFICIENT_SOURCES | #1 INSUFFICIENT_SOURCES |
| UNSUPPORTED_CLAIM | #2 UNSUPPORTED_CLAIM |
| CONFLICT_UNRESOLVED | #3 CONFLICT_UNRESOLVED |
| SCOPE_MISMATCH | #4 SCOPE_MISMATCH |
| METHODOLOGY_TOO_WEAK | #5 METHODOLOGY_TOO_WEAK |
| NEEDS_USER_CONTEXT | #6 NEEDS_USER_CONTEXT |
| TOOL_FAILURE | #7 TOOL_FAILURE / #8 FETCH_FAILED |
| —（enhanced mode §8） | #9 AGENT_MCP_APPROVAL_REQUIRED / AGENT_MCP_UNAVAILABLE |
| —（报告契约 §27/§60） | #10 REPORT_INVALID |
| —（裁决前门） | #11 PRE_VERDICT_FAILED |

## 测试覆盖（tests/test_skill_behavior.py）

| Scenario | 行为约束 | 覆盖状态 |
|---|---|---|
| A | 跳过论文必须拒绝，不可直接结论 | `UNSUPPORTED_CLAIM`、`INSUFFICIENT_SOURCES` |
| B | 已安装但未确认模型表不得 spawn | `AGENT_MCP_APPROVAL_REQUIRED`、`AGENT_MCP_UNAVAILABLE` |
| C | 只允许 Codex + OMP 时只派发这两个 CLI | 派发约束（无失败状态） |
| D | 拒绝的模型不进入推荐 | 推荐约束（无失败状态） |
| E | 只找支持证据也必须做反方检索 | `CONFLICT_UNRESOLVED`、`UNSUPPORTED_CLAIM` |
| F | 抓取失败不编造来源 | `FETCH_FAILED`、`FETCH_PARTIAL`、`TOOL_FAILURE` |
| G | 证据不足强求 ADOPT → 拒绝高置信度 | `INSUFFICIENT_SOURCES` → `INSUFFICIENT`/`PILOT` |
