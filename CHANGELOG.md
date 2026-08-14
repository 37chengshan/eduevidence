# Changelog

所有显著变更均记录于此。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)；版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [3.0.0-dev] — 2026-08-14

> v3 开发基线（`engine/versions.py` → `ENGINE_VERSION = "3.0.0-dev"`）。v3 三大方向：**可信度收口**（每个结论收紧到可追溯、可反驳、可审计）、**实证 Benchmark**（Layer B 真实模型运行）、**闭环能力**（PILOT → 真实数据 → 再裁决）。

### 可信度收口（Credibility Tightening）

- **Evidence Matrix 三列化（P1-1）**：支持 / 反驳 / 中性证据分列呈现，混合列不再被静默统计（`77db8b5`、`303054e`）。
- **Pre-Verdict Gate 严格化（OPEN-1）**：`uncertain_claims` 必须绑定证据（`evidence_ids`），无绑定即校验失败（`77db8b5`）。
- **outcome_mapping 报告（OPEN-2）**：决策输出新增 outcome 映射报告，学习效果与任务表现显式区分（`77db8b5`）。
- **角色 prompt schema 契约（OPEN-4）**：八角色 prompt 内嵌 schema 契约与枚举值表，输出即契约（`352015a`）。
- **agent MCP 三态（OPEN-5）**：MCP 可用性三态检测，`install` 自动写入 env（`a735cf6`）。
- **检索层回归测试补强（P0-1）**：检索 / 校验层回归测试补强，并修复 dedupe stale-index 合并（`de741d0`）。
- **Source fallback 诚实化（P1-2）**：真实 DOI 解析判 tier1，否则 tier5 + incomplete，杜绝编造 canonical URL（`985239e`）。
- **fetch 基准站点标题无害化**：中文站点标题英文化 + 分类泛化（`d7f068b`）。

### 实证 Benchmark（Empirical Benchmark，Layer B）

- **benchmark_v3 harness**：真实模型调用 + run manifest 契约（`schemas/v3/run-manifest.schema.json`），SIMULATED 与 EMPIRICAL 严格区分（`26a1d1b`）。
- **gold-based evaluator**：对照 `benchmarks/annotations/gold-*.json` 计算六项指标，每条标注 `method: heuristic`，均值按 95% CI 报告（`26a1d1b`）。
- **30 金标补齐**：Q11–Q30 金标标注 + 一致性校验测试（`fced61c`）。
- **CliDriver(omp)**：`omp` CLI 执行后端（`--driver cli`），实证运行落地 `benchmarks/empirical/run-empirical-01`（`503abca`）。

### 闭环能力（Phase 2）

- **Decision-to-Outcome Loop（pilot）**：PILOT 试点结果回填 → redecide → 再裁决（`715fae7`）。
- **Multi-project library synthesis**：跨项目证据库综合 + `REPORT_CONTRACT_VERSION 3.0` + pilots 目录（`eb059fb`）。
- **CLI 新子命令**：`pilot` / `synthesize` / `benchmark`（`400b346`）。

### 交付与文档

- **HTML 报告可访问性与诚实性小修**（6.1–6.5，保持视觉风格）（`d54d23a`）。
- **文档统一**：Canonical Protocol 9 步（6+3）、Schema 13 个、方法论文档 11 篇、V2 contracts 17 个等数字口径修正（`5b0e886`、`907cd11`）。
- **版本基线**：`3.0.0-dev`（`715fae7`）。
