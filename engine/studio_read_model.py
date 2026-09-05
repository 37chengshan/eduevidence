"""Read-only, portable projections for Research Studio.

No ProjectWorkspace.create, GraphStore.create, service initialization or state
repair is allowed here. Missing/corrupt inputs are visible diagnostics, not
successful empty studies. Static export includes examples only.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

THEMES = (
    ('claude', 'Claude Research', 'light'),
    ('academic', 'Academic Paper', 'light'),
    ('datalab', 'DataLab', 'light'),
    ('datalab-dark', 'DataLab Dark', 'dark'),
    ('presentation', 'Presentation / Judge', 'dark'),
)
TABLES = ('sources', 'studies', 'findings', 'outcomes', 'claims', 'evidence_links', 'audits')
MAX_BYTES = 16 * 1024 * 1024


def finite(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def first_value(*values: Any) -> Any:
    return next((value for value in values if value is not None), None)


def json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def numeric_effect(row: dict) -> dict:
    effect = first_value(row.get('effect_estimate'), row.get('effect_size'))
    if isinstance(effect, dict):
        value = finite(effect.get('value'))
        lo = finite(first_value(effect.get('ci_lower'), effect.get('ci_lo'), effect.get('ci_low')))
        hi = finite(first_value(effect.get('ci_upper'), effect.get('ci_hi'), effect.get('ci_high')))
        metric = effect.get('metric') or effect.get('type') or row.get('effect_metric')
    else:
        value = finite(first_value(effect, row.get('hedges_g'), row.get('g'), row.get('effect_size_value')))
        lo, hi = finite(row.get('ci_lower')), finite(row.get('ci_upper'))
        metric = row.get('effect_metric') or row.get('metric')
    # Never fabricate an interval or erase a legitimate zero endpoint.
    interval = 'not_reported'
    if lo is not None and hi is not None:
        interval = 'reported' if lo <= hi and (value is None or lo <= value <= hi) else 'invalid'
    elif lo is not None or hi is not None:
        interval = 'incomplete'
    return {'value': value, 'ci_lower': lo, 'ci_upper': hi, 'interval_status': interval,
            'metric': str(metric or 'unspecified')}


class StudioReader:
    """Build a bounded public DTO from committed, project-scoped inputs."""

    def __init__(self, examples: Path, home: Path, *, static: bool = False):
        self.examples = Path(examples).resolve()
        self.home = Path(home).expanduser().resolve()
        self.static = static
        self.issues: list[dict] = []

    def _read(self, path: Path, default: Any = None) -> Any:
        if not path.exists():
            return default
        try:
            if not path.resolve().is_relative_to(self.examples) and not path.resolve().is_relative_to(self.home):
                raise ValueError('path escapes the read scope')
            if path.stat().st_size > MAX_BYTES:
                raise ValueError('file exceeds the Studio read limit')
            if path.suffix == '.jsonl':
                return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
            return json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            self.issues.append({'code': 'unreadable_artifact', 'artifact': path.name, 'message': str(exc).split(':')[0]})
            return default

    def _directory(self, key: str) -> tuple[Path, str]:
        if key.startswith('example--'):
            name = key[len('example--'):]
            base, kind = self.examples, 'example'
        elif key.startswith('project--') and not self.static:
            name = key[len('project--'):]
            base, kind = self.home / 'projects', 'project'
            if not re.fullmatch(r'PRJ-[A-Za-z0-9_-]+', name):
                raise FileNotFoundError('unknown project')
        else:
            raise FileNotFoundError('unknown project')
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
            raise FileNotFoundError('unknown project')
        path = base / name
        if path.is_symlink() or not path.is_dir() or not path.resolve().is_relative_to(base.resolve()):
            raise FileNotFoundError('unknown project')
        return path, kind

    def _catalog_keys(self) -> list[str]:
        keys = []
        if self.examples.is_dir():
            keys.extend('example--' + p.name for p in sorted(self.examples.iterdir())
                        if p.is_dir() and not p.is_symlink() and (p / 'result.json').is_file())
        if not self.static and (self.home / 'projects').is_dir():
            keys.extend('project--' + p.name for p in sorted((self.home / 'projects').iterdir())
                        if p.is_dir() and not p.is_symlink() and (p / 'project.json').is_file())
        return keys

    def _db_rows(self, table: str, project_id: str) -> list[dict]:
        if table not in {'artifacts', 'events'}:
            raise ValueError('unknown read table')
        path = self.home / 'research-control.sqlite3'
        if not path.is_file():
            return []
        if path.is_symlink():
            self.issues.append({'code': 'database_unavailable', 'message': 'symlink database refused'})
            return []
        try:
            uri = path.as_uri() + '?mode=ro'
            with sqlite3.connect(uri, uri=True, timeout=2) as connection:
                connection.row_factory = sqlite3.Row
                order = 'seq' if table == 'events' else 'created_at'
                rows = connection.execute(f'SELECT * FROM {table} WHERE project_id=? ORDER BY {order} DESC LIMIT 500', (project_id,)).fetchall()
            output = []
            for record in rows:
                item = dict(record)
                item.pop('path', None)  # Never expose host filesystem paths.
                for field in ('payload', 'metadata'):
                    if isinstance(item.get(field), str):
                        item[field] = json.loads(item[field])
                if isinstance(item.get('payload'), dict):
                    item['payload'].pop('path', None)
                output.append(item)
            return output
        except (sqlite3.Error, ValueError):
            self.issues.append({'code': 'database_unavailable', 'message': 'Research event index is unavailable'})
            return []

    def _reports(self, directory: Path, key: str, kind: str) -> list[dict]:
        rows = []
        default = directory / 'EduEvidence_Report.html'
        default_theme = None
        if default.is_file() and not default.is_symlink():
            with default.open(encoding='utf-8', errors='replace') as handle:
                match = re.search(r'<html[^>]*data-theme=[\"\']([a-z-]+)', handle.read(4096))
            default_theme = match.group(1) if match else None
        for theme, title, tone in THEMES:
            path = directory / 'reports-5themes' / f'EduEvidence_Report_{theme}.html'
            if not path.is_file() and theme == default_theme:
                path = directory / 'EduEvidence_Report.html'
            available = path.is_file() and path.resolve().is_relative_to(directory.resolve())
            url = None
            if available:
                url = (f'../reports/{directory.name}/{path.name}' if self.static else
                       f'/api/studio/projects/{quote(key, safe="")}/report?theme={theme}')
            rows.append({'theme': theme, 'title': title, 'tone': tone, 'available': available, 'url': url})
        if kind == 'project':
            rows = []
            report_dir = directory / 'reports'
            if not report_dir.resolve().is_relative_to(directory.resolve()):
                return rows
            for path in sorted(report_dir.glob('*.html')):
                if path.is_symlink():
                    continue
                rows.append({'theme': path.stem, 'title': path.stem, 'tone': 'light', 'available': True,
                             'url': f'/api/studio/projects/{quote(key, safe="")}/report?file={quote(path.name)}'})
        return rows

    def report_path(self, key: str, *, theme: str = 'claude', filename: str | None = None) -> Path:
        directory, kind = self._directory(key)
        if kind == 'example':
            if theme not in {row[0] for row in THEMES}:
                raise FileNotFoundError('unknown report theme')
            path = directory / 'reports-5themes' / f'EduEvidence_Report_{theme}.html'
            if not path.is_file():
                available = {row['theme'] for row in self._reports(directory, key, kind) if row['available']}
                if theme in available:
                    path = directory / 'EduEvidence_Report.html'
        else:
            if not filename or not re.fullmatch(r'[A-Za-z0-9_.-]+\.html', filename):
                raise FileNotFoundError('unknown report')
            path = directory / 'reports' / filename
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(directory):
            raise FileNotFoundError('report not generated')
        return path

    def detail(self, key: str) -> dict:
        self.issues = []
        directory, kind = self._directory(key)
        en = self._read(directory / 'result.json', {}) if kind == 'example' else {}
        zh = self._read(directory / 'result.zh.json', {}) if kind == 'example' else {}
        if not isinstance(en, dict) or not isinstance(zh, dict):
            raise ValueError('invalid result object')
        result = en or {}
        manifest = self._read(directory / 'project.json', {}) if kind == 'project' else {}
        meta = result.get('meta') or {}
        sources = result.get('sources') or []
        findings = result.get('evidence') or []
        claims = result.get('claims') or []
        outcomes = result.get('outcomes') or []
        audits, designs, analyses = [], [], []
        studies, links, revisions, decisions, runs, artifacts, events, gaps, iterations = [], [], [], [], [], [], [], [], []
        active_revision = None
        if kind == 'project':
            head = directory / 'graph' / 'HEAD'
            if head.is_file():
                try:
                    active_revision = int(head.read_text().strip())
                    if active_revision < 0:
                        raise ValueError('negative revision')
                except (OSError, ValueError):
                    self.issues.append({'code': 'invalid_graph_head', 'message': 'Graph HEAD cannot be read'})
            if active_revision is not None and active_revision != manifest.get('graph_revision'):
                self.issues.append({'code': 'revision_mirror_mismatch', 'message': 'Project revision mirror differs from Graph HEAD'})
            if active_revision:
                revdir = directory / 'graph' / 'revisions' / f'rev-{active_revision:06d}'
                tables = {t: self._read(revdir / f'{t}.jsonl', []) for t in TABLES}
                for t in TABLES:
                    if not (revdir / f'{t}.jsonl').exists():
                        self.issues.append({'code': 'missing_graph_table', 'artifact': t, 'message': 'Committed graph table missing'})
                sources, studies, findings, claims, links, outcomes, audits = (tables[t] for t in ('sources', 'studies', 'findings', 'claims', 'evidence_links', 'outcomes', 'audits'))
            # Follow only the committed ancestry. Orphan directories are not history.
            revision = active_revision
            visited: set[int] = set()
            while revision and revision not in visited:
                visited.add(revision)
                revision_meta = self._read(directory / 'graph' / 'revisions' / f'rev-{revision:06d}' / 'manifest.json', {})
                if not isinstance(revision_meta, dict) or revision_meta.get('revision') != revision:
                    self.issues.append({'code': 'invalid_revision_manifest', 'message': 'Revision ancestry is incomplete'})
                    break
                revisions.append({**revision_meta, 'active': revision == active_revision})
                parent = revision_meta.get('parent_revision')
                if type(parent) is not int or not 0 <= parent < revision:
                    self.issues.append({'code': 'invalid_revision_parent', 'message': 'Revision parent is invalid'})
                    break
                revision = parent
            revisions.reverse()
            decisions = [d for p in sorted((directory / 'decisions').glob('DEC-*.json')) if isinstance((d := self._read(p)), dict)]
            decisions.sort(key=lambda d: (d.get('graph_revision', 0), d.get('created_at', '')), reverse=True)
            runs = [d for p in sorted((directory / 'runs').glob('*/run.json')) if isinstance((d := self._read(p)), dict)]
            runs.sort(key=lambda d: d.get('started_at', ''), reverse=True)
            for run in runs:
                run_id = str(run.get('run_id', ''))
                if re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
                    run['stage_state'] = self._read(directory / 'runs' / run_id / 'state.json', {})
                    run['execution_plan'] = self._read(directory / 'runs' / run_id / 'execution_plan.json', {})
                    run['gate_report'] = self._read(directory / 'runs' / run_id / 'gate_report.json', {})
            artifacts = self._db_rows('artifacts', manifest.get('project_id', directory.name))
            events = self._db_rows('events', manifest.get('project_id', directory.name))
            if active_revision is not None:
                gaps = self._read(directory / 'gaps' / f'gaps-rev-{active_revision:06d}.jsonl', [])
            iterations = self._read(directory / 'autoresearch' / 'research-iterations.jsonl', [])
            designs = [d for p in sorted((directory / 'study-designs').glob('DSN-*.json')) if isinstance((d := self._read(p)), dict)]
            analyses = [d for p in sorted((directory / 'analyses').glob('*.json')) if isinstance((d := self._read(p)), dict)]
        for records in (sources, studies, findings, claims, links, outcomes, runs, events, artifacts, gaps, iterations):
            if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
                raise ValueError('invalid record collection')
        sources = [{**r, 'title': r.get('title') or (r.get('extensions') or {}).get('title') or r.get('source_id'),
                    'canonical_url': r.get('canonical_url') or r.get('canonical_locator') or r.get('source_location')}
                   for r in sources]
        localized_findings = {r.get('evidence_id'): r for r in zh.get('evidence', [])}
        evidence = []
        seen = set()
        studies_by_id = {r.get('study_id'): r for r in studies}
        outcomes_by_id = {r.get('outcome_id'): r for r in outcomes}

        for row in findings:
            eid = str(row.get('finding_id') or row.get('evidence_id') or '')
            if not eid or eid in seen:
                continue
            seen.add(eid)
            local = localized_findings.get(eid, {})
            # A Finding's observed effect is NOT its relation to a Claim.
            study = studies_by_id.get(row.get('study_id'), {})
            outcome = outcomes_by_id.get(row.get('outcome_id'), {})
            claim_links = [l for l in links if l.get('finding_id') == eid]
            relationships = sorted({l.get('relation_to_claim') or l.get('relation') or 'unassigned' for l in claim_links})
            relation = (relationships[0] if len(relationships) == 1 else 'multiple') if relationships else row.get('relation_to_claim') or row.get('direction') or 'unassigned'
            source_ids = ([row['source_id']] if row.get('source_id') else study.get('source_ids', []))
            evidence.append({**row, 'id': eid,
                             'title': row.get('title') or row.get('measure') or row.get('finding') or eid,
                             'title_zh': local.get('title'), 'claim_zh': local.get('claim'),
                             'claim': row.get('claim') or row.get('raw_result_text'),
                             'source_id': source_ids[0] if source_ids else None, 'source_ids': source_ids,
                             'study_type': row.get('study_type') or study.get('study_design'),
                             'sample_size': first_value(row.get('sample_size'), study.get('sample_size')),
                             'audits': [a for a in audits if a.get('study_id') == row.get('study_id')],
                             'outcome_type': row.get('outcome_type') or outcome.get('outcome_type') or row.get('measure'),
                             'relation': relation, 'claim_links': claim_links,
                             'effect_direction': row.get('effect_direction') or 'not_reported',
                             'numeric': numeric_effect(row)})
        decision = decisions[0] if decisions else result.get('decision') or {}
        bound_revision = decision.get('graph_revision')
        stale = bool(kind == 'project' and decision and bound_revision != active_revision)
        decision_view = {
            **decision,
            'action': decision.get('decision') or decision.get('recommended_action'),
            'confidence': decision.get('confidence_label') or decision.get('confidence'),
            'graph_revision': bound_revision,
            'stale': stale,
            'supported': decision.get('supported_claims') or [],
            'uncertain': decision.get('uncertain_claims') or decision.get('missing_evidence') or [],
            'contradicted': decision.get('contradicted_claims') or [],
            'rationale': decision.get('decision_rationale') or decision.get('rationale') or '',
        }
        if stale:
            self.issues.append({'code': 'stale_decision', 'message': 'Latest decision is not bound to active GraphRevision'})
        claim_nodes = [{**r, 'id': str(r.get('claim_id')), 'label': r.get('claim') or r.get('text') or r.get('claim_id'), 'kind': 'claim'} for r in claims if r.get('claim_id')]
        nodes = [{'id': str(r.get('source_id')), 'label': r.get('title') or r.get('source_id'), 'kind': 'source'} for r in sources if r.get('source_id')]
        nodes += [{'id': r['id'], 'label': r['title'], 'kind': 'finding'} for r in evidence]
        nodes += claim_nodes
        edges = []
        studies_by_id = {r.get('study_id'): r for r in studies}
        for r in evidence:
            study = studies_by_id.get(r.get('study_id'), {})
            source_ids = r.get('source_ids') or study.get('source_ids', [])
            for sid in source_ids:
                edges.append({'source': sid, 'target': r['id'], 'relation': 'provenance'})
        for c in claims:
            for eid in c.get('evidence_ids', []):
                ev = next((r for r in evidence if r['id'] == eid), {})
                edges.append({'source': eid, 'target': c.get('claim_id'), 'relation': ev.get('relation', 'unassigned')})
        for link in links:
            edges.append({'source': link.get('finding_id'), 'target': link.get('claim_id'), 'relation': link.get('relation') or link.get('relation_to_claim') or 'unassigned'})
        node_ids = {n['id'] for n in nodes}
        invalid_edges = [e for e in edges if e['source'] not in node_ids or e['target'] not in node_ids]
        if invalid_edges:
            self.issues.append({'code': 'unresolved_graph_links', 'message': f'{len(invalid_edges)} graph relationships have missing endpoints'})
        edges = [e for e in edges if e not in invalid_edges]
        reports = self._reports(directory, key, kind)
        info = {
            'id': key, 'project_id': manifest.get('project_id'), 'kind': kind,
            'title': manifest.get('title') or (zh.get('meta') or {}).get('question') or (zh.get('decision') or {}).get('decision_question') or meta.get('question') or directory.name,
            'title_en': manifest.get('title') or decision.get('decision_question') or meta.get('question') or directory.name,
            'question': manifest.get('question') or meta.get('question') or '',
            'domain': manifest.get('domain') or meta.get('domain') or 'education',
            'status': (runs[0].get('status') if runs else None) or manifest.get('status') or ('example' if kind == 'example' else 'not_started'),
            'data_origin': meta.get('data_origin') or ('local_project' if kind == 'project' else 'not_reported'),
            'updated_at': manifest.get('updated_at') or meta.get('generated_at'),
            'active_revision': active_revision, 'decision': decision_view,
            'counts': {'sources': len(sources), 'findings': len(evidence), 'claims': len(claim_nodes),
                       'studies': len({r.get('study_id') for r in findings if r.get('study_id')}),
                       'runs': len(runs)},
            'reports': reports,
        }
        if kind == 'project' and active_revision is not None:
            try:
                if int((directory / 'graph' / 'HEAD').read_text().strip()) != active_revision:
                    raise ValueError('Graph HEAD changed during projection; retry')
            except OSError as exc:
                raise ValueError('Graph HEAD unavailable after read') from exc
        return json_safe({
            'schema_version': 1, 'project': info, 'sources': sources, 'studies': studies,
            'evidence': evidence, 'claims': claims, 'graph': {'nodes': nodes, 'edges': edges, 'origin': 'canonical_revision' if kind == 'project' else 'result_projection'},
            'decisions': decisions, 'revisions': revisions, 'runs': runs, 'events': events,
            'artifacts': artifacts, 'gaps': gaps, 'iterations': iterations,
            'applicability': decision.get('applicability_boundary') or result.get('applicability') or decision.get('applicability') or {},
            'intervention': result.get('intervention') or ({'study_designs': designs} if designs else {}),
            'evaluation': result.get('evaluation') or ({'analyses': analyses} if analyses else {}),
            'decision_zh': zh.get('decision') or {}, 'issues': list(self.issues),
            'snapshot_taken_at': datetime.now(timezone.utc).isoformat(),
            'measurement_policy': 'No pooled effect or mean is computed by Studio. Missing values remain null.',
        })

    def catalog(self) -> dict:
        projects, issues = [], []
        for key in self._catalog_keys():
            try:
                detail = self.detail(key)
                projects.append(detail['project'])
                issues.extend({'project': key, **issue} for issue in detail['issues'])
            except (OSError, ValueError, TypeError, AttributeError):
                issues.append({'project': key, 'code': 'invalid_project', 'message': 'Project could not be read'})
        return {'schema_version': 1, 'mode': 'static' if self.static else 'local', 'readonly': True,
                'generated_at': datetime.now(timezone.utc).isoformat(), 'projects': projects, 'issues': issues}

    def evolution(self) -> dict:
        # Deliberately distinct from project ResearchIterations; no arbitrary
        # session directory or rejected candidate files are exposed.
        rows = []
        if not self.static:
            path = self.examples.parent / 'autoevolve' / 'experiments.jsonl'
            if path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_BYTES:
                try:
                    allowed = ('experiment_id', 'session_id', 'hypothesis', 'status', 'promotion_reason', 'candidate_commit', 'parent_skill_revision')
                    rows = [{k: r.get(k) for k in allowed} for line in path.read_text().splitlines() if line.strip() for r in [json.loads(line)]]
                except (ValueError, OSError):
                    return {'experiments': [], 'status': 'unavailable'}
        return {'experiments': rows[-100:], 'status': 'recorded' if rows else 'not_recorded'}
