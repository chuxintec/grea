"""Join locally serialized Material references through the original provider prefab."""
import re
from pathlib import Path
from .io import inside, load, read, safe, sha
from .sources.compiled import fail


def bind(project, report, roots, nodes, objects, edges, moves, existing):
    pin = project / 'Analysis/Evidence/provider-index-paths.json'
    if not pin.is_file():
        return
    paths = load(read(pin))
    index = read(safe(paths['inventory']), max_bytes=128*1024*1024)
    if sha(index) != report['providerInventorySha256']:
        fail('UNITY_PREFAB_PROVIDER_INDEX', str(pin), 'Original provider inventory differs')
    files = {r['path']: r['sha256'] for r in load(index, max_nodes=8_000_000)['files']}
    provider = safe(paths['exportRoot'])
    def payload(path):
        raw = read(inside(provider, path))
        if sha(raw) != files.get(path):
            fail('UNITY_PREFAB_PROVIDER_DRIFT', path, 'Original provider bytes differ')
        return raw.decode('utf-8')
    by_guid = {r['guid']:r for r in moves}
    doc_header = re.compile(r'^--- !u!(\d+) &(-?\d+)\s*$', re.M)
    for root_id, root in roots.items():
        parts = doc_header.split(payload(root['providerPath']))
        docs = {local:(int(kind),body) for kind,local,body in zip(parts[1::3],parts[2::3],parts[3::3])}
        root_tr = [local for local,(kind,body) in docs.items() if kind in (4,224) and '\n  m_Father: {fileID: 0}' in body]
        if len(root_tr)!=1:continue
        stack=[(root_id,root_tr[0])]
        while stack:
            nid, transform = stack.pop()
            node=nodes[nid];tr=docs[transform][1]
            owner=re.search(r'^  m_GameObject: \{fileID: (-?\d+)\}',tr,re.M)
            if not owner:continue
            go=docs[owner[1]][1];name=re.search(r'^  m_Name: (.*)$',go,re.M)
            if not name or name[1]!=node['name']:continue
            local_ids=re.findall(r'^  - component: \{fileID: (-?\d+)\}',go,re.M)
            children=re.search(r'^  m_Children:(?: \[\])?\n((?:  - \{fileID: -?\d+\}\n)*)',tr,re.M)
            cids=re.findall(r'fileID: (-?\d+)',children[1]) if children else []
            if len(cids)==len(node['childSourceObjectIds']):
                stack.extend(zip(node['childSourceObjectIds'],cids))
            if len(local_ids)!=len(node['orderedComponents']):continue
            for cid,row in zip(local_ids,node['orderedComponents']):
                sid=row['sourceObjectId'];obj=objects[sid];kind,body=docs[cid]
                if obj['classId']!=kind:continue
                target=edges.get((sid,'$/m_Material'),{}).get('targetSourceObjectId')
                if not target or target in existing or objects[target]['type']!='Material':continue
                ref=re.search(r'^  m_Material: \{fileID: (2100000), guid: ([0-9a-f]{32}), type: 2\}',body,re.M)
                if not ref or ref[2] not in by_guid:continue
                move=by_guid[ref[2]];original='ExportedProject/'+move['source']
                mat=payload(original);meta=payload(original+'.meta')
                if (not mat.startswith('%YAML') or '\n--- !u!21 &2100000\n' not in mat
                    or '\n  m_Name: '+objects[target]['name']+'\n' not in mat
                    or '\nguid: '+ref[2]+'\n' not in meta):continue
                existing[target]=dict(path=move['target'],guid=ref[2],localId=ref[1],sourceType='Material',
                                      providerOwnerPath=root['providerPath'],sourceComponentId=sid)
