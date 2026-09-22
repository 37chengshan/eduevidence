# Jev 生态实验模式（Experimental Jev / SemDecide Tier-0）

> **实验性加速层，不是科学门。** Tier-0（screen / rerank / extract / classify / verify）
> 只做窄域类型化判断，**不替代** `scripts/pre_verdict_gate.py`、Skeptic 九项检查、
> 方法学审计与 Tribunal。不确定 / 非法结果 **fail-closed** 升级大模型。
>
> 入口开关：`--experimental <0|1|2|3>` 或 `EDU_EXPERIMENTAL_JEV=<mode>`。
> 密钥仅存 `~/.eduevidence/env`（`AI_GATEWAY_API_KEY` + `JEV_PROVIDER=vercel`，可选
> `TYPESAFE_API_KEY`；或 FreeJev：`FREEJEV_API_KEY` + `JEV_PROVIDER=freejev`），
> **禁止写入仓库**。

## 1. 定位

| 组件 | 实现 | 上游 |
|---|---|---|
| `integrations/jev_mcp.py` | detect → approval → urllib 调 Vercel AI Gateway `typesafe-ai/jev` | TypeSafe System One / `@jkudish/jev-mcp` |
| `integrations/semantic_decide.py` | subprocess `semdecide is / filter / choose` | [sharziki/semdecide](https://github.com/sharziki/semdecide) |
| `engine/capabilities.py` | 注册 5 个实验能力（`experimental_capability_registry()`；默认科学注册表不含它们，避免协议角色门误伤） | 本仓库能力注册表 |
| `skill/workflows/experimental-jev.md` | 模式 / 九阶段映射 / fail-closed | Skill 工作流覆盖层 |

原则（与 agent-mcp 一致）：**检测 → 推荐 → 用户确认 → 调用 → 降级**。不迁移、不复制
上游实现；上游不可用时整体退回 Platform Native / mode 0，科学协议不变。

## 2. 启用方式

```bash
# 0) 密钥（本地，勿提交）
# ~/.eduevidence/env
#   # Vercel AI Gateway 路径
#   export AI_GATEWAY_API_KEY=...
#   export JEV_PROVIDER=vercel
#   # 或 FreeJev 路径
#   export FREEJEV_API_KEY=...
#   export JEV_PROVIDER=freejev

# 1) 检测
python3 integrations/jev_mcp.py --experimental 3
python3 integrations/semantic_decide.py --experimental 3

# 2) 用户确认门 → ~/.eduevidence/jev_mcp_approval.json
python3 integrations/jev_mcp.py --experimental 3 --approve

# 3) 运行时打开 overlay
eduevidence run --question "..." --run-id <id> --experimental 3
# 或 export EDU_EXPERIMENTAL_JEV=3
```

| Mode | 名称 | 后端 |
|---:|---|---|
| 0 | standard | 仅大模型（默认，无 `--experimental`） |
| 1 | jev-mcp | FreeJev / Vercel Gateway urllib **或** 文档化 MCP |
| 2 | semdecide | `semdecide is / filter / choose` |
| 3 | hybrid | 1 + 2 |

### Provider（Mode 1 / 3）

| `JEV_PROVIDER` | 密钥 | Decide 端点 | 备注 |
|---|---|---|---|
| `freejev` | `FREEJEV_API_KEY` | `https://freejev.org/api/v1/decide` | 仅 `FREEJEV_API_KEY` 时可自动选中 |
| `vercel`（默认） | `AI_GATEWAY_API_KEY`（或 `TYPESAFE_API_KEY`） | `https://ai-gateway.vercel.sh/typesafe/v1/systemone` | `model=typesafe-ai/jev` |

MCP 备选（不自动 spawn，仅文档化）：

```bash
# FreeJev MCP
#   https://freejev.org/mcp   + FREEJEV_API_KEY
# npx 包路径
claude mcp add jev -- npx -y @jkudish/jev-mcp
# 通用 JSON：npx -y @jkudish/jev-mcp + TYPESAFE_API_KEY / AI_GATEWAY_API_KEY
python3 integrations/jev_mcp.py --mcp-guide
```

**FreeJev `request_id` 不重试。** Decide 调用的 `request_id` 是幂等键：同一
`request_id` **禁止重试**（超时 / 5xx / 未知结果一律不重发）。本调用
fail-closed 升级大模型；若业务上必须再问一次，使用**新的** `request_id` 发起
新调用，并单独记录 provenance。

## 3. Tier-0 API 列表

传输：`POST` 到 provider decide 端点（Vercel System One 或 FreeJev），
`Authorization: Bearer $AI_GATEWAY_API_KEY` / `$FREEJEV_API_KEY`，
`model=typesafe-ai/jev`。
请求体 TypeSafe System One：`{ model, state, questions }` → `{ model, answers, usage }`。
FreeJev 另带 `request_id`（见上：**不重试**）。

| # | Python API | capability_id | MCP 工具 | SemDecide 对应 | 问题形态 | 默认阈值 |
|---|---|---|---|---|---|---|
| 1 | `jev_mcp.screen(text, purpose)` | `content_screen` | `jev_screen` | — | 3× Noul：injection / substance / relevance | `block_at=0.75`, `review_at=0.25` |
| 2 | `jev_mcp.rerank(query, candidates)` | `semantic_rerank` | `jev_rerank` | — | 1× Noul / candidate | `auto_accept=0.70` |
| 3 | `jev_mcp.extract(document, fields)` | `field_extract` | `jev_extract` | — | 1× Choice / field（regex 候选 + `none_of_them`） | `auto_accept=0.80`, `margin=0.40` |
| 4 | `jev_mcp.classify(items, classes)` | `classify_check` | `jev_classify` | `choose` 可路由 | 1× Choice / item | `auto_accept=0.85`, `margin=0.50` |
| 5 | `jev_mcp.verify(claims, evidence)` | `claim_verify` | `jev_verify` | `is` 可预筛 | 1× Choice / claim：supports / contradicts / says_nothing | `auto_accept=0.80` |

统一入口：`jev_mcp.safe_call(capability_id, ...)`（先过 approval 门）。

SemDecide 封装（exit 2/3/4 → 升级大模型）：

| API | CLI | 用途 |
|---|---|---|
| `semdecide.is_predicate(text, predicate)` | `semdecide is` | 语义谓词 |
| `semdecide.filter_records(records, predicate)` | `semdecide filter` | JSONL 语义过滤（保序） |
| `semdecide.choose_route(text, question, options)` | `semdecide choose` | 命名选项路由 |

### 状态与 fail-closed（与 `integrations/semantic_decide.py` 对齐）

Jev / Tier-0：

| 状态 | 含义 | 管道行为 |
|---|---|---|
| `ok` + `action/auto` | 可自动采用（仍不是科学门） | 记录 provenance，继续阶段 |
| `review` / `not_found` / `JEV_INVALID_RESPONSE` | 低置信或非法答案（envelope 缺 `answers` 等） | **升级大模型**；extract 的 `review` 值不得当作已抽取 |
| `JEV_APPROVAL_REQUIRED` | 无/错 approval | 不发网络请求 |
| `JEV_UNAVAILABLE` | 无密钥 / 无可用传输 | 本调用升级大模型；hybrid 可切 mode 2 切片 |
| `JEV_PROVIDER_ERROR` | 上游失败（HTTP 401/403/429/529/5xx） | 本调用升级大模型；FreeJev **`request_id` 不重试** |

SemDecide（`EXIT_MEANINGS` / `ESCALATE_EXIT_CODES={2,3,4}`）：

| exit / status | `EXIT_MEANINGS` | 管道行为 |
|---|---|---|
| `0` | `true/selected/match` | 语义结果可用 |
| `1` | `false/no match` | 语义结果可用；`filter` 的 exit 1 **不**单独升级 |
| **`2`** | `invalid input` | 修输入重跑，或整段决策**升级大模型**（`escalate_plan`） |
| **`3`** | `uncertain` | **升级大模型 / 人工**；禁止强行 true/false |
| **`4`** | `provider failure` | **升级大模型**（仅本调用）；记录 attempt |
| `SEMDECIDE_UNAVAILABLE` | binary 缺失 / spawn 失败 | **升级大模型**（`requires_llm_escalation`） |
| `SEMDECIDE_TIMEOUT` | 超时 | **升级大模型**（`result.escalate=ESCALATE_TO_LLM`） |

`screen` 的 recommendation（pass / review / block / skip）仅为咨询；拦截执行权在调用方。

## 4. 阈值

| 参数 | 默认 | 调节建议 |
|---|---:|---|
| `screen_block_at` | 0.75 | 注入概率 ≥ 则 block（咨询） |
| `screen_review_at` | 0.25 | 注入概率 ≥ 则 review |
| `verify_auto_accept` | 0.80 | 关系裁决 confidence ≥ 才 `auto` |
| `classify_auto_accept` | 0.85 | top 概率门槛 |
| `classify_minimum_margin` | 0.50 | 冠亚军差门槛（二者同时满足才 auto） |
| `extract_auto_accept` | 0.80 | 字段挑选 confidence |
| `extract_minimum_margin` | 0.40 | 候选差门槛；失败 → `review` |
| `rerank_auto_accept` | 0.70 | 相关 Noul 门槛 |
| SemDecide `--threshold` | 0.70 | `is` / `filter` |
| SemDecide `--min-confidence` | 0.70 | `choose`；低于则 exit 3 |
| SemDecide `--uncertainty-margin` | 0.0 | 边缘区不强行二值化 |

阈值是起点（TypeSafe cookbook 基线），**先在自有数据上校准再强制**。

## 5. 九阶段映射（加速点）

`frame → retrieve → extract → challenge → audit → adjudicate → applicability → intervene → evaluate`

| 阶段 | Jev Tier-0 | SemDecide | 不变的科学门 |
|---|---|---|---|
| Frame | — | `choose` 可选 | frame schema |
| Retrieve | screen / rerank / classify | `filter`, `is` | 检索计划 + 反方检索 + Fetch/Validate |
| Extract | extract / classify | `is` 预检 | Evidence Objects、task ≠ learning |
| Challenge | **verify 仅辅助** | `is` 辅助 | **Skeptic 九项检查** |
| Audit | verify 辅助 | `is` 预筛 | 方法学审计 + guard |
| Adjudicate | —（禁止 Tier-0 定裁决） | — | **Pre-Verdict Gate** + 四态裁决 |
| Applicability | classify 可选 | `choose` 可选 | 人群/条件/排除/不确定性 |
| Intervene | — | — | intervention_design |
| Evaluate | — | — | evaluation_design / data_validation |

完整矩阵见 `skill/workflows/experimental-jev.md`。

## 6. 加速比口径（speedup）

只比较**同一问题、同一 Complexity Gate、同一九阶段协议**下 mode 0 基线 vs 实验模式。

| 指标 | 定义 | 统计范围 |
|---|---|---|
| `T_stage` | 单阶段 wall-clock（s），从进入阶段到产物过 schema/gate | 仅计 **gate 通过** 的阶段 |
| `T_run` | Frame→Applicability（或声明的阶段子集）累计 | 同上 |
| `speedup_stage` | `T_stage(mode0) / T_stage(exp)` | per stage |
| `speedup_run` | `T_run(mode0) / T_run(exp)` | per run |
| `cost_tokens` | 主模型 + Tier-0 `usage.input_tokens/output_tokens` | 双方同口径合计 |
| `escalation_rate` | fail-closed 升级次数 / Tier-0 调用次数 | 实验侧 |
| `gate_pass_rate` | 过科学门的阶段数 / 执行阶段数 | 双方 |

规则：

1. **质量门优先**：`gate_pass_rate(exp) < gate_pass_rate(mode0)` 时 speedup **无效**（质量退化不算加速）。
2. Tier-0 调用耗时与 token 计入实验侧成本，不得只计大模型。
3. 升级到大模型的调用耗时计入实验侧（含往返），避免“看起来快”。
4. 未过 gate / 中断 / 人工改写的 run **不进入** speedup 均值，单独列表。
5. 报告格式：每 run 一行 `{run_id, mode, T_run, speedup_run, cost_tokens, escalation_rate, gate_pass_rate}`。

示例（示意，非承诺值）：

| run | mode | T_run | speedup_run | escalations | gate_pass |
|---|---:|---:|---:|---:|---:|
| ai-cs1-b | 0 | 3120s | 1.00× | — | 7/7 |
| ai-cs1-j | 3 | 1810s | 1.72× | 4/38 | 7/7 |

## 7. A/B 验收

| 项 | 通过条件 |
|---|---|
| 科学完整性 | 挑战阶段九项 Skeptic 全跑；Adjudicate 前 `pre_verdict_gate` 必跑且结论不被 Tier-0 覆盖 |
| 质量非劣 | `gate_pass_rate` 不低于基线；Pre-Verdict critical 失败数不增加 |
| 校准 | `verify`/`classify` 的 auto 集抽样人工一致率 ≥ 约定阈值（建议 ≥ 0.9） |
| Fail-closed | 抽检 100% 的 SemDecide exit 2/3/4、`SEMDECIDE_TIMEOUT`/`SEMDECIDE_UNAVAILABLE` 与 `JEV_INVALID_RESPONSE`/`JEV_PROVIDER_ERROR` 都有升级记录 |
| 密钥卫生 | 仓库与 run 产物无 `AI_GATEWAY_API_KEY` / `TYPESAFE_API_KEY` / `FREEJEV_API_KEY` 明文 |
| FreeJev 幂等 | 抽检无同一 `request_id` 重试；失败一律升级大模型 |
| 可复现 | mode、approval `tools_hash`、阈值、上游 model id 写入 run 元数据 |
| 加速有效 | `speedup_run ≥ 1.2`（目标，可调）且质量非劣；否则保持 mode 0 |

## 8. 降级路径

```
--experimental 3 (hybrid)
  ├─ provider key + jev_mcp_approval.json → Tier-0 screen/rerank/extract/classify/verify
  │    (FreeJev: FREEJEV_API_KEY + JEV_PROVIDER=freejev；request_id 不重试)
  ├─ semdecide on PATH                  → is/filter/choose
  ├─ exit 2/3/4 / SEMDECIDE_TIMEOUT
  │    / JEV_INVALID_RESPONSE / JEV_PROVIDER_ERROR
  │                                    → 单次升级大模型（fail-closed）
  ├─ Jev 不可用                         → 仅 SemDecide（mode 2 切片）
  ├─ semdecide 不可用                   → 仅 Jev（mode 1 切片）
  └─ 双不可用 / 未开 --experimental     → mode 0 standard

科学门永不降级：Pre-Verdict Gate / Skeptic 九项 / 方法学审计 / Tribunal 始终在宿主路径执行。
```

## 9. API 速查（代码）

```python
from integrations.jev_mcp import (
    detect_jev_mcp, write_approval, load_approval,
    screen, rerank, extract, classify, verify, safe_call,
    resolve_experimental_mode, npx_mcp_guide,
)
from integrations.semdecide import (
    detect_semdecide, is_predicate, filter_records, choose_route,
    requires_llm_escalation, escalate_plan,
)

mode = resolve_experimental_mode(3)          # 0..3
approval = load_approval()                   # ~/.eduevidence/jev_mcp_approval.json
verdict = safe_call("claim_verify", claims, evidence, approval=approval)
if verdict.get("escalate"):
    ...  # fail-closed → large model
```

## 10. 变更记录

| 日期 | 内容 |
|---|---|
| 2026-09-22 | 首版：Tier-0 五能力、approval 门、mode 0–3、阈值、加速比口径、A/B 验收、降级路径 |
| 2026-09-22 | 收口：FreeJev（`FREEJEV_API_KEY` / `JEV_PROVIDER=freejev` / MCP `https://freejev.org/mcp` / `request_id` 不重试）；fail-closed 表与 `semantic_decide.py` 对齐 |
