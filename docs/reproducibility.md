# EduEvidence 复现指南

本指南确保任何人在全新环境中都能复现 EduEvidence 的校验、测试与 Benchmark 结果。全部命令以仓库根目录 `/Users/cc/edu`（即 pyproject.toml 所在目录）为工作目录执行。

## 〇、V2 Research Engine 复现

- 引擎模块 `engine/`（stdlib-only）可独立复现：`python3 -m pytest tests/test_v2_*.py`。
- 图状态复现：`graph/HEAD` + `revisions/rev-N` 快照 + `manifest.json` 的 before/after 哈希链；同一输入 bundle 提交产生确定性哈希。
- V1 历史产物（`examples/ai-coding-assistant/`、旧 `runs/`）不可变；`eduevidence migrate-v1 --pack <dir>` 生成新 V2 Project 且不改动源包。
- Shared Research Library 与 Project 图同用不可变 revision 模型；快照导入记录 `library_revision/library_entity_id/content_hash/imported_at`。
- 测试覆盖：V1 兼容基线、图原子性/孤儿 revision/HEAD 镜像分歧修复、迁移不变量、模式推荐、能力规划、synthesis 独立计数、Tribunal 政策、Gap 推导、数据集隐私门、全周期单 revision 提交、决策 diff、CLI 薄分发。

## 一、环境要求

- **Python**：≥ 3.10（pyproject.toml 中 `requires-python = ">=3.10"`）；
- **pytest**：≥ 7.0（dev 依赖，安装时自动带入）；
- 无其它强制运行时依赖：EduEvidence 本体是文档+Schema+脚本，Mode A 平台原生模式下不需要 daemon / CLI / Agent MCP；
- 操作系统：macOS / Linux / Windows 均可；建议使用 venv 隔离环境。

### 1.1 创建虚拟环境（推荐）

```bash
cd /Users/cc/edu
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

## 二、安装步骤

在虚拟环境内安装本项目（含 dev 依赖）：

```bash
pip install -e '.[dev]'
```

- `-e`（editable）安装使脚本与 schema 变更即时生效，无需重装；
- `.[dev]` 安装 `pytest>=7.0`；
- 安装成功后可用 `python -c "import sys; print(sys.version)"` 确认版本 ≥ 3.10。

## 三、运行测试

```bash
pytest
```

- 测试自动发现 `tests/` 下 `test_*.py` 文件（见 pyproject.toml `[tool.pytest.ini_options]`）；
- 覆盖范围：schema 校验器、confidence 规则化计算、Complexity Gate 判级、benchmark 输出格式等；
- 预期结果：全部测试通过（`addopts = "-q"` 输出简洁）。

## 四、运行 Schema 验证

校验某份数据是否符合对应 Schema（mandatory 字段缺失会标记为 UNSUPPORTED）：

```bash
python scripts/validate_schema.py \
  --schema schemas/evidence.schema.json \
  --data examples/ai-coding-assistant/evidence.jsonl
```

- `--schema`：指定任一顶层 Schema（schemas/ 下 13 个契约，如 education-frame / evidence / methodology / verdict / intervention / evaluation / report-result 等）；
- `--data`：指定要校验的 JSON 或 JSONL 数据文件；
- 主 Demo 示例数据位于 `examples/ai-coding-assistant/evidence.jsonl`，验证通过时应输出每条 evidence 的校验状态与 SUPPORTED/UNSUPPORTED 统计；
- 合格线：**校验通过率 100%**，任一条未通过即非零退出码。

## 五、运行 Benchmark

逐题运行五条基线（B0–B4）并生成结果：

```bash
python scripts/benchmark.py --questions benchmarks/questions.jsonl
```

- `--questions`：第一版 30 题（S×10 / M×10 / L×10），每题字段为 `id`、`level`（S/M/L）、`domain`、`question`、`expected_outcomes`、`notes`（与 `validate_questions()` 校验一致）；人工金标注位于 `benchmarks/annotations/gold-<id>.json`；
- 运行产物：每题一个 JSON，写入 `benchmarks/results/`；
- 核心指标（Citation Support Precision、Unsupported Claim Rate、Contradiction Discovery Rate、Outcome Separation Accuracy、Scope Calibration、Intervention Evidence Alignment）由 `benchmarks/evaluator/` 对照 `benchmarks/annotations/` 计算；
- 可选参数（如 `--ablation` 跑 A1–A7、`--repeat 5` 测稳定性）以 `python scripts/benchmark.py --help` 为准。

## 六、输出产物：Research & Decision Pack

每次端到端运行（Demo 或 L 级题目）产出一份双层 Research & Decision Pack：

- **Visual Brief**：用于快速浏览 Decision、Outcome Separation、Evidence Tribunal、Evidence-to-Action 与关键来源。
- **Full Report**：由当前研究内容规划为 **5–7 个动态章节**，而不是固定章节模板。

完整报告必须覆盖以下语义模块；这些模块可以按研究叙事合并进同一章节，但不得遗漏：

| 模块 | 内容 |
|------|------|
| decision | 最终决策、Confidence、可说/不可说与主要风险 |
| scope | Education Research Frame、研究边界与决策标准 |
| retrieval | 检索策略、来源覆盖与证据选择 |
| outcomes | Outcome Separation：任务表现、学习、保持、迁移与风险 |
| evidence | Claim-Level Evidence 与 Evidence Matrix |
| quality | Methodology / Evidence Quality Audit |
| conflicts | Skeptic / Counter-Evidence / Conflict Analysis |
| trace | Evidence Tribunal + Claim → Evidence → Source 追溯 |
| applicability | 适用性、外推边界与必要条件 |
| intervention | 最小可验证干预、Guardrails 与 Stop Conditions |
| evaluation | Baseline / Post-test / Retention / Transfer 评价方案 |
| sources | Sources、Provenance 与附录 |

Pack 的证据链始终可以从 Decision / Claim 反查到 Evidence，再追溯到 Source 与 source location；章节如何合并不改变这一追溯关系。

## 七、常见问题（FAQ）

| 现象 | 处理 |
|------|------|
| `pytest` 无测试收集 | 确认在仓库根目录运行且依赖已安装 |
| validate_schema 报非零退出 | 逐条查看 UNSUPPORTED 记录，补齐 mandatory 字段 |
| benchmark 输出缺失 | 检查 `benchmarks/results/` 目录可写；确认 `benchmarks/questions.jsonl` 字段完整 |
| pip install 找不到 `[dev]` | 确认工作目录是根目录（pyproject.toml 存在） |
| Python 版本低于 3.10 | 升级解释器或使用 pyenv 安装 ≥3.10 |

## 八、端到端复现三步走

```bash
pip install -e '.[dev]'   # 1. 安装
pytest                    # 2. 验证环境
python scripts/validate_schema.py --schema schemas/evidence.schema.json --data examples/ai-coding-assistant/evidence.jsonl
python scripts/benchmark.py --questions benchmarks/questions.jsonl   # 3. 复现示例与基准
```

三步全部成功即视为复现完成。
