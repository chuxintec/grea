"""Restore broken provider Sprite texture pointers from the source Atlas and exact cached ASTC variant."""
import argparse
import base64
import hashlib
import json
import re
import struct
from pathlib import Path
from PIL import Image
from grea.recovery.normalize import open_texture


def guid_key(key):
    raw = struct.pack('<4I', *(key[f'data[{i}]'] for i in range(4))).hex()
    return ''.join(raw[i+1] + raw[i] for i in range(0, 32, 2))


def restore(graph, project, pool):
    edges = {(e['sourceObjectId'], e['location']): e.get('targetSourceObjectId') for e in graph['referenceEdges']}
    objects = {o['sourceObjectId']: o for o in graph['reachableObjects']}
    assets = project / 'Assets'
    files = {}
    for f in assets.rglob('*.asset'):
        raw = f.read_bytes()
        if b'--- !u!213 ' not in raw[:110] or b'0000000deadbeef15deadf00d0000000' not in raw:
            continue
        key = re.search(rb'm_RenderDataKey:\s*([0-9a-f]{32}): (-?\d+)', raw)
        if key:
            files.setdefault((key[1].decode(), int(key[2])), []).append(f)
    prepared = {}
    log = []
    tokens = {}
    for f in pool.rglob('*.txt'):
        tokens.setdefault(f.stem, []).append(f)
    for atlas in objects.values():
        if atlas['type'] != 'SpriteAtlas':
            continue
        members = {edges.get((atlas['sourceObjectId'], f'$/m_PackedSprites/{i}')) for i in range(len(atlas['data']['m_PackedSprites']))}
        keys = {json.dumps(objects[s]['data'].get('m_RenderDataKey'), sort_keys=True) for s in members if s in objects}
        for i,(key,render) in enumerate(atlas['data']['m_RenderDataMap']):
            if json.dumps(key,sort_keys=True) not in keys:
                continue
            matches = files.get((guid_key(key[0]), key[1]), [])
            if len(matches) != 1:
                continue
            sid = edges.get((atlas['sourceObjectId'], f'$/m_RenderDataMap/{i}/1/texture'))
            if sid not in objects:
                continue
            tex = objects[sid]['data']
            if sid not in prepared:
                payload = base64.b64decode(tex['image data']['base64'])
                marker = re.fullmatch(rb'.(.+)_(\d+)###', payload, re.S)
                if not marker:continue
                token = marker[1].decode()
                valid = {}
                for f in tokens.get(token, []):
                    b = f.read_bytes()
                    if b[:4] == bytes.fromhex('13aba15c') and int.from_bytes(b[7:10],'little') == tex['m_Width'] and int.from_bytes(b[10:13],'little') == tex['m_Height']:
                        valid[hashlib.sha256(b).hexdigest()] = f
                if len(valid) != 1:continue
                digest, f = next(iter(valid.items()))
                guid = hashlib.sha256(('monkey:atlas:'+sid+':'+digest).encode()).hexdigest()[:32]
                target = assets / 'Game/Content/RecoveredAtlases' / (guid + '.png')
                target.parent.mkdir(parents=True,exist_ok=True)
                image = open_texture(f.read_bytes(), '.astc').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                image.save(target)
                Path(str(target)+'.meta').write_text('fileFormatVersion: 2\nguid: '+guid+'\nTextureImporter:\n  serializedVersion: 12\n  mipmaps:\n    enableMipMap: 0\n  maxTextureSize: 8192\n  textureSettings:\n    filterMode: 1\n    wrapU: 1\n    wrapV: 1\n  textureType: 0\n  nPOTScale: 0\n')
                prepared[sid]=(guid,digest,str(f))
            guid,digest,source=prepared[sid]
            f=matches[0];raw=f.read_bytes()
            old=b'texture: {fileID: 2800000, guid: 0000000deadbeef15deadf00d0000000, type: 2}'
            if raw.count(old)!=1:continue
            rect=re.search(rb'  m_RD:.*?    textureRect:\s+serializedVersion: \d+\s+x: ([^\n]+)\s+y: ([^\n]+)\s+width: ([^\n]+)\s+height: ([^\n]+)',raw,re.S)
            if not rect or any(abs(float(v)-render['textureRect'][k])>0.001 for k,v in zip(('x','y','width','height'),rect.groups())):continue
            f.write_bytes(raw.replace(old,f'texture: {{fileID: 2800000, guid: {guid}, type: 3}}'.encode()))
            log.append(dict(sprite=str(f.relative_to(project)),texture=sid,cache=source,sha256=digest))
    return log


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('graph','project','cache','report'):parser.add_argument('--'+k,type=Path,required=True)
    a=parser.parse_args();rows=restore(json.loads(a.graph.read_bytes()),a.project,a.cache)
    a.report.write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(len(rows),'sprite bindings restored')
