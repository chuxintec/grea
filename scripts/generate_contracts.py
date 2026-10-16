#!/usr/bin/env python3
"""Generate portable operation contracts from the shared source; --check never writes."""
import argparse,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'src'))
from grea.contracts import catalog,ENVELOPE_SCHEMA,unity_documents,capability_matrix
from grea.common import digest
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
value={'schema_version':1,'operations':catalog()};value['sha256']=digest(value)
outputs={'operations.json':value,'result.schema.json':dict(ENVELOPE_SCHEMA,**{'$schema':'https://json-schema.org/draft/2020-12/schema'})}
outputs.update(unity_documents())
from grea.cocos_contracts import documents as cocos_documents
outputs.update(cocos_documents())
from grea.native_exit_contracts import documents as native_exit_documents
outputs.update(native_exit_documents())
from grea.authoring_contracts import documents as authoring_documents
outputs.update(authoring_documents())
from grea.evidence_contracts import documents as evidence_documents
outputs.update(evidence_documents())
outputs['unity-capabilities.json']=capability_matrix()
failed=[]
for name,value in outputs.items():
 path=root/'schemas'/name;content=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
 if a.check:
  if not path.exists() or path.read_text()!=content:failed.append(name)
 else:path.write_text(content)
print(json.dumps({'ok':not failed,'drifted':failed,'written':[] if a.check else list(outputs)}))
raise SystemExit(1 if failed else 0)
