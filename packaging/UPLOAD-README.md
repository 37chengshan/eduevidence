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
```

**Local Web Studio（三页只读）**：

```bash
python3 scripts/dashboard_server.py --port 8765
# http://127.0.0.1:8765/  → Dashboard / Report Browser / Data Visualization
```

报告浏览支持默认报告和已烘焙主题变体；数据可视化按 `result.json` / `evidence_graph.json` 读取。Web 交互图加载 jsDelivr ECharts 5.4.3，网络不可用时应使用静态报告。

**命令行跑一个新问题**：

```bash
eduevidence run --question "小学是否应采用自适应练习平台替代纸质练习册？" --depth deep
eduevidence status --run-id <id>
eduevidence gate --run-id <id>
```

**最小验证（无需联网 / 无第三方依赖）**：

```bash
python3 visualization/eduevidence-report/scripts/build_report.py \
  --result examples/ai-coding-assistant/result.json \
  --out /tmp/eduevidence-smoke.html
```

## 五、怎么跑测试

```bash
.venv/bin/python -m pytest -q
# 或在未建 .venv 的环境：python3 -m pytest -q
```

当前开发仓库验证结果：`786 passed, 1 skipped`。提交包为 allowlist 运行时包，不含 tests/、benchmarks/ 或内部 brief。

## 六、目录导读

| 路径 | 内容 |
|---|---|
| `SKILL.md` | Skill 唯一入口（9 步 Workflow、输出契约、能力路由） |
| `skill/` | 子技能、角色协议、阶段任务简报 |
| `references/` | 教育研究方法与裁决规则 |
| `schemas/` | JSON Schema 数据契约 |
| `engine/` | 证据综述、图谱、综合、裁决、研究设计、数据分析 |
| `scripts/` | 确定性脚本、DID、报告与三页 Studio 服务 |
| `retrieval/` | 检索与抓取层 |
| `integrations/` | Agent MCP / Smart Web Fetch 可选增强 |
| `visualization/` | 双语报告渲染器与三适配器 |
| `web/` | Dashboard / Report Browser / Data Visualization 三页前端 |
| `examples/` | 6 个可运行课题工件（主 Demo 含报告） |
| `docs/` | 架构、Demo、复现与 release contract |
| `LICENSE` / `README*.md` | 许可证与双语项目说明 |

## 七、提交包构建与验证

```bash
bash packaging/make_upload.sh
```

输出：`dist/eduevidence-submission/`，不生成压缩包。脚本按 allowlist 从临时 staging 重建目录，编译 Python 文件，验证主 Demo，并写 `submission-manifest.json`（内容文件 SHA-256、字节数、POSIX 路径；manifest 自身不计入清单）。当前实测 301 个内容文件、24,693,641 bytes。

## 八、上架注意事项

1. 排除 `.venv/`、`.git/`、缓存、`.DS_Store`、内部 brief、旧 Web 归档和 `visualization/lieflat-charts`。
2. 官方提交媒介、大小限制、联网策略、Python/浏览器版本以官方规则为准；24.7MB 不是平台硬门。
3. 核对 `packaging/scp-manifest.json`；它描述仓库来源清单，实际比赛包以 `dist/eduevidence-submission/` 和其 manifest 为准。
