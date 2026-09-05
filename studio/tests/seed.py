"""Generate explicitly synthetic, temporary records for frontend integration tests."""
from pathlib import Path
import json
import os
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from engine.research_service import ResearchService
from engine.graph_store import GraphStore
from engine.run import finish_run
from test_v2_graph_store import _valid_bundle

home = Path(os.environ['EDUEVIDENCE_HOME'])
service = ResearchService(home)
project = service.create_project(question='Synthetic browser fixture only', title='Fixture-only local research')
if not list((project.path / 'runs').glob('*/run.json')):
    run = service.start_run(project.project_id, purpose='Synthetic test review', capabilities=['source_validation'])
    store = GraphStore.create(project)
    bundle = _valid_bundle()
    bundle.upserts['findings'][0]['effect_estimate'] = {'metric': 'g', 'value': 0.1, 'ci_low': 0, 'ci_high': 0.2, 'raw_text': 'Synthetic fixture only'}
    store.commit(run_id=run['run_id'], reason='Synthetic browser fixture', mutation=bundle)
    finish_run(project, run['run_id'], status='completed', graph_revision_after=1)
    service.submit_artifact(project.project_id, run_id=run['run_id'], artifact_type='fixture-record', content=b'{"data_origin":"synthetic"}')
    state = project.path / 'runs' / run['run_id'] / 'state.json'
    state.write_text(json.dumps({'stages': {'retrieve': {'status': 'completed'}, 'audit': {'status': 'waiting_for_review'}}}))
print(project.project_id)
