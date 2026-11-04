"""Typed conversion-time IR; never a target runtime interpreter."""
import math
from pathlib import Path
from PIL import Image
from . import __version__
from .io import safe, inside, read, load, sha, encoded, new_output, finish, write_json, diagnostic, stage_document, stage_bytes
from .sources.compiled import fail, ParseError
from .assets.bitmap import normalize_font
from .assets.audio import AudioDecodeError, decode_m4a

MAX_PIXELS = 16_777_216
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def open_texture(raw, suffix):
    from io import BytesIO
    if suffix != '.astc':
        image = Image.open(BytesIO(raw))
        if image.format not in ('PNG','JPEG'):
            fail('UNSUPPORTED_IMAGE_ENCODING', '$', 'Only PNG/JPEG content is accepted')
        return image
    if len(raw) < 16 or raw[:4] != bytes.fromhex('13aba15c'):
        fail('INVALID_ASTC', '$.header', 'Invalid ASTC header')
    bx, by, bz = raw[4:7]
    w, h, depth = [int.from_bytes(raw[i:i+3], 'little') for i in (7,10,13)]
    valid = {(4,4),(5,4),(5,5),(6,5),(6,6),(8,5),(8,6),(8,8),(10,5),(10,6),(10,8),(10,10),(12,10),(12,12)}
    if (bx,by) not in valid or bz != 1 or depth != 1 or min(w,h) <= 0 or w*h > MAX_PIXELS:
        fail('INVALID_ASTC', '$.header', 'Unsupported ASTC dimensions or pixel budget')
    size = ((w+bx-1)//bx)*((h+by-1)//by)*16
    if len(raw) != size+16:
        fail('INVALID_ASTC', '$.payload', 'ASTC payload size mismatch')
    try:
        import texture2ddecoder
        from importlib.metadata import version
        if version('texture2ddecoder') != '1.0.6':
            fail('DEPENDENCY_VERSION', '$', 'Expected texture2ddecoder==1.0.6')
    except ImportError:
        fail('DEPENDENCY_MISSING', '$', 'Install project extra astc; no automatic install')
    decoded = texture2ddecoder.decode_astc(raw[16:],w,h,bx,by)
    if len(decoded) != w*h*4:
        fail('INVALID_ASTC', '$', 'Decoder returned incorrect byte count')
    return Image.frombytes('RGBA',(w,h),decoded,'raw','BGRA')


def numbers(value, count, location):
    if not isinstance(value, list) or len(value) != count or any(type(x) not in (int, float) or not math.isfinite(x) for x in value):
        fail('INVALID_GEOMETRY', location, 'Expected finite numeric vector')
    return value


def sprite(atlas, frame):
    x, y, w, h = numbers(frame.get('rect'), 4, '$.rect')
    ow, oh = numbers(frame.get('originalSize', [w, h]), 2, '$.originalSize')
    ox, oy = numbers(frame.get('offset', [0, 0]), 2, '$.offset')
    insets = numbers(frame.get('capInsets', [0, 0, 0, 0]), 4, '$.capInsets')
    rotated = frame.get('rotated', 0)
    if type(rotated) is not int or rotated not in (0, 1):
        fail('INVALID_ROTATION', '$.rotated', 'Expected 0 or 1')
    if any(v != int(v) for v in [x, y, w, h, ow, oh]) or min(w, h, ow, oh) <= 0 or min(x, y, *insets) < 0:
        fail('INVALID_GEOMETRY', '$.rect', 'Invalid pixel dimensions/insets')
    x, y, w, h, ow, oh = map(int, [x, y, w, h, ow, oh])
    if ow * oh > MAX_PIXELS or max(ow,oh)>16384:
        fail('PIXEL_BUDGET', '$.originalSize', 'Image exceeds pixel budget')
    if insets[0] + insets[2] > w or insets[1] + insets[3] > h:
        fail('INVALID_INSETS', '$.capInsets', 'Borders exceed trimmed frame')
    cw, ch = (h, w) if rotated else (w, h)
    if x + cw > atlas.width or y + ch > atlas.height:
        fail('ATLAS_BOUNDS', '$.rect', 'Frame outside atlas')
    trimmed = atlas.crop((x, y, x + cw, y + ch)).convert('RGBA')
    if rotated:
        trimmed = trimmed.transpose(Image.Transpose.ROTATE_90)
    # Cocos offset is center-relative, y up; PNG origin is top left.
    left, top = (ow - w) / 2 + ox, (oh - h) / 2 - oy
    if left != int(left) or top != int(top):
        fail('SUBPIXEL_TRIM', '$.offset', 'Cannot reconstruct fractional pixel placement losslessly')
    left, top = int(left), int(top)
    if left < 0 or top < 0 or left + w > ow or top + h > oh:
        fail('TRIM_BOUNDS', '$.offset', 'Trim rectangle exceeds original size')
    full = Image.new('RGBA', (ow, oh))
    full.paste(trimmed, (left, top))
    return trimmed, full, dict(rect=[x,y,w,h], rotated=bool(rotated), originalSize=[ow,oh],
                              offset=[ox,oy], trimOrigin=[left,top], capInsets=insets,
                              capInsetsOrder=['left','top','right','bottom'],
                              colorSpace='unknown', premultipliedAlpha='unknown')


def normalize(manifest_path, output, *, audio_provider=None):
    manifest_path = safe(manifest_path)
    m = stage_document(manifest_path)
    if m.get('sourceProfile') not in ('cocos-2.4.15-bundle','cocos-2.4.15-project','cocos-3.8.7-bundle','cocos-3.4.1-bundle','cocos-2.4.11-bundle','cocos-2.1.2-resource') or m.get('schemaVersion') != 1:
        fail('UNSUPPORTED_MANIFEST', '$', 'Expected inspect schema 1')
    roots = {name:safe(path) for name,path in m.get('sourceRoots',{m['bundle']:m['sourceRoot']}).items()}
    expected = {(i.get('bundle',m['bundle']),i['path']):i for i in m['inputs']}
    def checked(relative,bundle):
        if (bundle,relative) not in expected:
            fail('UNTRACKED_INPUT', relative, 'Source not in manifest')
        raw = read(inside(roots[bundle], relative))
        if sha(raw) != expected[(bundle,relative)]['sha256']:
            fail('SOURCE_CHANGED', relative, 'Source no longer matches inspect manifest')
        return raw
    for evidence in m.get('evidenceFiles',[]):
        if sha(read(evidence['path']))!=evidence['sha256']:
            fail('SOURCE_CHANGED',evidence['path'],'Source evidence no longer matches inspect manifest')
    for bundle,relative in expected:
        from .sources.containers import fingerprint
        if fingerprint(inside(roots[bundle],relative))!=expected[(bundle,relative)]['sha256']:
            fail('SOURCE_CHANGED',relative,'Source no longer matches inspect manifest')
    out = new_output(output, [*roots.values(),manifest_path.parent,*[safe(e['path']) for e in m.get('evidenceFiles',[])]])
    (out / 'assets').mkdir()
    diagnostics = list(m['diagnostics'])
    by_id = {a['sourceId']:a for a in m['assets']}
    aliases = {a['sourceId']:a['redirectTarget'] for a in m['assets'] if a.get('redirectTarget')}
    def resolved(key):
        seen=set()
        while key in aliases:
            if key in seen:
                fail('REDIRECT_CYCLE',key,'Bundle redirection cycle')
            seen.add(key);key=aliases[key]
        return key
    from .names import source_names
    result = dict(schemaVersion=1, toolVersion=__version__, sourceProfile=m['sourceProfile'],
                  sourceManifestSha256=sha(stage_bytes(manifest_path)),sourceManifestPath=str(manifest_path),sourceRoots=m.get('sourceRoots',{m['bundle']:m['sourceRoot']}),
                  sourceNames=source_names(m),sourceLocations={a['sourceId']:dict(bundle=a.get('bundle',m['bundle']),importPath=a.get('importPath'),nativePath=a.get('native')) for a in m['assets']}, evidenceFiles=m.get('evidenceFiles',[]),aliases=aliases, assets=[], spriteFrames=[], bitmapFonts=[],materials=[], nodes=[],
                  components=[], sourceValueObjects=[], quarantinedAssets=[],prefabInstances=[],prefabOverrideGaps=[],animationSchemaVersion=1,animationClips=[],diagnostics=diagnostics,
                  scopeMode='whole-input' if m.get('packageSelection') else 'asset-selection',
                  coordinateConvention=dict(origin='center anchor', x='right', y='up', units='pixels'))
    prefab_resolver=None
    if m['sourceProfile']in ('cocos-3.8.7-bundle','cocos-3.4.1-bundle'):
        from .sources.cocos38_prefabs import Resolver
        prefab_resolver=Resolver(m['assets'],m['sourceProfile'])
    for asset in m['assets']:
        sid = asset['sourceId']
        name = sha(sid.encode())[:24]
        doc = asset.get('document')
        if doc:
            objects = doc['instances']
            value = objects[doc['root']]
            kind = value.get('__type__', asset.get('kind'))
        else:
            objects, value, kind = [], {}, asset.get('kind')
        lengths={k:len(result[k]) for k in ('assets','spriteFrames','bitmapFonts','materials','nodes','components','sourceValueObjects','animationClips')}
        try:
            cocos38=m.get('sourceProfile')=='cocos-3.8.7-bundle'
            cocos34=m.get('sourceProfile')=='cocos-3.4.1-bundle'
            cocos3=cocos38 or cocos34
            if cocos34 and kind not in ('cc.SpriteFrame','cc.Texture2D','cc.ImageAsset','cc.TTFFont','cc.AudioClip','cc.JsonAsset','cc.Prefab','cc.Scene','cc.SceneAsset','cc.BitmapFont','redirect','native'):
                result['quarantinedAssets'].append(dict(sourceId=sid,kind=kind,reason='COCOS34_RESOURCE_PROFILE_ONLY'))
                diagnostics.append(diagnostic('COCOS34_RESOURCE_PROFILE_ONLY',asset.get('importPath',sid),'3.4.1 '+str(kind)+' semantics need a dedicated adapter; original retained',sid));continue
            if m.get('sourceProfile')=='cocos-2.1.2-resource' and kind not in ('cc.SpriteFrame','cc.Texture2D','cc.TTFFont','cc.AudioClip'):
                result['quarantinedAssets'].append(dict(sourceId=sid,kind=kind,reason='LEGACY_RESOURCE_ONLY'))
                diagnostics.append(diagnostic('LEGACY_RESOURCE_ONLY',asset.get('importPath',sid),'2.1.2 graph, clip and other semantics require a dedicated adapter',sid));continue
            if cocos3 and kind in ('cc.Prefab','cc.Scene','cc.SceneAsset'):
                from .sources.cocos38_graphs import resolved_graph
                if cocos34:
                    from .sources.cocos34_graphs import resolved_graph
                nodes38,components38,gaps38,resolved38=resolved_graph(asset,prefab_resolver)
                result['nodes'].extend(nodes38);result['components'].extend(components38)
                result['prefabInstances'].extend(resolved38['prefabInstances']);result['prefabOverrideGaps'].extend(resolved38['pendingPrefabOverrides'])
                diagnostics.extend(diagnostic('COCOS3_PREFAB_OVERRIDE_HANDOFF',asset.get('importPath',sid),g['kind']+': '+'.'.join(g.get('propertyPath')or[]),g['target'])for g in resolved38['pendingPrefabOverrides'])
                diagnostics.extend(diagnostic('COCOS3_SOURCE_SEMANTIC_HANDOFF',asset.get('importPath',sid),g['message'],g['sourceId'])for g in gaps38)
                continue
            if kind == 'cc.SpriteFrame':
                resource_evidence={}
                if cocos3:
                    from .sources.cocos38 import frame as frame38
                    if cocos34:
                        from .sources.cocos34 import frame as frame38
                    frame,source,resource_evidence=frame38(asset,by_id,resolved)
                    texture_key=resource_evidence['sourceTexture']
                else:
                    frame = value.get('data', {})
                    texture = frame.get('texture')
                    texture_key = texture.get('__uuid__') if isinstance(texture, dict) else texture
                    if texture_key is None and len(asset['references']) == 1:
                        texture_key = asset['references'][0]
                    source = by_id.get(resolved(asset.get('bundle',m['bundle'])+':'+str(texture_key)), {})
                path = source.get('native')
                try:
                    if not path:
                        fail('MISSING_TEXTURE', sid, 'No exact native texture binding: ' + str(texture_key))
                    if Path(path).suffix.lower() not in ('.png', '.jpg', '.jpeg', '.astc'):
                        fail('UNSUPPORTED_TEXTURE', path, 'Only PNG/JPEG decoders enabled; no ASTC fallback')
                    from io import BytesIO
                    with open_texture(checked(path,source.get('bundle',m['bundle'])), Path(path).suffix.lower()) as image:
                        if image.width * image.height > MAX_PIXELS:
                            fail('PIXEL_BUDGET', path, 'Atlas exceeds pixel budget')
                        trimmed, full, semantic = sprite(image, frame)
                    trimmed_path, full_path = f'assets/{name}.png', f'assets/{name}-original.png'
                    trimmed.save(out / trimmed_path)
                    full.save(out / full_path)
                    result['spriteFrames'].append(dict(sourceId=sid, textureRef=source['sourceId'],
                        image=trimmed_path, originalImage=full_path, **semantic,**(dict(sourceResourceEvidence=resource_evidence)if resource_evidence else {})))
                except (ParseError, OSError, Image.DecompressionBombError) as error:
                    diagnostics.append(diagnostic(getattr(error, 'code', 'IMAGE_ERROR'),
                        getattr(error, 'location', sid), str(error), sid))
            elif cocos3 and kind=='cc.Texture2D':
                diagnostics.append(diagnostic('COCOS3_SAMPLER_HANDOFF',sid,'Source sampler preserved in typed texture metadata; target sampler behavior is pending',sid))
            elif kind in ('cc.Texture2D', 'cc.ImageAsset', 'cc.TTFFont', 'cc.AudioClip', 'native'):
                path = asset.get('native')
                if path and kind not in ('cc.Texture2D','cc.ImageAsset'):
                    suffix = Path(path).suffix.lower()
                    if kind == 'cc.AudioClip' and suffix == '.m4a':
                        raw=checked(path,asset.get('bundle',m['bundle']))
                        try:
                            wav,audio_evidence=decode_m4a(raw,provider=audio_provider)
                        except AudioDecodeError as error:
                            issue=diagnostic(error.code,path,str(error),sid)
                            issue['severity']='error'
                            diagnostics.append(issue)
                            continue
                        target='assets/'+name+'.wav'
                        (out/target).write_bytes(wav)
                        result['assets'].append(dict(sourceId=sid,kind=kind,path=target,
                            audioDecode=dict(sourcePath=path,sourceBundle=asset.get('bundle',m['bundle']),
                                logicalPath=asset.get('logicalPath'),**audio_evidence)))
                    elif suffix in ('.ttf', '.mp3', '.wav', '.ogg', '.png', '.jpg', '.jpeg'):
                        target = 'assets/' + name + suffix
                        raw=checked(path,asset.get('bundle',m['bundle']))
                        metadata={}
                        if kind=='cc.TTFFont':
                            from .assets.ttf import coverage
                            try:metadata['fontCoverage']=coverage(raw)
                            except ParseError as error:
                                diagnostics.append(diagnostic(error.code,path,str(error),sid));continue
                        (out / target).write_bytes(raw)
                        result['assets'].append(dict(sourceId=sid, kind=kind, path=target,**metadata))
                    else:
                        diagnostics.append(diagnostic('UNSUPPORTED_NATIVE', path, suffix, sid))
                elif not path:
                    diagnostics.append(diagnostic('MISSING_NATIVE', sid, 'No native binding', sid))
            elif kind == 'cc.JsonAsset':
                if 'json' not in value:
                    diagnostics.append(diagnostic('UNSUPPORTED_JSON_ASSET',asset.get('importPath',sid),'Expected decoded JsonAsset.json property; no positional payload guessing',sid))
                else:
                    target='assets/'+name+'.json'
                    raw=encoded(value['json']);(out/target).write_bytes(raw)
                    result['assets'].append(dict(sourceId=sid,kind=kind,path=target,payloadSha256=sha(raw),
                                                  semanticRole='recovered-json-payload-unclassified'))
            elif kind == 'cc.Material':
                if value.get('_name')=='builtin-2d-sprite' and value.get('_techniqueData',{}).get('0',{}).get('defines',{})=={'USE_TEXTURE':True}:
                    result['materials'].append(dict(sourceId=sid,nativeRole='standard-ugui'))
                else:diagnostics.append(diagnostic('UNSUPPORTED_MATERIAL',asset.get('importPath',sid),'Custom effect/defines require material mapping',sid))
            elif kind == 'cc.AnimationClip':
                from .assets.animation import normalize_clip
                clip,gaps=normalize_clip(value,sid,str(asset.get('importPath'))+'#instances/'+str(doc['root']))
                result['animationClips'].append(clip);diagnostics.extend(gaps)
            elif kind == 'cc.BitmapFont':
                continue
            elif kind == 'redirect':
                continue
            elif kind in ('cc.Prefab', 'cc.SceneAsset'):
                node_start=len(result['nodes']);component_start=len(result['components'])
                try:
                    # Nodes/components remain conversion-time data; unknown fields reported downstream.
                    expanded = list(expand_nodes(objects,sid))
                    component_indices = {v.get('__id__') for _, n in expanded
                        if isinstance(n,dict) and n.get('__type__') in ('cc.Node','cc.Scene')
                        for v in n.get('_components',[]) if isinstance(v,dict) and type(v.get('__id__')) is int}
                    for index, obj in expanded:
                        typ = obj.get('__type__') if isinstance(obj, dict) else None
                        location = f"{asset.get('importPath')}#instances/{index}"
                        if typ in ('cc.Node','cc.Scene'):
                            obj = dict(obj)
                            refs = []
                            for ordinal, value in enumerate(obj.get('_components', [])):
                                if isinstance(value, dict) and '__type__' in value:
                                    inline_index = f'{index}/components/{ordinal}'
                                    inline_id = sid+'#'+inline_index
                                    component, component_gaps = component_ir(sid, inline_index, value, source_profile=m['sourceProfile'])
                                    result['components'].append(component)
                                    diagnostics.extend(diagnostic('UNSUPPORTED_COMPONENT_SEMANTIC',location+f'/_components/{ordinal}',g,inline_id) for g in component_gaps)
                                    refs.append({'__sourceId__':inline_id})
                                elif value is None:
                                    diagnostics.append(diagnostic('MISSING_COMPONENT',location+f'/_components/{ordinal}','Null serialized component',sid+'#'+str(index)))
                                else:
                                    refs.append(value)
                            obj['_components'] = refs
                            node, gaps = node_ir(sid, index, obj)
                            if typ=='cc.Scene': node['sourceType']='cc.Scene'
                            result['nodes'].append(node)
                            diagnostics.extend(diagnostic('UNSUPPORTED_NODE_FIELD', location, g, node['sourceId']) for g in gaps)
                        elif typ not in ('cc.Prefab', 'cc.PrefabInfo', 'cc.SceneAsset', None):
                            if index not in component_indices and 'node' not in obj:
                                # Referenced serializable values (e.g. ClickEvent)
                                # are not node components. Preserve their complete
                                # source payload and identity without inventing a node.
                                import copy
                                result['sourceValueObjects'].append(dict(sourceId=sid+'#'+str(index),
                                    type=typ, sourceData=copy.deepcopy(obj), native='not_run'))
                                continue
                            component, gaps = component_ir(sid, index, obj, source_profile=m['sourceProfile'])
                            result['components'].append(component)
                            diagnostics.extend(diagnostic('UNSUPPORTED_COMPONENT_SEMANTIC', location, g, component['sourceId']) for g in gaps)
                except (ParseError,KeyError,TypeError,ValueError,IndexError,AttributeError) as error:
                    del result['nodes'][node_start:];del result['components'][component_start:]
                    result['quarantinedAssets'].append(dict(sourceId=sid,kind=kind,reason=getattr(error,'code','UNSUPPORTED_OBJECT_GRAPH')))
                    diagnostics.append(diagnostic('UNSUPPORTED_OBJECT_GRAPH',asset.get('importPath',sid),str(error),sid))
            else:
                diagnostics.append(diagnostic('UNSUPPORTED_ASSET', asset.get('importPath', sid), str(kind), sid))
        except (ParseError,KeyError,TypeError,ValueError,IndexError,AttributeError,OSError) as error:
            for key,length in lengths.items():del result[key][length:]
            result['quarantinedAssets'].append(dict(sourceId=sid,kind=kind,reason=getattr(error,'code','UNSUPPORTED_ASSET_SEMANTIC')))
            diagnostics.append(diagnostic('UNSUPPORTED_ASSET_SEMANTIC',asset.get('importPath',sid),str(error),sid))
    frames={f['sourceId']:f for f in result['spriteFrames']}
    quarantined={a['sourceId']for a in result['quarantinedAssets']}
    for asset in m['assets']:
        if asset.get('kind')!='cc.BitmapFont':continue
        if asset['sourceId']in quarantined:continue
        if not asset.get('document'):continue  # Source-only profile already records the quarantined payload.
        value=asset['document']['instances'][asset['document']['root']]
        atlas_ref=resolved(ref(value.get('spriteFrame'),asset['sourceId']))
        frame=frames.get(atlas_ref)
        try:
            if m['sourceProfile']=='cocos-3.4.1-bundle':
                if 'fntConfig'in value and '_fntConfig'in value:fail('COCOS34_BITMAP_CONFIG',asset['sourceId'],'Conflicting serialized font config names')
                value=dict(value,_fntConfig=value.get('fntConfig'))
            if not frame:fail('BITMAP_ATLAS_MISSING',asset['sourceId'],str(atlas_ref))
            font=normalize_font(value,asset['sourceId'],atlas_ref,frame['originalSize'])
            if m['sourceProfile']=='cocos-3.4.1-bundle':font['kerningConvention']='source-3.4.1-unscaled-pair-offset'
            font['atlasImage']=frame['originalImage']
            result['bitmapFonts'].append(font)
        except (ParseError,KeyError,ValueError) as error:
            diagnostics.append(diagnostic(getattr(error,'code','INVALID_BITMAP_FONT'),asset.get('importPath',''),str(error),asset['sourceId']))
    quarantine_graphs(result)
    from .prefab_completeness import audit, SUPPORTED
    if m['sourceProfile'] in SUPPORTED:
        selected = [a['sourceId'] for a in m['assets']
                    if a.get('kind') in ('cc.Prefab', 'cc.SceneAsset')]
        ledger = audit(m, result, selected)
        write_json(out / 'prefab-completeness.json', ledger)
        result['prefabCompleteness'] = dict(
            report='prefab-completeness.json',
            **{key: ledger[key] for key in ('status', 'sourceNodes', 'sourceComponents',
                                          'mapped', 'unmapped', 'unknown')},
            fieldSemantics='unverified', native='not_run', runtime='not_run',
            visual='not_run', complete=False)
    if m['sourceProfile'] in SUPPORTED:
        from .prefab_static_pipeline import attach_static_fields
        write_json(out / 'prefab-static-fields.json', attach_static_fields(m, result))
    write_json(out / 'ir.json', result)
    return finish(out, result)


def expand_nodes(objects,namespace):
    """Flatten explicitly typed inline child nodes, as already done for inline components."""
    pending=list(enumerate(objects));position=0
    while position<len(pending):
        index,obj=pending[position];position+=1
        if isinstance(obj,dict) and obj.get('__type__') in ('cc.Node','cc.Scene'):
            obj=dict(obj);children=[]
            for ordinal,child in enumerate(obj.get('_children',[])):
                if isinstance(child,dict) and child.get('__type__')=='cc.Node':
                    child_index=f'{index}/_children/{ordinal}';child=dict(child)
                    if '_parent' not in child:child['_parent']={'__sourceId__':namespace+'#'+str(index)}
                    pending.append((child_index,child));children.append({'__sourceId__':namespace+'#'+child_index})
                else:children.append(child)
            obj['_children']=children
        yield index,obj


def quarantine_graphs(ir):
    """Unsupported/inconsistent source graphs do not poison independently valid views."""
    groups={}
    for node in ir['nodes']:groups.setdefault(node['sourceId'].split('#')[0],[]).append(node)
    bad={}
    for source,nodes in groups.items():
        by_id={n['sourceId']:n for n in nodes}
        for n in nodes:
            if n['parent'] is not None and n['parent'] not in by_id:
                bad[source]='parent outside decoded source graph';break
            if len(n['children'])!=len(set(n['children'])) or any(c not in by_id or by_id[c]['parent']!=n['sourceId'] for c in n['children']):
                bad[source]='child/parent inconsistency or absent child';break
            if n['parent'] and n['sourceId'] not in by_id[n['parent']]['children']:
                bad[source]='parent does not list child';break
            seen=set();cursor=n['sourceId']
            while cursor is not None:
                if cursor in seen:
                    bad[source]='source parent cycle';break
                seen.add(cursor)
                cursor=by_id.get(cursor,{}).get('parent')
    if bad:
        ir['nodes']=[n for n in ir['nodes'] if n['sourceId'].split('#')[0] not in bad]
        ir['components']=[c for c in ir['components'] if c['sourceId'].split('#')[0] not in bad]
        ir['prefabInstances']=[x for x in ir.get('prefabInstances',[])if x['root'].split('#')[0]not in bad]
        for source,reason in sorted(bad.items()):
            ir.setdefault('quarantinedAssets',[]).append(dict(sourceId=source,reason='INVALID_NODE_GRAPH',detail=reason))
            ir['diagnostics'].append(diagnostic('UNSUPPORTED_NODE_GRAPH',source,reason+'; original decoded object retained',source))
    return bad


def ref(value, namespace):
    if value is None:
        return None
    if isinstance(value, dict) and isinstance(value.get('__sourceId__'),str):
        return value['__sourceId__']
    if isinstance(value, dict) and type(value.get('__id__')) is int:
        return namespace + '#' + str(value['__id__'])
    if isinstance(value, dict) and isinstance(value.get('__uuid__'), str):
        return namespace.split(':', 1)[0] + ':' + value['__uuid__']
    fail('INVALID_REFERENCE', namespace, 'Expected typed object/resource reference')


def vector(value, keys, default):
    if value is None:
        return default
    if isinstance(value, dict) and '__value_type__' in value:
        values = value['values']
        if len(keys) == 4 and len(values) == 1 and type(values[0]) is int:
            packed = values[0]
            return [(packed >> shift) & 255 for shift in (0,8,16,24)]
        return numbers(values, len(keys), '$.value_type')
    if isinstance(value, dict):
        return numbers([value.get(k, d) for k,d in zip(keys,default)], len(keys), '$.vector')
    fail('INVALID_VECTOR', '$', 'Unknown vector encoding')


def node_ir(namespace, index, obj):
    gaps = []
    t = obj.get('_trs', {})
    values = t.get('array', t.get('values', [])) if isinstance(t, dict) else t if isinstance(t, list) else []
    if values:
        if len(values) == 1 and isinstance(values[0], list):
            values = values[0]
        numbers(values, 10, '$._trs')
        position, rotation, scale = values[:3], values[3:7], values[7:10]
    else:
        position, rotation, scale = [0,0,0], [0,0,0,1], [1,1,1]
        if '_trs' in obj: gaps.append('unrecognized transform encoding; identity requires review')
    if obj.get('_skewX', 0) or obj.get('_skewY', 0):
        gaps.append('skew unsupported')
    size = vector(obj.get('_contentSize'), ['width','height'], [0,0])
    anchor = vector(obj.get('_anchorPoint'), ['x','y'], [.5,.5])
    color = vector(obj.get('_color'), ['r','g','b','a'], [255]*4)
    known = {'__type__','_name','_objFlags','_parent','_children','_active','_components','_prefab','_opacity',
             '_color','_contentSize','_anchorPoint','_trs','_eulerAngles','_skewX','_skewY','_groupIndex','groupIndex','_id','_zIndex'}
    gaps.extend('unknown node field: ' + key for key in obj if key not in known)
    return dict(sourceId=namespace+'#'+str(index), name=obj.get('_name','Node'),
                parent=ref(obj.get('_parent'),namespace), children=[ref(v,namespace) for v in obj.get('_children',[])],
                position=position, rotation=rotation, scale=scale,
                size=size, anchor=anchor,
                active=obj.get('_active',True), color=color,
                opacity=obj.get('_opacity',255), components=[ref(v,namespace) for v in obj.get('_components',[])]), gaps


def component_ir(namespace, index, obj, *, source_profile=None):
    typ = obj.get('__type__')
    base = dict(sourceId=namespace+'#'+str(index), type=typ, node=ref(obj.get('node'),namespace), enabled=obj.get('_enabled',True),materials=[ref(v,namespace) for v in obj.get('_materials',[]) if v])
    gaps = []
    if typ == 'cc.Sprite':
        base.update(spriteFrame=ref(obj.get('_spriteFrame'),namespace), mode=obj.get('_type',0),
                    sizeMode=obj.get('_sizeMode',0), trim=obj.get('_isTrimmedMode',True))
        if base['mode'] not in (0,1,2): gaps.append('sprite mode '+str(base['mode']))
        known = {'_materials','_spriteFrame','_type','_sizeMode','_isTrimmedMode','_fillType','_fillCenter','_fillStart','_fillRange','_atlas'}
    elif typ == 'cc.Label':
        family_values = [obj[key] for key in ('fontFamily', '_fontFamily', '_N$fontFamily') if key in obj]
        if any(not isinstance(value, str) or not value.strip() for value in family_values):
            fail('LABEL_FONT_FAMILY_INVALID', base['sourceId'], 'Expected a nonempty system font family')
        if len(set(family_values)) > 1:
            fail('LABEL_FONT_FAMILY_ALIAS_CONFLICT', base['sourceId'], 'Conflicting font family aliases')
        base['fontFamily'] = family_values[0] if family_values else 'Arial'
        base['fontFamilyEvidence'] = 'serialized' if family_values else 'creator-label-default-Arial'
        if '_overflow' in obj and '_N$overflow' in obj and obj['_overflow'] != obj['_N$overflow']:
            fail('LABEL_OVERFLOW_ALIAS_CONFLICT',base['sourceId'],'Conflicting serialized Label overflow aliases')
        base.update(text=obj.get('_string',obj.get('_N$string','')),font=ref(obj.get('_N$file'),namespace),
                    fontSize=obj.get('_fontSize',40),lineHeight=obj.get('_lineHeight',40),
                    horizontalAlign=obj.get('_N$horizontalAlign',obj.get('_horizontalAlign',0)),verticalAlign=obj.get('_N$verticalAlign',obj.get('_verticalAlign',0)),
                    bold=bool(obj.get('_styleFlags',0)&1),italic=bool(obj.get('_styleFlags',0)&2),underline=bool(obj.get('_styleFlags',0)&4),
                    spacing=obj.get('_spacingX',0),systemFont=obj.get('_isSystemFontUsed',True),
                    overflow=obj.get('_overflow',obj.get('_N$overflow',0)),wrap=obj.get('_enableWrapText',True))
        known = {'fontFamily','_string','_N$string','_N$file','_fontSize','_lineHeight','_horizontalAlign','_verticalAlign',
                 '_N$horizontalAlign','_N$verticalAlign','_materials','_overflow','_N$overflow','_enableWrapText','_isSystemFontUsed','_fontFamily','_N$fontFamily','_cacheMode','_styleFlags','_spacingX'}
        if not base['font']: gaps.append('system font requires source-backed explicit matching font binding')
        if base['overflow'] not in (0,1,2,3): gaps.append('unknown label overflow mode')
    elif typ == 'cc.Widget':
        base.update(flags=obj.get('_alignFlags',0),target=ref(obj.get('_target'),namespace),
                    margins=[obj.get(k,0) for k in ('_left','_bottom','_right','_top')],
                    absolute=[obj.get(k,True) for k in ('_isAbsLeft','_isAbsBottom','_isAbsRight','_isAbsTop')],alignMode=obj.get('alignMode',1),
                    center=[obj.get('_horizontalCenter',0),obj.get('_verticalCenter',0)],centerAbsolute=[obj.get('_isAbsHorizontalCenter',True),obj.get('_isAbsVerticalCenter',True)])
        known={'_alignFlags','_target','_left','_bottom','_right','_top','_isAbsLeft','_isAbsBottom','_isAbsRight','_isAbsTop','_originalWidth','_originalHeight','alignMode','_horizontalCenter','_verticalCenter','_isAbsHorizontalCenter','_isAbsVerticalCenter'}
    elif typ == 'cc.Mask':
        base.update(maskType=obj.get('_type',obj.get('_N$type',0)),inverted=obj.get('_inverted',obj.get('_N$inverted',False)))
        known={'_type','_N$type','_inverted','_N$inverted','_alphaThreshold','_N$alphaThreshold','_spriteFrame','_materials','_segments'}
    elif typ == 'cc.ScrollView':
        base.update(content=ref(obj.get('_N$content'),namespace),horizontal=obj.get('horizontal',True),vertical=obj.get('vertical',True))
        known={'_N$content','horizontal','vertical','_N$horizontalScrollBar','_N$verticalScrollBar','bounceDuration','brake','elastic','inertia','scrollEvents','cancelInnerEvents'}
        if obj.get('scrollEvents'):gaps.append('scroll events need business binding')
    elif typ == 'cc.ProgressBar':
        # Exact 2.4.15 engine declarations define omitted serialized values.
        # Other versions and direct unversioned callers retain unknowns.
        base.update(barSprite=ref(obj.get('_N$barSprite'),namespace),
                    progress=obj.get('_N$progress'),totalLength=obj.get('_N$totalLength'),
                    progressMode=obj.get('_N$mode'),progressReverse=obj.get('_N$reverse'))
        known={'_N$barSprite','_N$progress','_N$totalLength','_N$mode','_N$reverse','_materials'}
        if source_profile in ('cocos-2.4.15-bundle','cocos-2.4.15-project'):
            defaults={}
            for source_key,field,value in [('_N$progress','progress',1),('_N$totalLength','totalLength',1),
                                          ('_N$mode','progressMode',0),('_N$reverse','progressReverse',False)]:
                if source_key not in obj:
                    base[field]=value;defaults[field]=dict(sourceField=source_key,value=value)
            if defaults:base['engineDefaults']=dict(version='2.4.15',fields=defaults,
                source='https://github.com/cocos/cocos-engine/blob/v2.4.15/cocos2d/core/components/CCProgressBar.js')
        if base['barSprite'] is None or base['progress'] is None or base['totalLength'] is None:
            gaps.append('progress needs explicit source bar, progress and total length')
    elif typ == 'cc.Layout':
        if '_N$cellSize'in obj and '_cellSize'in obj and vector(obj['_N$cellSize'],['width','height'],[40,40])!=vector(obj['_cellSize'],['width','height'],[40,40]):
            fail('CONFLICTING_LAYOUT_CELL_SIZE',str(index),'Source cell-size aliases disagree')
        base.update(layoutType=obj.get('_N$layoutType',0),resize=obj.get('_resize',0),
                    spacingXY=[obj.get('_N$spacingX',0),obj.get('_N$spacingY',0)],
                    padding=[obj.get('_N$paddingLeft',0),obj.get('_N$paddingBottom',0),obj.get('_N$paddingRight',0),obj.get('_N$paddingTop',0)],
                    horizontalDirection=obj.get('_N$horizontalDirection',0),verticalDirection=obj.get('_N$verticalDirection',1),
                    startAxis=obj.get('_N$startAxis',0),cellSizeFromSource=('_N$cellSize'in obj or '_cellSize'in obj),cellSize=vector(obj.get('_N$cellSize',obj.get('_cellSize')),['width','height'],[40,40]),
                    affectedByScale=obj.get('_affectedByScale',False),alignCross=obj.get('_isAlign',False),constraint=obj.get('_constraint',0),constraintCount=obj.get('_constraintNum',2))
        known={'_N$layoutType','_resize','_N$spacingX','_N$spacingY','_N$paddingLeft','_N$paddingRight','_N$paddingTop','_N$paddingBottom','_N$horizontalDirection','_N$verticalDirection','_N$startAxis','_N$cellSize','_cellSize','_layoutSize','_affectedByScale','_isAlign','_constraint','_constraintNum'}
    elif typ == 'cc.Button':
        events=[]
        for ordinal,event in enumerate(obj.get('clickEvents',[]) or []):
            if not isinstance(event,dict) or '__id__' in event:
                events.append(dict(status='unresolved_source_event',sourceIndex=ordinal,
                                   eventReference=ref(event,namespace) if isinstance(event,dict) else None))
                gaps.append('click event requires source reference/null handling');continue
            events.append(dict(target=ref(event.get('target'),namespace),component=event.get('_componentId'),
                               handler=event.get('handler'),customData=event.get('customEventData','')))
        base.update(target=ref(obj.get('_N$target'),namespace),transition=obj.get('_N$transition',0),
                    zoomScale=obj.get('zoomScale',1.2),duration=obj.get('duration',.1),interactable=obj.get('interactable',True),
                    events=events)
        known={'_N$target','_N$transition','zoomScale','duration','interactable','clickEvents','_N$normalColor','_N$pressedColor','_N$hoverColor','_N$disabledColor','_N$normalSprite','_N$pressedSprite','_N$hoverSprite','_N$disabledSprite','_normalMaterial','_pressedMaterial','_hoverMaterial','_disabledMaterial','_N$autoGrayEffect','_N$enableAutoGrayEffect'}
    elif typ == 'cc.Animation':
        base.update(clips=[ref(c,namespace) for c in obj.get('_clips',[]) if c is not None],
                    defaultClip=ref(obj.get('_defaultClip'),namespace),playOnLoad=obj.get('playOnLoad',False))
        known={'_clips','_defaultClip','playOnLoad'}
    elif typ == 'cc.BlockInputEvents':
        known = set()
    elif typ == 'cc.LabelOutline':
        base.update(width=obj.get('_width',1),outlineColor=vector(obj.get('_color'),['r','g','b','a'],[255]*4))
        known={'_width','_color'}
    else:
        base['supported'] = False
        gaps.append('component '+str(typ)+' requires adapter or AI implementation')
        known = set()
    ignored = {'__type__','_name','_objFlags','node','_enabled','_id'}
    gaps.extend('unknown component field: '+key for key in obj if key not in known|ignored)
    return base, gaps
