# EduEvidence 上架包说明（给评审 / 上架方）

> 参赛作品：**书生国智科探挑战赛 · 自由赛道（赛道六）AI for Social Science**
> 上架平台：Intern Discovery（书生科学发现平台）SCP 广场
> 本说明配套 `packaging/scp-manifest.json`（上架清单）与 `packaging/upload-layout.md`（上传文件夹布局）。

## 一、项目一句话

**EduEvidence** 是一个教育证据决策 Scientific Skill：把“是否采用某种教学方式 / 工具 / AI 教学干预”从经验判断，转化为**可追溯、可反驳、可验证**的证据决策流程（检索 → 反证 → 方法学审计 → 证据裁决 → 干预与评估设计 → 双语 HTML 报告）。

## 二、这是什么（30 秒版）

- 面向教师、教研员、教育管理者与教育研究者：输入一个教育决策问题，例如“大一 C 语言课程能否允许学生使用 GitHub Copilot 这类生成式 AI 编程助手”。
- 输出不是“允许 / 禁止”二选一，而是四态决策 **ADOPT / PILOT / REJECT / INSUFFICIENT EVIDENCE**，并附带证据矩阵、置信度分解、方法学审计结论与可落地的分阶段干预 + 评估方案。
- 双研究模式：**Evidence Review**（二手证据研究）与 **Full Research Cycle**（证据综述 → 知识缺口 → 研究设计 → 你的数据 → 分析 → 更新决策）。
- 核心纪律：**没有证据支撑就没有新研究设计**（Knowledge Gap 必须引用明确证据）；**任务完成 ≠ 学习发生**（方法学审计会点名并降级这类研究）。
- 工程形态：Skill 本体（SKILL.md + 8 角色协议 + 11 篇方法论文档）+ Python 引擎（27 个模块 + 21 个确定性脚本 + 33 个 JSON Schema 契约）；核心仅用 Python 标准库，无第三方运行时依赖，Agent MCP / Smart Web Fetch 为可选增强层。

## 三、安装方法

要求 Python ≥ 3.10。二选一：

```bash
# 方式 A：一键安装（venv + 依赖 + 自检 + 测试，等价 --dev）
cd <解压后的项目目录>
bash install.sh

# 方式 B：安装为 AI Agent Skill（交互式选择宿主，支持 11 种 Agent）
bash install.sh --skill
bash install.sh --list-hosts    # 查看支持的宿主与 Skill 落点
bash install.sh --dry-run       # 只预览不写入
```

> 也可用 pip 安装：`pip install -e .`（提供 `eduevidence` 命令行）。

## 四、怎么跑一个 Demo（3 分钟）

**最快路径**：直接打开现成报告，无需任何安装。

```bash
open examples/ai-coding-assistant/EduEvidence_Report.html
# 或浏览器打开 examples/ai-coding-assistant/reports-5themes/ 下的 5 主题预览
```

主 Demo 叙事（详见 `docs/demo.md`）：**大一 C 语言课程能否使用生成式 AI 编程助手**。核心观点“能更快完成作业 ≠ 编程学得更好”，最终收敛为带 Stop Conditions 的分阶段 **PILOT**（前 4 周禁用 AI → 中期允许 AI 辅助但需使用日志 → 后期限时无 AI 测验；指标下滑即回退）。

**命令行跑一个新问题**：

```bash
eduevidence run --question "小学是否应采用自适应练习平台替代纸质练习册？" --depth deep
eduevidence status --run-id <id>   # 查看进度
eduevidence gate --run-id <id>     # 查看发布门
```

**最小验证（无需联网 / 无第三方依赖）**：

```bash
# 1. 确定性脚本自检
python3 scripts/validate_schema.py --schema schemas/evidence.schema.json --data examples/ai-coding-assistant/evidence.jsonl

# 2. 从示例结果渲染报告（验证 visualization 完整）
python3 visualization/eduevidence-report/scripts/build_report.py \
  --result examples/ai-coding-assistant/result.json \
  --out /tmp/eduevidence-smoke.html
```

## 五、怎么跑测试

```bash
.venv/bin/python -m pytest -q        # 仓库自带 .venv；pyproject 已配置 testpaths=tests、addopts=-q
# 或在未建 .venv 的环境：python3 -m pytest -q
```

- 共 **56 个测试文件**（`tests/`），覆盖：V1/V2/V3 全研究周期、契约与 JSON Schema 严格校验、检索 / 抓取 / 去重回归、Skeptic 反证与发布门（pre_verdict_gate）、Agent MCP 门控、报告渲染与图表、benchmark 与发布合同。
- 测试为确定性软件 / 合同测试：验证引擎产出了符合规范的结构，不评判研究结论的科学正确性（内容级评估依赖人工金标注释，见 `benchmarks/v2/README.md`）。

## 六、目录导读

| 路径 | 内容 |
|---|---|
| `SKILL.md` | 参赛 skill.md：Skill 入口（name/description、When to Use、9 步 Workflow、输出契约、能力路由） |
| `skill/` | 8 个角色协议（Planner / Retriever / Analyst / Skeptic / Method Reviewer / Judge / Intervention / Evaluation Designer） |
| `references/` | 11 篇教育方法论文档（检索协议、反驳协议、方法学审计、裁决政策等） |
| `schemas/` | 33 个 JSON Schema 数据契约（V1/V2/V3） |
| `engine/` | 研究引擎核心：证据综述、证据图（版本化）、综合、裁决、知识缺口、研究设计、数据分析 |
| `scripts/` | 21 个确定性脚本：评分 / 矩阵 / 置信度 / 门控 / 渲染 / 基准 |
| `retrieval/` | 检索与抓取层（fetch / validate / dedupe / failures） |
| `integrations/` | Agent MCP 增强 + Smart Web Fetch 集成（可选） |
| `visualization/` | HTML 渲染器：5 主题中英双语报告 |
| `examples/` | 4 个示例（ai-coding-assistant 含可直接打开的报告 HTML） |
| `docs/` | 架构 / 方法论 / 安装指南 / Demo 与分镜 / 基准 / 可复现性 / 失败矩阵 / 项目评审 |
| `benchmarks/` | V1/V2 问题集、确定性指标评估器、基线、金标注释、结果 |
| `tests/` | 56 个测试文件 |
| `assets/` | 展示用可视化图片 |
| `LICENSE` / `README.md` / `README.en.md` | MIT 许可证 / 中英文项目说明 |
| `packaging/` | 本上架包：清单、本说明、上传布局 |

## 七、与比赛要求的对应关系

| 比赛要求（提交材料） | 本包对应物 | 状态 |
|---|---|---|
| `skill.md` 文件（**必须**） | `SKILL.md`，上传包内复制为 `skill.md`（内容一致；仓库内文件无需改名） | ✅ 已提供 |
| 项目源码（**必须**） | `engine/` `scripts/` `retrieval/` `integrations/` `schemas/` `skill/` `references/` `visualization/` + `eduevidence_cli.py` `pyproject.toml` `install.sh`（上传为 `src/`） | ✅ 已提供 |
| 展示材料 PPT / 视频 / 可视化图片（**可选，建议**） | `assets/` 三张可视化图 + `docs/demo.md`（Demo 叙事）`docs/demo-storyboard.md`（180 秒分镜表）`docs/PROJECT_REVIEW_2026-08-12.md`（项目评审）`docs/full-run-findings-2026-08-12.md`（全量运行发现） | ⚠️ 素材已备，正式 PPT/视频建议另附 |

**评审维度对照**：科研价值与实用性（证据决策 + 落地干预方案）✅ · 技术实现质量（契约化引擎 + 56 测试 + 确定性基准）✅ · 创新性与差异化（Skeptic 反证、方法学审计、四态裁决）✅ · 文档完整度与可复用性（README / 安装指南 / 架构 / 方法论 / 可复现性 + 本上架说明）✅。

## 八、上架注意事项

1. **排除项**：上传包不应包含 `.venv/`、`.git/`、`.pytest_cache/`、`__pycache__/`、`build/`、`dist/`、`*.egg-info/`、`.DS_Store`（见清单 `exclusions`）。
2. **`docs/competition-brief.md` 不随包上传**：该文件为比赛说明本地留存，明确标注“不提交版本库”。
3. 打包与核对请先看 `packaging/scp-manifest.json`（逐项 path/required/说明）与 `packaging/upload-layout.md`（上传文件夹布局），再按清单 `checklist` 逐项人工复核后上传。
