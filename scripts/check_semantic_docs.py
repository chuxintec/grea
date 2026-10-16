#!/usr/bin/env python3
"""Validate explicitly declared documentation references against product sources."""
import json
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parents[1]


def check(root):
    registry=json.loads((root/'registry.json').read_text());tools={t['id'] for t in registry['tools']}
    sources='\n'.join(p.read_text() for base in ('src','tools/unity') for p in (root/base).rglob('*') if p.suffix in ('.py','.cs') and 'node_modules' not in p.parts)
    errors=[];checked=0
    docs=[p for base in ('docs','plugin') for p in (root/base).rglob('*.md') if 'history' not in p.parts]
    for path in docs:
        for kind,value in re.findall(r'^<!-- grea:(tool|error|path) ([^\s]+) -->$',path.read_text(),re.M):
            checked+=1
            valid=value in tools if kind=='tool' else (re.search(r'\b'+re.escape(value)+r'\b',sources) is not None if kind=='error' else (root/value).is_file())
            if not valid:errors.append({'document':path.relative_to(root).as_posix(),'kind':kind,'missing':value})
    sys.path.insert(0,str(root/'src'))
    from grea.unity_project_contracts import capability_matrix
    if json.loads((root/'schemas/unity-capabilities.json').read_text())!=capability_matrix():
        errors.append({'kind':'generated_matrix_drift'})
    return {'ok':not errors,'checked_explicit_references':checked,'errors':errors,'scope':'Explicit grea annotations and current generated capability matrix; prose and historical statements need human review'}

if __name__=='__main__':
    result=check(ROOT);print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['ok'] else 1)
