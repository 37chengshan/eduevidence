"""Generate GitHub-safe vector diagrams from the canonical protocol registry."""
from pathlib import Path
import sys
from html import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.workflows import SCIENTIFIC_STAGE_IDS  # noqa: E402

OUT = ROOT / 'assets/readme'
OUT.mkdir(parents=True, exist_ok=True)


def start(title, subtitle, height):
    return [f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}" role="img" aria-label="{escape(title)}">
<title>{escape(title)}</title><desc>{escape(subtitle)}</desc>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10" fill="none" stroke="#a15c40" stroke-width="1.5"/></marker></defs>
<rect width="1200" height="{height}" rx="24" fill="#f7f5f0"/>
<g font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif">
<text x="48" y="43" font-size="12" letter-spacing="3" fill="#9b5e45">EDUEVIDENCE / RESEARCH STUDIO</text>
<text x="48" y="92" font-size="32" font-weight="600" fill="#272924">{escape(title)}</text>
<text x="48" y="126" font-size="16" fill="#6f7068">{escape(subtitle)}</text>''']


def card(parts, x, y, w, num, title, detail, accent=False):
    fill = '#eee2d8' if accent else '#ffffff'
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="96" rx="14" fill="{fill}" stroke="#dcd8ce"/>')
    parts.append(f'<text x="{x+20}" y="{y+28}" font-size="12" fill="#a15c40">{escape(num)}</text>')
    parts.append(f'<text x="{x+20}" y="{y+54}" font-size="21" font-weight="600" fill="#30332e">{escape(title)}</text>')
    parts.append(f'<text x="{x+20}" y="{y+78}" font-size="13" fill="#6f7068">{escape(detail)}</text>')


def line(parts, d):
    parts.append(f'<path d="{d}" fill="none" stroke="#a15c40" stroke-width="1.7" marker-end="url(#arrow)"/>')


labels = {
    'frame': ('Frame / 定义问题', 'Question, population, comparison, outcomes'),
    'retrieve': ('Retrieve / 检索来源', 'Primary sources and retrieval provenance'),
    'extract': ('Extract / 提取证据', 'Study findings, measures and uncertainty'),
    'challenge': ('Challenge / 反证质疑', 'Counter-evidence and alternative explanations'),
    'audit': ('Audit / 方法审计', 'Study quality, bias and evidence limitations'),
    'adjudicate': ('Adjudicate / 证据裁决', 'Supported claims and bounded decisions'),
    'applicability': ('Applicability / 适用边界', 'For whom, where and under which conditions'),
    'intervene': ('Intervene / 设计试点', 'A grounded knowledge gap before a new design'),
    'evaluate': ('Evaluate / 评估更新', 'Validate new data and revise the decision'),
}
p=start('From evidence to a decision you can inspect', 'Nine scientific stages · 三条公开工作流 · Education + organizational policy', 704)
for i, stage in enumerate(SCIENTIFIC_STAGE_IDS):
    row,col=divmod(i,3)
    if row==1: col=2-col
    x,y=48+col*376,166+row*128
    card(p,x,y,352,f'{i+1:02d}',*labels[stage],stage=='adjudicate')
    if i in (0,1,6,7): line(p,f'M{x+352} {y+48} H{x+370}')
    if i in (3,4): line(p,f'M{x} {y+48} H{x-18}')
    if i in (2,5): line(p,f'M{x+176} {y+96} V{y+121}')
p.append('<rect x="48" y="568" width="1104" height="88" rx="14" fill="#e9eee7"/>')
p.append('<text x="70" y="600" font-size="18" font-weight="600" fill="#456450">Projection / 展示制品</text>')
p.append('<text x="70" y="627" font-size="15" fill="#456450">Read-only Studio · Five report themes · Bilingual HTML · A report is not proof of an executed study.</text>')
p.append('<text x="48" y="682" font-size="12" fill="#6f7068">Evidence Review 01–07   /   Decision &amp; Pilot 01–08   /   Evaluate &amp; Update 09</text></g></svg>')
(OUT/'research-workflow.svg').write_text('\n'.join(p))
p=start('One research record. Controlled contributions.', 'Roles describe scientific responsibilities. Workers contribute only when the host supports delegation.',600)
card(p,48,178,290,'01 / LEAD','Plan the work','Bounded tasks and input snapshots')
card(p,442,178,310,'02 / EXECUTION','Native or delegated','Same scientific protocol and validation gates')
card(p,854,178,298,'03 / STAGING','Review contributions','Evidence, critique and audit artifacts')
line(p,'M338 226 H432'); line(p,'M752 226 H844');line(p,'M1004 274 V330 H599 V358')
card(p,442,368,310,'04 / VALIDATED COMMIT','Single writer','Lead commits a new immutable graph revision',True)
line(p,'M762 416 H844');card(p,854,368,298,'05 / PROJECTION','Read and trace','Studio, reports and revision history')
p.append('<text x="48" y="520" font-size="17" fill="#456450">Append evidence. Preserve provenance. Derive the decision from validated facts.</text>')
p.append('<text x="48" y="550" font-size="14" fill="#6f7068">Native execution needs no worker service. Cross-backend empirical performance is a separate verification task.</text></g></svg>')
(OUT/'controlled-execution.svg').write_text('\n'.join(p))
print('Generated research-workflow.svg and controlled-execution.svg from current protocol.')
