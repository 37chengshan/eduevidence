# EduEvidence 上传文件夹布局（upload/）

> 最终上传给评审 / 上架方的文件夹应按本文档组织。配套：`packaging/scp-manifest.json`（逐项清单与检查项）、`packaging/UPLOAD-README.md`（给评审方的说明）。

## 一、总体原则

1. **比赛三件套齐全**：`SKILL.md`（必须，根目录 Skill 文档，按项目决定只保留大写形式）、源码（必须，平铺目录）、展示材料（建议，`assets/` + 演示文档）。
2. **与仓库的映射关系**：仓库内文件一律不更名、不移动；上传目录是按文件复制得到的新布局。仓库 `SKILL.md` 即参赛 Skill 文档，上传时原样保留大写 `SKILL.md`（项目决定；若平台强制要求小写文件名，复制一份为 `skill.md` 即可，内容一致）。
3. **零泄漏**：`.venv/`、`.git/`、`.pytest_cache/`、`__pycache__/`、`build/`、`dist/`、`*.egg-info/`、`.DS_Store`、`runs/`（本地运行产物）、`upload/`、`docs/competition-brief.md` 一律不进上传目录。

## 二、布局总览

```text
upload/
├── SKILL.md                    # ← Skill 文档（仓库 SKILL.md，根目录唯一保留形式）
├── engine/ scripts/ retrieval/ integrations/ schemas/ skill/ references/ visualization/   # 项目源码（平铺，比赛要求“项目源码 必须提交”）
│   ├── engine/                 #   研究引擎核心（32 模块：证据综述/证据图/综合/裁决/缺口/研究设计）
│   ├── scripts/                #   确定性脚本（21 个：评分/矩阵/置信度/门控/渲染/基准）
│   ├── retrieval/              #   检索与抓取层（fetch/validate/dedupe/failures）
│   ├── integrations/           #   Agent MCP 增强 + Smart Web Fetch 集成
│   ├── schemas/                #   33 个 JSON Schema 数据契约（V1/V2/V3）
│   ├── skill/                  #   8 个角色协议
│   ├── references/             #   11 篇教育方法论文档
│   ├── visualization/          #   HTML 渲染器（5 主题双语报告）
│   ├── eduevidence_cli.py      #   CLI 入口
│   ├── pyproject.toml          #   包元数据 + pytest 配置
│   └── install.sh              #   一键安装脚本（--dev / --skill / --list-hosts / --dry-run）
├── examples/                   # 示例与演示（4 个；ai-coding-assistant 含可直接打开的报告 HTML）
├── docs/                       # 文档（16 篇；**不含 competition-brief.md**）
├── benchmarks/                 # 评测基准（V1/V2 问题集 + 确定性指标评估器 + 基线/注释/结果）
├── tests/                      # 测试（56 个 test_*.py + conftest.py）
├── assets/                     # 展示图片（top-banner / multi-agent-research / tribunal-workflow）
├── LICENSE                     # MIT 许可证
├── README.md                   # 项目说明（英文，仓库实为英文）
├── README.en.md                # 项目说明（中文版）
├── UPLOAD-README.md            # 给评审/上架方的本说明（从 packaging/ 复制）
├── scp-manifest.json           # 上架清单（从 packaging/ 复制）
└── upload-layout.md            # 本文档（从 packaging/ 复制）
```

## 三、逐项说明

| 上传项 | 来源（仓库路径） | 必须 | 说明 |
|---|---|:---:|---|
| `SKILL.md` | `SKILL.md` | ✅ | 参赛 Skill 文档。头部 YAML 含 name/description；正文含 9 步 Workflow 与输出契约。根目录大写形式（项目决定；平台强制小写时复制为 skill.md） |
| `src/` | 见上方树 | ✅ | 源码整体放入 src/，与根目录元数据（LICENSE/README）分离，目录清爽 |
| `examples/` | `examples/` | ✅ | 4 个示例完整复制，含报告 HTML 与 reports-5themes/ 预览 |
| `docs/` | `docs/`（剔除 competition-brief.md） | ✅ | 架构/方法论/安装指南/Demo/基准/可复现性/失败矩阵/项目评审/全量运行发现 |
| `benchmarks/` | `benchmarks/` | ✅ | 评测基准与确定性指标评估器，支撑“技术实现质量”评审维度 |
| `tests/` | `tests/` | ✅ | 61 个测试文件；`.venv/bin/python -m pytest -q` 可跑 |
| `assets/` | `assets/` | 建议 | 展示材料（可视化图片） |
| `LICENSE` | `LICENSE` | ✅ | MIT |
| `README.md` / `README.en.md` | 同名 | ✅ | 中英双语项目说明 |
| `UPLOAD-README.md` / `scp-manifest.json` / `upload-layout.md` | `packaging/` 同名 | ✅ | 上架三件套，随包带上 |

## 四、打包与核对步骤（建议顺序）

1. 新建 `upload/` 目录，按第二节布局复制文件（保留目录结构，剔除 exclusions）。
2. 复制 `packaging/scp-manifest.json` 到 `upload/`，按其中 `checklist` 逐项人工复核：
   - SKILL.md 存在且头部有 name/description（√ 已确认）；
   - LICENSE 存在（√）；README 存在（√）；examples 完整（√ 4 个）；
   - 测试可跑：`python3 -m pytest -q` 或 `.venv/bin/python -m pytest -q`（上架前在干净环境执行一次）；
   - 无 `.venv/`、`.git/` 及其他排除项泄漏。
3. 可选：将 `upload/` 打为 `eduevidence-skill-submission-v4.0.0.tar.gz`（上架前按本布局生成，确保含最新 `SKILL.md` 与平铺源码）。
4. 若平台接受单文件上传：上传 `SKILL.md` 与源码压缩包即可；若接受目录：直接上传 `upload/`。

## 五、替代方案（保持仓库原样）

若平台对 `skill.md` 文件名无强制要求，也可按仓库原样打包（根目录 `SKILL.md` + 各目录平铺），此时 `upload/` 即仓库剔除排除项后的完整拷贝。本布局采用“标准 skill 仓库”平铺形态：skill.md 与资源目录同在根目录，评审按 skill 结构直接可读。
