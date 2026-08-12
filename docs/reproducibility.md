# EduEvidence 复现指南

本指南确保任何人在全新环境中都能复现 EduEvidence 的校验、测试与 Benchmark 结果。全部命令以仓库根目录 `/Users/cc/edu`（即 pyproject.toml 所在目录）为工作目录执行。

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

- `--schema`：指定六类 Schema 之一（education-frame / evidence / methodology / verdict / intervention / evaluation）；
- `--data`：指定要校验的 JSON 或 JSONL 数据文件；
- 主 Demo 示例数据位于 `examples/ai-coding-assistant/evidence.jsonl`，验证通过时应输出每条 evidence 的校验状态与 SUPPORTED/UNSUPPORTED 统计；
- 合格线：**校验通过率 100%**，任一条未通过即非零退出码。

## 五、运行 Benchmark

逐题运行五条基线（B0–B4）并生成结果：

```bash
python scripts/benchmark.py --questions benchmarks/questions.jsonl
```

- `--questions`：第一版 30 题（S×10 / M×10 / L×10），字段包含 id、complexity、domain、question、expected_decision 与 reference；
- 运行产物：每题一个 JSON，写入 `benchmarks/results/`；
- 核心指标（Citation Support Precision、Unsupported Claim Rate、Contradiction Discovery Rate、Outcome Separation Accuracy、Scope Calibration、Intervention Evidence Alignment）由 `benchmarks/evaluator/` 对照 `benchmarks/annotations/` 计算；
- 可选参数（如 `--ablation` 跑 A1–A7、`--repeat 5` 测稳定性）以 `python scripts/benchmark.py --help` 为准。

## 六、输出产物：Research & Decision Pack（12 部分）

每次端到端运行（Demo 或 L 级题目）产出一份 Research & Decision Pack，共 12 部分：

| # | 部分 | 内容 |
|---|------|------|
| 01 | Executive Decision | 一页决策摘要：问题、结论（ADOPT/PILOT/REJECT/INSUFFICIENT）、置信度 |
| 02 | Education Frame | 结构化研究问题（learner/course/intervention/comparison/outcomes/scope） |
| 03 | Search & Retrieval Log | 检索词、来源、检索时间与 scope 范围记录 |
| 04 | Evidence Objects | 全部 Claim 级证据对象（evidence_id、claim、direction、source_location） |
| 05 | Evidence Matrix | 按 outcome_type×direction 汇总的证据矩阵与 quality 标注 |
| 06 | Methodology Audit | 每篇研究的 method review（PASS/CONCERN/FAIL + task_vs_learning_guard） |
| 07 | Skeptic Review | 反驳证据、负面结果、未发现与 confounder 清单 |
| 08 | Verdict | 结论判定、Confidence 分解、what_can / cannot_be_claimed、missing evidence |
| 09 | Intervention Plan | 最小可验证干预（阶段化 PILOT、Stop Conditions、Evidence Alignment） |
| 10 | Evaluation Plan | 评估设计（pre/post、Retention、Transfer、无 AI 环境测验） |
| 11 | Benchmark Comparison | 当前问题在 B2/B3/B4 上的指标对照 |
| 12 | Sources | 完整来源清单（DOI/URL、年份、study_type、quality_score） |

Pack 的每一部分都可从上一部分反查：12→04 追溯来源，04→08 追溯结论，09/10 追溯决策落地。

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
