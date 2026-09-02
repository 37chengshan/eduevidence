#!/usr/bin/env python3
"""Build static GitHub Pages artifact for landing + Studio demo."""
from __future__ import annotations
import json, shutil, sys, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
EXAMPLES_DIR = ROOT / "examples"
OUT_DIR = ROOT / "dist_gh_pages"
WEB_API_DIR = WEB_DIR / "api"
sys.path.insert(0, str(ROOT))
from scripts.dashboard_server import scan_local_projects, build_stats, build_viz_payload
import sys as _sys2
_sys2.path.insert(0, str(ROOT / 'visualization' / 'eduevidence-report' / 'scripts'))
from zh_labels import OUTCOME_ZH, ACTION_ZH, STUDY_ZH, AUTHORITY_ZH, CONFIDENCE_ZH

def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def main():
    print("== GH Pages Builder ==")
    projects = scan_local_projects()
    stats = build_stats(projects)
    print(f"projects: {len(projects)} -> {', '.join(p['id'] for p in projects)}")
    print(f"stats: {stats}")
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    labels = {"outcomes": OUTCOME_ZH, "actions": ACTION_ZH, "studies": STUDY_ZH, "authority": AUTHORITY_ZH, "confidence": CONFIDENCE_ZH}
    for base_dir in (OUT_DIR / "api", WEB_API_DIR):
        write_json(base_dir / "projects.json", {"projects": projects, "stats": stats})
        write_json(base_dir / "labels.json", labels)
        for p in projects:
            pid = p["id"]
            try:
                viz = build_viz_payload(pid)
            except Exception as e:
                print(f"warn viz {pid}: {e}")
                continue
            write_json(base_dir / "projects" / pid / "viz.json", viz)
    print("API JSON done")
    for item in WEB_DIR.iterdir():
        if item.name == "api":
            continue
        dest = OUT_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
    for p in projects:
        pid = p["id"]
        proj_dir = EXAMPLES_DIR / pid
        out_proj = OUT_DIR / "reports" / pid
        out_proj.mkdir(parents=True, exist_ok=True)
        src = proj_dir / "EduEvidence_Report.html"
        if src.is_file():
            shutil.copy2(src, out_proj / "EduEvidence_Report.html")
        variants_dir = proj_dir / "reports-5themes"
        if variants_dir.is_dir():
            for html in variants_dir.glob("*.html"):
                shutil.copy2(html, out_proj / html.name)
        for html in proj_dir.glob("EduEvidence_Report_*.html"):
            shutil.copy2(html, out_proj / html.name)
    print("reports copied")
    landing_src = WEB_DIR / "landing.html"
    studio_src = WEB_DIR / "index.html"
    if landing_src.is_file() and studio_src.is_file():
        landing_html = landing_src.read_text(encoding="utf-8")
        landing_html = landing_html.replace('href="/landing.html"', 'href="index.html"')
        landing_html = landing_html.replace('href="/index.html"', 'href="studio.html"')
        theme_map = {"claude_research": "claude", "academic_paper": "academic", "datalab_light": "datalab", "datalab_dark": "datalab-dark", "presentation_judge": "presentation"}
        def repl_report(m):
            q = m.group(1).replace("&amp;", "&")
            segs = q.split("&")
            pid = segs[0] if segs else ""
            theme_raw = "default"
            for seg in segs[1:]:
                if seg.startswith("theme="):
                    theme_raw = seg.split("=",1)[1]
                    break
            theme = theme_map.get(theme_raw, theme_raw)
            fname = "EduEvidence_Report.html" if theme=="default" else f"EduEvidence_Report_{theme}.html"
            return f'href="reports/{pid}/{fname}"'
        landing_html = re.sub(r'href="/report\?id=([^"]+)"', repl_report, landing_html)
        (OUT_DIR / "index.html").write_text(landing_html, encoding="utf-8")
        (OUT_DIR / "landing.html").write_text(landing_html, encoding="utf-8")
        studio_html = studio_src.read_text(encoding="utf-8")
        (OUT_DIR / "studio.html").write_text(studio_html, encoding="utf-8")
        (OUT_DIR / "studio").mkdir(exist_ok=True)
        (OUT_DIR / "studio" / "index.html").write_text(studio_html, encoding="utf-8")
        print("landing + studio written")
    (OUT_DIR / ".nojekyll").write_text("", encoding="utf-8")
    if not (OUT_DIR / "404.html").exists():
        shutil.copy2(OUT_DIR / "index.html", OUT_DIR / "404.html")
    print(f"dist files: {sum(1 for _ in OUT_DIR.rglob('*') if _.is_file())}")
    print(f"preview: python3 -m http.server 8000 --directory {OUT_DIR}")
if __name__ == "__main__":
    main()
