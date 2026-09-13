# 企业客服 AI 助手：人工选编的组织政策 demo

核验日期：2026-09-08。独立目录：`examples/workplace-ai-assistant/`。

本例回答“企业客服团队是否应引入生成式 AI 助手”，使用 `domains/policy/frame.schema.json`。建议 **PILOT：有监督、分岗位资历、限定任务的试点**。这是 `manual_curated` 文献演示，不属于模型执行 benchmark、系统综述或已完成的企业实验。未调用外部付费模型，未创建 Run、真实研究状态或部署记录。没有模型调用用量记录，因此不填执行拓扑、token、成本或虚构零值。

## 原文与版本核验

所有入选证据均读取出版方或原作者提供的原文；搜索摘要只用于发现。以下为释义，不是直接引文。来源条目及精确定位也保存在 `sources.jsonl`。

| 来源 | 原文关键事实和定位 | 适用限制 |
|---|---|---|
| S-001 Brynjolfsson, Li & Raymond (2025), [Generative AI at Work](https://academic.oup.com/qje/article/140/2/889/7990658), DOI `10.1093/qje/qjae044` | QJE 正式版本；III.B / 表 I：5,172 名客服、3,006,395 次会话。摘要、IV.A / 表 II：每小时解决问题数约增加 15%；会话处理时间下降。摘要、IV.B：资深高技能员工质量有小幅下降。VIII 说明外推限制。 | 直接客服证据，但为一家企业的非随机分批上线、特定工具与稳定产品支持；不能当作所有企业的平均因果效应。E-004 与 E-001 同一队列，亚组人数未提取，保留 null。 |
| S-002 Noy & Zhang (2023), [作者提供的 Science 对应稿](https://shakkednoy.com/Noy%20Zhang%20NBER%20SI.pdf), DOI `10.1126/science.adh2586` | PDF 第 1 页摘要、第 3 页 Method：453 名受过大学教育的职场人士，随机分配 ChatGPT；平均任务用时约减少 40%，评定写作质量约提高 18%。第 7 页 Limitations：任务不要求精确事实及特定情境知识。 | **间接证据，不可直接推广**到真实客服、事实安全或收益预测。没有把写作质量叫作学习效果。Science 页面读取失败，改读作者原稿；MIT 早期 444 人工作稿只用于版本辨别，未混用其中样本或效应。 |
| S-003 Dell’Acqua et al. (2026), [Organization Science 正式原文](https://pubsonline.informs.org/doi/10.1287/orsc.2025.21838), DOI `10.1287/orsc.2025.21838` | 页面明确发表于 2026-03-11；整项研究 758 人。4.2 / 图 5 / 表 7：超出能力边界任务分析人数 **373**；对照正确率约 84.5%，两个 AI 组约 60% / 70.6%，合并约低 **19 个百分点**。 | **间接证据，不可直接推广**：顾问完成实验商业案例，不是真实客服工单。正文与摘要“19%”口径不一致，采用正文明确的百分点。采用正式版，未照搬 2023 工作稿的质量提升数字。 |

网络工具实际打开 QJE 正文时跳转到 `https://oup.silverchair-cdn.com/article-minimal/7990658`。HBS 工作稿 PDF 读取失败，但同研究正式出版全文可读。未执行 Crossref 注册核验或撤稿库查询，因此不声明 `doi_verified=true` 或 `retracted=false`。不保存或再分发整篇版权原文。

`search_log.json` 记录人工检索计划、实际查询、失败读取、版本排除和停止理由。本次只有一项直接客服研究；不能声称检索穷尽，尤其不能声称不存在其他直接研究或零结果。

## 集成验收更新（2026-09-08）

以下旧审计表是子任务交付时的快照。主任务已经修复领域读取和干预契约：`meta.domain=policy`、`target_population` 可通过 schema，Studio 本地和静态 API 均显示 policy，报告使用“目标人群”。五主题已由共享构建器生成并经过浏览器加载检查；测试同时确认 3 个来源、4 条发现、0 条运行记录。旧例已迁入测试 fixtures，孤立生成目录已删除。原始来源和人工整理属性不变；真实模型九阶段运行仍未验证。

## 科学数据口径

- 四条 evidence、三项独立研究、三组已纳入样本；不能按四条证据称为四项研究。咨询研究的 758 是总体人数，反证条目使用表 7 的 373。
- E-001 的 `completion_time` 对应会话处理时间的定性下降。其 `extensions.raw_result` 中 15% 明确标为**另一个吞吐量指标**，不当作处理时间降幅。E-002 的 −40% 是用时相对变化；写作质量 +18% 只作独立文字描述。E-003 的 −19 是正确率绝对百分点变化。
- `effect_direction` 记录原研究观察方向；`relation_to_claim` 记录支持某项主张。反证 E-003/E-004 支持“可能发生质量损害”这一谨慎主张，因此关系是 support，效应方向是 negative。不能把支持关系的数量叫作受益研究数量。
- 没有计算 Hedges g、合并效应或置信度概率。`forest_plot_data=[]`，图中标准化效应、CI、p、置信度分数均为 null。原文确有部分回归标准误、p 值阈值及其他尺度的区间，但没有为本例所列摘要估计量提取匹配区间；**null 意为本例未提取，不是论文完全没报告，也不是零效应**。
- Moderate 与 pilot 边界由确定性策略（engine/decision_policy.py）计算并经 Pre-Verdict Gate 的决策动作一致性项复核：3 项研究、4 条证据、confidence_score=0.578、策略版本 2026-08-12.v3。它仍是对全面部署充分性的保守判断，不是概率。三项选择性证据不支持发表偏倚检验或元分析。
- 图的日期时间仅是核验日标记，`intent.timestamp_note` 明确不是运行时间。未伪造先试点、后更新的历史。

## 决策、试点与停止

`G-001` 指向本地成本、隐私、亚组质量与持续表现证据缺口，连到 E-001 至 E-004；试点及评估都绑定该 gap。建议两周基线、六周试点只是规划参数，未执行。需先用本地变异估计样本量、确定质量非劣界值与净成本阈值，未预先编造一个“统计充分”的人数。

按团队分配试点与同期对照，按资历和基线表现分层；记录污染并采用意向治疗、团队聚类不确定性估计。除有效解决量/付薪工时，还要盲评质量、重复联系、人工复核成本。初期仅开放知识库覆盖的低风险队列，人工审查所有回复；保留专家否决权。

隐私控制、供应商数据条款审查、访问/留存限制是建议的实施条件，**不是这三项研究已经证明有效的干预**。陌生、模糊、高风险及超出权限任务转交合格人员，不自动承诺赔付等事项。核实隐私泄漏、严重危险建议或越权承诺即暂停；质量跨越预先约定非劣界值则暂停扩展。满足质量、安全、效率和净成本条件后再议扩展，不把吞吐量收益直接换算成裁员依据。

## 契约限制和主代理集成事项

本子任务不修改共享代码。以下是当前读取代码的精确限制：

1. `schemas/report-result.schema.json → properties.meta.additionalProperties=false`，且 meta 没有 domain；`scripts/dashboard_server.py::scan_local_projects` 却读 `meta.domain` 并默认 `education`。本例在 `research_frame.extensions.domain=policy` 合法存储领域，**可被扫描但当前 Studio API 仍误标 education**。建议主代理允许 meta.domain，或从 frame.extensions.domain 回退读取，并同步静态导出。
2. `schemas/evidence.schema.json → properties.outcome_type.enum` 不接受 policy_effectiveness / implementation_risk。本例采用具有真实非教学含义的 completion_time / accuracy；`extensions.policy_outcome` 保存政策映射。没有改 enum、没有把客服改成学生。后续应按 domain 选择 taxonomy；不要静默把吞吐量转换成时间指标或标准化效应。
3. `schemas/intervention.schema.json → required` 强制 target_learners。本例明确填“不适用：组织政策”，实际对象在 extensions.target_population；没有 teacher_role、student_role、learning_goals。建议新增独立 policy intervention 契约或领域判别联合类型。
4. 报告双语门 `visualization/eduevidence-report/scripts/build_report.py::compare_parallel_result` 只允许白名单文本键翻译；本例扩展叙述用 note / summary，避免 description / scope_note 触发结构错误。语言门会把 intervention/evaluation/methodology 的 extensions.domain=policy 误当中文叙述；因此领域只存在 policy frame 和证据结构中。主代理可修复结构键豁免。
5. `engine/evidence_graph.py::EvidenceNode` 和 ClaimNode / DecisionNode 有默认数字。本例显式覆盖未知效应、置信度及 pooled_effect_g，避免默认 0、0.05 或 0.85 冒充测量。当前反序列化 roundtrip 通过；某些未测试的下游可能仍假定数值，需主代理完成全报告检查。
6. 要求读取的 `docs/CODEX-NAVIGATION-GUIDE.md` 不存在。本例依照根 SKILL.md、evidence-review workflow、policy frame/taxonomy/checklist 和参考示例执行。

## 子任务验证记录与演示

在仓库根目录运行：

```bash
python3 examples/workplace-ai-assistant/validate.py
```

2026-09-08 实际结果：**PASS**；27 个 schema 对象通过（双语 report/frame/verdict/intervention/evaluation/source/evidence/methodology，加 report spec）。独立 stage 文件与 result 内容一致；图反序列化 roundtrip、所有边端点、研究去重、样本口径、空标准化效应、构建器 contract/claim/bilingual/language/numbers/precision 输入门均通过。只读 Studio scanner 找到 `workplace-ai-assistant`，4 条证据、图存在、0 个标准化效应；domain 如上仍是 education。

`curate.py` 可以再生本目录的人工整理投影，不运行模型或研究；日后补充新证据应新建 revision，不用再生脚本覆盖既有研究历史。验证脚本不生成 HTML，不需要网络，也不修改研究状态。

演示步骤（主代理统一生成报告后）：

1. `python3 scripts/dashboard_server.py --host 127.0.0.1 --port 8765`，进入 `/studio/`，搜索本例中文问题。
2. 查看 PILOT、四条证据、原文链接和证据图；说明仅一项直接客服研究，其他为间接证据。不能把当前错误领域标签当成教育适用性证明。
3. 对照 E-003 的 373 与 study_total_n=758，展示百分点与百分比区分、null 保留、森林图无可合并效应。
4. 查看 G-001、试点条件、隐私和质量停止规则，强调方案尚未执行。
5. 主代理统一调用现有五主题构建器后，再查看五个独立离线双语报告。**本子任务未生成报告、未运行真实浏览器验收、未验证五主题最终 HTML**。`report_spec.json` 是符合 schema 的计划输入，无虚构 integrity PASS。

现有 `scripts/build_report_variants.py --examples` 参数接收包含项目目录的父目录，不是单个项目；主代理统一构建可用 `python3 scripts/build_report_variants.py --examples examples`，注意这会更新其他 demo 的报告，超出本子任务权限。

## 子任务交付时的旧 examples 审计快照

审计为当前工作树快照；其他代理同时工作，不能据此还原文件。没有实际删除或更新旧 demo。

| 目录 | 当前发现 | 建议及引用影响 |
|---|---|---|
| ai-coding-assistant | 是指向 ai-coding-assistant-evidence 的符号链接，不是第二份独立实证 | 保留兼容链接，统一公开入口到 evidence 目录。多个 `tests/test_build_*.py`、test_render_report.py、test_validate_schema.py、test_bilingual_contract.py 和 docs/demo.md、demo-storyboard.md 使用旧别名；改引用后再议移除。 |
| ai-coding-assistant-evidence | manual_curated；12 evidence、8 sources；meta.version=5.2.0，作为旗舰有独立价值 | 保留并由主代理审查、再烘焙；不要因为版本字符串旧就重写 provenance。本例是组织政策问题，不复制其教学结论。README 双语、docs/install-guide.md、CI 来源验证、dashboard 测试依赖它。 |
| ai-coding-assistant-50 | 没有 result.json，只有 reports-5themes；混有 report_* 和 EduEvidence_Report_* 两套文件，scanner 不收录 | 建议删除孤立陈旧报告目录，先查全仓引用和发布包残留。docs/plans/v5.2-v6.0-iteration-plan.md 记录过其随机效应/伪造 DOI 问题；本次没有把历史审计当作重新核验每篇论文的结果。 |
| ai-tutor | 老格式 1.0.0、6 evidence；未标 data_origin；与高中数学 synthetic demo 主题相近但目标人群不同；引用真实 URL不等于本次已核验提取 | 保留前补人工来源核验、双语及 provenance、非直接人群边界；或合并成一个有依据的数学主题。README 双语、test_validate_schema.py、web/api/projects.json 和 projects/ai-tutor/viz.json 有依赖。 |
| ai-writing-assistant | 老格式 1.0.0、8 evidence；未标 data_origin；与 ESL synthetic demo 主题重叠 | 优先更新这个有真实 URL 的版本，重新验证论文与主张匹配后再决定保留。README 双语、test_validate_schema.py、web/api/projects.json 及对应 viz.json 有依赖。 |
| esl-academic-writing-ai | 明确 synthetic、16 evidence；部分 evidence 无 source_location；示例 DOI `10.125/llt.2024.08` 不能作为有效研究证据 | 建议从公开实证演示中删除；如软件回归需要，迁入明确 fixture 目录并替换伪论文指针。清理 web/api/projects/esl-academic-writing-ai/viz.json 和 README 的 synthetic 分类入口；不要先删再留下静态卡片。 |
| highschool-math-ai-tutor | 明确 synthetic、16 evidence；示例 DOI `10.1016/j.compedu.2025.104920` 需隔离，不能凭 DOI 样式当作真实 | 同上：从公开实证演示删除或迁为 fixture，并更新 web/api/projects/highschool-math-ai-tutor/viz.json、README 分类说明。 |
| full-research-cycle-fixture | 名称及 docs/benchmark.md 明确为合成机制测试；没有 result.json，不进入 scanner | 保留为软件 fixture，不作为研究结果展示；删除会影响文档中 DID 演示用途。 |

已确认的本地断链接：`docs/demo-storyboard.md:108–110` 所述 `examples/ai-coding-assistant/chart_specs.json`、`infographics.json`、`figures/` 均不存在；同文第 111 行仍写 7 证据 / 3 来源，与当前旗舰 12 / 8 不符。建议更新为当前实际产物与数量，或由主代理统一生成后再引用。

外链检查仅抽查上述两条 synthetic DOI：web 工具都返回无法安全打开，**该错误本身不证明 DOI 404**；随后 urllib 实际请求确认两条均为 **HTTP 404**，结果保存在 `legacy-link-check.json`。未对所有旧 demo 的每个外链、DOI 标题一致性、撤稿情况做穷尽审计。`website/` 目录不存在，实际静态站点在 `web/`；本次读取了静态 projects 索引及相关 viz 文件引用，未修改它们。
