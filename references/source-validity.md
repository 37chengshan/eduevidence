# Source Validity（来源有效性校验）

## 1. 目的与定位

本协议是工作流第 4 步 Validate 的判定标准，回答一个问题：**这个来源能不能被引用？**

与 evidence-quality.md 的分工必须分清：

```
source-validity.md   → 来源是否真实、完整、可定位（能不能引用）
evidence-quality.md  → 研究设计质量高低（值不值得信）
```

**来源有效 ≠ 证据 strong**。一篇真实存在、抓取完整、可精确定位的论文，其证据
质量仍可能因设计缺陷只有 `weak`；反过来，一篇设计精良的研究若来源无法验证
（撤稿、抓取残缺、引用错位），也不能进入 Evidence Matrix。两者都通过，证据
才能被裁判庭使用。

## 2. 抓取完整性校验（对齐 fetch-result.schema.json）

每次 Fetch 尝试必须记录 `fetch_status`，并按以下规则判定：

| 状态 | 判定条件（validation 字段） | 是否可进入 Extraction |
| --- | --- | --- |
| `FETCH_VALID` | `http_success=true` 且 `body_length_ok=true` 且 `title_matches!=false` 且 `is_login_page=false` 且 `is_error_page=false` 且 `is_captcha_page=false` 且 `navigation_only=false` | ✅ 是 |
| `FETCH_PARTIAL` | 正文主体可读，但部分内容缺失（如页脚、附录、部分图表） | ⚠️ 仅当缺失部分**不涉及**结论依赖的关键数字/统计量时，经规则确认后可进入 |
| `FETCH_FAILED` | 上述任一关键项失败，或正文为空/被拦截 | ❌ 否；snippet 不得作为 SUPPORTED Evidence（RULE 2） |

### 完整性自检（PDF 与清洗链路）

- 清洗/解析可能丢弃表格与数字。抽取前必须抽查：**关键统计量（样本量、效应量、
  p 值、均值差）在清洗后正文中可找到**；找不到则按 `FETCH_PARTIAL` 处理并标注
  缺失项，禁止从摘要或引用片段"补回"数字。
- `date_identifiable=false` 时不得声称"最新研究"；按 `unknown + 如何获取` 标注
  （FR-03）。

## 3. 来源真实性校验

即使抓取完整，来源本身也可能不可信。逐项检查：

### 3.1 同行评审与出版状态

- 期刊/会议是否为正规出版渠道（可查 ISSN、出版社、会议主办方）；
- **撤稿检查**：检索 Retraction Watch / 出版方页面，确认无撤稿或更正记录；
- **掠夺性期刊筛查**：无同行评审流程、版面费可疑、ISSN 伪造等特征的期刊，
  其论文按 `tier5_general_web` 处理，不得作 SUPPORTED 证据。

### 3.2 预印本处理规则（tier2 场景）

arXiv / SSRN / 机构知识库等预印本与未同行评审稿（`tier2_academic_database`）：

- 预印本**可作候选证据**进入 Extraction，但结论中必须标注
  `预印本、未同行评审`，证据质量评分不得因"来源在 arXiv 上"获得加分；
- 同一研究已有正式发表版的，**以正式发表版为准**（见第 4 节版本一致性）；
  仅存预印本时，其结论在 Tribunal 中按降半档权重处理（如原本可支撑
  `moderate` 的仅能支撑 `weak`）；
- 预印本被撤下（withdrawn）或经同行评审大幅修改的，以最新状态为准并记录变更。

### 3.3 AI 生成论文筛查

以下特征组合出现时，将论文标为疑似 AI 生成，降级处理或排除：

- 无方法细节、无原始数据、无样本描述；
- 引用异常（引文存在但内容不相关、引用数量异常）；
- 讨论空洞、结论超出数据。

### 3.4 厂商与利益相关方声明

- 厂商/行业声明一律不得作独立证据（retrieval-protocol.md RP-03），即使
  authority_level 字段误标为学术来源，校验时必须修正。
- 论文的**资助方与利益冲突**必须记录：厂商资助的研究，其结论按证据质量
  评分后仍需在 applicability 的 `risk_factors` 中提示（applicability-policy.md）。

## 4. 内容一致性校验

| 检查 | 判定标准 | 失败处理 |
| --- | --- | --- |
| `title_matches` | 抓取到的页面标题与声称的来源标题一致 | 不一致 → `INVALID` 或回溯到正确 URL |
| `url_matches` | 内容确实来自 `canonical_url`，而非跳转后的无关页面 | 跳转后内容不符 → `INVALID` |
| 版本一致性 | 预印本与正式发表版并存时，**以正式发表版为准**；内容差异显著时两个版本分别记录并互相引用 | 未核对版本 → 结论限定"该版本" |
| 引文定位 | 引用的语句能在 `source_locator`（页码/段落/quote_hash）处找到原文 | 定位失败 → 证据标记 `UNSUPPORTED` |

引文定位是 Citation Audit 的前置条件：Claim → Evidence → Source → Source
Location 的追溯链（SKILL.md 第 10 章）在来源校验阶段就必须可走通，禁止"引用
存在但找不到原文位置"的证据进入 Matrix。

## 5. 去重（对齐 dedupe_keys）

`dedupe_keys` 四键：`canonical_url` / `doi` / `title_fingerprint` / `content_hash`。
任一键命中即视为同一来源：

| 情形 | 处理 |
| --- | --- |
| 同一论文多 URL（如出版社页 + PDF 直链） | 保留一个 `canonical_url`，其余标 `DUPLICATE` 并关联 |
| 同一研究多版本（会议版 + 期刊版 + 预印本） | 保留正式发表版为 primary，其余标 `DUPLICATE` 并关联；版本差异影响结论时按第 4 节处理 |
| 同一论文多个独立样本/子研究 | **不是重复**：各样本分别绑定 Evidence（Pre-Verdict Gate 的独立样本计数以此为准），但 `source_id` 需带样本后缀，禁止合并为一条 |
| 内容相同但 URL 不同的镜像站 | 按 `content_hash` 判重 |

## 6. 状态流转（对齐 source.schema.json `status` 枚举）

```text
DISCOVERED ──Fetch──▶ FETCHED ──Validate──▶ VALID（可进入 Extraction）
                    │                       ├─ PARTIAL（规则确认后可用）
                    │                       └─ INVALID（真实性/一致性失败）
                    ├──▶ FAILED（FETCH_FAILED，RULE 2）
                    └──▶ DUPLICATE（去重命中，关联 primary）
```

- `VALID` / `PARTIAL`：可进入 Evidence Extraction；
- `FAILED`：来源保留在 sources.jsonl 中作记录，snippet 不得升级为证据；
- `DUPLICATE`：不进入 Extraction，关联到 primary；
- `INVALID`：从候选移除，禁止引用；
- Pre-Verdict Gate 的 `Sources valid` 项要求：进入裁判的全部来源状态为
  `VALID` 或规则确认的 `PARTIAL`，且去重完成。

### 状态流转示例

> 某 arXiv 预印本声称"Copilot 提高作业正确率"：
>
> 1. `DISCOVERED` → Fetch 成功（正文完整、统计量可定位）→ `FETCHED`；
> 2. Validate：`title_matches=true`、内容与声称一致 → 初步 `VALID`；
> 3. 检索发现同一研究已有正式期刊版（带 DOI）→ 预印本标 `DUPLICATE`，
>    关联期刊版为 primary（§3.2 / §5）；
> 4. 期刊版结论为"正确率无显著差异" → 以期刊版为准，预印本不进入
>    Extraction，其摘要不得作为任何 Evidence 的内容（RULE 2）。

## 7. 执行规则（必须遵守）

| 编号 | 内容 |
| --- | --- |
| SV-01 | 每条证据的绑定来源必须经过完整性、真实性、一致性、可定位性四类校验，缺一不可。 |
| SV-02 | `FETCH_FAILED` 时 snippet 不得作为 SUPPORTED Evidence（RULE 2）；只能标注 `FAILED` 或 `DISCOVERED`。 |
| SV-03 | `FETCH_PARTIAL` 仅在缺失部分不涉及关键统计量时可用；涉及则降为 `FAILED`。 |
| SV-04 | 关键统计量（样本量/效应量/p 值/均值差）在清洗后正文中不可定位 → 按 `PARTIAL` 处理并标注缺失项。 |
| SV-05 | 撤稿论文、掠夺性期刊论文、疑似 AI 生成论文不得进入 Evidence Matrix；发现后从候选移除并记录原因。 |
| SV-06 | 厂商声明与利益相关方材料不得作独立证据（retrieval-protocol.md RP-03）；资助方信息必须记录。 |
| SV-07 | 引文无法在 `source_locator` 处定位 → 证据标记 `UNSUPPORTED`，禁止进入 Matrix。 |
| SV-08 | 同一研究的派生版本必须去重（第 5 节），独立样本不得合并计数。 |
| SV-09 | 来源校验通过 ≠ 证据质量高：仍须完成 evidence-quality.md 五维评分与 methodology-audit.md 审查。 |
| SV-10 | 预印本/未同行评审来源可作候选证据，但必须标注"预印本、未同行评审"；有正式发表版时以正式发表版为准（§3.2）。 |
