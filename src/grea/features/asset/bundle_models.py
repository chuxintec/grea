"""Prepare a native static-model handoff from GREA's pinned Unity bundle inspections."""
import argparse
import hashlib
import json
from pathlib import Path

from grea.common import hash_file
from grea.development.io import new_output, safe
from grea.recovery.layout import LayoutPlanner

def identity(file, pid):
    return file.lower() + ':' + str(pid)


def model_nodes(objects, root):
    nodes = []
    visited = set()
    def visit(go_id, parent):
        if go_id in visited:
            raise ValueError("Cyclic or shared model hierarchy")
        visited.add(go_id)
        go = objects[go_id]
        if any(p["component"]["fileId"] != "0" for p in go["data"]["m_Component"]):
            raise ValueError("External model component")
        components = [objects[p['component']['pathId']] for p in go['data']['m_Component']]
        kinds = [o['type'] for o in components]
        if kinds.count('Transform') != 1 or set(kinds) - {'Transform','MeshFilter','MeshRenderer'}:
            raise ValueError(f"Non-static model components on {go_id}: {kinds}")
        xf = next(o for o in components if o['type']=='Transform')['data']
        index = len(nodes)
        row = dict(name=go['data']['m_Name'], parent=parent, active=go['data']['m_IsActive'],
                   position=xf['m_LocalPosition'], rotation=xf['m_LocalRotation'], scale=xf['m_LocalScale'],
                   meshId='', materialIds=[])
        for component in components:
            refs = component['references']
            if component['type']=='MeshFilter':
                mesh = next(r for r in refs if r['location']=='$/m_Mesh')
                if mesh['fileId']!='0' or mesh['pathId']=='0':raise ValueError('External or absent model mesh')
                row['meshId']=mesh['pathId']
            if component['type']=='MeshRenderer':
                materials=[r for r in refs if r['location'].startswith('$/m_Materials/')]
                if any(r['fileId']!='0' or r['pathId']=='0' for r in materials):raise ValueError('External or empty model material slot')
                row['materialIds']=[r['pathId'] for r in materials]
        nodes.append(row)
        for child in xf['m_Children']:
            if child['fileId']!='0':raise ValueError('External model child')
            visit(objects[child['pathId']]['data']['m_GameObject']['pathId'], index)
    visit(root, -1)
    return nodes


def prepare(inspections, destination, occupied):
    root=safe(inspections)
    out=new_output(destination,[root,occupied])
    job=json.loads((root/'BatchInspection/job.json').read_text())
    planner=LayoutPlanner('unity')
    for line in safe(occupied).read_text().splitlines():planner.claim(line)
    bundles=[];requests=[];assets={}
    for src in job['files']:
        if hash_file(src['path'])['sha256']!=src['sha256']:raise ValueError('Source bundle changed')
        docfile=safe(src['inspection'])/'typed-objects.json'
        receipt=json.loads((docfile.parent/'inspection.json').read_text())
        if hash_file(docfile)['sha256']!=receipt['typedObjectsSha256'] or receipt['source']['sha256']!=src['sha256']:
            raise ValueError('Stale model inspection')
        doc=json.loads(docfile.read_bytes());models=[]
        for file in doc['files']:
            objects={o['pathId']:o for o in doc['objects'] if o['file']==file['id']}
            for container in (o for o in objects.values() if o['type']=='AssetBundle'):
                for address,entry in container['data']['m_Container']:
                    ptr=entry['asset']
                    if not address.lower().endswith('.fbx') or ptr['fileId']!='0':continue
                    obj=objects.get(ptr['pathId'])
                    if obj is None or obj['type']!='GameObject':continue
                    key=identity(file['name'],ptr['pathId'])
                    if key in assets:raise ValueError('Multiple root addresses for '+key)
                    nodes=model_nodes(objects,ptr['pathId'])
                    assets[key]=dict(kind='prefab',ext='.prefab',name=obj['name'],raw=obj['rawSha256'],address=address)
                    for node in nodes:
                        for pid in ([node['meshId']] if node['meshId'] else []) + node['materialIds']:
                            dep=objects[pid];depkey=identity(file['name'],pid)
                            if depkey in assets:continue
                            kind,ext={'Mesh':('model','.asset'),'Material':('material','.mat')}[dep['type']]
                            if kind=='material':
                                refs=[r for r in dep['references'] if r['pathId']!='0']
                                if not refs or any(r['location']!='$/m_Shader' or r['fileId']=='0' for r in refs):
                                    raise ValueError('Model material requires separate texture/shader recovery: '+depkey)
                                external=file['externals'][int(refs[0]['fileId'])-1]
                                if not external['path'].endswith('unity_builtin_extra'):
                                    raise ValueError('Custom model shader requires a verified shader mapping: '+depkey)
                            logical=address.rsplit('/',1)[0]+'/'+dep['name']+ext
                            assets[depkey]=dict(kind=kind,ext=ext,name=dep['name'],raw=dep['rawSha256'],address=logical)
                    models.append(dict(address=address,identity=key,file=file['name'],nodes=nodes))
        bundles.append(dict(path=src['path'],sha256=src['sha256'],models=models))
    for key,a in assets.items():
        requests.append((key,a['kind'],a['ext'],'',dict(logicalPath=a['address']),None))
    planner.reserve(requests)
    for bundle in bundles:
        for model in bundle['models']:
            model['target']=planner.path(model['identity'],'prefab','.prefab')
            for node in model['nodes']:
                def ref(pid):
                    key=identity(model['file'],pid);a=assets[key]
                    return dict(identity=key,raw=a['raw'],name=a['name'],target=planner.path(key,a['kind'],a['ext']))
                node['mesh']=ref(node['meshId']) if node['meshId'] else None
                node['materials']=[ref(pid) for pid in node['materialIds']]
    if not assets:
        raise ValueError('No static FBX roots in verified input')
    (out/'BundleModelRecovery.cs').write_bytes(Path(__file__).with_name('BundleModelRecovery.cs.txt').read_bytes())
    (out/'job.json').write_text(json.dumps(dict(bundles=bundles),ensure_ascii=False))
    return dict(bundles=len(bundles),models=sum(len(b['models']) for b in bundles),assets=len(assets),output=str(out),nativeMethod='Grea.VisualRecovery.BundleModels.Run',nativeScript=str(out/'BundleModelRecovery.cs'),nativeReadback='not_run')


def build_parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inspections',required=True);p.add_argument('--occupied',required=True,help='UTF-8 text, one existing Unity asset path per line')
    p.add_argument('--output',required=True)
    return p


def main(argv=None):
    args=build_parser().parse_args(argv)
    print(json.dumps(prepare(args.inspections,args.output,args.occupied)))
    return 0
