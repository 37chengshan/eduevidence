# Task Brief — stage: extract（角色：evidence-analyst）

## 目标
从校验通过的来源中抽取 Claim 级证据对象，执行 Outcome Separation；只结构化，不裁决。

## 前置输入
- `sources.jsonl`（全部为 FETCH_VALID / 规则确认的 FETCH_PARTIAL）
- `fetch/` 全文内容（raw + clean + provenance）

## 产出
- `evidence.jsonl`：每行一个 Evidence Object（evidence_id / source_id / study_id / sample_id / claim_id / claim /
  outcome_type / relation_to_claim / effect_direction / effect size 与 CI / sample size / source_location / quality_score），
  须通过 `schemas/evidence.schema.json` 校验（V1 顶层契约，修订 1.1）。

## 执行规则
- **任务表现 ≠ 学习效果**：outcome 分类不得混用；两者的取值一律分离记录。
- `relation_to_claim` 属于链接（EvidenceLink）而非研究本身——支持/反驳/中性三列严格分离，不静默合并。
- 未报告的统计量保持缺失（未知就是未知），禁止由显著性反推效应量或补造 CI。
- 数字与单位从原文抽取，保留页码/章节等 `source_location`，使每条发现可回查。
- claim 文本用可读人话，禁止把内部字段名写进叙述。

## 质量门
- [ ] 每行通过 evidence schema；枚举值合法（outcome_type / relation_to_claim / effect_direction）。
- [ ] 每条证据都能定位到 `fetch/` 中的具体内容。
- [ ] 任务表现与学习效果的记录互不混用。
- [ ] 缺失的效应量如实留空，未出现推断值。

## 失败模式与回退
| 失败 | 处理 |
|---|---|
| `UNSUPPORTED_CLAIM` | 该 claim 无法绑定可核验来源时降级或丢弃，不得保留。 |
| 表格/正文含混 | 回退读 `/content` 或原文相邻段落，必要时标 `FETCH_PARTIAL` 走人工确认。 |
| schema 校验失败 | 修复后重跑抽取。 |

## 语言与呈现契约
claim 与说明为人话；ID、枚举、统计符号保留原样以便追溯。

## 交接说明
`evidence.jsonl` 同时供 Challenge、Audit 与 Adjudicate 使用；三者都不得修改该文件，只新增各自产物。
