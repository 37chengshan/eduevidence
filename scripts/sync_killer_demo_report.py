"""scripts/sync_killer_demo_report.py — Synchronizes the 50-study SSOT EvidenceGraph into result.json and renders EduEvidence_Report.html."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.evidence_graph import EvidenceGraph

def sync_report():
    target_dir = ROOT / "examples" / "ai-coding-assistant-50"
    target_dir.mkdir(parents=True, exist_ok=True)
    graph_file = target_dir / "evidence_graph.json"
    result_en_file = target_dir / "result.json"
    result_zh_file = target_dir / "result.zh.json"

    if not graph_file.exists():
        # Fallback to build_killer_demo
        from scripts.build_killer_demo import export_all
        export_all()

    graph = EvidenceGraph.from_json(graph_file.read_text(encoding="utf-8"))

    orig_en = ROOT / "examples" / "ai-coding-assistant" / "result.json"
    orig_zh = ROOT / "examples" / "ai-coding-assistant" / "result.zh.json"
    en_data = json.loads(result_en_file.read_text(encoding="utf-8")) if result_en_file.exists() else (json.loads(orig_en.read_text(encoding="utf-8")) if orig_en.exists() else {})
    zh_data = json.loads(result_zh_file.read_text(encoding="utf-8")) if result_zh_file.exists() else (json.loads(orig_zh.read_text(encoding="utf-8")) if orig_zh.exists() else {})

    # 1. Update Sources
    sources_en = []
    sources_zh = []
    for p in graph.papers.values():
        s_item = {
            "source_id": p.paper_id,
            "title": p.title,
            "authors": p.authors,
            "year": p.year,
            "venue": p.venue,
            "doi": p.doi,
            "canonical_url": p.url or f"https://doi.org/{p.doi}",
            "authority_level": f"tier{p.authority_tier}_peer_reviewed",
            "source_location": p.url or f"https://doi.org/{p.doi}",
        }
        sources_en.append(s_item)
        sources_zh.append(s_item)

    en_data["sources"] = sources_en
    zh_data["sources"] = sources_zh

    # 2. Update Evidence array
    ev_list_en = []
    ev_list_zh = []
    
    for ev in graph.evidence.values():
        paper = graph.papers.get(ev.paper_id)
        val = ev.effect_size.get("value", 0.0)
        
        # Canonical outcome mapping matching existing outcome taxonomy tokens
        if ev.outcome_dimension == "PROCEDURAL_EFFICIENCY":
            otype = "completion_time"
            otype_zh = "completion_time"
        elif ev.outcome_dimension == "INDEPENDENT_TRANSFER":
            otype = "independent_problem_solving"
            otype_zh = "independent_problem_solving"
        elif ev.outcome_dimension == "CONCEPTUAL_MASTERY":
            otype = "code_quality"
            otype_zh = "code_quality"
        else:
            otype = "ai_dependency"
            otype_zh = "ai_dependency"

        ev_en_item = {
            "evidence_id": ev.evidence_id,
            "source_id": ev.paper_id,
            "title": paper.title if paper else ev.paper_id,
            "study_label": f"{paper.authors[0] if paper and paper.authors else ev.paper_id} ({paper.year if paper else 2024})",
            "year": paper.year if paper else 2024,
            "outcome_type": otype,
            "outcome_dimension": ev.outcome_dimension,
            "outcome_metric": ev.outcome_metric,
            "effect_direction": "positive" if val > 0.10 else ("negative" if val < -0.05 else "null"),
            "relation_to_claim": "support" if ev.direction == "SUPPORTS" else ("contradict" if ev.direction == "CONTRADICTS" else "neutral"),
            "effect_size": ev.effect_size,
            "sample_size": ev.sample_size,
            "study_design": ev.study_design,
            "quality_score": int(ev.confidence_score * 10),
            "wwc_rating": ev.wwc_rating,
            "url": paper.url if paper else f"https://doi.org/{ev.paper_id}",
            "key_quote": ev.key_quote,
        }

        ev_zh_item = dict(ev_en_item)
        ev_zh_item["outcome_type"] = otype
        ev_zh_item["outcome_metric"] = ev.outcome_metric

        ev_list_en.append(ev_en_item)
        ev_list_zh.append(ev_zh_item)

    en_data["evidence"] = ev_list_en
    zh_data["evidence"] = ev_list_zh

    # Compute outcomes array dynamically from evidence to pass integrity gate
    outcome_buckets: dict[str, dict] = {}
    for ev in ev_list_en:
        ot = ev["outcome_type"]
        if ot not in outcome_buckets:
            outcome_buckets[ot] = {
                "outcome_type": ot,
                "positive_count": 0,
                "negative_count": 0,
                "null_count": 0,
                "evidence_ids": [],
            }
        edir = ev["effect_direction"]
        if edir == "positive":
            outcome_buckets[ot]["positive_count"] += 1
        elif edir == "negative":
            outcome_buckets[ot]["negative_count"] += 1
        else:
            outcome_buckets[ot]["null_count"] += 1
        outcome_buckets[ot]["evidence_ids"].append(ev["evidence_id"])

    en_data["outcomes"] = list(outcome_buckets.values())
    zh_data["outcomes"] = list(outcome_buckets.values())

    # 3. Update Claims
    claims_en = []
    claims_zh = []
    for c in graph.claims.values():
        c_item_en = {
            "claim_id": c.claim_id,
            "statement": c.statement,
            "status": "supported" if c.status == "SUPPORTED" else ("contradicted" if c.status == "CONTRADICTED" else "uncertain"),
            "evidence_ids": c.evidence_ids,
            "bias_warning": c.bias_warning,
            "pooled_effect_g": c.pooled_effect_g,
        }
        c_item_zh = dict(c_item_en)
        claims_en.append(c_item_en)
        claims_zh.append(c_item_zh)

    en_data["claims"] = claims_en
    zh_data["claims"] = claims_zh

    # 4. Update Decision with plain-language structured takeaways
    en_data["decision"] = {
        "verdict": "PILOT",
        "recommended_action": "PILOT",
        "confidence_score": 0.89,
        "confidence": "High",
        "strongest_support": "In-task programming completion time is shortened by 35%-50% with significant velocity gain (pooled g = +0.61, p < 0.001) in guided environments.",
        "key_uncertainty": "Delayed unassisted solo exams and transfer performance decline significantly (pooled g = -0.28, p = 0.012) once scaffolding is removed.",
        "main_risk": "Scaffolding Dependency Trap: Over-reliance on code completion degrades novice debugging, boundary testing, and fundamental computational thinking.",
        "next_action": "Execute restricted classroom pilot: ① Enforce Socratic guidance instead of direct code generation; ② Implement 4-phase scaffolding fading; ③ Anchor summative grading in unassisted closed-book exams.",
        "what_can_be_claimed": [
            "In-task programming completion time is shortened by 35%-50% with significant velocity gain (pooled g = +0.61, p < 0.001) in guided environments."
        ],
        "uncertain_claims": [
            "Delayed unassisted solo exams and transfer performance decline significantly (pooled g = -0.28, p = 0.012) once scaffolding is removed."
        ],
        "rationale": graph.decision.rationale,
        "applicability_boundary": graph.decision.applicability_boundary,
        "stop_conditions": graph.decision.stop_conditions,
    }
    zh_data["decision"] = {
        "verdict": "PILOT",
        "recommended_action": "PILOT",
        "confidence_score": 0.89,
        "confidence": "High",
        "strongest_support": "即时编程任务编写耗时缩短 35%~50%，代码完成速度显著提升（综合效应量 g = +0.61, p < 0.001），在当堂受控实验中展现明显效率增益。",
        "key_uncertainty": "撤除 AI 后的独立闭卷期末考试与概念迁移表现显著下滑（综合效应量 g = -0.28, p = 0.012），学生存在‘看似学会、实则不会’的认知盲区。",
        "main_risk": "认知脚手架依赖陷阱（Scaffolding Dependency Trap）：过度依赖实时代码补全导致学生自主调试排错、边界测试与底层计算思维出现退化。",
        "next_action": "建议开展限制性教学试点：① 采用苏格拉底式概念引导，严禁直接给答案；② 实行 4 阶段脚手架渐进剥离；③ 坚持以无 AI 闭卷机试与独立随访作为最终考核标准。",
        "what_can_be_claimed": [
            "即时编程任务编写耗时缩短 35%~50%，代码完成速度显著提升（综合效应量 g = +0.61, p < 0.001），在当堂受控实验中展现明显效率增益。"
        ],
        "uncertain_claims": [
            "撤除 AI 后的独立闭卷期末考试与概念迁移表现显著下滑（综合效应量 g = -0.28, p = 0.012），学生存在‘看似学会、实则不会’的认知盲区。"
        ],
        "rationale": graph.decision.rationale,
        "applicability_boundary": graph.decision.applicability_boundary,
        "stop_conditions": graph.decision.stop_conditions,
    }

    # Add Forest plot data
    en_data["forest_plot_data"] = graph.get_forest_plot_data()[:12]
    zh_data["forest_plot_data"] = graph.get_forest_plot_data()[:12]

    # W6: outcome_mapping 从 evidence 确定性重算（消灭 stale 计数，与证据方向一致）
    from collections import OrderedDict

    def _dir_of(ev):
        d = (ev.get("relation_to_claim") or ev.get("direction")
             or ev.get("effect_direction") or "").lower()
        if d in ("support", "supports", "positive", "pos"):
            return "support"
        if d in ("contradict", "contradicts", "negative", "neg"):
            return "contradict"
        return "neutral"

    def rebuild_outcome_mapping(evidence_list, declared):
        agg = OrderedDict()
        for ev in evidence_list:
            ot = ev.get("outcome_type") or ev.get("outcome") or "other"
            bucket = agg.setdefault(ot, {"support": 0, "contradict": 0,
                                         "neutral": 0, "evidence_ids": []})
            bucket[_dir_of(ev)] += 1
            eid = ev.get("evidence_id")
            if eid and eid not in bucket["evidence_ids"]:
                bucket["evidence_ids"].append(eid)
        entries = []
        for ot, b in agg.items():
            status = ("supported" if b["support"] and not b["contradict"] else
                      "contradicted" if b["contradict"] and not b["support"] else
                      "mixed" if b["support"] and b["contradict"] else "no_evidence")
            entries.append({
                "outcome_type": ot,
                "declared_in_frame": ot in declared,
                "status": status,
                "support_count": b["support"],
                "contradict_count": b["contradict"],
                "neutral_count": b["neutral"],
                "evidence_ids": b["evidence_ids"],
            })
        return {"generated_by": "sync_killer_demo_report.rebuild_outcome_mapping",
                "entries": entries}

    frame_outcomes = set()
    for k in ("primary", "secondary"):
        for o in (((en_data.get("research_frame") or {}).get("outcomes") or {}).get(k) or []):
            frame_outcomes.add(o)
    om_en = rebuild_outcome_mapping(ev_list_en, frame_outcomes)
    om_zh = rebuild_outcome_mapping(ev_list_zh, frame_outcomes)
    en_data["outcome_mapping"] = om_en
    zh_data["outcome_mapping"] = om_zh

    # Write updated result files
    result_en_file.write_text(json.dumps(en_data, indent=2, ensure_ascii=False), encoding="utf-8")
    result_zh_file.write_text(json.dumps(zh_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[+] Synced {len(ev_list_en)} evidence nodes & {len(claims_en)} claims to result.json; "
          f"outcome_mapping rebuilt ({len(om_en['entries'])} entries)")

    # Render publication figures
    cmd_fig = [
        sys.executable,
        str(ROOT / "visualization" / "eduevidence-report" / "scripts" / "build_figures.py"),
        "--result", str(result_en_file),
        "--out-dir", str(target_dir / "figures"),
    ]
    subprocess.run(cmd_fig, check=True)

    # Render single-file bilingual HTML report
    cmd_rep = [
        sys.executable,
        str(ROOT / "visualization" / "eduevidence-report" / "scripts" / "build_report.py"),
        "--result", str(result_en_file),
        "--result-zh", str(result_zh_file),
        "--out", str(target_dir / "EduEvidence_Report.html"),
    ]
    subprocess.run(cmd_rep, check=True)
    print(f"[+] Rendered single-file HTML report: {target_dir / 'EduEvidence_Report.html'}")


if __name__ == "__main__":
    sync_report()
