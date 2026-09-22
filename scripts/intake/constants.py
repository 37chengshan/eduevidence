"""Shared constants for the one-shot two-round intake."""
from __future__ import annotations

SCHEMA_VERSION = 1
PREFS_NAME = "prefs.json"
THEME_NAMES = ("claude", "academic", "datalab", "datalab-dark", "presentation")
ENHANCEMENTS = ("agent_mcp", "jev", "semdecide", "none")
DEPTH_CHOICES = ("S", "M", "L", "auto")
DEPTH_ALIASES = {"quick": "S", "standard": "M", "deep": "L"}

# Fixed round-1 labels (mirrored verbatim in skill/workflows/intake.md).
ENHANCEMENT_BLURBS: dict[str, str] = {
    "agent_mcp": "Agent MCP — 多 CLI/多模型分工、独立子上下文、超时恢复（可选执行增强）",
    "jev": "Jev — 轻量工具子集派发，适合把确定性小步交给受限工具面",
    "semdecide": "SemDecide — 语义决策辅助，只结构化上游意图，不改下游确定性路由",
    "none": "均不启用 — 平台原生模式，零外部执行增强",
}
DEPTH_BLURBS: dict[str, str] = {
    "S": "S 快检 — 单点问题，最小检索面，直接给边界结论",
    "M": "M 标准 — 常规采用/比较问题，标准证据到决策流程",
    "L": "L 深研 — 高影响、有争议或要试点，完整深研与决策扩展",
    "auto": "自动 — 不选则按指南判定：单点→S，常规采用→M，高影响/争议/要试点→L，不确定取 M",
}

# Auto-depth guideline keywords (deterministic aid; the agent's judgment wins).
L_AUTO_SIGNALS = (
    "试点", "pilot", "高影响", "争议", "全校", "全面部署", "政策",
    "rollout", "high-stakes", "high stakes",
)
S_AUTO_SIGNALS = (
    "单点", "一句话", "快速", "简要", "是不是", "对不对", "解释一下",
    "定义", "公式", "quick", "trivial",
)
M_AUTO_SIGNALS = (
    "是否", "有效", "影响", "比较", "对比", "采用", "adopt", "vs",
    "效果", "evidence", "review",
)

# Frame boundary slots and light inference cues (never invent; only extract).
FRAME_SLOTS = ("population", "intervention", "comparison", "primary_outcome", "context")
POP_CUES = (
    "大一", "大二", "大三", "大四", "本科", "研究生", "高中", "初中", "小学",
    "成人", "职业", "CS1", "大学生", "中学生", "小学生", "undergraduate", "K-12",
)
OUTCOME_CUES = (
    "独立编程", "学习效果", "学习保持", "迁移", "学业成绩", "保持", "retention",
    "transfer", "learning", "成绩", "能力", "依赖", "诚信",
)
CONTEXT_CUES = ("线上", "线下", "混合", "小班", "大班", "MOOC", "翻转", "课堂", "实验室")

SLOT_LABELS = {
    "population": "人群（目标学习者/决策对象）",
    "intervention": "干预（具体方法/工具及用法）",
    "comparison": "对照（与什么比较；可用 BAU）",
    "primary_outcome": "主结果（一个主要结果指标）",
    "context": "情境（学制/班型/线上线下/支持条件）",
}
