"""A non-teaching example must use real population semantics and portable gates."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_workplace_demo_contract_and_population_rendering():
    import build_report as br
    result = subprocess.run([sys.executable, str(ROOT / 'examples/workplace-ai-assistant/validate.py')],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['studio_domain'] == 'policy'
    for language, filename, label in [('en', 'result.json', 'Target population'), ('zh', 'result.zh.json', '目标人群')]:
        data = json.loads((ROOT / 'examples/workplace-ai-assistant' / filename).read_text())
        assert 'target_learners' not in data['intervention']
        ui = br.UI_EN if language == 'en' else br.UI_ZH
        html = br.render_intervention(data, '', language, ui)
        assert label in html
        assert data['intervention']['target_population'] in html
