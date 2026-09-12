# Contributing to EduEvidence

EduEvidence 是一个**证据驱动的决策引擎**：它的产出要能被第三方复核。因此本仓库的贡献规则有一条主线——**契约先行**。每个科学概念都在多处声明（协议、能力、角色、简报、子技能、分包），任何一处漂移都会让结论失去可追溯性。

## 1. 环境准备

```bash
git clone https://github.com/37chengshan/eduevidence.git
cd eduevidence
bash install.sh            # venv + 依赖 + 自检 + 测试
# 或最小安装
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
```

要求 Python ≥ 3.10；内核（`engine/`、`retrieval/`）零第三方依赖，测试需要 `pytest`。Node 只在构建 Research Studio 前端时需要。

## 2. 提交前必须跑的门

```bash
python scripts/check_version_consistency.py   # 版本口径单一权威
python scripts/generate_metrics.py --check    # 文档数字与仓库一致
python scripts/skill_lint.py                  # Skill 结构完整
python scripts/check_protocol_alignment.py    # 协议五方对齐
ruff check --select E9,F63,F7,F82 .
python -m pytest -q
```

CI（`.github/workflows/ci.yml`）会重复执行上述门，外加 wheel 隔离安装冒烟、schema-smoke 与提交包构建。本地全绿是提交的最低门槛。

## 3. 科学不变量（不可协商）

- **任务表现 ≠ 学习效果**：任何把任务完成度当作学习收益的写法都会被门拒绝。
- **snippet ≠ 证据**：检索片段与摘要只是发现线索，只有抓取并通过校验门的正文可以抽取。
- **缺证据 ≠ 零效应**：证据不足时输出 `INSUFFICIENT EVIDENCE`，不得换算成"无效"。
- **无证据奠基不得设计新研究**：研究设计必须引用显式的 KnowledgeGap ID。
- **证据 append-only**：修订产生新 revision 与新 decision snapshot，绝不覆盖历史。
- **写入者唯一**：图修订只能由规范写入者提交，worker 不得直接写图。

详见 `references/scientific-invariants.md`，由 `scripts/check_autoresearch_invariants.py` 强制。

## 4. 如何新增一项能力（capability）

能力是"协议能做什么"的最小单元，它与模型、CLI、Agent 数量无关。新增一项能力需要同时落地四处，缺一不可：

1. `engine/capabilities.py`：用 `_register(...)` 注册 `capability_id`、输入/输出契约、是否可确定性本地执行，以及（如有）科学门。
2. `skill/roles/registry.yaml`：把能力分配给承担它的角色（`capabilities:` 列表）。
3. `skill/agents/<role>.md`：在 frontmatter 的 `capabilities` 中同步，并在正文写清产出契约。
4. `skill/sub-skills/<name>/SKILL.md`：frontmatter 写 `capability:`，正文按 recipe 模板给出 Inputs / Process / Output Contract / Quality Gates / Anti-Patterns。

跑 `python scripts/check_protocol_alignment.py` 验证五方一致。

## 5. 如何新增一个子技能（sub-skill）

子技能是内部能力配方，不是新的用户入口。模板：

```markdown
---
name: <dir-name>            # 必须与目录名一致
description: "..."
capability: <capability_id>  # 映射到 engine/capabilities.py
---

# <Title>
## When to Use
## Inputs
## Process
## Output Contract
## Quality Gates
## Anti-Patterns
## Worked Example
## References
```

## 6. 如何新增一个角色（role）

角色是责任单元，不是运行时 Agent。新增角色需要：`skill/roles/registry.yaml`（stage / capability / critical_path）、`skill/agents/<role>.md`（frontmatter 用 `role_id` / `capabilities` / `output_contracts` / `recommended_reasoning`，**不得写死模型或 CLI 名**）、`integrations/agent_mcp.py` 的 `ROLE_REQUIREMENTS`（只写能力等级）。

需要独立性的角色显式声明：`independence_required: different-model-family`（如 skeptic）或 `role-separation`（如 method-reviewer）。

## 7. 如何新增一个检索通道

1. 在 `retrieval/` 下实现 provider（stdlib-only、超时、定型错误，不抛异常到管道）。
2. 零配置通道进 `zero_config_academic` / `zero_config_web`；需 key 的学术通道进 `academic_key_providers`，并实现 `is_available()`。
3. 命中结果统一为 `SearchHit`；沿用 `doc_id` / `chunk_id` / `offset` 表达定位（如适用）。
4. 在 `docs/` 记录端点契约，在 `references/retrieval-compliance.md` 补齐配额与限制，在 `tests/` 用 mock HTTP 覆盖成功与各类失败。

## 8. 证据纪律与文档

- 示例与演示必须如实标注 `data_origin`（manual_curated / synthetic / hybrid）；不得把手工整理文献说成模型运行结果。
- 数字口径以 `docs/metrics.json` 为准，文档中不硬编码会漂移的计数。
- 内部文档用中文，`SKILL.md` 保持英文；协议语义（九步、四态、Projection 边界）不因文档改写而改变。

## 9. PR 检查表

- [ ] 五个门本地全绿（版本 / 指标 / skill_lint / 协议对齐 / 测试）。
- [ ] 新增或改动的契约在五方（协议 / 能力 / 角色 / 简报 / 子技能）一致。
- [ ] 未引入硬编码的模型名、CLI 名或密钥。
- [ ] 科学不变量未被弱化；如有例外，在 PR 说明中显式论证。
- [ ] 文档、CHANGELOG、`docs/plans/STATUS.md` 同步更新。
- [ ] 未提交本地运行状态、私有数据或凭据。

## 10. 行为准则

讨论以证据为准：提出结论时给出可核验来源；被反驳时更新结论而不是更新措辞。对他人贡献的评审聚焦"证据是否支撑结论"，不针对作者。

