---
name: research-planning
description: "Extracts the structured Research Frame (PICO + decision target, in the selected domain's vocabulary) from user natural language and determines execution mode (S/M/L) via the Complexity Gate."
capability: research_framing
---

# Research Planning Skill

## When to Use
Trigger this skill when the user initiates a new empirical inquiry — education, policy, organisational practice, or any other registered domain — or updates the research scope. This is the **Frame** stage of the Canonical Protocol (`docs/architecture.md`).

## Inputs
- 用户原始问题（自然语言，可能含隐含假设）
- 可选结构化线索：population / intervention / comparison / outcomes / constraints / depth
- 领域（决定 frame 词汇）：education（learner/course）/ policy（decision_object/population/stakeholders），或其他注册在 `domains/` 下的领域

## Process
1. **Frame Formulation (Research Frame，字段随领域而定)**
   - **Population (P)**: Who or what the decision acts on — learners and courses in education, affected groups and stakeholders in policy, customers or staff in organisations. Use the field vocabulary of the selected domain.
   - **Intervention (I)**: The specific practice under decision — a teaching method, tool, AI system, curriculum change, regulation, process or programme.
   - **Comparison (C)**: Active control, business-as-usual, or non-intervention baseline.
   - **Outcomes (O)**: Primary and secondary outcome metrics; task performance and delayed transfer must stay separate.
   - **decision target + scope + inclusion/exclusion criteria**: required by the selected domain's frame schema.
2. **Complexity Gating (S/M/L)** — `scripts/complexity_gate.py` is the single authority:
   - S (Quick Fact): fact-check a single claim (k=3–5).
   - M (Standard Review): full multi-source evidence review (k=8–15).
   - L (Deep Causal Cycle): synthesis + trial design + empirical DID regression.
3. **Missing inputs**: ask the user (`NEEDS_USER_CONTEXT`); never invent a default population, comparator, or outcome.

## Output Contract
- Frame body validates against the selected domain's frame schema (`domains/<id>/manifest.json` → `frame_schema`): `schemas/education-frame.schema.json` for education, `domains/policy/frame.schema.json` for policy.
- Research-intent projection uses `schemas/v2/research-intent.schema.json` (V2 contract).
- **No intervention advice may be produced before framing completes** — the domain layer's first gate.

## Quality Gates
- [ ] PICO 五要素齐全，comparator 明确，且字段词汇与所选领域一致。
- [ ] primary outcome 与 secondary/risk outcome 分离。
- [ ] scope 与纳排标准可操作，非"相关研究"式表述。
- [ ] 随 frame 输出 S/M/L 等级建议。

## Anti-Patterns
- 把"相关研究"当作 scope；把任务完成速度当作学习效果；为缺失人群编造默认值；frame 未完成即给干预建议；把某个领域的字段强制套到另一个领域。

## Worked Example
输入"大一 C 语言课程要不要允许用 AI 编程助手？" → education 域：population=CS1 学生；intervention=生成式 AI 编程助手（含护栏）；comparison=无 AI 常规教学；primary outcome=独立考试成绩（learning）；decision_target=teaching_decision。同一协议在 policy 域写成：population=客服团队与受影响客户；intervention=带人工审核的 AI 助手；decision_object=adopt。

## References
- `schemas/education-frame.schema.json`、`references/education-framing.md`、`references/outcome-taxonomy.md`、`skill/task-briefs/frame.md`
