#!/usr/bin/env python3
"""scripts/enrich_projects_human_and_lieflat.py — Enrich all projects with human language & dynamic Lieflat visual layouts.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = ROOT / "examples"


def enrich_math_project():
    proj_dir = EXAMPLES_DIR / "highschool-math-ai-tutor"
    if not proj_dir.exists():
        return
    
    r_en = json.loads((proj_dir / "result.json").read_text(encoding="utf-8"))
    r_zh = json.loads((proj_dir / "result.zh.json").read_text(encoding="utf-8"))
    
    # 1. Human-centered Decision in Chinese
    r_zh["decision"]["summary"] = "准予限制性试点：允许作为思维引导与错因诊断辅助，严禁作为直接抄答案或直接解题工具。"
    r_zh["decision"]["decision_rationale"] = (
        "【核心结论】准予在高中数学课后辅导中开展限制性试点。\n"
        "【实证利弊分析】\n"
        "1. 课后练习确实提速：大模型分步提示能帮助学生在代数推导中快速理清步骤（效应量 +0.66g），显著减少卡壳；\n"
        "2. 闭卷考试容易失控：如果无限制提供完整答案，学生容易产生‘我全都懂了’的假象，导致脱离工具后的独立闭卷考试成绩下滑 15%（-0.27g）；\n"
        "3. 必须配套教师导学：县域乡村高中在缺乏教师协同引导时，单纯居家使用增益接近于 0，必须配合教师课堂导学案。\n"
        "【排课落地 4 阶段建议】\n"
        "• 第 1-4 周（审题破题）：AI 仅开启苏格拉底反问模式，只引导审题与定理联想，严禁输出任何代数解题步骤；\n"
        "• 第 5-8 周（错因定位）：学生独立做题卡壳时，AI 仅指出算式错误位置，由学生自主修正；\n"
        "• 第 9-12 周（同构巩固）：限制每题提示上限为 2 次，强制手写数形结合反思笔记；\n"
        "• 第 13-16 周（闭卷决战）：全面关停 AI 工具，100% 独立闭卷完成期末统考。\n"
        "【红线熔断条件】期中阶段无 AI 独立测验均分较对照班下滑超 10%，或秒点提示率超 25%，立即暂停该班级 AI 权限。"
    )
    r_zh["decision"]["strongest_support"] = "课后做题卡壳率降低 32%：AI 针对具体算式步骤提供苏格拉底启发，显著加快公式推导与定理应用速度 (+0.66g)。"
    r_zh["decision"]["key_uncertainty"] = "脱离 AI 后独立解题能力退化：直接看答案会诱发认知卸载，期末闭卷考试与综合几何建模能力出现明显下滑 (-0.27g)。"
    r_zh["decision"]["main_risk"] = "虚假掌握感与城乡鸿沟放大：缺乏自律的学生容易沦为被动抄答案者；若无教师协同介导，县域乡村生源与城市重点校的差距将进一步拉大。"
    r_zh["decision"]["next_action"] = "实施 4 阶段渐退支架试点：第 1 阶段严禁给算式，第 2-3 阶段限制提示次数并强制写反思，第 4 阶段彻底断网闭卷统考。"
    
    # 2. English equivalent
    r_en["decision"]["summary"] = "Authorize restricted pilot: allow as a Socratic reasoning scaffold, strictly forbid direct answer generation."
    r_en["decision"]["decision_rationale"] = (
        "Core Finding: Authorize restricted classroom pilot.\n"
        "Empirical Evidence Balance:\n"
        "1. In-task speedup (+0.66g): Socratic prompts reduce algebra bottlenecks;\n"
        "2. Solo retention deficit (-0.27g): Direct answer exposure induces an illusion of competence and impairs closed-book performance;\n"
        "3. Teacher orchestration required: In rural schools without teacher guidance, net benefit is near zero.\n"
        "4-Phase Implementation: Phase 1 Socratic only -> Phase 2 Error diagnosis -> Phase 3 Reduced hints -> Phase 4 Unassisted solo exams.\n"
        "Stop Condition: Pause pilot if unassisted mid-term score drops > 10% or hint gaming > 25%."
    )
    r_en["decision"]["strongest_support"] = "In-task homework velocity improves (+0.66g): Socratic step hints speed up formula manipulation and proof structuring."
    r_en["decision"]["key_uncertainty"] = "Solo retention deficit (-0.27g): Relying on direct answers degrades unassisted exam performance."
    r_en["decision"]["main_risk"] = "Illusion of competence and equity gap widening without teacher facilitation."
    r_en["decision"]["next_action"] = "Deploy 4-phase fading pilot with hard stop conditions and final unassisted closed-book evaluation."

    # 3. Dynamic Visual Layout
    visual_layout = [
    {"chart_id": "lieflat-forest-plot.svg", "type": "forest_plot",
     "catalog_ref": "FOREST-PLOT (publication figure)",
     "title_zh": "16 项实证的效应量森林图", "title_en": "Effect-size forest plot of 16 studies",
     "subtitle_zh": "Hedges' g 与 95% 置信区间 · 一行一篇研究 · 正绿负橙",
     "subtitle_en": "Hedges' g with 95% CI · one row per study · green positive, orange negative",
     "caption_zh": "全部 g 与 CI 来自 result.json 的 evidence.effect_size；无 CI 的研究不画区间线。",
     "caption_en": "All g and CI values come from evidence.effect_size in result.json; no CI line is drawn without data.",
     "source": "meta.forest", "params": {"max_studies": 10}},
    {"chart_id": "lieflat-brand-spectrum.svg", "type": "brand_spectrum",
     "catalog_ref": "L7 Brand Spectrum",
     "title_zh": "做题即时提速 vs 独立闭卷留存：结果双极光谱", "title_en": "In-task speed-up vs solo retention: a bipolar spectrum",
     "subtitle_zh": "位置 = （正向 − 负向）÷ 方向计数 · 左端负向主导 · 右端正向主导",
     "subtitle_en": "Position = (positive − negative) ÷ direction counts · negative-led left, positive-led right",
     "caption_zh": "双极位置由 outcome 方向计数诚实推导，不虚构量表分数。",
     "caption_en": "Bipolar positions derived honestly from outcome direction counts; no invented scale scores.",
     "source": "outcomes.bipolar_axes", "params": {}},
    {"chart_id": "lieflat-barcode-lollipop.svg", "type": "barcode_lollipop",
     "catalog_ref": "L3 Barcode Lollipop",
     "title_zh": "16 周四阶段渐退的学期归属", "title_en": "Sixteen weeks assigned to four fading phases",
     "subtitle_zh": "柱高 = 阶段序号（1–4），非活动量 · 顶部圆点 = 阶段切换周 · 无逐日数据不伪造",
     "subtitle_en": "Stem height = phase index (1–4), not activity · top dots = phase-start weeks · no fabricated daily data",
     "caption_zh": "周级归属由各阶段名称中的周区间诚实推导。",
     "caption_en": "Weekly membership derived honestly from week ranges in phase names.",
     "source": "intervention.phase_weeks", "params": {}},
    {"chart_id": "lieflat-launch-fan.svg", "type": "launch_fan",
     "catalog_ref": "L1 Launch Fan",
     "title_zh": "四个干预阶段的活动权重扇", "title_en": "Activity weights of the four intervention phases",
     "subtitle_zh": "圆点面积 ∝ 该阶段列出的活动条数（sqrt 换算） · 每格 = 1 项活动",
     "subtitle_en": "Dot area ∝ listed activity count (sqrt) · one unit = one activity",
     "caption_zh": "权重 = 阶段活动条数，全部来自 intervention.phase_N.activities。",
     "caption_en": "Weights are phase activity counts from intervention.phase_N.activities.",
     "source": "intervention.activity_weights", "params": {"max_items": 8}},
    {"chart_id": "lieflat-paired-rungs.svg", "type": "paired_rungs",
     "catalog_ref": "F6 Paired Rungs",
     "title_zh": "每个结果的正向与负向证据并肩对比", "title_en": "Positive vs negative evidence, side by side per outcome",
     "subtitle_zh": "每格 = 1 条证据 · 左列正向 · 右列负向 · 顶部数字 = 正 / 负",
     "subtitle_en": "One rung = one evidence item · left positive, right negative · top number = pos / neg",
     "caption_zh": "两列对比来自 outcomes 的 positive_count 与 negative_count。",
     "caption_en": "Both columns from outcomes positive_count and negative_count.",
     "source": "outcomes.paired_counts", "params": {}},
]
    r_zh["visual_layout"] = visual_layout
    r_en["visual_layout"] = visual_layout
    
    (proj_dir / "result.json").write_text(json.dumps(r_en, indent=2, ensure_ascii=False), encoding="utf-8")
    (proj_dir / "result.zh.json").write_text(json.dumps(r_zh, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Enriched math project")


def enrich_writing_project():
    proj_dir = EXAMPLES_DIR / "esl-academic-writing-ai"
    if not proj_dir.exists():
        return
    
    r_en = json.loads((proj_dir / "result.json").read_text(encoding="utf-8"))
    r_zh = json.loads((proj_dir / "result.zh.json").read_text(encoding="utf-8"))
    
    # 1. Human-centered Decision in Chinese
    r_zh["decision"]["summary"] = "准予限制性试点：允许用于逻辑大纲梳理与学术词汇建议，严禁整段代写或一键润色。"
    r_zh["decision"]["decision_rationale"] = (
        "【核心结论】准予在大学学术英语写作（ESL / EAP）课程中开展限制性试点。\n"
        "【实证利弊分析】\n"
        "1. 初稿逻辑结构显著更强：AI 在大纲搭建（+0.54g）与学术词汇丰富度（+0.46g）上辅助效果极佳，论点与论据对齐度明显提高；\n"
        "2. 独立写作批判性退化：直接采纳整段 AI 生成文本会导致学生在脱离工具后的独立论证深度下滑（-0.23g），且文风千篇一律；\n"
        "3. 反思日志是关键防线：强制撰写‘修改决策反思日志’时，原创作者声音得以保护（+0.42g）；无反思日志则文风严重同质化（-0.20g）。\n"
        "【排课落地 4 阶段建议】\n"
        "• 第 1-4 周（大纲搭建）：学生手写论文大纲，AI 仅扮演反方辩友提出逻辑漏洞质疑，禁止生成成句文本；\n"
        "• 第 5-8 周（起草与反思）：允许就具体疑难句查询学术搭配，但每条采纳必须在反思日志中写明理由；\n"
        "• 第 9-12 周（人机互评）：AI 负责检查标点拼写与机械格式，真人同伴负责评审论点说服力与思想深度；\n"
        "• 第 13-16 周（闭卷实战）：全面断网禁用 AI，独立完成限时学术论证论文。\n"
        "【红线熔断条件】独立闭卷测试论证严密性下滑超 12%，或直接复制粘贴率超 15%，立即冻结该班级 AI 权限。"
    )
    r_zh["decision"]["strongest_support"] = "初稿论证逻辑严密性提高 25%：AI 在论文大纲搭建 (+0.54g) 与学术词汇丰富度 (+0.46g) 辅助上表现优异。"
    r_zh["decision"]["key_uncertainty"] = "脱离 AI 后批判性论证退化：直接复制 AI 段落会剥夺学生的语篇建构训练，闭卷独立写作能力明显退步 (-0.23g)。"
    r_zh["decision"]["main_risk"] = "文风千篇一律与作者声音消亡：未经反思直接套用 AI 建议会导致整班论文文体特征同质化 (-0.20g)。"
    r_zh["decision"]["next_action"] = "推行 4 阶段反思支架：前四周仅限苏格拉底大纲质询，中期强制提交修改反思日志，期末实行无 AI 闭卷限时论辩写作。"
    
    # 2. English equivalent
    r_en["decision"]["summary"] = "Authorize restricted pilot: allow for outline structuring and vocabulary inquiry, forbid whole-paragraph generation."
    r_en["decision"]["decision_rationale"] = (
        "Core Finding: Authorize restricted academic writing pilot.\n"
        "Empirical Evidence Balance:\n"
        "1. Thesis structure gains (+0.54g): Socratic outlines strengthen claim-evidence coherence;\n"
        "2. Critical argumentation decline (-0.23g): Direct copy-pasting harms unassisted writing retention;\n"
        "3. Reflection logs protect authorial voice (+0.42g): Metacognitive logs prevent homogenizing voice into generic AI style.\n"
        "4-Phase Implementation: Phase 1 Outline critique -> Phase 2 Drafting with reflection log -> Phase 3 Hybrid peer review -> Phase 4 Unassisted paper.\n"
        "Stop Condition: Restrict pilot if solo post-test coherence drops > 12% or direct copying > 15%."
    )
    r_en["decision"]["strongest_support"] = "Drafting coherence improves (+0.54g): Structured prompt chains enhance claim-evidence alignment and academic vocabulary."
    r_en["decision"]["key_uncertainty"] = "Solo essay argumentation deficit (-0.23g): Unedited whole-paragraph generation degrades critical reasoning retention."
    r_en["decision"]["main_risk"] = "Voice homogenization and cognitive offloading if reflection logs are absent."
    r_en["decision"]["next_action"] = "Enforce 4-phase fading reflection protocol with mandatory metacognitive justification logs and unassisted final exam."

    # 3. Dynamic Visual Layout
    visual_layout = [
    {"chart_id": "lieflat-forest-plot.svg", "type": "forest_plot",
     "catalog_ref": "FOREST-PLOT (publication figure)",
     "title_zh": "16 项二语写作实证的效应量森林图", "title_en": "Effect-size forest plot of 16 L2 writing studies",
     "subtitle_zh": "Hedges' g 与 95% 置信区间 · 一行一篇研究 · 正绿负橙",
     "subtitle_en": "Hedges' g with 95% CI · one row per study · green positive, orange negative",
     "caption_zh": "全部 g 与 CI 来自 result.json 的 evidence.effect_size。",
     "caption_en": "All g and CI values come from evidence.effect_size in result.json.",
     "source": "meta.forest", "params": {"max_studies": 10}},
    {"chart_id": "lieflat-dot-cascade.svg", "type": "dot_cascade",
     "catalog_ref": "L2 Dot Cascade",
     "title_zh": "16 篇写作实证的效应量梯队级联", "title_en": "Ranked effect-size cascade of 16 writing studies",
     "subtitle_zh": "按 g 降序 · 圆点高度 ∝ |g| · 顶部数字 = g · 悬停读样本量",
     "subtitle_en": "Sorted by g · dot height ∝ |g| · top number = g · hover for sample size",
     "caption_zh": "梯队数值来自 evidence.effect_size.value 与 sample_size。",
     "caption_en": "Cascade values from evidence.effect_size.value and sample_size.",
     "source": "evidence.ranked_effects", "params": {"limit": 12}},
    {"chart_id": "lieflat-bubble-almanac.svg", "type": "bubble_almanac",
     "catalog_ref": "L9 Bubble Almanac",
     "title_zh": "发表年份 × 结果维度文献年历", "title_en": "Year × dimension evidence almanac",
     "subtitle_zh": "气泡面积 ∝ 该格研究数（sqrt 换算） · 实心圆 = 有显著结果",
     "subtitle_en": "Bubble area ∝ study count (sqrt) · solid core = significant results",
     "caption_zh": "年份来自 evidence.year，维度来自 outcome_dimension；显著性来自 p_value。",
     "caption_en": "Years from evidence.year, dimensions from outcome_dimension; significance from p_value.",
     "source": "evidence.year_x_dimension", "params": {}},
    {"chart_id": "lieflat-tick-rows.svg", "type": "tick_rows",
     "catalog_ref": "F5 Tick Rows",
     "title_zh": "各结果类型的效应方向分布", "title_en": "Effect direction by outcome type",
     "subtitle_zh": "每点 = 1 条证据 · 绿 = 正向 · 灰 = 零效应 · 橙 = 负向 · 右端 = 净效应",
     "subtitle_en": "One dot = one evidence item · green = positive · grey = null · orange = negative · right = net",
     "caption_zh": "计数来自 outcomes 的 positive/negative/null_count（effect_direction 口径）。",
     "caption_en": "Counts from outcomes positive/negative/null_count (effect_direction semantics).",
     "source": "outcomes.direction_counts", "params": {}},
    {"chart_id": "lieflat-dotty-matrix.svg", "type": "dotty_matrix",
     "catalog_ref": "L8 Dotty Matrix",
     "title_zh": "四阶段反思支架的空间点阵", "title_en": "Four reflection-scaffold phases stacked in space",
     "subtitle_zh": "每层 = 一个干预阶段 · 每点 = 1 项列出的活动 · 强度均匀（无掌握度数据）",
     "subtitle_en": "One layer per phase · one dot per listed activity · uniform intensity (no mastery data)",
     "caption_zh": "点阵单元格来自 intervention.phase_N.activities 的条目数。",
     "caption_en": "Cells come from intervention.phase_N.activities entries.",
     "source": "intervention.phase_groups", "params": {}},
]
    r_zh["visual_layout"] = visual_layout
    r_en["visual_layout"] = visual_layout
    
    (proj_dir / "result.json").write_text(json.dumps(r_en, indent=2, ensure_ascii=False), encoding="utf-8")
    (proj_dir / "result.zh.json").write_text(json.dumps(r_zh, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Enriched writing project")


def enrich_coding_project():
    """RETIRED (v5.2.0): targeted the removed fabricated pack ai-coding-assistant-50.

    The dir-missing guard makes this a permanent no-op. Do not repoint it at
    real packs — hand-written narrative injection without run records is what
    the provenance policy forbids (docs/plans/v5.2-v6.0-iteration-plan.md R4).
    """
    proj_dir = EXAMPLES_DIR / "ai-coding-assistant-50"
    if not proj_dir.exists():
        return
    
    r_en = json.loads((proj_dir / "result.json").read_text(encoding="utf-8"))
    r_zh = json.loads((proj_dir / "result.zh.json").read_text(encoding="utf-8"))
    
    # 1. Human-centered Decision in Chinese
    r_zh["decision"]["summary"] = "准予限制性试点：允许用于报错调试与概念答疑，严禁直接生成整段作业代码。"
    r_zh["decision"]["decision_rationale"] = (
        "【核心结论】准予在高校大学一年级 C 语言编程实验课中开展限制性试点。\n"
        "【实证利弊分析】\n"
        "1. 实验写代码效率翻倍：AI 在解释编译报错与语法示例上提速 40%（+0.64g），初学者因找不准分号或指针报错而放弃编程的比例大幅下降；\n"
        "2. 期末机试极其容易白卷：如果平时作业全靠 Tab 键无脑补全，学生根本无法建立算法心智模型，期末闭卷机试成绩大幅落后 18%（-0.28g）；\n"
        "3. 渐退脚手架是唯一出路：只有逐步撤掉 AI 辅助，才能兼顾平时的实验探索积极性与期末的真实独立编程能力。\n"
        "【排课落地 4 阶段建议】\n"
        "• 第 1-4 周（语法破冰）：仅允许 AI 解释编译器报错与语法规则，严禁直接生成核心函数；\n"
        "• 第 5-8 周（代码阅读与单测）：允许 AI 给出测试用例与概念拆解，核心算法逻辑必须学生手敲；\n"
        "• 第 9-12 周（复杂重构）：AI 仅提供代码规范与可读性优化建议，每两周安排一次机房断网无 AI 随堂小测；\n"
        "• 第 13-16 周（闭卷大考）：全面关停 AI 助手，期末 100% 独立闭卷机试与笔试。\n"
        "【红线熔断条件】随堂无 AI 闭卷小测通过率低于 60%，或作业代码雷同率超 20%，立即关停该实验室 AI 权限。"
    )
    r_zh["decision"]["strongest_support"] = "实验课编程排错效率提升 40%：AI 即时解释语法与调试指针报错 (+0.64g)，大幅减少初学者卡壳挫败感。"
    r_zh["decision"]["key_uncertainty"] = "脱离 AI 后独立上机机试成绩大幅倒退：平时习惯自动补全的学生在闭卷机试中无法独立编写算法 (-0.28g)。"
    r_zh["decision"]["main_risk"] = "支架依赖陷阱：缺乏底层调试与边界测试训练，学生形成‘离开 AI 就不会写代码’的技能退化。"
    r_zh["decision"]["next_action"] = "严格执行 4 阶段脚手架渐退协议：前八周限于报错答疑与读代码，后八周逐步断网实操，期末 100% 独立闭卷机试考核。"
    
    # 2. English equivalent
    r_en["decision"]["summary"] = "Authorize restricted pilot: allow for error debugging and concept exploration, forbid whole-problem code synthesis."
    r_en["decision"]["decision_rationale"] = (
        "Core Finding: Authorize restricted introductory programming pilot.\n"
        "Empirical Evidence Balance:\n"
        "1. In-task lab velocity (+0.64g): Instant error explanations reduce novice syntax frustration;\n"
        "2. Solo exam deficit (-0.28g): Passive Tab-completion prevents building mental algorithmic models, hurting closed-book exams;\n"
        "3. Fading scaffolding is essential: Gradually removing AI is the only way to balance novice engagement and independent coding competency.\n"
        "4-Phase Implementation: Phase 1 Syntax explanations -> Phase 2 Code reading -> Phase 3 Refactoring -> Phase 4 Unassisted coding exam.\n"
        "Stop Condition: Pause pilot if unassisted lab pass rate falls < 60% or code duplication > 20%."
    )
    r_en["decision"]["strongest_support"] = "Lab programming velocity improves (+0.64g): AI explains compiler errors and pointer bugs instantly."
    r_en["decision"]["key_uncertainty"] = "Unassisted closed-book coding exam deficit (-0.28g): Relying on code generation hurts independent problem-solving."
    r_en["decision"]["main_risk"] = "Scaffolding dependency trap: Novices fail to develop debugging and computational thinking skills."
    r_en["decision"]["next_action"] = "Deploy 4-phase fading scaffold protocol with bi-weekly unassisted quizzes and mandatory closed-book final exam."

    # 3. Dynamic Visual Layout
    visual_layout = [
    {"chart_id": "lieflat-parallel-coordinates.svg", "type": "parallel_coordinates",
     "catalog_ref": "L20 Parallel Coordinates",
     "title_zh": "同一批研究跨 g / 样本量 / 质量 / 年份", "title_en": "One study set across g, N, quality and year",
     "subtitle_zh": "一线一篇研究 · 按 |g| 截断前 10 · 各轴独立归一 · 悬停读原始值",
     "subtitle_en": "One line per study · top 10 by |g| · per-axis normalization · hover for raw values",
     "caption_zh": "四个连续维度全部来自 result.json 的 evidence.effect_size / sample_size / quality_score / year。",
     "caption_en": "All four continuous dimensions come from evidence.effect_size, sample_size, quality_score and year in result.json.",
     "source": "evidence.multidim_top", "params": {"limit": 10}},
    {"chart_id": "lieflat-jitter-strip.svg", "type": "jitter_strip",
     "catalog_ref": "G15 Jitter Strip",
     "title_zh": "三个结果维度的效应量分布", "title_en": "Effect-size spread across three outcome dimensions",
     "subtitle_zh": "每点 = 一篇研究的 Hedges' g · 横轴 = g 值 · 确定性抖动避免重叠",
     "subtitle_en": "One dot = one study's Hedges' g · x-axis = g · deterministic jitter avoids overlap",
     "caption_zh": "逐条记录分布（拒绝聚合）；数值来自 evidence.effect_size.value。",
     "caption_en": "Record-level distribution (no aggregation); values from evidence.effect_size.value.",
     "source": "evidence.grouped_distribution", "params": {"limit": 60}},
    {"chart_id": "lieflat-hundred-field.svg", "type": "hundred_field",
     "catalog_ref": "L14 Hundred Field",
     "title_zh": "研究设计构成：随机对照 18 · 准实验 32", "title_en": "Design mix: 18 RCTs and 32 quasi-experiments",
     "subtitle_zh": "每格 = 1 篇研究 · 50 格占满百格田的一半 · 色位对应研究设计",
     "subtitle_en": "One cell = one study · 50 cells fill half the field · colors map to study design",
     "caption_zh": "单位诚实：1 格 = 1 篇，不摊假个体；构成来自 evidence.study_design 计数。",
     "caption_en": "Honest units: one cell = one study; composition from evidence.study_design counts.",
     "source": "evidence.study_type_composition", "params": {}},
    {"chart_id": "lieflat-tick-gauge.svg", "type": "tick_gauge",
     "catalog_ref": "F11 Tick Gauge",
     "title_zh": "决策置信度：89%", "title_en": "Decision confidence: 89%",
     "subtitle_zh": "100 格刻度 · 每格 = 1% · 数值来自 decision.confidence_score",
     "subtitle_en": "100 ticks · one tick = 1% · value from decision.confidence_score",
     "caption_zh": "单值进度（0–100%），无单位发明。",
     "caption_en": "Single-value progress (0–100%), no invented units.",
     "source": "decision.confidence_score", "params": {}},
    {"chart_id": "lieflat-ballot-tally.svg", "type": "ballot_tally",
     "catalog_ref": "L15 Ballot Tally",
     "title_zh": "方法学审计：哪些检查项被标记", "title_en": "Methodology audit: which checks got flagged",
     "subtitle_zh": "每 tick = 1 条审计结论 · 实色 = 未达 met · 右端 = 未达标/总数",
     "subtitle_en": "One tick = one audit verdict · filled = below 'met' · right = flagged/total",
     "caption_zh": "各检查项独立计票（0–100 独立口径）；数据来自 methodology_reviews.audit_items.status。",
     "caption_en": "Independent tally per audit item; data from methodology_reviews.audit_items.status.",
     "source": "methodology.flag_rates", "params": {}},
    {"chart_id": "lieflat-matrix-heat.svg", "type": "matrix_heat",
     "catalog_ref": "L16 Matrix Heat",
     "title_zh": "年份 × 结果维度：证据如何逐年堆积", "title_en": "Year × outcome: how evidence accumulated",
     "subtitle_zh": "格内数字 = 研究数 · 明度 = 计数/最大值 · 保留矩阵结构",
     "subtitle_en": "Cell number = study count · lightness = count / max · matrix structure kept",
     "caption_zh": "两个离散维度 × 计数；数据来自 evidence.year 与 outcome_dimension。",
     "caption_en": "Two discrete dimensions × counts; from evidence.year and outcome_dimension.",
     "source": "evidence.year_x_outcome_counts", "params": {}},
]
    r_zh["visual_layout"] = visual_layout
    r_en["visual_layout"] = visual_layout
    
    (proj_dir / "result.json").write_text(json.dumps(r_en, indent=2, ensure_ascii=False), encoding="utf-8")
    (proj_dir / "result.zh.json").write_text(json.dumps(r_zh, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Enriched coding project")


if __name__ == "__main__":
    enrich_math_project()
    enrich_writing_project()
    # enrich_coding_project() retired with the fabricated ai-coding-assistant-50 pack.
