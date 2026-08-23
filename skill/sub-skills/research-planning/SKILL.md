---
name: research-planning
description: "Extracts the structured Education Research Frame (PICO + decision target) from user natural language and determines execution mode (S/M/L) via the Complexity Gate."
---
# Research Planning Skill

## 1. When to Use
Trigger this skill when the user initiates a new empirical educational or social science inquiry or updates the research scope. This is the **Frame** stage of the Canonical Protocol (docs/architecture.md).

## 2. Process
1. **Frame Formulation (Education Research Frame)**:
   - **Population (P)**: Target learner/cohort demographics, grade level, domain.
   - **Intervention (I)**: Specific pedagogical technique, tool, AI system, or curriculum change.
   - **Comparison (C)**: Active control, business-as-usual, or non-intervention baseline.
   - **Outcomes (O)**: Primary and secondary outcome metrics (task performance vs delayed transfer must be separated).
   - **decision_target + scope + inclusion/exclusion criteria**: required by education-frame.schema.json.
2. **Complexity Gating (S/M/L)** (scripts/complexity_gate.py, 全程唯一权威分级):
   - S (Quick Fact): Fact-checking single claim (k=3-5).
   - M (Standard Review): Full multi-source evidence review (k=8-15).
   - L (Deep Causal Cycle): Synthesis + Trial Design + Empirical DID Regression.
3. **Output Contract**: Frame 本体按 schemas/education-frame.schema.json（V1）校验；研究意图投影用 schemas/v2/research-intent.schema.json（V2 契约）。框架完整前禁止任何教学建议（领域层第一道闸门）。
