# EduEvidence 项目整体多维度审查报告

> 日期：2026-08-12  
> 范围：项目定位、架构、EvidenceFlow 方法论、Schema / 数据契约、检索与 Fetch、证据追溯、Benchmark、Agent MCP、测试、HTML / UI、文档一致性、安装与复现、比赛展示完整性。  
> 当前验证：`python3 -m pytest -q` → **50 / 50 tests passed**。  
> 注意：测试全部通过不代表项目已达到发布级可信度；当前测试主要覆盖核心确定性脚本，检索、Fetch、可视化、Agent MCP 集成等关键路径几乎没有自动化测试。

---

## 1. 总体结论

EduEvidence 当前已经具备一个很清晰、也有差异化的产品骨架：它不是普通“搜索论文 + 总结”的研究 Agent，而是围绕高校 AI 教学决策，把 **Frame → Evidence → Skeptic → Methodology → Tribunal → Applicability → Intervention → Evaluation** 串成一条可追溯的证据决策链。

从参赛项目角度看，项目最强的部分不是代码量，而是以下三点：

1. **领域冻结做得好**：第一版聚焦“高校课程是否、何时、如何引入生成式 AI / AI 教学工具”，没有无限扩张。
2. **Outcome Separation 是真正有价值的方法学差异点**：任务完成速度、作业成绩、保持、迁移、独立问题解决、AI 依赖被明确拆开，能够直接击中 AI 教学研究最常见的错误推断。
3. **从 Evidence 到 Action 的桥完整**：不是只给“研究结论”，而是进一步给出 Applicability、PILOT、Stop Conditions、Evaluation Plan，这比普通文献综述更接近真实教学决策工具。

但当前离“可以把结果数字、完整性 PASS、Benchmark 优势直接拿去比赛展示”的状态还有明显距离。最关键的问题不在 UI，而在 **科学完整性门、Fetch 可靠性、Schema 真校验和 Benchmark 真实性**。

### 当前建议状态

**项目主体：可以继续作为参赛主线。**  
**当前版本：建议标记为 Beta / Research Prototype，不建议直接宣称 Benchmark 已证明 B3/B4 优于基线。**  
**优先级：先修科学完整性与 Benchmark，再做 UI 精修。**

---

## 2. 维度评分

以下评分是工程成熟度参考，不是科学统计量。

| 维度 | 评分 | 结论 |
|---|---:|---|
| 项目定位与差异化 | 9.0 / 10 | 明确，有比赛记忆点 |
| 教育方法论设计 | 8.5 / 10 | Outcome Separation / Tribunal / Pilot 很强 |
| 架构分层 | 8.0 / 10 | Domain / Protocol / Execution 分层合理，但文档存在版本漂移 |
| Evidence / Claim 数据契约 | 7.0 / 10 | Schema 设计完整，但实际校验器没有完整执行 Schema |
| 检索与 Fetch 可靠性 | 4.5 / 10 | 当前存在几个会直接破坏可靠性的逻辑缺陷 |
| Citation / Provenance 完整性 | 5.5 / 10 | 有正确思想，但 result 组装会生成“看起来真实但实际未采集”的字段 |
| Benchmark 科学性 | 4.0 / 10 | v2 是 deterministic simulation，不能作为真实性能证据 |
| 核心代码可维护性 | 7.5 / 10 | 文件职责清晰，函数较小，确定性脚本可读 |
| 自动化测试 | 6.0 / 10 | 50 测试通过，但关键集成路径缺测试 |
| HTML / UI 信息设计 | 7.5 / 10 | 双语、主题、静态优先方向好；细节和完整性门仍需修 |
| 安装 / 复现体验 | 7.0 / 10 | install.sh 较完整，但 README 与真实环境存在入口差异 |
| 比赛展示成熟度 | 6.5 / 10 | 故事线很好，核心可信度问题修完后上限很高 |

---

# 3. P0：发布 / 比赛前必须修复

## P0-1 Fetch Validation Gate 当前存在实质性失效

### 位置

- `retrieval/validate.py:75`
- `retrieval/fetch.py:111-170`
- `integrations/smart_web_fetch.py:25-44`

### 问题 A：URL 校验永远为 True

当前：

```python
checks["url_matches"] = result.get("resolved_url") in (result.get("original_url", ""),) or True
```

结尾的 `or True` 让这个检查永久通过。

这意味着文档中声明的 “URL match Validation Gate” 实际没有执行。

### 问题 B：Fallback 顺序和 Validation Gate 顺序反了

`fetch_url()` 当前逻辑是：

```text
native HTTP 成功
→ 立即标记 FETCH_VALID
→ 因为已经 VALID，所以不进入 Jina / markdown.new fallback
→ 最后才执行 validate_fetch_result()
→ 如果发现是登录页 / CAPTCHA / 错误页，只降为 FETCH_PARTIAL
```

结果是：

**只要原站 HTTP 200，即使拿到的是 Cloudflare / 登录页 / 反爬页面，也不会再尝试更干净的 fallback provider。**

这与项目“Smart Web Fetch 降级链”的核心设计目标相反。

### 问题 C：DOI URL 会被误判为“私有 URL”

`integrations/smart_web_fetch.py` 的 `is_private()` 直接做字符串包含：

```python
private_hints = (
    "localhost", "127.0.0.1", "10.", "192.168.", "172.16.", ...
)
```

论文 DOI URL 常见：

```text
https://doi.org/10.1145/...
```

其中包含 `10.`，因此会被判断为 private，从而 **禁用第三方 Smart Fetch fallback**。

这会直接影响项目最核心的学术论文读取场景。

### 推荐修改

1. `is_private()` 必须用 `urllib.parse.urlparse()` 解析 hostname，再用 `ipaddress.ip_address()` / `ipaddress.ip_network()` 判断回环、私网、链路本地地址。
2. URL 路径中的 `10.`、`login`、`account` 不应该影响主机安全判定。
3. 每个 provider 抓取后立即执行 Validation Gate；只有 `validation.passed=True` 才结束降级链。
4. HTTP 200 + validation fail 应继续尝试下一 provider。
5. 记录真实 `resp.geturl()` 作为 resolved URL，并对 redirect 后的目标重新执行 private-network 检查。
6. 为 DOI、ACM、Springer、PNAS、Cloudflare 页面、登录页、短正文、redirect 增加自动化测试。

### 验收标准

- DOI URL 不再触发 private false positive。
- 200 状态但 CAPTCHA 页面会自动继续 fallback。
- `url_matches` 不再恒为 true。
- 至少增加 10 个 Fetch / Validation 单测。

---

## P0-2 Schema 文件比实际 Validator 能力更强，导致“校验通过”并不等价于符合 Schema

### 位置

- `scripts/validate_schema.py`
- `schemas/source.schema.json`
- `schemas/report-result.schema.json`
- `schemas/report-spec.schema.json`
- `schemas/fetch-result.schema.json`

### 问题

项目自定义零依赖 validator 只实现了：

- type
- properties
- required
- enum
- minimum / maximum
- minLength
- additionalProperties
- items

但当前 Schema 已经实际使用：

- `$ref`
- `const`
- `format: uri`
- `format: date-time`

例如：

```json
"fetch": { "$ref": "#/definitions/fetchProvenance" }
```

以及：

```json
"skill": { "type": "string", "const": "eduevidence" }
```

当前 validator 会直接忽略这些约束。

因此“Schema validation PASS”目前是一个 **不完整校验**，尤其会影响 Source / Report / Provenance 层。

### 推荐修改

二选一：

**方案 A（推荐）**：核心继续零依赖，但增加一个 `strict` 可选依赖使用标准 `jsonschema` 包；发布 / Benchmark / HTML Integrity Gate 必须走 strict validator。

**方案 B**：补齐当前项目实际使用到的 `$ref`、`const`、`format` 解析，并给这些关键字逐一写测试。

不要继续维持“Schema 里写了但 validator 不执行”的状态。

### 验收标准

- 所有 12 个 Schema 都由真正支持其关键字的 validator 校验。
- 写一个 `meta.skill != eduevidence` 的坏样本，必须失败。
- 写一个非法 URI / 非法 date-time，严格模式必须失败。
- `$ref` 内部字段非法时必须失败。

---

## P0-3 HTML 的 Scientific Integrity Gate 当前有“声明已验证，但实际上没有验证”的字段

### 位置

`visualization/eduevidence-report/scripts/build_report.py:1178-1191`

当前直接写：

```python
integrity = {
    "status": "PASS",
    ...
    "no_axis_distortion": True,
    "no_false_precision": True,
    "colorblind_safe": True,
}
```

这些值不是检查函数计算出来的，而是硬编码 True。

同时 `validate_contract()` 只是浅层检查顶层 key，并没有真正调用 `report-result.schema.json`。

`audit_claims()` 也主要检查：

```text
Claim → Evidence ID 是否存在 → Source ID 是否存在
```

但没有完整复用 `scripts/claim_audit.py` 已经定义的：

```text
Claim
→ Evidence
→ Source
→ Direction
→ Outcome Match
→ Scope
→ Support Relationship
```

因此报告底部显示：

```text
数据一致性校验：通过
integrity: PASS
```

目前语义过强。

### 推荐修改

把 Integrity Gate 改成真实可计算项目：

```text
schema_valid
claim_evidence_binding_valid
source_resolution_valid
outcome_counts_match
bilingual_structure_match
chart_numbers_match
```

如果没有真正实现以下检查：

```text
no_axis_distortion
no_false_precision
colorblind_safe
```

应该改成：

```text
NOT_CHECKED
```

而不是 True。

### 验收标准

- 所有 PASS 必须来自实际检查函数。
- 任意修改一条 outcome count，报告构建必须失败。
- 任意删除 source_id，报告构建必须失败。
- 任意制造 EN/ZH ID 不一致，报告构建必须失败。
- 未实现的质量检查明确显示 `NOT_CHECKED`。

---

## P0-4 Benchmark v2 是“模拟结果”，不能当作真实模型性能证据

### 位置

- `scripts/benchmark_v2.py`
- `benchmarks/results/v2-summary.json`
- `benchmarks/results/v2-report.md`
- `docs/benchmark.md`
- `README.md`

### 当前事实

`benchmark_v2.py` 已经明确写明：

```text
Runs are deterministic (seeded)
Live LLM runs can replace the synthetic results later
```

并且 `BASELINE_PROFILES` 是人工预设：

```python
B2 citation_support = 0.60
B3 citation_support = 0.85
B4 citation_support = 0.92
```

然后通过随机种子生成结果。

`v2-summary.json` 也明确：

```json
"mode": "deterministic_simulation"
```

这类结果可以用于：

- 测试 Benchmark pipeline
- 测试图表
- 测试 evaluator
- 测试输出格式

但 **不能用于证明 EduEvidence 真正优于 Direct LLM / Search LLM / Standard Agent**。

当前 README Roadmap 把 “Phase 7 Benchmark v2（B4 / Ablation / 成本对比）” 标成已完成，容易让阅读者误解为真实实验已完成。

### 另一个问题：旧 Benchmark evaluator 和正式 result.json 契约已经漂移

`scripts/benchmark.py` 当前仍读取：

```text
citations
verdicts
discovered_contradictions
```

而正式 `result.json` 主要结构是：

```text
claims
evidence
sources
decision
```

因此直接拿正式产物去跑部分指标，会出现错误的 0 值或失真结果。

### 推荐修改

将 Benchmark 明确拆为：

```text
Benchmark Harness Validation
    deterministic simulation
    只证明评测框架能运行

Benchmark Empirical Runs
    B0 / B1 / B2 / B3 / B4 真实模型调用
    固定模型家族
    固定题目
    固定检索条件
    记录真实 Token / latency / cost
```

比赛展示只能使用第二类结果。

### 验收标准

至少完成：

- 10 个金标问题的真实 B2 vs B3；
- 如果资源允许，再完成 10 个 B3 vs B4；
- 每组至少重复 3 次，最好 5 次；
- 明确模型、temperature、工具、时间、检索 provider；
- 报告均值 + 方差 / CI，而不是只给单值；
- deterministic simulation 的图表必须明确标注 `SIMULATED / HARNESS VALIDATION ONLY`。

---

# 4. P1：高优先级质量问题

## P1-1 Evidence Matrix 把 neutral 放进 contradiction 列

### 位置

`scripts/evidence_matrix.py:45-49`

当前：

```python
bucket = "support" if direction == "support" else "contradiction"
```

所以：

```text
support → support
contradict → contradiction
neutral → contradiction   ← 错误
```

测试 `tests/test_evidence_matrix.py` 甚至把这个行为固定成预期：

```python
assert "E-2" in row["contradiction"]
```

这是典型的“测试通过，但测试验证的是错误逻辑”。

### 风险

EduEvidence 最重要的卖点就是严格区分：

```text
negative evidence
null evidence
insufficient evidence
```

如果 neutral 被塞入 contradiction，Tribunal 的冲突程度会被系统性放大。

### 推荐修改

Evidence Matrix 必须三列：

```text
Support | Contradiction | Neutral
```

Verdict 逻辑也需要区分：

```text
NEUTRAL / NULL
CONFLICTED
CONTRADICTED
SUPPORTED
```

---

## P1-2 Source Registry fallback 会错误估计来源权威等级

### 位置

`scripts/build_result.py:96-111`

如果没有 `sources.jsonl`，当前会从 Evidence 自动生成 Source：

```python
"authority_level": "tier1_paper_doi"
if source_location.startswith("https://doi.org")
else "tier3_professional_institution"
```

因此：

```text
ACM DOI 页面
PNAS DOI 页面
Springer journal 页面
```

即使 URL 中明确包含 DOI，也会被降成 tier3。

项目其实已经有：

```python
retrieval.source.parse_doi_from_url()
```

但这里没有复用。

### 推荐修改

Source Registry 应成为唯一真相源：

```text
Evidence 只引用 source_id
Source Registry 负责 DOI / canonical URL / authors / year / source_type / authority
```

如果缺失 Source Registry，不建议“猜”权威级别；应明确标记 `source_metadata_incomplete`。

---

## P1-3 result.json 中存在“未知数据被写成 0 / 当前时间”的问题

### 位置

`scripts/build_result.py:113-145`

当前默认：

```json
"usage": {
  "input_tokens": 0,
  "output_tokens": 0,
  "cost_usd": 0.0,
  "latency_s": 0.0
}
```

但这些不是实际测量值，只是没有采集。

另外：

```python
"provenance": {
    "search_provider": "n/a",
    "fetched_at": datetime.now(...)
}
```

这里的 `fetched_at` 是 **result 组装时间**，并不是真正的文献 fetch 时间。

### 风险

在 Benchmark / HTML 中，这些数字看起来是“真实测量的 0 成本 / 0 延迟”，而不是“未知”。

### 推荐修改

未知就不要伪造精确值：

```json
"usage": {
  "measurement_status": "NOT_CAPTURED"
}
```

或者直接不写未采集字段。

Provenance 应从 Source.fetch 汇总，不能拿 result build 时间代替 fetch 时间。

---

## P1-4 Source 去重算法无法可靠处理“一个有 DOI、一个没有 DOI”的同一论文

### 位置

`retrieval/dedupe.py:24-48`

当前每条 Source 只选第一个可用 key：

```text
DOI → canonical_url → title_fingerprint → content_hash
```

例如：

```text
Source A：有 DOI → key = DOI
Source B：没有 DOI，但 canonical_url / title 与 A 一致 → key = URL
```

两者使用不同字典 key，因此不会碰撞。

### 推荐修改

维护多索引：

```text
doi_index
url_index
title_index
hash_index
```

任意一个 key 命中已有 Source 都视为候选 duplicate，再按 authority / metadata completeness 合并。

---

## P1-5 Fetch 文档声明有 defuddle，但代码没有实现

### 位置

`retrieval/fetch.py`

Docstring 和 `FETCH_PROVIDERS`：

```text
builtin → jina_reader → markdown_new → defuddle → raw_html
```

实际循环只有：

```text
jina_reader
markdown_new
```

没有 defuddle provider 实现。

### 建议

二选一：

- 真正实现；或
- 从能力说明、Schema enum / docs 中删除，避免“目录写了能力但运行时不存在”。

---

## P1-6 Fetch provenance 不完整

当前 `_http_get()` 只返回：

```text
status, body
```

没有返回：

- 最终 redirect URL
- Content-Type
- Charset
- response headers

同时 fallback provider 成功时没有完整更新 `raw_size / clean_size / compression_ratio`。

如果原 URL 返回 PDF，也缺少 PDF content type 分支；Schema 中已有 `pdf_parser`，但当前 fetch 主逻辑没有对应实现。

建议把 provider adapter 统一成：

```python
FetchAttempt(
    requested_url,
    resolved_url,
    status_code,
    content_type,
    charset,
    raw_bytes,
    cleaned_text,
    provider,
    validation
)
```

---

## P1-7 `docs/methodology.md` 有一句会误导 Skeptic 行为

### 位置

`docs/methodology.md:30`

当前写：

> Skeptic 的职责是主动生成反驳

但 `SKILL.md` 已经明确：

> 禁止为形成“双边观点”虚构反方证据；没有反方证据就输出 NO CONTRADICTORY EVIDENCE FOUND。

建议将文档统一改成：

> Skeptic 的职责是主动**寻找、验证和记录**反方证据、null result 与替代解释，而不是生成反方事实。

这是科学可信度的重要措辞。

---

## P1-8 Complexity Gate / Workflow 文档存在版本漂移

当前仓库同时存在几套表述：

### `SKILL.md`

```text
9 步：Frame / Retrieve / Extract / Challenge / Audit / Adjudicate / Applicability / Intervene / Evaluate
```

S / M / L 的执行拓扑也强调：

```text
S 单 Agent
M Primary + Independent Check
L 完整角色工作流
```

### `docs/architecture.md`

写的是：

```text
EvidenceFlow 6 阶段
```

且目录结构仍描述“六类 JSON Schema”，实际仓库已经是 12 个 Schema。

### `docs/methodology.md`

又写：

```text
M = 八角色全走
S 可以跳过完整 Skeptic / Method Reviewer
```

与 SKILL 的当前拓扑不完全一致。

### 推荐统一

建议定义唯一 canonical protocol：

```text
Research Core 6 stages:
Frame → Retrieve → Extract → Challenge → Audit → Adjudicate

Decision Extension 3 stages:
Applicability → Intervene → Evaluate

总计 9 steps
```

这样既能保留六阶段 EvidenceFlow，又能解释 9 步端到端流程。

所有 README / architecture / methodology / demo 都引用这一套定义。

---

## P1-9 本地 Search 层实际上没有实现，应明确 Host Capability Boundary

总体方案曾规划本地 Search / Retrieval，但当前 `retrieval/` 只有：

```text
fetch.py
validate.py
source.py
dedupe.py
failures.py
```

没有本地 `search.py`。

这不一定是问题——因为 Platform Native Mode 本来就可以使用宿主模型 / 平台搜索工具。

问题在于能力声明必须准确。

建议明确：

```text
Discovery/Search = Host capability / Agent tool
Fetch Reliability / Validation / Source Registry / Dedupe = EduEvidence local deterministic layer
```

这样会比补一个没有真实搜索后端的空壳 `search.py` 更可信。

---

## P1-10 Agent MCP Enhanced Mode 更像“适配器 / payload builder”，不是本项目自己执行多 Agent

`integrations/agent_mcp.py` 的边界其实写得很正确：

```text
EduEvidence only detect → call → fallback
本模块只构建 spawn_agent / memory payload，真正执行由 host MCP 完成
```

README 和比赛演示时也应该保持这个口径。

不要把它讲成：

> EduEvidence 自己实现了一个多 Agent runtime。

更准确的是：

> EduEvidence 有一套与执行框架解耦的 EvidenceFlow Protocol；接入 Agent MCP 时，可把角色协议映射到独立上下文、多模型和 Memory Bank。

这样反而体现架构解耦能力。

---

# 5. 自动化测试评估

## 当前状态

执行：

```bash
python3 -m pytest -q
```

结果：

```text
.................................................. [100%]
50 passed
```

核心确定性脚本目前整体稳定。

## 现有覆盖较好的区域

- `validate_schema.py` 基础类型 / enum / required
- `evidence_score.py`
- `evidence_matrix.py`
- `claim_audit.py`
- `benchmark.py` 旧指标函数
- Markdown report renderer
- 三个 example pack 的基础 Schema

## 缺口

当前 `tests/` 没有覆盖：

```text
retrieval/fetch.py
retrieval/validate.py
retrieval/source.py
retrieval/dedupe.py
retrieval/failures.py
integrations/smart_web_fetch.py
integrations/agent_mcp.py
visualization/eduevidence-report/scripts/build_report.py
build_charts.py
build_infographics.py
build_figures.py
双语 EN/ZH 同构
HTML 静态 fallback
HTML ECharts enhancer
```

这也是为什么 50/50 通过，但仍能发现多个 P0。

### 建议测试矩阵

至少扩展到约 90–120 个测试，重点不是数量，而是覆盖关键失效模式：

```text
Fetch: 15+
Schema strict: 10+
Result assembly / provenance: 8+
Evidence matrix edge cases: 5+
Benchmark real-contract evaluator: 10+
HTML integrity / bilingual: 15+
Dedupe / source registry: 8+
Agent MCP payload/fallback: 5+
```

---

# 6. HTML / UI / 可视化专项评价

## 做得好的部分

1. **静态优先方向正确**：即使没有 ECharts，核心决策 / Matrix / Tribunal / Intervention / Source 仍有 HTML / SVG fallback。
2. **单文件离线输出适合比赛演示和研究交付**。
3. **Claude / Academic / Editorial / Datalab / Presentation 五主题**适合不同用户场景。
4. **12 Section 结构完整**，从 Executive Decision 到 Sources & Provenance 的阅读路径合理。
5. Table 使用 `overflow-x:auto`，至少考虑了小屏溢出。
6. Figure / Infographic / ECharts 被分成不同 adapter，展示层没有直接回写研究核心数据，架构方向正确。

## P1 / P2 UI 问题

### 6.1 英文模式仍有中文硬编码

`build_report.py` 中：

```python
<span class='summary-tag pos'>支持</span>
<span class='summary-tag neg'>反驳</span>
（置信度：...）
```

英文模式会出现中英混排。

另外静态 SVG aria-label 仍写中文。

建议全部进入 UI_ZH / UI_EN 字典。

### 6.2 ECharts 不存在时，`.chart-mount` 仍固定占 320px 高度

当前：

```css
.chart-mount { height:320px; }
```

如果没有 vendor ECharts，JS 直接 return，但空容器仍可能留下大块空白。

建议默认：

```css
.chart-mount { display:none; }
.chart-mount.is-mounted { display:block; height:320px; }
```

成功 init 后再加 class。

### 6.3 双语完整性只检查“各自数字”，没有检查 EN / ZH 数据严格同构

README 声明：

```text
键 / 数字 / ID / URL 一致
```

但当前 builder 没有真正做结构 diff。

建议专门实现：

```python
compare_parallel_result(en, zh)
```

只允许文本字段不同；ID、enum、URL、数字、数组结构必须完全一致。

### 6.4 Integrity Footer 语义应更严谨

目前 Footer：

```text
数据一致性校验：通过
```

建议改成具体：

```text
Schema PASS · Claim Binding PASS · Numeric Consistency PASS · Bilingual Structure PASS
```

不要用一个模糊 PASS 覆盖未执行的检查。

### 6.5 可访问性可以再补一层

- 语言切换后同步更新 `<html lang>`；
- theme/lang button 增加 `aria-pressed`；
- 表格筛选控件增加 label；
- SVG 图增加双语 title / desc；
- source link 增加安全 scheme 白名单，只允许 `http / https / doi` 类链接。

---

# 7. Benchmark 专项建议

这是当前最需要重点重构的一块，因为它直接决定比赛中“我们比普通 Agent 好多少”的论证能否成立。

## 7.1 当前 Benchmark 最适合怎么定义

### Layer A：Harness Validation

用途：

```text
证明题目集、evaluator、report、图表、成本字段、Ablation pipeline 都能运行
```

数据：

```text
deterministic simulation
```

必须标记：

```text
SIMULATED
NOT EMPIRICAL MODEL PERFORMANCE
```

### Layer B：Empirical Benchmark

至少真实跑：

```text
B2 Standard Research Agent
B3 EduEvidence Single-Agent
```

这组最重要，因为它可以证明：

> 在同一模型家族下，仅增加 EduEvidence 教育证据方法论，是否改善 Citation Support / Unsupported Claim / Outcome Separation / Scope Calibration。

如果资源足够再做：

```text
B3 vs B4
```

证明 Agent MCP 的独立上下文 / 多模型 / Skeptic 增强是否真的带来收益。

## 7.2 指标实现需要升级

当前 `metric_outcome_separation()` 只检查：

```python
outcome_type in OUTCOME_SET
```

这只能说明枚举合法，不能证明“Outcome 分类正确”。

真正的 Outcome Separation Accuracy 应与 gold annotation 对照：

```text
某 Claim 应是 assignment_score 还是 retention？
某 Task metric 是否被错误解释为 learning outcome？
```

同理：

### Citation Support Precision

不能只看模型自己写：

```json
{"supports_claim": true}
```

应由独立标注 / evaluator 判断 Claim 与 Source excerpt 是否一致。

### Scope Calibration

不能只看结果自己写 `exceeds_evidence_boundary=false`，需要 gold allowed_scope 或独立 Judge。

### Contradiction Discovery

需要同时报告：

```text
precision
recall
```

否则系统可以靠“少说反方”刷 precision，或“疯狂报反方”刷 recall。

---

# 8. 文档与仓库一致性

## 8.1 README 总体质量较高

README 已经很好地回答：

```text
What Problem We Solve
Why Education Evidence Is Hard
How It Works
Outcome Separation
Evidence Tribunal
From Evidence to Action
Benchmark
Visualization
Architecture
Install
Usage
Limitations
Roadmap
```

这是比赛项目很重要的优势。

## 8.2 需要统一的事实

### Schema 数量

`docs/architecture.md` 仍写“六类 JSON Schema”，实际：

```text
12 schemas
```

### Scripts 数量 / 目录结构

Architecture 文档展示的是早期极简目录，已经落后于当前：

```text
retrieval/
integrations/
visualization/
更多 scripts
12 schemas
3 examples
```

### Benchmark Roadmap

建议把：

```text
Phase 7 Benchmark v2 [x]
```

拆成：

```text
[x] Benchmark v2 harness / simulation
[ ] Empirical B2 vs B3
[ ] Empirical B3 vs B4
```

这会显著提升项目可信度。

---

# 9. 安装与复现

## 优点

`install.sh` 已经包含：

```text
Python 版本检查
venv
editable install
pytest
Schema smoke test
HTML render smoke test
matplotlib optional capability
```

整体完成度不错。

## 问题

README 直接写：

```bash
pytest
```

但未激活 `.venv` 时系统 PATH 可能没有 pytest。当前本地就是这种情况：直接 `pytest` 不可用，但：

```bash
python3 -m pytest -q
```

可以正常执行 50 个测试。

建议所有文档统一使用：

```bash
python -m pytest
```

或明确：

```bash
source .venv/bin/activate
pytest
```

`python -m pytest` 跨平台可复现性更好。

---

# 10. 仓库卫生与代码地图

当前 `.gitignore` 已排除：

```text
.venv/
__pycache__/
.pytest_cache/
```

Git 层面没有问题。

但 CodexPro workspace inventory 仍扫描到了大量 `.venv` 与 `__pycache__` 内容，导致符号 / 文件分析受到噪声污染。

这属于工具分析边界问题，不影响最终 Python 运行，但会影响：

- AI 代码地图
- 自动审查
- token 使用
- symbol relationship 分析

建议为本地 AI 工具增加专用 ignore 配置（根据实际工具支持的 `.ignore` / workspace exclude / analysis exclude），明确排除：

```text
.venv/**
**/__pycache__/**
.pytest_cache/**
examples/**/figures/*.png
生成后的大 HTML
```

---

# 11. 建议的最终工程结构

建议不再继续大扩功能，先把当前能力收口成以下稳定边界：

```text
EduEvidence
│
├─ 1. Domain Methodology
│   ├─ Education Frame
│   ├─ Outcome Taxonomy
│   ├─ Evidence Quality
│   ├─ Skeptic Protocol
│   ├─ Methodology Audit
│   ├─ Evidence Tribunal
│   ├─ Applicability
│   ├─ Intervention
│   └─ Evaluation
│
├─ 2. Deterministic Core
│   ├─ strict schema validation
│   ├─ evidence scoring
│   ├─ evidence matrix
│   ├─ claim audit
│   ├─ source registry
│   └─ result assembly
│
├─ 3. Retrieval Reliability
│   ├─ Host Search Adapter
│   ├─ Fetch providers
│   ├─ Validation Gate
│   ├─ Dedupe
│   └─ Provenance
│
├─ 4. Execution Adapters
│   ├─ Platform Native
│   └─ Agent MCP Enhanced
│
├─ 5. Benchmark
│   ├─ Harness Simulation
│   ├─ Empirical Runs
│   ├─ Gold Annotations
│   └─ Evaluator
│
└─ 6. Visualization
    ├─ Chart Adapter
    ├─ Infographic Adapter
    ├─ Academic Figure Adapter
    └─ Bilingual HTML Composer
```

其中最重要的是：

> **Search 是 Host Capability；Evidence / Validation / Audit / Decision 才是 EduEvidence 自己的核心能力。**

这会让项目边界更清晰，也更容易解释为什么它是一个可复用 Skill，而不是一个绑定某搜索 API 的应用。

---

# 12. 推荐修改顺序

## 第一轮：Scientific Integrity Foundation

必须先做：

1. 修 `is_private()` DOI 误判；
2. 重构 Fetch：每次 fetch 后立即 validation，再决定 fallback；
3. 修 `url_matches ... or True`；
4. Schema validator 支持项目真正使用的 `$ref / const / format`；
5. HTML Integrity Gate 取消硬编码 PASS；
6. `build_report.py` 复用严格 Schema + Claim Audit；
7. 修 Evidence Matrix neutral 分类；
8. result usage / provenance 未采集值改成 NOT_CAPTURED。

## 第二轮：Benchmark 重构

1. 统一正式 result schema 与 evaluator；
2. 将 simulation 与 empirical 完全分开；
3. 重写 Citation Support / Outcome Separation / Scope 指标为 gold-based；
4. 真实跑 B2 vs B3；
5. 再决定是否跑 B4；
6. Ablation 只在真实 B3 pipeline 上关闭组件，不再用人工 profile 证明组件价值。

## 第三轮：Integration Tests

补：

```text
Fetch / validation
Dedupe
Source registry
Result assembly
HTML integrity
Bilingual parity
Agent MCP adapter
```

目标不是“测试数更多”，而是关键链路都能失败注入。

## 第四轮：HTML / UI 收尾

1. 英文硬编码清理；
2. ECharts 空容器修复；
3. 双语结构 Gate；
4. Accessibility；
5. Source / Provenance 卡片视觉升级；
6. 第一屏进一步压缩成：Question → Verdict → Evidence Boundary → Action。

## 第五轮：比赛材料

最后再做：

```text
3 分钟 Demo
README 精简首屏
真实 Benchmark 对比图
架构图
Outcome Separation 高光案例
“为什么普通 Research Agent 不够”对比
```

---

# 13. 建议比赛 Demo 的核心故事

不要把演示重点放在“五主题 HTML”或“有很多 Agent”。

最强的故事应该是：

```text
普通 AI：
AI 编程助手让学生做题更快
→ 所以 AI 有助于学习

EduEvidence：
任务完成速度 ↑
≠ 保持能力 ↑
≠ 无 AI 独立解决问题 ↑
≠ 迁移能力 ↑

然后：
正方证据
+ null evidence
+ 反方证据
+ 方法学质量
+ 适用范围
→ Tribunal
→ PILOT
→ Guardrail
→ Retention / Transfer Evaluation
```

这一段就是项目最容易让评委记住的差异点。

第二个高光点再展示：

```text
每条最终 Claim
→ Evidence ID
→ Source ID
→ 原始论文位置
→ Outcome
→ Quality
→ Applicability
```

最后用真实 B2 vs B3 Benchmark 证明：

> 这套方法不是“看起来严谨”，而是真的降低 Unsupported Claim、改善 Scope Calibration 和 Outcome Separation。

---

# 14. 最终验收清单

在项目进入“可发布 / 可比赛主展示”状态前，建议全部满足：

### Evidence / Research

- [ ] neutral 不再计入 contradiction
- [ ] Skeptic 文档明确禁止虚构反方证据
- [ ] Source Registry 是引用元数据唯一真相源
- [ ] Claim Audit 真正检查 outcome / scope / support relationship

### Fetch / Provenance

- [ ] DOI 不再被 private URL 规则误伤
- [ ] Validation fail 会进入 fallback
- [ ] redirect URL 被真实记录和安全检查
- [ ] `url_matches` 真正执行
- [ ] PDF / content type 有明确处理策略
- [ ] Fetch provenance 不使用伪造时间 / 0 值

### Schema

- [ ] `$ref` 被执行
- [ ] `const` 被执行
- [ ] URI / datetime strict validation 可用
- [ ] 12 schemas 全部有正向 + 负向测试

### Benchmark

- [ ] simulation 与 empirical 明确分离
- [ ] README 不把 simulation 当真实效果
- [ ] B2 vs B3 有真实运行结果
- [ ] evaluator 使用正式 result contract
- [ ] 核心指标使用 gold annotation / independent judge
- [ ] 至少报告重复运行与方差

### HTML

- [ ] Integrity PASS 无硬编码
- [ ] EN / ZH 同构检查
- [ ] 英文模式没有中文残留
- [ ] ECharts 未加载时无空白大容器
- [ ] Source links / SVG accessibility 完整

### Tests

- [ ] Fetch / retrieval 有测试
- [ ] visualization 有测试
- [ ] integration 有测试
- [ ] failure injection 有测试
- [ ] `python -m pytest` 全绿

### Docs / Competition

- [ ] 6-stage Evidence Core + 3-stage Action Extension 口径统一
- [ ] Architecture 更新到当前真实目录
- [ ] Benchmark Roadmap 真实标记
- [ ] Host Search 与 Local Fetch 边界说清楚
- [ ] Agent MCP 定位为增强执行适配器，不夸大为自研 runtime

---

# 15. 一句话评价

**EduEvidence 的核心方向是成立的，真正的竞争力是“教育领域证据纪律 + Outcome Separation + Evidence-to-Action”，而不是多 Agent 或漂亮 HTML。当前最需要做的不是继续加功能，而是把 Fetch、Schema、Provenance、Benchmark 和 Integrity Gate 从“设计上严谨”提升到“实现上也真正严谨”。这几项修完，项目整体可信度和比赛说服力会明显上一个台阶。**
