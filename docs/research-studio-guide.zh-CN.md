# Research Studio：研究观察与报告阅读

## 1. 产品边界

Research Studio 是研究过程的只读观察窗口，不是另一个 Agent，也不代替研究引擎。研究仍由 Skill、CLI 和经过授权的执行器驱动。控制台不创建课题、不启动或停止研究、不修改证据、不批准试点，也不派发子代理。

控制台允许搜索、筛选、切换阅读方式、查看详细记录、刷新读取结果和下载已有报告。这些操作只改变当前浏览状态，不改变研究状态。

介绍页和 Agent MCP 的实现不属于本次重构范围。

## 2. 信息架构

| 入口 | 内容 | 数据权威 |
|---|---|---|
| 研究总览 | 本地研究与公开案例，问题、数据来源、决定、更新时间 | Project 和案例结果的只读投影 |
| 研究详情／总览 | 当前决定、依据、适用边界、试点与评价资料 | DecisionSnapshot 及明确关联的输入 |
| 研究详情／证据 | 可筛选 Finding、原文来源、方法学记录、数值与区间 | 当前 GraphRevision 或案例 result.json |
| 研究详情／图谱 | 来源、发现、主张之间已经存在的关系 | 已记录的关系，不由浏览器补造连接 |
| 研究详情／运行 | Run、阶段状态、产物、事件、实际保存的执行计划与门控记录 | 运行文件及只读事件索引 |
| 研究详情／版本 | 已提交版本链、决定快照、KnowledgeGap、研究迭代 | Graph HEAD 的父版本链 |
| 报告阅览室 | 五主题、摘要／全文、中英文、独立 HTML | 实际生成并通过数据门控的报告 |
| 系统迭代 | Skill Autoevolve 实验与保留／拒绝原因 | 独立的系统实验记录 |
| 流程导览 | 三种工作流、九阶段、角色与状态权威 | 项目现有科学协议 |

本地研究和案例库有独立标记。合成案例必须保留其数据来源标识，不能与真实人工整理文献混为一谈。统计数字表示已记录条目，不暗示独立研究数量、科学质量或真实业务收益。

## 3. 三条用户工作流

### Evidence Review：先理解已有证据

研究问题 → Frame → Retrieve → Extract → Challenge → Audit → Adjudicate。

控制台依次帮助回答：研究边界是什么，找到哪些来源，提取了什么结果，哪些反证存在，质量和直接性有什么限制，当前决定依据什么成立。

### Decision & Pilot：把不确定性变成可验证问题

DecisionSnapshot → Applicability → 有证据依据的 KnowledgeGap → Intervene。

PILOT 不是“先试试”的泛泛建议。其对象、对照、结局、时间和停止条件应来自引擎已有产物。没有产物就显示未提供，不由前端自动补全。

### Evaluate & Update：新数据回来以后重新判断

实际分析结果 → 经校验的 Finding → 新 GraphRevision → 新 DecisionSnapshot。

新证据不必改变决定标签；它可能只改变适用边界、确定性或下一步研究方向。旧版本必须保留。控制台显示真实变化，不为了形成漂亮的进度曲线而制造进展。

### 两种迭代不能混淆

研究迭代针对一个现实问题，更新项目证据；Skill Autoevolve 针对研究系统本身，修改并评估候选实现。因此二者分开显示，不共享一个“成功率”或一条版本时间线。

Protocol Stage、Scientific Role、Capability、Worker 和 Model 是不同概念。九阶段不等于九个子代理。实际派发结果只在对应 Run 保存了执行记录时显示。

## 4. 科学数据的展示规则

1. 图谱优先读取 Graph HEAD 指向的已提交版本，并沿 parent_revision 还原历史；游离版本目录不算已提交历史。
2. 决定绑定的 graph_revision 与当前 HEAD 不同时，明确标记过期，不能表现为当前有效裁决。
3. `0.0` 是合法数值，不等同于缺失。布尔值、NaN、Infinity 和不可解析内容不能转换成效应量。
4. 缺失、仅一侧存在或倒置的置信区间有不同标记；不填默认标准误，不把未知画成零。
5. 浏览器不计算合并效应量，不平均不同研究、不同结局或不同量纲。森林图按指标、结局和时间点分组；未知指标分开展示。
6. Finding 的效应方向不等于其对 Claim 的支持／反驳关系；同一 Finding 对不同 Claim 的关系可以不同。
7. 报告字段缺失时显示缺失，不填入固定案例的百分比、显著性、风险或教学方案。
8. 研究正在更新时，如果读取前后的 Graph HEAD 不一致，本次投影失败并允许重试，不返回混合版本。
9. 事件和产物索引以只读 SQLite 连接访问；页面读取不能初始化工作区、修复数据库或创建研究文件。
10. 相同内容可复用内容哈希，但项目／运行／产物类型的关联身份必须独立，避免跨项目提交后产物消失。

## 5. 五主题：同一事实，五种阅读气质

| 主题 | 保留的视觉身份 | 阅读重点 |
|---|---|---|
| Claude Research | 暖纸色、赤陶强调、舒展阅读 | 默认研究阅读和决定依据 |
| Academic Paper | 论文式排版、克制边框、正式层级 | 方法、来源、全文与打印 |
| DataLab | 浅色分析工作台、紧凑数据密度 | 证据比较、筛选、图表 |
| DataLab Dark | 深色分析工作台 | 长时间查看数据与证据 |
| Presentation / Judge | 深色、强层级、重点突出 | 快速抓住问题、边界与下一步 |

共同阅读层包括：固定工具条、阅读进度、摘要目录、完整报告目录、证据筛选、展开细节、来源链接、键盘焦点、手机布局、减少动画偏好与打印样式。

主题在生成时确定，独立报告内只切换语言与摘要／全文。控制台选择另一主题时加载另一份已生成报告；不存在的主题不伪装成可用。

报告是独立 HTML，不依赖外部 CDN 才能阅读。嵌入阅览室采用隔离 iframe；原始 HTML 下载后保留阅读工具。主题变化不能改变来源、数值、结论和适用范围。

完整双语输入可在构建阶段批量生成五主题。缺少输入的历史案例仍可查看原始证据，主题显示“尚未生成”；不得为了凑齐展示而伪造翻译或科学字段。

## 6. 前端与后端分工

```text
studio/src                    React + TypeScript 源码
        ↓ npm run build
web/studio                    可直接分发的静态资源
        ↓
Python 本地服务 / GitHub Pages
```

前端负责阅读状态、导航和交互。`engine/studio_read_model.py` 负责受限只读投影。研究引擎继续独立管理科学状态。

本地 API：

```text
GET /api/studio/catalog
GET /api/studio/projects/<key>
GET /api/studio/projects/<key>/report?theme=<theme>
GET /api/studio/evolution
```

其中 `example--...` 和 `project--PRJ-...` 是两个不同命名空间。文件路径、主题名、报告名均受约束；不能把任意本地路径传给服务读取。

生产控制台只发送读取请求。服务不提供研究变更接口。请求失败、内容格式错误和报告不存在都有明确界面状态；不会把 iframe 的 load 事件当作报告成功的证明。

## 7. 本地使用、开发与静态部署

### 完整分发包使用

```bash
python3 scripts/dashboard_server.py --host 127.0.0.1 --port 8765
```

打开本地 `/studio/`。分发包包含构建后的资源，不要求用户安装 Node。

本地项目根目录由 `EDUEVIDENCE_HOME` 指定。未创建本地研究时案例库仍可阅读，页面不会代替引擎创建工作区。

### 前端开发

```bash
cd studio
npm ci
npm run typecheck
npm run build
```

### 报告和静态站

```bash
python3 scripts/build_report_variants.py
python3 scripts/build_gh_pages.py
```

静态导出只包含仓库内公开案例，不读取或打包个人研究目录、运行历史、外部实验目录或拒绝的候选代码。静态模式没有本地操作能力，也不假装正在连接实时研究。子路径部署通过相对资源地址及 hash 导航支持。

### 分发包

```bash
bash packaging/make_upload.sh
```

构建阶段生成经过门控的报告和完整资源清单。最终上传包不包含 node_modules、前端开发工具、测试材料或私人研究历史。

## 8. 验证要求

Python 验证覆盖：只读副作用、零值与区间状态、跨项目产物关联、路径约束、陈旧决定、版本链、公开导出的隐私边界和 HTTP 拒绝行为。

TypeScript 编译与 Vite 构建覆盖组件和资源依赖。Playwright 在真实 HTTP 服务上验证项目导航、筛选、详情关闭与焦点恢复、图谱选择、真实运行夹具、报告切换、独立下载、API 失败、静态子路径部署和 320／390／768／1440 像素布局。报告还验证五主题的摘要／全文、中英文和键盘可达性。

自动可访问性检测和截图检查相互补充。自动规则通过不等于完整的人工可访问性认证，必须同时查看实际构图、文字密度和图表解释。

验证状态以当前 PR 对应提交的 CI 结果为准，不沿用旧提交的绿灯。

## 9. 设计参考与复用边界

- Linear：低噪声侧栏、清晰的项目层级与重点阅读。参考 https://linear.app/now/how-we-redesigned-the-linear-ui 。
- Langfuse：运行追踪与产物的层级组织。参考 https://github.com/langfuse/langfuse 。
- Evidence：数据驱动报告与静态交付。参考 https://github.com/evidence-dev/evidence 。
- OpenStatus：状态观察与故障表达，仅参考交互思想，不复制 AGPL 项目的实现。参考 https://github.com/openstatusHQ/openstatus 。
- Vite：传统后端接入和静态部署。参考 https://vite.dev/guide/backend-integration 与 https://vite.dev/guide/static-deploy 。
- WCAG Reflow：正文重排与数据表格的局部二维滚动。参考 https://www.w3.org/WAI/WCAG22/Understanding/reflow.html 。

本实现使用自主编写的布局与组件，不移植参考产品代码或品牌资源。第三方依赖许可证由分发清单单独记录。