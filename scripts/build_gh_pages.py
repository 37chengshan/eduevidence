#!/usr/bin/env python3
"""Build public Pages: unchanged introduction + read-only example Studio.

Only repository examples are exported. The user's EDUEVIDENCE_HOME, local
projects, run events and Autoevolve session data never enter this artifact.
"""
from __future__ import annotations
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / 'web'
EXAMPLES_DIR = ROOT / 'examples'
OUT_DIR = ROOT / 'dist_gh_pages'
sys.path.insert(0, str(ROOT))
from engine.studio_read_model import StudioReader  # noqa: E402
from scripts.build_report_variants import bake  # noqa: E402
from scripts.dashboard_server import scan_local_projects, build_stats, build_viz_payload  # noqa: E402


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')


def main():
    if not (WEB_DIR / 'studio' / 'index.html').is_file():
        raise SystemExit('Build the frontend first: cd studio && npm ci && npm run build')
    bake(EXAMPLES_DIR)
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    for item in WEB_DIR.iterdir():
        if item.name == 'api':
            continue
        if item.is_dir():
            shutil.copytree(item, OUT_DIR / item.name, dirs_exist_ok=True)
        else:
            shutil.copy2(item, OUT_DIR / item.name)

    # Legacy landing endpoints kept without modifying source web/api artifacts.
    projects = scan_local_projects()
    for project in projects:
        name = project['id']
        project['html_report_path'] = f'reports/{name}/EduEvidence_Report.html' if project.get('html_report_path') else None
        for variant in project.get('report_variants', []):
            variant['path'] = f"reports/{name}/{Path(variant['path']).name}"
    write_json(OUT_DIR / 'api' / 'projects.json', {'projects': projects, 'stats': build_stats(projects)})
    for project in projects:
        write_json(OUT_DIR / 'api' / 'projects' / project['id'] / 'viz.json', build_viz_payload(project['id']))

    reader = StudioReader(EXAMPLES_DIR, ROOT / '.static-export-no-local-state', static=True)
    catalog = reader.catalog()
    write_json(OUT_DIR / 'api' / 'studio' / 'catalog.json', catalog)
    write_json(OUT_DIR / 'api' / 'studio' / 'evolution.json', {'experiments': [], 'status': 'not_exported'})
    for project in catalog['projects']:
        key = project['id']
        detail = reader.detail(key)
        write_json(OUT_DIR / 'api' / 'studio' / 'projects' / f'{key}.json', detail)
        name = key.removeprefix('example--')
        source = EXAMPLES_DIR / name
        target = OUT_DIR / 'reports' / name
        target.mkdir(parents=True, exist_ok=True)
        for path in (source / 'reports-5themes').glob('*.html'):
            shutil.copy2(path, target / path.name)
        current_default = source / 'reports-5themes' / 'EduEvidence_Report_claude.html'
        if not current_default.exists():
            current_default = source / 'EduEvidence_Report.html'
        if current_default.is_file():
            shutil.copy2(current_default, target / 'EduEvidence_Report.html')
    write_json(OUT_DIR / 'studio' / 'config.json', {'mode': 'static', 'api_base': '../api/studio', 'readonly': True})
    # Keep old public entry links functional without changing the landing design.
    redirect = '<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=./studio/"><title>Research Studio</title><a href="./studio/">Open Research Studio</a><script>location.replace("./studio/"+location.hash)</script></html>'
    (OUT_DIR / 'studio.html').write_text(redirect, encoding='utf-8')
    landing = WEB_DIR / 'landing.html'
    if landing.is_file():
        page = landing.read_text(encoding='utf-8')
        page = page.replace('href="/landing.html"', 'href="index.html"').replace('href="/index.html"', 'href="studio/"')
        theme_alias = {'claude_research':'claude', 'academic_paper':'academic', 'datalab_light':'datalab', 'datalab_dark':'datalab-dark', 'presentation_judge':'presentation'}
        def report_link(match):
            parts = match.group(1).replace('&amp;', '&').split('&')
            project_id = parts[0]
            theme = next((s.split('=', 1)[1] for s in parts[1:] if s.startswith('theme=')), 'default')
            theme = theme_alias.get(theme, theme)
            filename = 'EduEvidence_Report.html' if theme == 'default' else f'EduEvidence_Report_{theme}.html'
            return f'href="reports/{project_id}/{filename}"'
        page = re.sub(r'href="/report\?id=([^\"]+)"', report_link, page)
        (OUT_DIR / 'index.html').write_text(page, encoding='utf-8')
        (OUT_DIR / 'landing.html').write_text(page, encoding='utf-8')
    (OUT_DIR / '.nojekyll').write_text('', encoding='utf-8')
    print(f'Pages ready: {len(catalog["projects"])} public cases; local projects excluded')


if __name__ == '__main__':
    main()
