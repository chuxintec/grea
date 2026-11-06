"""Prepare native visual repairs for an exported Unity project.

Usage: repair_unity_visuals.py --project PROJECT --sources manifest.json --pool ASTC_DIR
The JSON manifest has bundles (explicit local bundle paths) and roots with asset
(project-relative prefab path), cab (serialized file name) and pathId (GameObject).
The pool should contain the exact source-token .txt files to repair. Run
UnitySourceVisualRepair.Apply and, in a fresh Editor, UnitySourceVisualRepair.Verify.
"""
import argparse
import hashlib
import io
import json
import math
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from PIL import Image
from grea.recovery.normalize import open_texture
from grea.recovery.unity_object_dependencies import pointer

MARKER = re.compile(rb'.([^/\\\x00]+?\.[0-9a-fA-F]{8})(?:_\d+###)?', re.S)
ROTATIONS = {1: Image.Transpose.FLIP_LEFT_RIGHT, 2: Image.Transpose.FLIP_TOP_BOTTOM,
             3: Image.Transpose.ROTATE_180, 4: Image.Transpose.ROTATE_270}

def render_key(key):
    guid, local_id = key
    return tuple(guid[f'data[{i}]'] for i in range(4)), local_id

def sprite_pixels(page, data, rd):
    rect = rd['textureRect']
    x, y = rect['x'], rect['y']
    box = tuple(map(round, (x, y, x+rect['width'], y+rect['height'])))
    if not (0 <= box[0] < box[2] <= page.width and 0 <= box[1] < box[3] <= page.height):
        raise ValueError(f'Sprite rectangle outside source texture: {box}')
    part = page.crop(box)
    rotation = (rd['settingsRaw'] >> 2) & 15
    if rd['settingsRaw'] & 1 and rotation:
        if rotation not in ROTATIONS:
            raise ValueError(f'Unsupported sprite packing rotation: {rotation}')
        part = part.transpose(ROTATIONS[rotation])
    scale = rd.get('downscaleMultiplier') or 1
    if scale != 1:
        part = part.resize(tuple(max(1, round(v*scale)) for v in part.size), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', tuple(max(1, round(data['m_Rect'][k])) for k in ('width','height')))
    offset = rd['textureRectOffset']
    canvas.paste(part, tuple(round(offset[k]*scale) for k in ('x','y')))
    return canvas.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

def write_owned(path, raw):
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f'Conflicting generated asset: {path}')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent) as tmp:
        tmp.write(raw)
        tmp.flush()
        try:
            os.link(tmp.name, path)
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ValueError(f'Conflicting generated asset: {path}')

def replace_file(path, content):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        temp_path = Path(tmp.name)
        try:
            tmp.write(content)
            tmp.flush()
            os.replace(temp_path, path)
        finally:
            temp_path.unlink(missing_ok=True)


def install_editor_sources(project):
    source = Path(__file__).parent/'targets/unity_source'
    editor = project/'Assets/Editor'
    receipt = project/'visual-tool-ownership.json'
    existing = json.loads(receipt.read_text()) if receipt.exists() else {}
    names = ('UnitySourceVisualRepair.cs','UnitySourceOverlapReview.cs')
    planned = {name:(source/name).read_bytes() for name in names}
    editor.mkdir(parents=True,exist_ok=True)
    for name,raw in planned.items():
        dest = editor/name
        if dest.exists() and dest.read_bytes()!=raw:
            if hashlib.sha256(dest.read_bytes()).hexdigest()!=existing.get(name):
                raise ValueError(f'Conflicting editor source: {dest}')
    for name,raw in planned.items():
        dest = editor/name
        if not dest.exists() or dest.read_bytes()!=raw:
            replace_file(dest,raw)
    hashes = {name:hashlib.sha256(raw).hexdigest() for name,raw in planned.items()}
    replace_file(receipt,json.dumps(hashes,indent=2).encode())


def write_texture_meta(path, meta):
    if not path.exists():
        write_owned(path, meta.encode())
        return
    # Unity expands importer defaults and rounds floats when saving .meta files.
    # Compare only the fields this generator owns, leaving other settings intact.
    current = path.read_text()
    for line in meta.splitlines():
        field, value = line.strip().split(':', 1)
        if not value.strip() or field == 'serializedVersion':
            continue
        match = re.search(r'^' + re.escape(line[:len(line)-len(line.lstrip())]+field) + r': (.+)$', current, re.M)
        expected = value.strip()
        if match and match[1].strip() == expected:
            continue
        if match and field in ('spritePivot', 'spriteBorder', 'spritePixelsToUnits'):
            floats = r'[-+]?(?:[0-9]+(?:[.][0-9]*)?|[.][0-9]+)(?:[eE][-+]?[0-9]+)?'
            a, b = re.findall(floats, expected), re.findall(floats, match[1])
            if a and len(a)==len(b) and all(math.isclose(float(x),float(y),rel_tol=1e-6,abs_tol=1e-6) for x,y in zip(a,b)):
                continue
        raise ValueError(f'Conflicting texture importer setting {field}: {path}')


class SourceImages:
    def __init__(self, files, pool, project):
        self.files = files
        self.pool = pool
        self.project = project
        self.atlases = {}
        self.assets = {}
        self.outside_pool = {}
        self.page = lru_cache(maxsize=6)(self._page)
        self.image = lru_cache(maxsize=None)(self._image)

    def _page(self, key):
        file = self.files.get(key[0])
        if not file or key[1] not in file.objects:
            return None
        data = file.objects[key[1]].read_typetree()
        marker = MARKER.fullmatch(bytes(data['image data']))
        if not marker:
            return None
        token = marker[1].decode()
        path = self.pool / (token+'.txt')
        if not path.is_file():
            self.outside_pool[token] = [data["m_Width"],data["m_Height"]]
            return None
        raw = path.read_bytes()
        im = open_texture(raw, '.astc')
        if im.size != (data['m_Width'], data['m_Height']):
            raise ValueError(f'Wrong dimensions for {token}')
        return im, token, hashlib.sha256(raw).hexdigest()

    def _image(self, key):
        if not key or key[0] not in self.files:
            return None
        sf = self.files[key[0]]
        obj = sf.objects.get(key[1])
        if obj is None or obj.type.name not in ('Sprite','Texture2D'):
            return None
        data = obj.read_typetree()
        sprite = obj.type.name == 'Sprite'
        if sprite:
            source_key = render_key(data['m_RenderDataKey'])
            if source_key[0] == (0,0,15,0) and source_key[1] == 10913 and data['m_Name']=='Knob':
                return dict(kind='builtinSprite',asset='',token='10913')
            atlas_ref = pointer(sf, data.get('m_SpriteAtlas'))
            atlas_file = self.files.get(atlas_ref[0]) if atlas_ref else sf
            atlas = atlas_file.objects.get(atlas_ref[1]) if atlas_ref and atlas_file else None
            if atlas_ref and (not atlas or atlas.type.name != 'SpriteAtlas'):
                return None
            owner = atlas_ref or (key[0], None)
            if owner not in self.atlases:
                entries = {}
                objects = [atlas] if atlas else sf.objects.values()
                for item in objects:
                    if item.type.name != 'SpriteAtlas':
                        continue
                    for original, render in item.read_typetree()['m_RenderDataMap']:
                        identity = render_key(original)
                        if identity in entries and entries[identity] != render:
                            raise ValueError(f'Ambiguous atlas region: {identity}')
                        entries[identity] = render
                self.atlases[owner] = entries
            rd = self.atlases[owner].get(source_key)
            if rd is None:
                rd = data['m_RD']
                atlas_file = sf
            page_key = pointer(atlas_file, rd['texture'])
        else:
            page_key = key
        page = self.page(page_key) if page_key else None
        if not page:
            return None
        pixels, token, sha = page
        image = sprite_pixels(pixels,data,rd) if sprite else pixels.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        kind = 'sprite' if sprite else 'texture'
        # Spine resolves atlas pages against Material.mainTexture.name. Keep
        # the source filename and use a per-identity directory for collisions.
        version = 1 if sprite else 2
        digest = hashlib.sha256(f'monkey.visual.v{version}:{key}:{sha}'.encode()).hexdigest()[:32]
        name = data['m_Name']
        if not sprite and (not name or name in ('.','..') or re.search(r'[/\\:\x00]', name)):
            raise ValueError(f'Unrepresentable source texture name: {name!r}')
        rel = f'Assets/RecoveredSourceImages/{digest}.png' if sprite else f'Assets/RecoveredSourceImages/{digest}/{name}.png'
        self.assets[rel] = dict(source=list(key),token=token,sha256=sha,name=data['m_Name'])
        buf = io.BytesIO()
        image.save(buf,format='PNG')
        write_owned(self.project/rel,buf.getvalue())
        meta = f'fileFormatVersion: 2\nguid: {digest}\nTextureImporter:\n  serializedVersion: 12\n  mipmaps:\n    enableMipMap: 0\n  maxTextureSize: 8192\n  nPOTScale: 0\n  alphaIsTransparency: 1\n  textureType: {8 if sprite else 0}\n'
        if sprite:
            p,b=data['m_Pivot'],data['m_Border']
            meta+=f"  spriteMode: 1\n  alignment: 9\n  spritePivot: {{x: {p['x']}, y: {p['y']}}}\n  spriteBorder: {{x: {b['x']}, y: {b['y']}, z: {b['z']}, w: {b['w']}}}\n  spritePixelsToUnits: {data['m_PixelsToUnits']}\n"
        write_texture_meta(Path(str(self.project/rel)+'.meta'),meta)
        return dict(kind=kind,asset=rel,token=token,sourceName=name)

def coincident_views(left, right):
    """Only compare fixed-size RectTransforms in the same anchoring frame."""
    for anchor in ('m_AnchorMin', 'm_AnchorMax'):
        if left.get(anchor) != right.get(anchor):
            return False
    if left.get('m_AnchorMin') != left.get('m_AnchorMax'):
        return False
    def bounds(rect):
        size = rect['m_SizeDelta']
        corner = [rect['m_AnchoredPosition'][axis] - rect['m_Pivot'][axis]*size[axis] for axis in ('x','y')]
        return (*corner, corner[0]+size['x'], corner[1]+size['y'])
    a, b = bounds(left), bounds(right)
    area_a = (a[2]-a[0])*(a[3]-a[1])
    area_b = (b[2]-b[0])*(b[3]-b[1])
    if min(area_a,area_b) <= 0:
        return False
    overlap = max(0,min(a[2],b[2])-max(a[0],b[0])) * max(0,min(a[3],b[3])-max(a[1],b[1]))
    return overlap >= 0.9*min(area_a,area_b) and overlap >= 0.75*max(area_a,area_b)


def sibling_states(children, rules, asset):
    decisions = []
    for rule in rules:
        keep = [c for c in children if c['node']==rule['keep'] and c['active']]
        hide = [c for c in children if c['node']==rule['hide'] and c['active']]
        if len(keep)!=1 or len(hide)!=1 or keep[0] is hide[0]:
            continue
        if coincident_views(keep[0]['rect'],hide[0]['rect']):
            decisions.append(dict(root=asset,path=hide[0]['path'],node=hide[0]['node'],
                                  active=False,reason=rule['reason']))
    return decisions


def equivalent_texture_sources(keys, files):
    """Return a representative only for identical named source texture markers and settings."""
    signatures = set()
    for key in keys:
        if not key or key[0] not in files:
            return None
        obj = files[key[0]].objects.get(key[1])
        if obj is None or obj.type.name != 'Texture2D':
            return None
        data = obj.read_typetree()
        marker = MARKER.fullmatch(bytes(data['image data']))
        if not marker:
            return None
        signatures.add((marker[1], data['m_Name'], data['m_Width'], data['m_Height'],
                        data['m_ColorSpace'], data['m_TextureDimension'],
                        tuple(sorted(data['m_TextureSettings'].items()))))
    return min(keys) if len(signatures) == 1 else None


def reviewed_overlap_states(findings, rules, source_nodes):
    """Choose explicit sibling states only after the native glyph audit observed a collision."""
    decisions = {}
    for hit in findings:
        root = hit['root']
        paths = (hit['first'], hit['second'])
        parent = paths[0].rpartition('/')[0]
        if hit['coverage'] < 0.85 or paths[0] == paths[1] or parent != paths[1].rpartition('/')[0]:
            continue
        children = [source_nodes.get((root, path)) for path in paths]
        if not all(child and child[1] for child in children):
            continue
        names = [child[0] for child in children]
        for rule in rules:
            if set(names) != {rule['keep'], rule['hide']} or rule['keep'] == rule['hide']:
                continue
            if rule.get('parent') and source_nodes.get((root, parent), (None,))[0] != rule['parent']:
                continue
            if not rule['reason']:
                raise ValueError('Missing static-state rationale')
            keep = (root, paths[names.index(rule['keep'])])
            hide = (root, paths[names.index(rule['hide'])])
            if decisions.get(keep) is False or decisions.get(hide) is True:
                raise ValueError(f'Conflicting static label rules in {root}')
            decisions[keep] = True
            decisions[hide] = False
            yield dict(root=root, path=hide[1], node=rule['hide'], active=False, reason=rule['reason'])


def restore_empty_font_atlases(project, files):
    """Preserve source zero-sized dynamic TMP atlases skipped by bitmap exporters."""
    assets = project / 'Assets'
    dynamic = []
    font_paths = defaultdict(list)
    for path in assets.rglob('*.asset'):
        with path.open('rb') as stream:
            header = stream.read(8192)
        if b'  m_AtlasPopulationMode: 1\n' not in header:
            continue
        match = re.search(rb'^  m_AtlasTextures:\s*\n  - \{fileID: 2800000, guid: ([a-f0-9]{32}), type: [23]\}', header, re.M)
        if match:
            name = re.search(rb'^  m_Name: (.+)$', header, re.M)
            if name:
                guid = match[1].decode()
                dynamic.append((name[1].decode(), guid))
                font_paths[guid].append(path)
    if not dynamic:
        return []
    known = set()
    for meta in assets.rglob('*.meta'):
        match = re.search(rb'^guid: ([a-f0-9]{32})$', meta.read_bytes(), re.M)
        if match:
            known.add(match[1].decode())
    wanted = {guid for _, guid in dynamic} - known
    if not wanted:
        return []
    # Static and dynamic fallback assets can share a material name. Follow the
    # font object's own atlas pointer before matching its material texture slot.
    font_names = {name for name, guid in dynamic if guid in wanted}
    font_keys = defaultdict(set)
    for sf in files.values():
        for obj in sf.objects.values():
            if obj.type.name != 'MonoBehaviour' or obj.peek_name() not in font_names:
                continue
            font = obj.read_typetree()
            if font.get('m_AtlasPopulationMode') == 1 and font.get('m_AtlasTextures'):
                font_keys[font['m_Name']].add(pointer(sf, font['m_AtlasTextures'][0]))
    restored = []
    for path in assets.rglob('*.mat'):
        data = path.read_text()
        ref = re.search(r'^ +(?:- )?_MainTex:\s*\n\s*m_Texture: \{fileID: 2800000, guid: ([a-f0-9]{32}), type: [23]\}', data, re.M)
        if not ref or ref[1] not in wanted:
            continue
        candidates = set()
        keys = {key for name, guid in dynamic if guid == ref[1] for key in font_keys[name]}
        for key in keys:
            obj = files[key[0]].objects.get(key[1]) if key and key[0] in files else None
            if not obj or obj.type.name != 'Texture2D':
                candidates.add(None)
                continue
            tex = obj.read_typetree()
            if tex['m_Width'] or tex['m_Height'] or tex['image data'] or tex['m_StreamData']['size']:
                candidates.add(None)
                continue
            settings = tex['m_TextureSettings']
            candidates.add((tex['m_Name'], tex['m_TextureFormat'], tex['m_IsReadable'], tex['m_MipCount'],
                            tex['m_ColorSpace'], *(settings[k] for k in ('m_FilterMode','m_Aniso','m_MipBias','m_WrapU','m_WrapV','m_WrapW'))))
        if len(candidates) != 1 or None in candidates:
            continue
        name, fmt, readable, mips, color, filt, aniso, bias, u, v, w = candidates.pop()
        guid = ref[1]
        target = assets / 'RecoveredEmptyAtlases' / (guid + '.asset')
        yaml = f"""%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!28 &2800000
Texture2D:
  m_ObjectHideFlags: 0
  m_Name: {json.dumps(name, ensure_ascii=False)}
  serializedVersion: 2
  m_Width: 0
  m_Height: 0
  m_CompleteImageSize: 0
  m_TextureFormat: {fmt}
  m_MipCount: {mips}
  m_IsReadable: {int(readable)}
  m_ImageCount: 1
  m_TextureDimension: 2
  m_TextureSettings:
    serializedVersion: 2
    m_FilterMode: {filt}
    m_Aniso: {aniso}
    m_MipBias: {bias}
    m_WrapU: {u}
    m_WrapV: {v}
    m_WrapW: {w}
  m_ColorSpace: {color}
  image data: 0
  _typelessdata:
  m_StreamData:
    offset: 0
    size: 0
    path:
"""
        write_owned(target, yaml.encode())
        write_owned(Path(str(target)+'.meta'), f'fileFormatVersion: 2\nguid: {guid}\nNativeFormatImporter:\n  mainObjectFileID: 2800000\n'.encode())
        for owner in [path, *font_paths[guid]]:
            raw = owner.read_bytes()
            original = f'fileID: 2800000, guid: {guid}, type: 3'.encode()
            native = original[:-1] + b'2'
            if original in raw:
                replace_file(owner, raw.replace(original, native))
        wanted.remove(guid)
        restored.append(target.relative_to(project).as_posix())
    return restored


def prepare(project, sources, pool):
    try:
        import UnityPy
    except ImportError as error:
        raise ValueError("Install the unity-visuals optional dependencies") from error
    if not (project/'Assets').is_dir() or not pool.is_dir():
        raise ValueError('Expected an existing Unity project and texture pool')
    files={}
    for path in sources['bundles']:
        for sf in UnityPy.load(Path(path).read_bytes()).assets:
            files[sf.name.lower()]=sf
    images=SourceImages(files,pool,project)
    native_objects={(o['cab'].lower(),int(o['pathId'])):o for o in sources.get('objects',[])}
    edits=[]
    selected_states=[]
    source_nodes = {}
    overlap_rules = sources.get('overlapRules', [])
    rules=sources.get('exclusiveViews',[])
    def visit(sf,go,path,asset):
        node=sf.objects[go].read_typetree()
        if overlap_rules:
            source_nodes[asset, path] = node['m_Name'], node['m_IsActive']
        transform=None
        for index,entry in enumerate(node['m_Component']):
            obj=sf.objects[entry['component']['m_PathID']]
            if obj.type.name in ('Transform','RectTransform'):
                transform=obj.read_typetree()
            if obj.type.name=='ParticleSystem':
                shape=obj.read_typetree().get('ShapeModule', {})
                key=pointer(sf,shape.get('m_Mesh'))
                exported=native_objects.get(key)
                if exported:
                    mesh=files[key[0]].objects[key[1]]
                    if mesh.type.name!='Mesh' or mesh.peek_name()!=exported['name']:
                        raise ValueError(f'Unexpected source mesh: {key}')
                    edits.append(dict(root=asset,path=path,node=node['m_Name'],index=index,component='ParticleSystem',
                                      field='ShapeModule.m_Mesh',kind='mesh',asset=exported['asset'],token=exported['name']))
            if obj.type.name!='MonoBehaviour':
                continue
            data=obj.read_typetree()
            for field in ('m_Sprite','m_Texture','m_Detail2D','m_FontData.m_Font'):
                ref=data.get('m_FontData',{}).get('m_Font') if field=='m_FontData.m_Font' else data.get(field)
                key=pointer(sf,ref)
                if key==('unity default resources',10102) and field=='m_FontData.m_Font':
                    source=dict(kind='builtinFont',asset='',token='10102')
                else:
                    source=images.image(key)
                if source:
                    script=pointer(sf,data['m_Script'])
                    cls=files[script[0]].objects[script[1]].read_typetree()['m_ClassName']
                    edits.append(dict(root=asset,path=path,node=node['m_Name'],index=index,component=cls,field=field,**source))
        children=[]
        for idx,child in enumerate(transform['m_Children']):
            obj=sf.objects[child['m_PathID']].read_typetree()
            child_path=path+'/'+str(idx)
            child_id=obj['m_GameObject']['m_PathID']
            if rules and 'm_AnchorMin' in obj:
                go_data=sf.objects[child_id].read_typetree()
                children.append(dict(node=go_data['m_Name'],active=go_data['m_IsActive'],rect=obj,path=child_path))
            visit(sf,child_id,child_path,asset)
        if rules:
            selected_states.extend(sibling_states(children,rules,asset))
    for row in sources['roots']:
        rel=row['asset']
        if not rel.startswith('Assets/') or '..' in Path(rel).parts or not (project/rel).is_file():
            raise ValueError(f'Invalid prefab path: {rel}')
        visit(files[row['cab'].lower()],int(row['pathId']),'0',rel)
    materials=defaultdict(list)
    addresses=defaultdict(list)
    for sf in files.values():
        for obj in sf.objects.values():
            if obj.type.name=='AssetBundle':
                for address,entry in obj.read_typetree()['m_Container']:
                    key=pointer(sf,entry['asset'])
                    if key:addresses[key].append(address.lower().removeprefix('assets/'))
        for obj in sf.objects.values():
            if obj.type.name=='Material':
                materials[obj.peek_name()].append(obj)
    slots=[]
    ambiguous=[]
    equivalent=[]
    exact_materials = sources.get('materialObjects', {})
    for path in sorted((project/'Assets').rglob('*.mat')):
        m=re.search(r'^  m_Name: (.*)',path.read_text(),re.M)
        if not m or not materials.get(m[1]):continue
        # A duplicate material name is acceptable only when every candidate
        # identifies the same source texture for the serialized slot.
        candidates=[]
        rel=path.relative_to(project).as_posix().lower()
        pool_materials=materials[m[1]]
        located=[o for o in pool_materials if any(rel.endswith('/'+a) for a in addresses[o.assets_file.name.lower(),o.path_id])]
        selected = located or pool_materials
        if exact := exact_materials.get(path.relative_to(project).as_posix()):
            keys = {(cab.lower(), int(pid)) for cab, pid in exact}
            selected = [o for o in pool_materials if (o.assets_file.name.lower(), o.path_id) in keys]
            if len(selected) != len(keys):
                raise ValueError(f'Source material identity mismatch: {path}')
        for obj in selected:
            envs=obj.read_typetree()['m_SavedProperties']['m_TexEnvs']
            candidates.append({slot:pointer(obj.assets_file,v['m_Texture']) for slot,v in envs})
        for slot in sorted(set().union(*candidates)):
            keys = {c.get(slot) for c in candidates}
            if keys == {None}:continue
            key = next(iter(keys))
            if len(keys) > 1:
                key = equivalent_texture_sources(keys, files)
                if key is None:
                    ambiguous.append([str(path.relative_to(project)),slot])
                    continue
                equivalent.append(dict(material=str(path.relative_to(project)),slot=slot,sources=sorted(keys)))
            source=images.image(key)
            if source:
                slots.append(dict(root=path.relative_to(project).as_posix(),field=slot,**source))
    plan=dict(equivalentTextureSources=equivalent,emptyFontAtlases=restore_empty_font_atlases(project,files),edits=edits,slots=slots,assets=images.assets,ambiguous=ambiguous,outsideSuppliedPool=images.outside_pool,
              roots=[r['asset'] for r in sources['roots']],layouts=sources.get('layouts',[]),outlineFallback=sources.get('outlineFallback',''))
    selected_states.extend(reviewed_overlap_states(sources.get('overlapFindings', []), overlap_rules, source_nodes))
    states = {(s['root'],s['path']):s for s in selected_states}
    for state in sources.get('states',[]):
        states[state['root'],state['path']] = state
    plan['states'] = list(states.values())
    install_editor_sources(project)
    replace_file(project/'visual-states.json',json.dumps({'states':plan['states']},ensure_ascii=False).encode())
    replace_file(project/'visual-repair.json',json.dumps(plan,ensure_ascii=False).encode())
    return plan

class SameHostOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def fetch_declared_textures(base, requests, pool):
    """Read only declared source tokens from the explicitly supplied HTTPS origin."""
    url = urllib.parse.urlsplit(base)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.fragment or url.query:
        raise ValueError('Expected a credential-free HTTPS base directory')
    pool.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(SameHostOnly())
    receipt = []
    for spec in requests:
        token = spec['token']
        decoded = urllib.parse.unquote(token)
        if not re.fullmatch(r'[\w.% ()+-]+\.[0-9a-fA-F]{8}', token) or '/' in decoded or chr(92) in decoded or '..' in decoded:
            raise ValueError(f'Invalid source texture token: {token!r}')
        size = int(spec['width']), int(spec['height'])
        if min(size) < 1 or max(size)>16384:
            raise ValueError(f'Invalid dimensions for {token}')
        target = pool/(token+'.txt')
        raw = target.read_bytes() if target.is_file() else None
        origin = None
        if raw is None:
            for dim in dict.fromkeys(size):
                for quoted in dict.fromkeys((urllib.parse.quote(token, safe=''),urllib.parse.quote(decoded, safe=''))):
                    origin = f'{base.rstrip("/")}/{dim}/{quoted}.txt'
                    try:
                        with opener.open(origin, timeout=20) as response:
                            raw = response.read(32*1024*1024 + 1)
                    except urllib.error.HTTPError as e:
                        if e.code == 404:
                            continue
                        raise
                    break
                if raw is not None:
                    break
        if raw is None:
            receipt.append({'token':token, 'status':'not_found'})
            continue
        if len(raw)>32*1024*1024 or open_texture(raw,'.astc').size != size:
            raise ValueError(f'Invalid ASTC payload for {token}')
        digest = hashlib.sha256(raw).hexdigest()
        if spec.get('sha256') and spec['sha256'] != digest:
            raise ValueError(f'Hash mismatch for {token}')
        write_owned(target,raw)
        receipt.append({'token':token, 'sha256':digest, 'origin':origin, 'status':'available'})
    return receipt


def add_arguments(parser):
    for name in ('project','sources','pool'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--fetch-base', help='Explicit HTTPS ASTC directory; fetch only manifest.textureRequests')


def run(args):
    sources=json.loads(args.sources.read_text())
    if args.fetch_base:
        receipt=fetch_declared_textures(args.fetch_base,sources['textureRequests'],args.pool)
        replace_file(args.project/'visual-fetch.json',json.dumps(receipt,indent=2).encode())
    plan=prepare(args.project,sources,args.pool)
    return dict(status='prepared',plan=str(args.project/'visual-repair.json'),
                images=len(plan['assets']),componentSlots=len(plan['edits']),materialSlots=len(plan['slots']),
                staticStates=len(plan['states']),layoutRepairs=len(plan['layouts']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    print(json.dumps(run(parser.parse_args()),ensure_ascii=False))


if __name__ == '__main__':
    main()
