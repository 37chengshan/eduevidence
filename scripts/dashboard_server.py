"""scripts/dashboard_server.py — EduEvidence 5.0 Local Web Studio.

Lightweight static + API server for the 3-page Web Studio (web/):

  1. 仪表盘 (Dashboard)          — cross-project KPIs, effect-size comparison, asset matrix
  2. 报告浏览 (Report Browser)    — browse baked report files (default + reports-5themes/* variants)
                                    in an iframe; themes are fixed at generation time
  3. 数据可视化 (Data Visualization) — per-project forest plot / effect-size distribution /
                                    outcome-dimension summary / SSOT evidence graph

No agent dispatch, no subprocess streaming. Every value is read directly from the
project artifacts the skill pipeline emits (examples/<id>/result.json +
evidence_graph.json), so a newly completed project appears automatically.

Usage:
    python3 scripts/dashboard_server.py --host 127.0.0.1 --port 8765
"""
from __future__ import annotations

import argparse
import http.server
import json
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
EXAMPLES_DIR = ROOT / "examples"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.evidence_graph import EvidenceGraph  # noqa: E402

import sys as _sys
_VIZ_SCRIPTS = ROOT / "visualization" / "eduevidence-report" / "scripts"
if str(_VIZ_SCRIPTS) not in _sys.path:
    _sys.path.insert(0, str(_VIZ_SCRIPTS))
from zh_labels import OUTCOME_ZH, ACTION_ZH, STUDY_ZH, AUTHORITY_ZH, CONFIDENCE_ZH  # noqa: E402

# Friendly display names for known demo projects; everything else falls back to
# the question text inside result.json so new projects need no manual entry.
PROJECT_TITLES: Dict[str, str] = {
    "ai-coding-assistant-evidence": "高校大一引入 AI 编程助手（真实文献旗舰示例）",
    "highschool-math-ai-tutor": "高中数学引入大模型自适应 AI Tutor 评估",
    "esl-academic-writing-ai": "大学 ESL 学术英语写作与同行评审 AI 评估",
    "ai-tutor": "大学高数课程 AI Tutor 评估",
    "ai-writing-assistant": "AI 写作助手评估",
}


def unquote_path(path: str) -> str:
    """Decode a URL path once and reject encoded separators / NUL bytes."""
    decoded = urllib.parse.unquote(path)
    if "\x00" in decoded or "\\" in decoded:
        raise ValueError("unsafe path characters")
    return decoded


def _read_json(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _decision_fields(decision: Any) -> tuple[Any, Any]:
    """Return (verdict, confidence) tolerating the three decision shapes in the wild."""
    if not isinstance(decision, dict):
        return None, None
    verdict = decision.get("verdict") or decision.get("recommended_action") or decision.get("decision")
    confidence = decision.get("confidence_score")
    if not isinstance(confidence, (int, float)):
        confidence = decision.get("confidence")
    return verdict, confidence


def _extract_effect(ev: Dict[str, Any]) -> tuple[Any, Any, Any]:
    """Return (value, ci_lower, ci_upper) from both nested and flat effect_size shapes."""
    es = ev.get("effect_size")
    if isinstance(es, dict):
        return es.get("value"), (es.get("ci_lower") or es.get("ci_lo")), (es.get("ci_upper") or es.get("ci_hi"))
    value = es if isinstance(es, (int, float)) else None
    if value is None:
        for key in ("hedges_g", "g", "effect_size_value"):
            if isinstance(ev.get(key), (int, float)):
                value = ev[key]
                break
    return value, ev.get("ci_lower"), ev.get("ci_upper")


def _graph_node_count(path: Path) -> int:
    """与 evidence_graph.export_echarts_graph() 同口径的节点数。"""
    try:
        graph = EvidenceGraph.from_json(path.read_text(encoding="utf-8"))
        export = graph.export_echarts_graph()
        nodes = export.get("nodes") or []
        return len(nodes)
    except Exception:
        data = _read_json(path) or {}

        def _size(key: str) -> int:
            value = data.get(key) or {}
            return len(value) if isinstance(value, dict) else len(value)

        return _size("papers") + _size("evidence") + _size("claims")


def _direction_counts(evidence: list) -> Dict[str, int]:
    """按 evidence 的 relation_to_claim / direction / effect_direction 聚合。"""
    counts = {"support": 0, "contradict": 0, "neutral": 0}
    for ev in evidence:
        if not isinstance(ev, dict):
            continue
        d = (ev.get("relation_to_claim") or ev.get("direction")
             or ev.get("effect_direction") or "").lower()
        if d in ("support", "supports", "positive", "pos"):
            counts["support"] += 1
        elif d in ("contradict", "contradicts", "negative", "neg"):
            counts["contradict"] += 1
        else:
            counts["neutral"] += 1
    return counts


def _outcome_rollup(evidence: list) -> List[Dict[str, Any]]:
    """无 outcome_mapping 时按 outcome_type 聚合方向计数（回退链）。"""
    roll: Dict[str, Dict[str, int]] = {}
    for ev in evidence:
        if not isinstance(ev, dict):
            continue
        ot = ev.get("outcome_type") or ev.get("outcome") or "other"
        d = (ev.get("relation_to_claim") or ev.get("direction")
             or ev.get("effect_direction") or "").lower()
        bucket = roll.setdefault(ot, {"support": 0, "contradict": 0, "neutral": 0})
        if d in ("support", "supports", "positive", "pos"):
            bucket["support"] += 1
        elif d in ("contradict", "contradicts", "negative", "neg"):
            bucket["contradict"] += 1
        else:
            bucket["neutral"] += 1
    return [{"outcome_type": k, **v} for k, v in roll.items()]


def _known_project_ids() -> set:
    """Project ids = directories with a real result.json (not the deduped display list)."""
    if not EXAMPLES_DIR.exists():
        return set()
    return {d.name for d in EXAMPLES_DIR.iterdir()
            if d.is_dir() and (d / "result.json").exists()}


def scan_local_projects() -> List[Dict[str, Any]]:
    projects: List[Dict[str, Any]] = []
    if not EXAMPLES_DIR.exists():
        return projects

    for proj_dir in sorted(EXAMPLES_DIR.iterdir()):
        if not proj_dir.is_dir():
            continue
        result_path = proj_dir / "result.json"
        if not result_path.exists():
            continue

        result = _read_json(result_path) or {}
        meta = result.get("meta") or {}
        frame = result.get("research_frame") or {}
        question = meta.get("question") or frame.get("question") or ""
        verdict, confidence = _decision_fields(result.get("decision"))

        evidence = result.get("evidence") or []
        forest = result.get("forest_plot_data") or []
        effect_values: List[float] = []
        for ev in evidence:
            value, _, _ = _extract_effect(ev)
            if isinstance(value, (int, float)):
                effect_values.append(float(value))
        for f in forest:
            if isinstance(f.get("effect_size"), (int, float)):
                effect_values.append(float(f["effect_size"]))

        graph_path = proj_dir / "evidence_graph.json"
        html_path = proj_dir / "EduEvidence_Report.html"
        report_variants: List[Dict[str, str]] = []
        themes_dir = proj_dir / "reports-5themes"
        if themes_dir.is_dir():
            for variant_file in sorted(list(themes_dir.glob("EduEvidence_Report_*.html")) + list(themes_dir.glob("report_*.html"))):
                theme_name = variant_file.stem.replace("EduEvidence_Report_", "").replace("report_", "")
                if not any(v["theme"] == theme_name for v in report_variants):
                    report_variants.append({
                        "theme": theme_name,
                        "path": str(variant_file),
                    })

        zh_result = _read_json(proj_dir / "result.zh.json") or {}
        zh_question = ((zh_result.get("meta") or {}).get("question")
                       or (zh_result.get("research_frame") or {}).get("question") or "")

        projects.append({
            "id": proj_dir.name,
            "title": PROJECT_TITLES.get(proj_dir.name) or (zh_question[:72] if zh_question else (question[:72] or proj_dir.name)),
            "title_zh": zh_question[:72] if zh_question else None,
            "domain": meta.get("domain") or "education",
            "question": question,
            "verdict": verdict,
            "confidence": confidence,
            "evidence_count": len(evidence) if isinstance(evidence, list) else 0,
            "forest_count": len(forest) if isinstance(forest, list) else 0,
            "effect_count": len(effect_values),
            "mean_effect_size": round(sum(effect_values) / len(effect_values), 3) if effect_values else None,
            "direction_counts": _direction_counts(evidence) if isinstance(evidence, list) else
                                {"support": 0, "contradict": 0, "neutral": 0},
            "has_graph": graph_path.exists(),
            "node_count": _graph_node_count(graph_path) if graph_path.exists() else 0,
            "html_report_path": str(html_path) if html_path.exists() else None,
            "report_variants": report_variants,
        })
    # Canonical question deduplication: keep the project with the highest evidence count
    deduped: Dict[str, Dict[str, Any]] = {}
    for p in projects:
        norm_q = (p.get("question") or p["id"]).strip().lower()
        if norm_q not in deduped or (p["evidence_count"] > deduped[norm_q]["evidence_count"]):
            deduped[norm_q] = p
    return list(deduped.values())


def build_stats(projects: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "total_projects": len(projects),
        "total_evidence": sum(p["evidence_count"] for p in projects),
        "total_effect_sizes": sum(p["effect_count"] for p in projects),
        "total_nodes": sum(p["node_count"] for p in projects),
    }


def get_aggregate_stats(projects: List[Dict[str, Any]]) -> Dict[str, Any]:
    """V2 兼容封装（旧 API/测试沿用）：build_stats 字段。

    Token / 成本矩阵已移除（provenance 纠偏）：历史版本在此返回硬编码的
    假 token 用量与模型成本，没有任何真实运行记录支撑。运行时未采集
    usage 前，这些指标一律如实标注 NOT_CAPTURED，不再虚构数值。
    """
    stats = build_stats(projects)
    stats["total_tokens"] = None
    stats["usage_measurement_status"] = "NOT_CAPTURED"
    return stats


def build_viz_payload(proj_id: str) -> Dict[str, Any]:
    proj_dir = EXAMPLES_DIR / proj_id
    result = _read_json(proj_dir / "result.json") or {}
    meta = result.get("meta") or {}
    frame = result.get("research_frame") or {}
    question = meta.get("question") or frame.get("question") or ""
    verdict, confidence = _decision_fields(result.get("decision"))
    title = PROJECT_TITLES.get(proj_id) or question[:72] or proj_id

    forest_items: List[Dict[str, Any]] = []
    for f in (result.get("forest_plot_data") or []):
        forest_items.append({
            "study_label": f.get("study_label") or f.get("evidence_id") or "",
            "venue": f.get("venue") or "",
            "outcome_dimension": f.get("outcome_dimension") or f.get("outcome_metric") or "",
            "effect_size": f.get("effect_size"),
            "ci_lower": f.get("ci_lower"),
            "ci_upper": f.get("ci_upper"),
            "sample_size": f.get("sample_size"),
            "direction": f.get("direction"),
            "wwc_rating": f.get("wwc_rating") or "",
        })

    effect_items: List[Dict[str, Any]] = []
    for ev in (result.get("evidence") or []):
        value, lo, hi = _extract_effect(ev)
        if isinstance(value, (int, float)):
            effect_items.append({
                "study_label": ev.get("study_label") or ev.get("title") or ev.get("evidence_id") or "",
                "value": value,
                "ci_lower": lo,
                "ci_upper": hi,
                "outcome_dimension": ev.get("outcome_dimension") or ev.get("outcome_type") or "",
                "direction": ev.get("relation_to_claim") or ev.get("direction") or ev.get("effect_direction") or "",
            })
    if not effect_items:
        for f in (result.get("forest_plot_data") or []):
            if isinstance(f.get("effect_size"), (int, float)):
                effect_items.append({
                    "study_label": f.get("study_label") or f.get("evidence_id") or "",
                    "value": f["effect_size"],
                    "ci_lower": f.get("ci_lower"),
                    "ci_upper": f.get("ci_upper"),
                    "outcome_dimension": f.get("outcome_dimension") or f.get("outcome_metric") or "",
                    "direction": f.get("direction"),
                })

    evidence_list = result.get("evidence") or []
    outcome_items: List[Dict[str, Any]] = []
    om = result.get("outcome_mapping") or {}
    entries = (om.get("entries") or []) if isinstance(om, dict) else (om if isinstance(om, list) else [])
    if entries:
        for e in entries:
            outcome_items.append({
                "outcome_type": e.get("outcome_type") or e.get("outcome") or "",
                "status": e.get("status") or "",
                "support_count": e.get("support_count") or 0,
                "contradict_count": e.get("contradict_count") or 0,
                "neutral_count": e.get("neutral_count") or 0,
            })
    else:
        # 回退链：无 outcome_mapping 时按 evidence 方向聚合
        outcome_items = _outcome_rollup(evidence_list)

    # 方向分布（任何课题都有值）
    direction_counts = _direction_counts(evidence_list) if isinstance(evidence_list, list) else \
        {"support": 0, "contradict": 0, "neutral": 0}

    graph = None
    graph_path = proj_dir / "evidence_graph.json"
    if graph_path.exists():
        try:
            graph = EvidenceGraph.from_json(graph_path.read_text(encoding="utf-8")).export_echarts_graph()
        except Exception:
            graph = None

    return {
        "id": proj_id,
        "title": title,
        "question": question,
        "verdict": verdict,
        "confidence": confidence,
        "forest": forest_items,
        "effect_sizes": effect_items,
        "outcome_mapping": outcome_items,
        "direction_counts": direction_counts,
        "labels": {
            "outcomes": OUTCOME_ZH,
            "actions": ACTION_ZH,
            "studies": STUDY_ZH,
            "authority": AUTHORITY_ZH,
            "confidence": CONFIDENCE_ZH,
        },
        "graph": graph,
    }








class StudioHandler(http.server.SimpleHTTPRequestHandler):
    """Serves web/ statically and exposes the artifact JSON API."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    # -- response helpers -------------------------------------------------
    def _send_bytes(self, data: bytes, content_type: str, status: int = 200,
                    extra_headers: Optional[Dict[str, str]] = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if extra_headers:
            for name, value in extra_headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def _send_report_bytes(self, data: bytes) -> None:
        # Reports are static, self-contained documents: no remote origins, no
        # same-origin access; sandbox-friendly CSP + X-Content-Type-Options.
        self._send_bytes(data, "text/html; charset=utf-8", extra_headers={
            "Content-Security-Policy":
                "default-src 'none'; script-src 'unsafe-inline'; "
                "style-src 'unsafe-inline'; img-src data:; "
                "font-src data:; connect-src 'none'; frame-ancestors 'self'",
            "X-Content-Type-Options": "nosniff",
        })

    def _send_json(self, payload: Any, status: int = 200) -> None:
        self._send_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                         "application/json; charset=utf-8", status)

    def _serve_file(self, path: Path, content_type: str) -> None:
        if path.exists():
            self._send_bytes(path.read_bytes(), content_type)
        else:
            self._send_json({"error": "not found"}, 404)


    # -- POST: disabled (read-only Studio) --------------------------------
    def do_POST(self) -> None:
        self._send_json({"error": "method not allowed"}, 405)

    # -- GET --------------------------------------------------------------
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Only the three-page Studio entry + the read-only artifact API.
        if path in ("/", "/index.html", "/dashboard", "/studio", "/console"):
            self._serve_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
            return

        if path == "/api/projects":
            projects = scan_local_projects()
            self._send_json({"projects": projects, "stats": build_stats(projects)})
            return

        if path == "/api/labels":
            self._send_json({
                "outcomes": OUTCOME_ZH,
                "actions": ACTION_ZH,
                "studies": STUDY_ZH,
                "authority": AUTHORITY_ZH,
                "confidence": CONFIDENCE_ZH,
            })
            return

        if path.startswith("/api/projects/"):
            suffix = urllib.parse.unquote(path[len("/api/projects/"):]).rstrip("/")
            if suffix.endswith("/viz"):
                suffix = suffix[:-len("/viz")].rstrip("/")
                if suffix not in _known_project_ids():
                    self._send_json({"error": "unknown project"}, 404)
                    return
                self._send_json(build_viz_payload(suffix))
                return
            self._send_json({"error": "not found"}, 404)
            return

        if path == "/report":
            self._serve_report(query)
            return

        # Static assets only from web/ (allowlisted), with URL-decode once and
        # containment; everything else is a JSON 404 (never super().do_GET()).
        if path.startswith("/js/") or path.startswith("/css/") or path == "/styles.css":
            self._serve_web_asset(path)
            return

        self._send_json({"error": "not found"}, 404)

    def _serve_web_asset(self, path: str) -> None:
        """Serve a static asset strictly inside WEB_DIR (decode once, no escapes)."""
        try:
            candidate = (WEB_DIR / unquote_path(path).lstrip("/")).resolve()
        except (ValueError, OSError):
            self._send_json({"error": "not found"}, 404)
            return
        base = WEB_DIR.resolve()
        if base != candidate and base not in candidate.parents:
            self._send_json({"error": "not found"}, 404)
            return
        if not candidate.is_file() or candidate.suffix not in (".js", ".css"):
            self._send_json({"error": "not found"}, 404)
            return
        ctype = "application/javascript; charset=utf-8" if candidate.suffix == ".js" \
            else "text/css; charset=utf-8"
        self._send_bytes(candidate.read_bytes(), ctype)

    def _serve_report(self, query: Dict[str, List[str]]) -> None:
        """Serve a baked report for a known project and explicit theme."""
        proj_id = query.get("id", [""])[0]
        theme = query.get("theme", ["default"])[0]

        if proj_id not in _known_project_ids():
            self._send_json({"error": "unknown project"}, 404)
            return

        proj_dir = EXAMPLES_DIR / proj_id
        if theme == "default":
            html_path = proj_dir / "EduEvidence_Report.html"
            if not html_path.is_file():
                self._send_json({"error": "report not found"}, 404)
                return
        else:
            if not theme or not all(c.isalnum() or c in "-_" for c in theme):
                self._send_json({"error": "unknown report theme"}, 404)
                return
            variants_dir = proj_dir / "reports-5themes"
            html_path = variants_dir / f"EduEvidence_Report_{theme}.html"
            if (not html_path.is_file() or
                    html_path.resolve().parent != variants_dir.resolve()):
                self._send_json({"error": "unknown report theme"}, 404)
                return

        self._send_report_bytes(html_path.read_bytes())

def run_dashboard_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = None
    actual_port = port
    for offset in range(10):
        try:
            candidate = port + offset
            server = http.server.ThreadingHTTPServer((host, candidate), StudioHandler)
            server.allow_reuse_address = True
            actual_port = candidate
            break
        except OSError as e:
            if e.errno == 48:
                continue
            raise

    if server is None:
        print(f"❌ 端口 {port}-{port + 9} 均被占用。")
        return

    print("============================================================")
    print(f"🚀 EduEvidence Web Studio running at http://{host}:{actual_port}/")
    print("   📊 仪表盘        /dashboard")
    print("   📄 报告浏览      /report")
    print("   📈 数据可视化    /#viz (Web UI)")
    print("   📦 数据契约      /api/projects  ·  /api/projects/<id>/viz")
    print("============================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    run_dashboard_server(args.host, args.port)


if __name__ == "__main__":
    main()
