#!/usr/bin/env python3
"""Read-only name/reference/identity audit; native outputs remain a separate gate."""
import argparse
import json
import re
import unicodedata
from pathlib import Path
from monkey.io import safe,read,load,new_output,write_json,stage_document


def run(candidate,previous,output):
    root=safe(candidate);old=safe(previous);out=new_output(output,[root,old]);issues=[];projects=[]
    receipt=load(read(root/'conversion-result.json'))
    for item in receipt['projects']:
        name=item['path'];base=root/name;manifest=load(read(base/'manifest.json',max_bytes=128*1024*1024),max_nodes=8_000_000)
        owned={f['path'] for f in manifest['files']}
        plan=load(read(base/('Assets/Game/Editor/Conversion/import-plan.json' if name=='UnityProject' else 'extensions/monkey-import/import-plan.json'),max_bytes=128*1024*1024),max_nodes=8_000_000)
        maps={}
        for file in ('name-map.json','module-name-map.json','decoded-name-map.json','package-name-map.json'):
            data=load(read(base/'Analysis'/file,max_bytes=128*1024*1024),max_nodes=8_000_000)
            maps[file]={k:v for k,v in data.items() if k!='records'}
            if file!='name-map.json':
                for row in data['records']:
                    if row['target'] not in owned:issues.append(dict(project=name,code='NAME_MAP_NOT_OWNED',path=row['target']))
        paths=([a['path'] for a in plan['textures']]+[a['path'] for a in plan['assets']]+[a['path'] for a in plan['bitmapFonts']]) if name=='UnityProject' else [a['path'] for a in plan['assets']]
        for path in paths:
            if path not in owned:issues.append(dict(project=name,code='RESOURCE_REFERENCE_NOT_EXACT_OWNED',path=path))
        for path in owned:
            if any(re.search(r'[<>:"\\|?*\x00-\x1f]',s) or s.endswith((' ','.')) or re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)',s,re.I) for s in path.split('/')):
                issues.append(dict(project=name,code='CROSS_PLATFORM_PATH',path=path))
        canonical=[unicodedata.normalize('NFC',p).casefold() for p in owned]
        if len(set(canonical))!=len(canonical):issues.append(dict(project=name,code='CANONICAL_PATH_COLLISION'))
        spine=load(read(base/'Analysis/spine-closures.json',max_bytes=128*1024*1024),max_nodes=8_000_000)
        for row in spine['skeletons']:
            for file in row['files']:
                if file['path'] not in owned:issues.append(dict(project=name,code='SPINE_PATH_NOT_OWNED',path=file['path']))
        if name=='UnityProject':
            a=load(read(old/name/'Analysis/source-map.json',max_bytes=128*1024*1024),max_nodes=8_000_000)['assets']
            source_map=load(read(base/'Analysis/source-map.json',max_bytes=128*1024*1024),max_nodes=8_000_000);b=source_map['assets']
            ids_equal={a['sourceId']:a['guid'] for a in a}=={a['sourceId']:a['guid'] for a in b}
            font_paths={a['id']:a['fontAssetPath'] for a in plan['assets'] if a.get('fontAssetPath')}
            for font in source_map['fonts']:
                if font['sourceId'] in font_paths and font['target']!=font_paths[font['sourceId']]:issues.append(dict(project=name,code='FONT_HANDOFF_PATH',path=font['target']))
        else:
            a=load(read(old/name/'extensions/monkey-import/import-plan.json',max_bytes=128*1024*1024),max_nodes=8_000_000)['assets'];b=plan['assets']
            ids_equal={a['sourceId']:a['uuid'] for a in a}=={a['sourceId']:a['uuid'] for a in b}
        if not ids_equal:issues.append(dict(project=name,code='RESOURCE_IDENTITY_CHANGED'))
        projects.append(dict(project=name,maps=maps,resourcePaths=len(paths),identityEntries=len(a),identitiesEqual=ids_equal,
            spine=dict(closed=spine['closed'],unresolved=spine['unresolved'],decodedPages=spine['decodedPages'],reusedPages=spine['reusedPages']),nativeValidation='not_run'))
    before=stage_document(old/'Structured/normalize/ir.json');after=stage_document(root/'Structured/normalize/ir.json')
    for field in ('sourceNames','sourceRoots','sourceManifestPath','sourceManifestSha256','stageReuse'):
        before.pop(field,None);after.pop(field,None)
    unchanged=before==after
    if not unchanged:issues.append(dict(code='IR_NON_NAME_DATA_CHANGED'))
    result=dict(schemaVersion=1,status='pass' if not issues else 'failed',projects=projects,issues=issues,
        nonNameIrUnchanged=unchanged,sourceCodeParserExecuted=receipt.get('sourceCodeParserExecuted'),
        sourceStageReuse=receipt.get('sourceStageReuse'),scope='allocated/owned paths and seeded identities; no Editor or business acceptance')
    write_json(out/'audit.json',result);print({'status':result['status'],'issues':len(issues),'nonNameIrUnchanged':unchanged,'report':str(out/'audit.json')})
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--previous',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();raise SystemExit(0 if run(a.candidate,a.previous,a.out)['status']=='pass' else 1)
