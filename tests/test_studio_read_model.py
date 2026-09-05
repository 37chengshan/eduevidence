"""Contract and scientific integrity regressions for the read-only Studio."""
import hashlib
import json
from pathlib import Path

import pytest

from engine.project import ProjectWorkspace
from engine.research_service import ResearchService
from engine.studio_read_model import StudioReader, numeric_effect


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def example(tmp_path, **extra):
    examples = tmp_path / 'examples'
    value = {'meta': {'question': 'A test question', 'data_origin': 'synthetic'},
             'evidence': [{'evidence_id': 'E-1', 'study_id': 'STU-1', 'source_id': 'S-1',
                           'effect_direction': 'negative', 'relation_to_claim': 'support'}],
             'sources': [{'source_id': 'S-1', 'title': 'Test source'}],
             'claims': [{'claim_id': 'C-1', 'claim': 'A negative claim', 'evidence_ids': ['E-1']}], **extra}
    put(examples / 'case' / 'result.json', value)
    return StudioReader(examples, tmp_path / 'home')


def test_studio_absent_home_is_not_created(tmp_path):
    reader = StudioReader(tmp_path / 'examples', tmp_path / 'absent-home')
    assert reader.catalog()['projects'] == []
    assert reader.evolution()['experiments'] == []
    assert not reader.home.exists()


def test_studio_zero_effect_and_zero_ci_are_preserved():
    result = numeric_effect({'effect_size': {'value': 0, 'ci_lower': 0, 'ci_upper': 0.2}})
    assert result['value'] == result['ci_lower'] == 0
    assert result['interval_status'] == 'reported'


def test_studio_v2_effect_estimate_is_projected_without_precision_invention():
    result = numeric_effect({'effect_estimate': {'metric': 'g', 'value': -0.1, 'ci_low': -0.3, 'ci_high': 0}})
    assert result['metric'] == 'g'
    assert result['ci_upper'] == 0
    assert result['interval_status'] == 'reported'
    assert numeric_effect({'effect_size': 0.5})['ci_lower'] is None


@pytest.mark.parametrize('value', [True, False, float('nan'), float('inf'), '0.4'])
def test_studio_non_numeric_effects_are_not_zero(value):
    assert numeric_effect({'effect_size': value})['value'] is None


def test_studio_inverted_interval_is_flagged():
    assert numeric_effect({'effect_size': 1, 'ci_lower': 2, 'ci_upper': 0})['interval_status'] == 'invalid'


def test_studio_claim_relation_is_independent_of_observed_direction(tmp_path):
    data = example(tmp_path).detail('example--case')
    assert data['evidence'][0]['relation'] == 'support'
    assert data['evidence'][0]['effect_direction'] == 'negative'
    assert data['graph']['edges'][-1]['relation'] == 'support'


def test_studio_no_mean_or_pooled_effect_is_invented(tmp_path):
    info = example(tmp_path).detail('example--case')['project']
    assert 'mean_effect_size' not in info
    assert 'pooled_effect' not in info


def test_studio_report_availability_follows_files_and_theme(tmp_path):
    reader = example(tmp_path)
    directory = reader.examples / 'case'
    (directory / 'EduEvidence_Report.html').write_text('<html data-theme="academic"><body>test</body></html>')
    available = {r['theme'] for r in reader.detail('example--case')['project']['reports'] if r['available']}
    assert available == {'academic'}
    assert reader.report_path('example--case', theme='academic').name == 'EduEvidence_Report.html'
    with pytest.raises(FileNotFoundError):
        reader.report_path('example--case', theme='claude')


@pytest.mark.parametrize('key', ['example--../case', 'example--case/../../secret', 'project--PRJ-../../secret', 'unknown'])
def test_studio_path_traversal_fails_closed(tmp_path, key):
    with pytest.raises(FileNotFoundError):
        example(tmp_path).detail(key)


def test_studio_symlink_alias_is_not_a_second_project(tmp_path):
    reader = example(tmp_path)
    (reader.examples / 'alias').symlink_to('case', target_is_directory=True)
    assert len(reader.catalog()['projects']) == 1
    with pytest.raises(FileNotFoundError):
        reader.detail('example--alias')


def test_studio_static_export_never_includes_local_projects(tmp_path):
    reader = example(tmp_path)
    ProjectWorkspace.create(reader.home, research_mode="evidence_review", title='PRIVATE', question='PRIVATE question')
    assert len(reader.catalog()['projects']) == 2
    static = StudioReader(reader.examples, reader.home, static=True)
    assert len(static.catalog()['projects']) == 1
    assert 'PRIVATE' not in json.dumps(static.catalog())


def test_studio_reads_events_without_modifying_research_state(tmp_path):
    reader = example(tmp_path)
    service = ResearchService(reader.home)
    project = service.create_project(question='Local test', title='Local test')
    run = service.start_run(project.project_id, purpose='Review', capabilities=['retrieve'])
    service.submit_artifact(project.project_id, run_id=run['run_id'], artifact_type='test', content=b'{}')
    before = {p.relative_to(reader.home): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in reader.home.rglob('*') if p.is_file() and not p.name.endswith(('-shm', '-wal'))}
    data = reader.detail('project--' + project.project_id)
    assert len(data['runs']) == 1 and len(data['artifacts']) == 1
    assert data['events'][0]['type'] == 'artifact_submitted'
    assert 'path' not in data['artifacts'][0]
    after = {p.relative_to(reader.home): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in reader.home.rglob('*') if p.is_file() and not p.name.endswith(('-shm', '-wal'))}
    assert before == after


def test_studio_stale_decision_is_not_presented_as_current(tmp_path):
    reader = example(tmp_path)
    project = ProjectWorkspace.create(reader.home, research_mode="evidence_review", question='Local Q', title='Local Q')
    (project.path / 'graph' / 'HEAD').write_text('2')
    put(project.path / 'decisions' / 'DEC-old.json', {'decision_snapshot_id': 'DEC-old', 'decision': 'PILOT', 'graph_revision': 1})
    data = reader.detail('project--' + project.project_id)
    assert data['project']['decision']['stale'] is True
    assert any(i['code'] == 'stale_decision' for i in data['issues'])


def test_studio_reads_canonical_iteration_filename(tmp_path):
    reader = example(tmp_path)
    project = ProjectWorkspace.create(reader.home, research_mode="evidence_review", question='Q iteration', title='Q iteration')
    path = project.path / 'autoresearch' / 'research-iterations.jsonl'
    path.parent.mkdir()
    path.write_text('{"iteration_id":"RIT-1","status":"completed_no_gain"}\n')
    assert reader.detail('project--' + project.project_id)['iterations'][0]['iteration_id'] == 'RIT-1'


def test_same_content_can_belong_to_different_projects_and_runs(tmp_path):
    service = ResearchService(tmp_path)
    a = service.create_project(question='QA', title='A')
    b = service.create_project(question='QB', title='B')
    left = service.submit_artifact(a.project_id, artifact_type='test', content=b'{}')
    right = service.submit_artifact(b.project_id, artifact_type='test', content=b'{}')
    repeated = service.submit_artifact(a.project_id, artifact_type='test', content=b'{}')
    assert left['sha256'] == right['sha256']
    assert left['artifact_id'] != right['artifact_id']
    assert repeated == left
    assert len(service.artifacts(a.project_id)) == len(service.artifacts(b.project_id)) == 1


def test_report_missing_summary_has_no_fabricated_scientific_result():
    import build_report as br
    for locale, ui in [('en', br.UI_EN), ('zh', br.UI_ZH)]:
        html = br.first_screen({}, locale, ui)
        for forbidden in ('35%', '50%', '+0.61', '-0.28', 'p = 0.012', 'Socratic', '4-phase'):
            assert forbidden not in html


def test_report_inline_json_cannot_close_script():
    import build_report as br
    value = {'x': '</script><script>alert(1)</script>', 'y': '\u2028'}
    escaped = br.script_json(value)
    assert '</script>' not in escaped
    assert json.loads(escaped) == value
