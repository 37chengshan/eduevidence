#!/usr/bin/env python3
"""Bake all five report identities from the same validated bilingual inputs.

This is a build step, never a read endpoint. No evidence or decision is changed.
Failures are explicit and never replaced with a synthetic success document.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEMES = ('claude', 'academic', 'datalab', 'datalab-dark', 'presentation')


def bake(examples: Path, *, force: bool = False) -> list[dict]:
    renderer_dir = ROOT / 'visualization' / 'eduevidence-report'
    renderer = renderer_dir / 'scripts' / 'build_report.py'
    digest = hashlib.sha256()
    for path in sorted(renderer_dir.rglob('*')):
        if path.suffix in {'.py', '.css', '.js', '.json'} and '__pycache__' not in path.parts:
            digest.update(path.relative_to(renderer_dir).as_posix().encode())
            digest.update(path.read_bytes())
    engine_hash = digest.hexdigest()
    reports = []
    for directory in sorted(examples.iterdir()):
        if not directory.is_dir() or directory.is_symlink():
            continue
        source, parallel = directory / 'result.json', directory / 'result.zh.json'
        if not source.exists() or not parallel.exists():
            continue
        result_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        cache_key = hashlib.sha256((engine_hash + result_hash + hashlib.sha256(parallel.read_bytes()).hexdigest()).encode()).hexdigest()
        out_dir = directory / 'reports-5themes'
        manifest = out_dir / 'reader-manifest.json'
        if not force and manifest.is_file():
            try:
                prior = json.loads(manifest.read_text(encoding='utf-8'))
                valid = prior.get('cache_key') == cache_key and all(
                    (out_dir / record['file']).is_file() and hashlib.sha256((out_dir / record['file']).read_bytes()).hexdigest() == record['sha256']
                    for record in prior.get('reports', [])) and len(prior.get('reports', [])) == len(THEMES)
                if valid:
                    reports.append(prior)
                    continue
            except (ValueError, KeyError, OSError):
                pass
        out_dir.mkdir(parents=True, exist_ok=True)
        records = []
        for theme in THEMES:
            target = out_dir / f'EduEvidence_Report_{theme}.html'
            # Build to temporary files, promote only after scientific gates pass.
            temporary = out_dir / f'.{theme}.pending.html'
            spec = out_dir / f'report_spec_{theme}.json'
            completed = subprocess.run([sys.executable, str(renderer), '--result', str(source),
                                        '--result-zh', str(parallel), '--theme', theme,
                                        '--out', str(temporary), '--spec-out', str(spec)],
                                       cwd=ROOT, capture_output=True, text=True, timeout=120)
            if completed.returncode:
                temporary.unlink(missing_ok=True)
                raise RuntimeError(f'{directory.name}/{theme}: renderer rejected input\n{completed.stdout}\n{completed.stderr}')
            os.replace(temporary, target)
            records.append({'theme': theme, 'file': target.name, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
        value = {'schema_version': 1, 'project': directory.name, 'cache_key': cache_key,
                 'result_sha256': result_hash, 'renderer_sha256': engine_hash, 'reports': records}
        manifest.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
        reports.append(value)
        print(f'{directory.name}: {len(records)} verified report variants')
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--examples', type=Path, default=ROOT / 'examples')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    bake(args.examples, force=args.force)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
