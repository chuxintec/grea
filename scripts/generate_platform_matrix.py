#!/usr/bin/env python3
"""Generate declarations, never infer native validation from a host_support label."""
import argparse,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def matrix():
 entries=json.loads((ROOT/'registry.json').read_text(encoding='utf-8'))['tools'];by_id={e['id']:e for e in entries}
 def canonical(e,seen=()):
  if e['id'] in seen:raise ValueError('Alias cycle')
  return canonical(by_id[e['alias_of']],(*seen,e['id'])) if e.get('alias_of') else e
 rows=[]
 for entry in sorted(entries,key=lambda e:e['id']):
  e=canonical(entry);support=e.get('host_support',{});commands=e.get('platform_commands',{})
  platforms={}
  for system in ('Darwin','Windows','Linux'):
   declared=system in support.get('systems',[])
   platforms[system]={'adapter':'implemented' if declared else 'unsupported',
     'requires_provider':e.get('category')=='provider',
     'native_validation':'not_run_per_tool','verification_scope':'See run-specific native CI and business reports; declarations are not proof.'}
  rows.append({'id':entry['id'],'canonical_id':e['id'],'platforms':platforms})
 return {'schema_version':1,'tools':rows,'count':len(rows),'scope':'Static routing declarations, no probes or native/business success inference.'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();path=ROOT/'schemas/tool-platform-matrix.json';text=json.dumps(matrix(),ensure_ascii=False,indent=2)+'\n'
 if a.check:
  if not path.is_file() or path.read_text(encoding='utf-8')!=text:raise SystemExit('Platform matrix drift')
 else:path.write_text(text,encoding='utf-8')
