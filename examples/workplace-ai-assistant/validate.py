"""Read-only contract and scientific consistency checks; does not bake reports."""
import json
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
def read(name): return json.loads((HERE/name).read_text())
def validate(value, schema):
 from scripts.validate_schema import Validator
 p = ROOT / schema
 obj = json.loads(p.read_text())
 Validator(obj, base_dir=p.parent).validate(value, obj)

def main():
 en,zh=read('result.json'),read('result.zh.json')
 checks=0
 for r in [en,zh]:
  validate(r,'schemas/report-result.schema.json'); checks+=1
  for key,schema in [('research_frame','domains/policy/frame.schema.json'),('decision','schemas/verdict.schema.json'),('intervention','schemas/intervention.schema.json'),('evaluation','schemas/evaluation.schema.json')]:validate(r[key],schema);checks+=1
  for key,schema in [('sources','source'),('evidence','evidence'),('methodology_reviews','methodology')]:
   for row in r[key]:validate(row,f'schemas/{schema}.schema.json');checks+=1
 validate(read('report_spec.json'),'schemas/report-spec.schema.json'); checks+=1
 for key in ['sources','evidence','claims']:
  assert [json.loads(line) for line in (HERE/(key+'.jsonl')).read_text().splitlines()]==en[key]
 for file,key in [('frame','research_frame'),('verdict','decision'),('intervention','intervention'),('evaluation','evaluation')]:assert read(file+'.json')==en[key]
 assert read('methodology.json')==en['methodology_reviews'][0]
 assert len({e['study_id'] for e in en['evidence']})==3
 assert en['evidence'][2]['sample_size']==373 and en['evidence'][2]['extensions']['study_total_n']==758
 assert en['evidence'][3]['sample_size'] is None
 assert not en['forest_plot_data'] and 'benchmark' not in en and 'execution' not in en
 assert en['research_frame']['extensions']['domain']=='policy'
 for e in en['evidence']:
  raw=e['extensions']['raw_result']
  assert raw['ci_lower'] is None and raw['ci_upper'] is None and raw['p_value'] is None
  assert e['extensions']['standardized_effect'] is None
 from engine.evidence_graph import EvidenceGraph
 graph=read('evidence_graph.json');g=EvidenceGraph.from_dict(graph)
 assert g.to_dict()==graph
 ids=set().union(*(set(graph[k]) for k in ['papers','evidence','claims','outcomes','risks','gaps']))|{'D-001'}
 assert all(e['source_id'] in ids and e['target_id'] in ids for e in graph['edges'])
 for e in g.evidence.values():assert e.effect_size['value'] is None and e.confidence_score is None
 renderer=ROOT/'visualization/eduevidence-report/scripts'
 sys.path.insert(0,str(renderer))
 import build_report as br
 for label,errors in [('contract',br.validate_contract(en)+br.validate_contract(zh)),('claims',br.audit_claims(en)+br.audit_claims(zh)),('bilingual',br.compare_parallel_result(en,zh)),('language',br.check_language_parallel(en,zh)),('numbers',br.check_numbers(en,{})),('precision',br.check_no_false_precision(en,{})+br.check_no_false_precision(zh,{}))]:
  assert not errors,(label,errors)
 from scripts import dashboard_server as ds
 projects=ds.scan_local_projects()
 project=next(p for p in projects if p['id']=='workplace-ai-assistant')
 assert project['evidence_count']==4 and project['has_graph'] and project['effect_count']==0
 print(json.dumps({'status':'PASS','schema_objects_validated':checks,'graph_roundtrip':'PASS','report_input_gates':'PASS','studio_scanned':project['id'],'studio_domain':project['domain'],'reports_generated':False},indent=2))
if __name__=='__main__':main()
