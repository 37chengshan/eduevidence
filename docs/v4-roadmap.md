# EduEvidence v4 优化迭代地图 —— 六大方向 · 30 项

> v4（4.0.0-dev）定位：**教育通用**。从"教育证据决策"走向"任意教育问题的可证据决策"——
> 教学方法、课程、评估、学习干预与 AI 教育工具都是同一套证据协议的应用域。
> 对应本届命题 **「科艺融合 × 通用智能」**：方法学纪律（科）与多形态呈现（艺）融合，
> 面向全学科教育场景的通用智能研究助理。

**六大方向 = 五大支柱方向 + 一条横切主线**：能力扩展（8 项）、可信度（6 项）、
工程（6 项）、生态（4 项）、方法深化（6 项）合计 **30 项**；横切主线
「科艺融合 × 通用智能」贯穿全部 30 项，不单独计数。

优先级：**P0** = 发布/上架前必须闭环；**P1** = 本迭代内完成；**P2** = 后续迭代储备。
实施状态：**已实施** / **进行中** / **规划**。

## 一、能力扩展（8 项）—— 教育通用 · 科艺融合

| ID | 项目 | 优先级 | 状态 |
|----|------|:---:|:---:|
| C1 | 教育通用定位：教学方法/课程/评估/学习干预/AI 工具五域统一协议 | P0 | 已实施 |
| C2 | 三大 AI 教育工具全流程示例（ai-coding-assistant / ai-tutor / ai-writing-assistant） | P0 | 已实施 |
| C3 | 中英双语报告（lang 可切换，内容同源） | P1 | 已实施 |
| C4 | Decision-to-Outcome Loop：PILOT → 结果数据 → 再裁决（engine/pilot.py） | P0 | 已实施 |
| C5 | 跨项目综合 synthesize：Shared Research Library 聚合（engine/meta_synthesis.py） | P1 | 已实施 |
| C6 | Full Research Cycle：证据综述 → 知识缺口 → 研究设计 → 数据 → 分析 → 图更新 | P0 | 已实施 |
| C7 | 多形态呈现：HTML / Markdown / JSON 报告 + 图表 / 信息图 / 图规格 | P1 | 已实施 |
| C8 | 演示级输出：PPT / 视频 storyboard 一键生成 | P2 | 规划 |

## 二、可信度（6 项）—— 每个结论可追溯、可反驳、可审计

| ID | 项目 | 优先级 | 状态 |
|----|------|:---:|:---:|
| T1 | Evidence Matrix 三列化：支持 / 反驳 / 中性严格分离，不静默混合 | P0 | 已实施 |
| T2 | 规则化置信度：0.30 质量 + 0.25 一致性 + 0.20 直接性 + 0.25 独立研究数 − 双罚分 | P0 | 已实施 |
| T3 | Pre-Verdict Gate：uncertain_claims 必须绑定证据，无绑定即失败 | P0 | 已实施 |
| T4 | 方法学审计：Method Reviewer 独立于内容判断，task ≠ learning 铁律 | P0 | 已实施 |
| T5 | HTML 报告完整性真实检查（篡改探针 → REPORT_INVALID） | P1 | 已实施 |
| T6 | 跨模型交叉评审：独立模型复核 Draft Verdict（schemas/cross-model-review.schema.json） | P1 | 进行中 |

## 三、工程（6 项）—— 零依赖、契约化、可复现

| ID | 项目 | 优先级 | 状态 |
|----|------|:---:|:---:|
| E1 | Native Core 零第三方依赖（Python stdlib only，不要求 MCP/daemon） | P0 | 已实施 |
| E2 | Schema 契约体系 33 个（V1 13 + V2 17 + V3 3）+ 零依赖校验器 | P0 | 已实施 |
| E3 | GitHub Actions CI 三作业并行：test / schema-smoke / upload-build | P0 | 已实施 |
| E4 | 确定性 HTML/图表构建 + 生成物一致性 diff（chart_specs / infographics / figures） | P1 | 已实施 |
| E5 | 上传包自动构建（packaging/make_upload.sh）+ SKILL.md 一致性 + 零泄漏检查 | P0 | 已实施 |
| E6 | 测试体系：610+ 用例覆盖检索/校验/schema/pilot/benchmark/HTML | P1 | 已实施 |

## 四、生态（4 项）—— 让方法学流动起来

| ID | 项目 | 优先级 | 状态 |
|----|------|:---:|:---:|
| S1 | 多宿主 Skill 安装（install.sh --skill：Claude / OMP / Codex / OpenCode / Kimi 等） | P0 | 已实施 |
| S2 | Agent MCP 增强模式：三态检测 + 适配器 + env 自动写入 | P1 | 已实施 |
| S3 | 文档体系：架构 / 方法学 / 基准 / 复现 / 安装 / 活证据等完整叙事 | P1 | 已实施 |
| S4 | SCP 广场上架与社区运营（书生科学发现平台，收藏 + 专家评审双轨） | P0 | 进行中 |

## 五、方法深化（6 项）—— 方法学纪律的持续收敛

| ID | 项目 | 优先级 | 状态 |
|----|------|:---:|:---:|
| M1 | 八角色协议：职责单元不绑定 Agent 数，Single/Multi-Agent 双映射 | P0 | 已实施 |
| M2 | Complexity Gate：S/M/L 判级与快/标/深执行路径，防小题大做、大题浅做 | P0 | 已实施 |
| M3 | Canonical Protocol 9 步（6 研究核心 + 3 决策扩展），唯一权威定义 | P0 | 已实施 |
| M4 | 实证 Benchmark：Layer B 真实模型运行 + run manifest 契约（SIMULATED 严格隔离） | P0 | 已实施 |
| M5 | 金标 30 题（Q01–Q30 标注 + 字段/枚举/outcome 一致性校验） | P1 | 已实施 |
| M6 | 效应量合成 / 发表偏倚 / 稳健性检验方法学（docs/evidence-synthesis.md） | P1 | 进行中 |

## 横切主线：科艺融合 × 通用智能

- **科**：方法学纪律（八角色、复杂度分级、规则化置信度、活证据闭环）是"科学"半边，
  保证结论可追溯、可反驳、可审计；
- **艺**：多主题报告（claude / academic / datalab / presentation）、图表与信息图、
  双语呈现是"艺术"半边，让证据决策能被一线教师真正读懂；
- **通用智能**：教育域五类问题统一协议，AI 工具只是应用域之一；证据协议不绑定
  任何模型，可运行于任意宿主智能体。

**迭代节奏**：P0 全部闭环并进 CI → P1 逐项完成并更新本表状态 → P2 作为 v4.x 储备。
