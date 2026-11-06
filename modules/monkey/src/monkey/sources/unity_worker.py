"""Isolated fixed UnityPy provider protocol; never resolves/executes source scripts."""
import base64
import hashlib
import json
import math
import re
import sys
import time
from collections import Counter
from pathlib import Path

# -I worker imports only its installed tool code, never source-side Python.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from monkey.unity_semantics import validate_component
from monkey.unity_parse_limits import parse_limits as resolve_limits,reader_fingerprint
from monkey.unity_payloads import StreamedArray,PayloadWriter,read_streamed,write_document

PROVIDER_VERSION = '1.25.3'
MAX_BYTES = 128 * 1024 * 1024
MAX_OBJECTS = 250_000
MAX_VALUES = 250_000
MAX_TYPED_VALUES = 8_000_000


def runtime_stats(start):
    try:
        import resource
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform!='darwin':peak*=1024
    except ImportError:peak=None
    return dict(elapsedSeconds=round(time.monotonic()-start,3),peakRssBytes=peak,peakScope='worker-lifetime')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def identifier(value):
    if type(value) is not int or not -(1 << 63) <= value < (1 << 63):
        raise ValueError('Expected signed 64-bit Unity identifier')
    return str(value)


def portable(value, refs, location='$', depth=0, counter=None, max_values=None):
    """PPtr fields are typed strings; arbitrary large integers are lossless tagged values."""
    if counter is None:
        counter = [0]
    counter[0] += 1
    if counter[0] > (MAX_VALUES if max_values is None else max_values) or depth > 96:
        raise ValueError('Typed value budget exceeded')
    if isinstance(value, StreamedArray):return value.descriptor
    if isinstance(value, dict):
        if set(value) == {'m_FileID', 'm_PathID'}:
            file_id, path_id = identifier(value['m_FileID']), identifier(value['m_PathID'])
            refs.append(dict(location=location, fileId=file_id, pathId=path_id))
            return {'$type': 'UnityPPtr', 'fileId': file_id, 'pathId': path_id}
        return {str(k): portable(v, refs, location + '/' + str(k), depth+1, counter, max_values) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [portable(v, refs, location + '/' + str(i), depth+1, counter, max_values) for i, v in enumerate(value)]
    if isinstance(value, bytes):
        return {'$type': 'bytes', 'base64': base64.b64encode(value).decode(), 'sha256': digest(value), 'bytes': len(value)}
    if isinstance(value, str):
        try:
            value.encode('utf-8')
            return value
        except UnicodeEncodeError:
            # UnityPy uses surrogateescape for arbitrary binary TextAsset bodies.
            return portable(value.encode('utf-8', errors='surrogateescape'), refs, location, depth+1, counter, max_values)
    if type(value) is int:
        return {'$type': 'integer', 'decimal': str(value)} if abs(value) > (1 << 53)-1 else value
    if isinstance(value, float) and not math.isfinite(value):
        return {'$type': 'nonfinite', 'value': repr(value)}
    if value is None or isinstance(value, (bool, float)):
        return value
    raise ValueError('Unsupported typed value ' + type(value).__name__)


def texture_payload(typed):
    payload=typed.get('image data')
    if not isinstance(payload,bytes) or not payload:
        return dict(kind='empty-or-streamed',resourceResolution='not_evaluated')
    if len(payload)<256 and payload[0]==len(payload)-1:
        try:key=payload[1:].decode('ascii')
        except UnicodeDecodeError:key=''
        match=re.fullmatch(r'([^/\\\x00]{1,240}\.[0-9a-f]{8})(?:_([0-9]+)###)?',key)
        if match:
            return dict(kind='external-key-token-candidate',key=match[1],wireKey=key,
                        blockSizeHint=int(match[2]) if match[2] else None,bytes=len(payload),sha256=digest(payload),
                        resourceResolution='required',nativePixelsVerified=False)
    # ETC1 requires at least one 8-byte block, even for a 1x1 texture.
    # Missing mip levels are not inferred, and streamed/token payloads were
    # handled above. This identifies invalid bytes without decoding pixels.
    width,height=typed.get('m_Width'),typed.get('m_Height')
    stream=typed.get('m_StreamData',{})
    if typed.get('m_TextureFormat')==34 and type(width)is int and type(height)is int and width>0 and height>0 and isinstance(stream,dict) and not stream.get('size') and not stream.get('path'):
        minimum=((width+3)//4)*((height+3)//4)*8
        if len(payload)<minimum:
            return dict(kind='invalid-inline-etc1',bytes=len(payload),sha256=digest(payload),minimumBaseLevelBytes=minimum,nativePixelsVerified=False,resourceResolution='source-payload-missing')
    return dict(kind='inline-payload',bytes=len(payload),sha256=digest(payload),nativePixelsVerified=False)


def schema_node(node,depth=0):
    if depth>64:raise ValueError('Embedded schema depth budget')
    result = dict(name=node.m_Name,type=node.m_Type,children=[schema_node(n,depth+1) for n in node.m_Children])
    for source, target in [('m_MetaFlag','metaFlag'),('m_Version','version'),('m_ByteSize','byteSize')]:
        if hasattr(node, source): result[target] = getattr(node, source)
    return result


def type_identity(asset, serialized_type):
    if serialized_type is None or serialized_type.class_id != 114:
        return None
    script_id, old_hash = serialized_type.script_id, serialized_type.old_type_hash
    if len(script_id) != 16 or len(old_hash) != 16 or not any(script_id) or not any(old_hash):
        return None
    return (asset.unity_version, str(asset.target_platform), script_id.hex(), old_hash.hex())


def full_schema(node):
    # Include layout/alignment/version flags, not just field names and types.
    return [{k:v for k,v in n.items() if k != 'm_Children'} for n in node.to_dict_list()]


def component_prefix(obj):
    """Keep independently decoded native PPtrs when a component body is unknown."""
    head=obj.parse_monobehaviour_head();refs=[];values={}
    for name in ('m_GameObject','m_Script'):
        ptr=getattr(head,name)
        values[name]=portable(dict(m_FileID=ptr.m_FileID,m_PathID=ptr.m_PathID),refs,'$/'+name)
    return dict(status='prefix-only',body='unparsed',fields=values),refs


def schema_pool(assets, job, all_schemas=False):
    import UnityPy
    wanted = {type_identity(a, o.serialized_type) for a in assets for o in a.objects.values()
              if o.type.name == 'MonoBehaviour' and not (o.serialized_type and o.serialized_type.node)} - {None}
    matches, total = {}, 0
    for row in job['files']:
        source = Path(row['path'])
        with source.open('rb') as stream: raw = stream.read(MAX_BYTES+1)
        total += len(raw)
        if len(raw) != row['bytes'] or len(raw) > MAX_BYTES or digest(raw) != row['sha256'] or total > 1024*1024*1024:
            raise ValueError('Frozen schema pool identity or budget changed')
        env = UnityPy.load(raw)
        for asset in env.assets:
            for typ in asset.types:
                key = type_identity(asset, typ)
                if key is None or (not all_schemas and key not in wanted) or typ.node is None: continue
                encoded = json.dumps(full_schema(typ.node), sort_keys=True, separators=(',',':')).encode()
                schema_hash = digest(encoded)
                if key in matches and matches[key]['sha256'] != schema_hash:
                    raise ValueError('Ambiguous exact-identity TypeTree in frozen pool')
                record = matches.setdefault(key, dict(node=typ.node, sha256=schema_hash, sources=[]))
                provenance = dict(bundleSha256=digest(raw), file=asset.name)
                if provenance not in record['sources']: record['sources'].append(provenance)
        with source.open('rb') as stream: after = stream.read(MAX_BYTES+1)
        if digest(after) != row['sha256']: raise ValueError('Schema source changed while reading')
    return matches


def inspect_bytes(raw, schema_job=None, schema_cache=None, parse_limits=None, payload_root=None):
    import UnityPy
    if UnityPy.__version__ != PROVIDER_VERSION:
        raise RuntimeError('Expected UnityPy ' + PROVIDER_VERSION)
    limits=resolve_limits(parse_limits or dict(objectValues=MAX_VALUES,containerValues=MAX_TYPED_VALUES))
    writer=PayloadWriter(payload_root,digest(raw)) if payload_root else None
    env = UnityPy.load(raw)  # bytes only: no source-side sibling or cache discovery
    assets = env.assets
    if not assets:
        raise ValueError('No serialized files found')
    if sum(len(f.objects) for f in assets) > MAX_OBJECTS:
        raise ValueError('Object budget exceeded')
    borrowed = schema_cache if schema_cache is not None else (schema_pool(assets, schema_job) if schema_job else {})
    files, objects, schemas, borrowed_schemas = [], [], {}, {};typed_values=0
    for index, asset in enumerate(assets):
        file_id = str(index)
        externals = [dict(fileId=str(i+1), path=e.path, guid=e.guid.hex()) for i, e in enumerate(asset.externals)]
        files.append(dict(id=file_id, name=asset.name, unityVersion=asset.unity_version,
                          targetPlatform=str(asset.target_platform), sourceTypeTreeEnabled=asset._enable_type_tree, externals=externals, objects=len(asset.objects)))
        if hasattr(asset, 'reader'):
            files[-1]['serializedFileSha256'] = digest(bytes(asset.reader.bytes))
        for obj in asset.objects.values():
            row = dict(file=file_id, pathId=identifier(obj.path_id), classId=int(obj.type), type=obj.type.name,
                       bytes=obj.byte_size, rawSha256=digest(obj.get_raw_data()), references=[],
                       typeTreeSource='embedded' if asset._enable_type_tree and obj.serialized_type and obj.serialized_type.node else 'provider-version-schema')
            if obj.type.name=='MonoBehaviour' and asset._enable_type_tree and obj.serialized_type and obj.serialized_type.node:
                shape=schema_node(obj.serialized_type.node)
                shape_id=digest(json.dumps(shape,sort_keys=True,separators=(',',':')).encode())
                schemas[shape_id]=shape;row['embeddedSchemaId']=shape_id
            exact = borrowed.get(type_identity(asset, obj.serialized_type)) if obj.type.name == 'MonoBehaviour' and not (obj.serialized_type and obj.serialized_type.node) else None
            if exact:
                shape = schema_node(exact['node'])
                shape_id = digest(json.dumps(shape,sort_keys=True,separators=(',',':')).encode())
                borrowed_schemas[shape_id] = shape
                row.update(typeTreeSource='exact-frozen-bundle', borrowedSchemaId=shape_id,
                    schemaProvenance=dict(identity=list(type_identity(asset,obj.serialized_type)), layoutSha256=exact['sha256'],
                        sourceManifestSha256=schema_job['sourceManifestSha256'], sources=exact['sources']))
            counter=[0];mark=len(writer.files) if writer else 0;blocks=[]
            row['parseMetrics']=dict(containerValuesBefore=typed_values)
            try:
                streamed=read_streamed(obj,writer,file_id)
                if streamed is not None:typed,blocks=streamed
                else:typed = obj.read_typetree(nodes=exact['node'], check_read=True) if exact else obj.read_typetree(check_read=True)
                if obj.type.name == 'MonoBehaviour':
                    node = exact['node'] if exact else (obj.serialized_type.node if obj.serialized_type else None)
                    if node is None:
                        raise ValueError('No proven MonoBehaviour schema for semantic validation')
                    head = obj.parse_monobehaviour_head()
                    header = {name: {'m_FileID': getattr(head, name).m_FileID,
                                     'm_PathID': getattr(head, name).m_PathID}
                              for name in ('m_Script', 'm_GameObject')}
                    validate_component(schema_node(node), typed, header)
                    row['semanticValidation'] = dict(status='passed', header='independent-native-prefix',
                                                      fields='schema-shape', fieldValues='not-cross-checked', writable=False)
                converted=portable(typed,row['references'],counter=counter,max_values=limits['objectValues'])
                typed_values+=counter[0]
                if typed_values>limits['containerValues']:
                    typed_values-=counter[0]
                    raise ValueError('Aggregate portable value budget exceeded; original object hash retained')
                row['data']=converted
                if blocks:row['payloads']=blocks
                if obj.type.name=='Texture2D' and isinstance(typed,dict):row['texturePayload']=texture_payload(typed)
                name = typed.get('m_Name') if isinstance(typed,dict) else None
                row['name'] = name if isinstance(name,str) and not any(0xd800 <= ord(c) <= 0xdfff for c in name) else None
                row['status'] = 'parsed'
            except Exception as error:
                # No relaxed read, zero-fill, guessed schema or source assembly execution.
                if writer:writer.rollback(mark)
                row['status'] = 'unparsed'
                row.pop('payloads',None)
                row.pop('data', None)
                row.pop('semanticValidation', None)
                row['references'] = []
                row['error'] = dict(type=type(error).__name__, message=str(error).splitlines()[0][:240])
                if obj.type.name=='MonoBehaviour':
                    try:
                        prefix,refs=component_prefix(obj)
                        row['nativePrefix']=prefix;row['references']=refs
                        row['referenceCoverage']='native-prefix-only;unknown-body-references-not-enumerated'
                        row['error']['code']='MONOBEHAVIOUR_BODY_UNPARSED'
                        if not exact and not (obj.serialized_type and obj.serialized_type.node):
                            row['error']['code']='MISSING_EXACT_MONOBEHAVIOUR_SCHEMA'
                            row['requiredSchemaIdentity']=type_identity(asset,obj.serialized_type)
                    except Exception as prefix_error:
                        row['nativePrefix']=dict(status='unreadable',error=str(prefix_error)[:240])
            row['parseMetrics'].update(inlineValues=counter[0],streamedValues=sum(b['length']for b in blocks)if row['status']=='parsed'else 0)
            objects.append(row)
    return dict(schemaVersion=1, sourceFamily='unity', provider=dict(name='UnityPy',version=PROVIDER_VERSION),
                parseLimits=limits,parseUsage=dict(inlineValues=typed_values,payloadBytes=writer.total if writer else 0,payloadChunks=len(writer.files)if writer else 0),
                payloadFiles=writer.files if writer else [],identifierEncoding='signed-int64-decimal-string-v1', files=files, objects=objects, embeddedSchemas=schemas, borrowedSchemas=borrowed_schemas,
                summary=dict(serializedFiles=len(files), objects=len(objects),
                             parsed=sum(o['status']=='parsed' for o in objects),
                             unparsed=sum(o['status']=='unparsed' for o in objects), borrowedSchemaParsed=sum(o['status']=='parsed' and o['typeTreeSource']=='exact-frozen-bundle' for o in objects), externalTextureTokens=sum(o.get('texturePayload',{}).get('kind')=='external-key-token-candidate' for o in objects), invalidInlineTextures=sum(o.get('texturePayload',{}).get('kind')=='invalid-inline-etc1' for o in objects), types=dict(Counter(o['type'] for o in objects))),
                sourceCodeExecuted=False, externalFilesResolved=False, nativeExport='not_run')


def astc_header(raw,width,height,hint=None):
    if len(raw)<16 or raw[:4]!=b'\x13\xab\xa1\x5c':raise ValueError('Exact cached payload is not ASTC')
    bx,by,bz=raw[4:7];w=int.from_bytes(raw[7:10],'little');h=int.from_bytes(raw[10:13],'little');d=int.from_bytes(raw[13:16],'little')
    if bx!=by or bx not in (4,5,6,8,10,12) or bz!=1 or d!=1 or w!=width or h!=height or w*h>16_777_216:
        raise ValueError('ASTC block/dimension profile mismatch')
    if hint is not None and hint!=bx:raise ValueError('Wire texture format hint differs from cached ASTC header')
    required=((w+bx-1)//bx)*((h+by-1)//by)*16
    if len(raw)!=required+16:raise ValueError('ASTC payload byte size mismatch')
    return dict(block=bx,width=w,height=h,payloadBytes=required)


def decode_cached_texture(cached,width,height,hint=None,kind='astc'):
    """Decode only the explicit cache family; the wire name is not a codec."""
    if kind not in ('astc','dds'):raise ValueError('Unsupported explicit texture cache family')
    if kind=='dds':
        from monkey.sources.unity_dds import decode_dds_dxt5
        rgba,header=decode_dds_dxt5(cached,width,height)
        return rgba,dict(dds=header,decoder=header['decoder'],normalization='DDS-DXT5-to-RGBA-no-flip-v1')
    header=astc_header(cached,width,height,hint)
    from importlib.metadata import version,PackageNotFoundError
    try:
        import texture2ddecoder
        installed=version('texture2ddecoder')
    except (ImportError,PackageNotFoundError) as error:
        raise ImportError('ASTC requires texture2ddecoder==1.0.6 in the selected provider; no automatic installation') from error
    if installed!='1.0.6':
        error=ImportError('ASTC requires texture2ddecoder==1.0.6 in the selected provider; found '+installed)
        error.code='DEPENDENCY_VERSION';raise error
    decoded=texture2ddecoder.decode_astc(cached[16:],width,height,header['block'],header['block'])
    if len(decoded)!=width*height*4:raise ValueError('Decoded texture byte budget/size differs')
    rgba=bytearray(len(decoded));rgba[0::4]=decoded[2::4];rgba[1::4]=decoded[1::4];rgba[2::4]=decoded[0::4];rgba[3::4]=decoded[3::4]
    return bytes(rgba),dict(astc=header,decoder='texture2ddecoder1.0.6',normalization='BGRA-to-RGBA-no-flip-v1')


def hydrate_manifest(job_path,output):
    import UnityPy
    from monkey.unity_texture_selection import matching_cache,validate_selection,cache_index
    if UnityPy.__version__!=PROVIDER_VERSION:raise RuntimeError('Expected UnityPy '+PROVIDER_VERSION)
    job=json.loads(job_path.read_text());source=Path(job['source']);raw=source.read_bytes()
    if len(raw)>MAX_BYTES or digest(raw)!=job['sourceSha256']:raise ValueError('Source changed')
    selection=job.get('selection')
    if selection is not None:selection=validate_selection(dict(schemaVersion=1,sourceSha256=job['sourceSha256'],objects=selection),job['sourceSha256'])
    chosen={(r['file'],r['pathId']):r for r in selection}if selection is not None else None
    env=UnityPy.load(raw);before={}
    for asset in env.assets:
        for obj in asset.objects.values():
            key=(asset.name,identifier(obj.path_id))
            if key in before:raise ValueError('Ambiguous serialized-file/object identity')
            before[key]=(obj.type.name,digest(obj.get_raw_data()))
    pool={x['logicalPath']:x for x in job['cache']};index=cache_index(pool);resolved=[];missing=[];deferred=[];diagnostics=[];modified=set()
    def finish(status,**extra):
        if digest(source.read_bytes())!=job['sourceSha256']:raise ValueError('Original changed during hydration')
        report=dict(schemaVersion=1,provider=dict(name='UnityPy',version=PROVIDER_VERSION),sourceSha256=digest(raw),status=status,
                    scope='selected-texture-set'if chosen is not None else'container',selectionComplete=(not missing and not diagnostics)if chosen is not None else None,
                    wholeContainerComplete=status=='hydrated',resolved=resolved,missing=missing,deferred=deferred,diagnostics=diagnostics,
                    originalSourceWritten=False,sourceCodeExecuted=False,pixelsDecoded=bool(resolved),serializationCommitted=False,inventoryComplete=False,
                    canonicalPixelDecoder=(resolved[0]['decoder']if resolved and len({r['decoder']for r in resolved})==1 else'per-cache-family-pinned-decoder'))
        report.update(extra);output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if chosen is not None:
        for key,row in chosen.items():
            actual=before.get(key)
            if actual!=('Texture2D',row['rawSha256']):
                reason='selected-object-missing'if actual is None else'selected-object-wrong-type'if actual[0]!='Texture2D'else'selected-object-raw-sha-changed'
                diagnostics.append(dict(code='UNITY_TEXTURE_SELECTION_IDENTITY',file=key[0],pathId=key[1],reason=reason,message='Exact selected Texture2D identity could not be verified'))
        if diagnostics:finish('needs_action');return
    for asset in env.assets:
        for obj in asset.objects.values():
            if obj.type.name!='Texture2D':continue
            key=(asset.name,identifier(obj.path_id));binding=chosen.get(key)if chosen is not None else None
            if chosen is not None and binding is None:
                deferred.append(dict(file=key[0],pathId=key[1],rawSha256=before[key][1],reason='not-selected-not-evaluated'));continue
            if not asset.unity_version.startswith('2021.3.'):
                diagnostics.append(dict(code='UNITY_TEXTURE_SOURCE_PROFILE',file=key[0],pathId=key[1],message='Texture token hydration currently verified for Unity2021.3 profile only'));finish('needs_action');return
            try:typed=obj.read_typetree(check_read=True)
            except Exception:
                diagnostics.append(dict(code='UNITY_TEXTURE_TYPE_TREE',file=key[0],pathId=key[1],message='Texture2D TypeTree could not be read; no inferred fields'));finish('needs_action');return
            token=texture_payload(typed)
            if token['kind']!='external-key-token-candidate':
                if binding:diagnostics.append(dict(code='UNITY_TEXTURE_SELECTION_PAYLOAD',file=key[0],pathId=key[1],message='Selected object is not an external-key texture token'));finish('needs_action');return
                continue
            if typed.get('m_MipCount')!=1 or typed.get('m_ImageCount')!=1:raise ValueError('Only original single-mip 2D texture hydration supported')
            try:matches=matching_cache(pool,token['key'],binding['logicalPath']if binding else None,index)
            except ValueError as error:
                diagnostics.append(dict(code='UNITY_TEXTURE_BINDING',file=key[0],pathId=key[1],message=str(error)));finish('needs_action');return
            if not matches:
                missing.append(dict(file=key[0],pathId=key[1],key=token['wireKey'],logicalPath=binding['logicalPath']if binding else None,filename=token['key']+'.txt',reason='exact-cache-key-missing'));continue
            if len(matches)!=1:
                diagnostics.append(dict(code='UNITY_TEXTURE_CACHE_AMBIGUOUS',file=key[0],pathId=key[1],logicalPaths=[r[1]for r in matches],message='Explicit object binding required; no path or encoding is guessed'));finish('needs_action');return
            kind,logical,item=matches[0]
            with Path(item['path']).open('rb')as stream:cached=stream.read(MAX_BYTES+1)
            if len(cached)!=item['bytes']or digest(cached)!=item['sha256']:
                diagnostics.append(dict(code='UNITY_TEXTURE_CACHE_IDENTITY',logicalPath=logical,message='Frozen cache bytes or SHA-256 changed'));finish('needs_action');return
            try:rgba,evidence=decode_cached_texture(cached,typed['m_Width'],typed['m_Height'],token.get('blockSizeHint'),kind)
            except (ImportError,ValueError)as error:
                from monkey.sources.unity_dds import DdsDependencyError
                code=getattr(error,'code','DEPENDENCY_MISSING')if isinstance(error,(ImportError,DdsDependencyError))else'UNITY_TEXTURE_CACHE_ENCODING'
                diagnostics.append(dict(code=code,logicalPath=logical,message=str(error)));finish('needs_action'if code.startswith('DEPENDENCY_')else'blocked');return
            typed['image data']=bytes(rgba);typed['m_CompleteImageSize']=len(rgba);typed['m_TextureFormat']=4
            obj.save_typetree(typed);modified.add(key)
            resolved.append(dict(file=key[0],pathId=key[1],sourceRawSha256=before[key][1],key=token['wireKey'],logicalPath=logical,
                                 cacheSha256=digest(cached),cacheBytes=len(cached),cacheFamily=kind,sourceTokenBlockSizeHint=token.get('blockSizeHint'),
                                 textureFormat=4,width=typed['m_Width'],height=typed['m_Height'],rgbaRawSha256=digest(rgba),**evidence))
    if missing:finish('needs_action'if chosen is not None else'blocked',inventoryComplete=True);return
    encoded=env.file.save(packer='lz4')
    if len(encoded)>MAX_BYTES:raise ValueError('Derived bundle byte budget')
    check=UnityPy.load(encoded);after={(a.name,identifier(o.path_id)):(o.type.name,digest(o.get_raw_data()))for a in check.assets for o in a.objects.values()}
    if before.keys()!=after.keys()or any(before[k]!=after[k]for k in before if k not in modified):raise ValueError('Unselected or non-texture object changed during serialization')
    proofs={(r['file'],r['pathId']):r for r in resolved}
    for asset in check.assets:
        for obj in asset.objects.values():
            key=(asset.name,identifier(obj.path_id))
            if key in modified:
                data=obj.read_typetree(check_read=True);proof=proofs[key]
                if data['m_TextureFormat']!=4 or data['m_Width']!=proof['width']or data['m_Height']!=proof['height']or digest(data['image data'])!=proof['rgbaRawSha256']:
                    raise ValueError('Texture RGBA hydration did not roundtrip exactly')
    if digest(source.read_bytes())!=job['sourceSha256']:raise ValueError('Original changed during hydration')
    (output.parent/'hydrated.bundle').write_bytes(encoded)
    finish('partial'if deferred else'hydrated',derivedBundleSha256=digest(encoded),derivedBundleBytes=len(encoded),
           serializationCommitted=True,inventoryComplete=True,nonTextureObjectsUnchanged=True,unselectedObjectsUnchanged=True,modifiedTextures=len(modified))


def export_selected_textures(job_path,output):
    import UnityPy
    from monkey.unity_texture_selection import validate_selection,matching_cache
    if UnityPy.__version__!=PROVIDER_VERSION:raise ValueError('Expected UnityPy '+PROVIDER_VERSION)
    job=json.loads(job_path.read_text());raw={}
    for name,path in job['paths'].items():
        with Path(path).open('rb')as stream:data=stream.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES or digest(data)!=job['pins'][name]:raise ValueError('Frozen export input identity changed')
        raw[name]=data
    selection=validate_selection(json.loads(raw['selectionManifest']),job['pins']['source']);proof=json.loads(raw['hydrationReport'])
    if selection!=job['selection']or proof!=job['proof']:raise ValueError('Frozen export job differs from its receipts')
    if proof.get('sourceSha256')!=job['pins']['source']or proof.get('derivedBundleSha256')!=job['pins']['derivative']or proof.get('selectionComplete')is not True or proof.get('serializationCommitted')is not True:
        raise ValueError('Hydration source/derivative proof is incomplete or changed')
    def objects(data):
        env=UnityPy.load(data);rows={}
        for asset in env.assets:
            for obj in asset.objects.values():
                key=(asset.name,identifier(obj.path_id))
                if key in rows:raise ValueError('Ambiguous serialized-file/object identity')
                rows[key]=obj
        return env,rows
    original,source=objects(raw['source']);derived,after=objects(raw['derivative']);chosen={(r['file'],r['pathId']):r for r in selection}
    if source.keys()!=after.keys():raise ValueError('Derivative object inventory differs')
    for key,obj in source.items():
        if key not in chosen and (obj.type.name!=after[key].type.name or digest(obj.get_raw_data())!=digest(after[key].get_raw_data())):
            raise ValueError('An unselected object differs from original bytes')
    deferred={(k[0],k[1]):digest(obj.get_raw_data())for k,obj in source.items()if k not in chosen and obj.type.name=='Texture2D'}
    reported={(r['file'],r['pathId']):r['rawSha256']for r in proof.get('deferred',[])}
    if reported!=deferred or len(reported)!=len(proof.get('deferred',[]))or proof['status']!=('partial'if deferred else'hydrated'):
        raise ValueError('Deferred texture inventory or partial state differs from original objects')
    proofs={}
    for row in proof['resolved']:
        key=(row['file'],row['pathId'])
        if key in proofs:raise ValueError('Duplicate hydration object proof')
        proofs[key]=row
    if proofs.keys()!=chosen.keys():raise ValueError('Hydration proof does not exactly cover selected objects')
    records=[];total=0
    for key,binding in chosen.items():
        obj=source.get(key);target=after.get(key);p=proofs[key]
        if obj is None or obj.type.name!='Texture2D'or target.type.name!='Texture2D'or digest(obj.get_raw_data())!=binding['rawSha256']or p['sourceRawSha256']!=binding['rawSha256']or p['logicalPath']!=binding['logicalPath']:
            raise ValueError('Exact selected source Texture2D identity differs')
        before=obj.read_typetree(check_read=True);data=target.read_typetree(check_read=True);token=texture_payload(before)
        if token['kind']!='external-key-token-candidate'or not matching_cache({binding['logicalPath']:p},token['key'],binding['logicalPath']):raise ValueError('Original texture token binding differs')
        w,h=p['width'],p['height']
        if type(w)is not int or type(h)is not int or w<=0 or h<=0 or w*h>16777216:raise ValueError('Selected texture pixel budget')
        if any(d.get('m_Width')!=w or d.get('m_Height')!=h or d.get('m_MipCount')!=1 or d.get('m_ImageCount')!=1 or d.get('m_TextureDimension')!=2 for d in (before,data)):
            raise ValueError('Exact single-mip 2D dimensions differ')
        if p.get('normalization')not in('BGRA-to-RGBA-no-flip-v1','DDS-DXT5-to-RGBA-no-flip-v1'):raise ValueError('Unproven canonical pixel normalization')
        pixels=data.get('image data');total+=len(pixels)if isinstance(pixels,bytes)else MAX_BYTES+1
        if data.get('m_TextureFormat')!=4 or not isinstance(pixels,bytes)or len(pixels)!=w*h*4 or digest(pixels)!=p['rgbaRawSha256']or total>MAX_BYTES:
            raise ValueError('Selected derivative pixels differ from hydration proof')
        relative='Payloads/'+digest((key[0]+'\0'+key[1]+'\0'+binding['rawSha256']).encode())+'.rgba';path=output.parent/relative;path.parent.mkdir(exist_ok=True);path.write_bytes(pixels)
        records.append(dict(file=key[0],pathId=key[1],sourceRawSha256=binding['rawSha256'],sourceName=before.get('m_Name'),
                            sourceSettings={k:before.get(k)for k in ('m_ColorSpace','m_TextureSettings','m_MipCount','m_TextureDimension')},
                            payloadPath=relative,width=w,height=h,**{k:p[k]for k in ('rgbaRawSha256','logicalPath','cacheSha256','normalization','decoder')}))
    if any(digest(Path(job['paths'][k]).read_bytes())!=job['pins'][k]for k in raw):raise ValueError('An export input changed during readback')
    output.write_text(json.dumps(dict(schemaVersion=1,status='selected-pixels-verified',textures=records,unselectedObjectsUnchanged=True,sourceAndDerivativeUnchanged=True,sourceCodeExecuted=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def quarantine_invalid_textures(job_path,output):
    import UnityPy
    if UnityPy.__version__!=PROVIDER_VERSION:raise RuntimeError('Expected UnityPy '+PROVIDER_VERSION)
    job=json.loads(job_path.read_text());source=Path(job['source']);raw=source.read_bytes()
    if len(raw)>MAX_BYTES or digest(raw)!=job['sourceSha256']:raise ValueError('Source changed')
    env=UnityPy.load(raw);before={};removed=[]
    for asset in env.assets:
        for obj in list(asset.objects.values()):
            key=(asset.name,identifier(obj.path_id))
            if key in before:raise ValueError('Ambiguous serialized file identity')
            before[key]=(obj.type.name,digest(obj.get_raw_data()))
            if obj.type.name!='Texture2D':continue
            typed=obj.read_typetree(check_read=True);payload=texture_payload(typed)
            if payload['kind']!='invalid-inline-etc1':continue
            removed.append(dict(file=asset.name,pathId=identifier(obj.path_id),name=typed.get('m_Name'),rawSha256=before[key][1],payload=payload))
            del asset.objects[obj.path_id]
    if not removed:raise ValueError('No exact invalid ETC1 payload to quarantine')
    encoded=env.file.save(packer='none' if raw.startswith(b'UnityWebData1.0\0') else 'lz4')
    if len(encoded)>MAX_BYTES:raise ValueError('Derived container byte budget')
    check=UnityPy.load(encoded);after={(a.name,identifier(o.path_id)):(o.type.name,digest(o.get_raw_data()))for a in check.assets for o in a.objects.values()}
    excluded={(r['file'],r['pathId'])for r in removed}
    expected={k:v for k,v in before.items()if k not in excluded}
    if after!=expected:raise ValueError('A retained object changed during quarantine')
    if digest(source.read_bytes())!=job['sourceSha256']:raise ValueError('Original changed')
    (output.parent/'derived.container').write_bytes(encoded)
    report=dict(schemaVersion=1,status='quarantined',sourceSha256=digest(raw),removed=removed,
        derivedSha256=digest(encoded),derivedBytes=len(encoded),retainedObjects=len(after),retainedObjectsUnchanged=True,
        sourceCodeExecuted=False,pixelsFabricated=False,referencesToRemovedObjects='unresolved-not-replaced',originalRetainedByConversion=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')


def index_manifest(manifest_path,output):
    import UnityPy
    if UnityPy.__version__!=PROVIDER_VERSION:raise RuntimeError('Expected UnityPy '+PROVIDER_VERSION)
    job=json.loads(manifest_path.read_text());rows=[];total=0;object_count=0
    for i,item in enumerate(job['files']):
        source=Path(item['path'])
        with source.open('rb') as stream:raw=stream.read(MAX_BYTES+1)
        if len(raw)!=item['bytes'] or len(raw)>MAX_BYTES or digest(raw)!=item['sha256']:raise ValueError('Source identity changed before indexing')
        total+=len(raw)
        if total>1024*1024*1024:raise ValueError('Aggregate input budget')
        row=dict(id=item['id'],source=dict(sha256=digest(raw),bytes=len(raw)),status='indexed',files=[])
        try:
            env=UnityPy.load(raw)
            for asset in env.assets:
                objects=[dict(pathId=identifier(o.path_id),type=o.type.name,classId=int(o.type)) for o in asset.objects.values()]
                object_count+=len(objects)
                if object_count>1_000_000:raise ValueError('Aggregate object budget')
                row['files'].append(dict(name=asset.name,unityVersion=asset.unity_version,
                    key=row['source']['sha256']+':'+asset.name,sourceTypeTreeEnabled=asset._enable_type_tree,
                    externals=[dict(fileId=str(j+1),path=e.path,guid=e.guid.hex()) for j,e in enumerate(asset.externals)],objects=objects))
            if not row['files']:raise ValueError('No serialized files')
        except Exception as error:
            row.update(status='failed',error=dict(type=type(error).__name__,message=str(error).splitlines()[0][:200]))
        with source.open('rb') as stream:after=stream.read(MAX_BYTES+1)
        if digest(after)!=item['sha256']:raise ValueError('Source changed while indexing')
        rows.append(row)
        if i%16==0:(output.parent/'index-progress.json').write_text(json.dumps(dict(processed=i+1,total=len(job['files']))))
    report=dict(schemaVersion=1,provider=dict(name='UnityPy',version=PROVIDER_VERSION),containers=rows,
        sourceManifestSha256=job['sourceManifestSha256'],identifierEncoding='signed-int64-decimal-string-v1',
        summary=dict(containers=len(rows),indexed=sum(r['status']=='indexed' for r in rows),failed=sum(r['status']=='failed' for r in rows),objects=object_count,inputBytes=total),
        objectBodiesParsed=False,pixelsDecoded=False,sourceCodeExecuted=False,sourceUnchanged=True)
    encoded=json.dumps(report,ensure_ascii=False,separators=(',',':')).encode()
    if len(encoded)>MAX_BYTES:raise ValueError('Index output budget')
    output.write_bytes(encoded)


def inspect_batch(job_path, output):
    """Read each frozen schema bundle once, then inspect every explicit container."""
    import UnityPy
    if UnityPy.__version__ != PROVIDER_VERSION: raise RuntimeError('Expected UnityPy '+PROVIDER_VERSION)
    job=json.loads(job_path.read_text());pool=job.get('schemaPool');rows=job['files'];limits=resolve_limits(job.get('parseLimits'))
    if job.get('readerContractSha256')!=reader_fingerprint():raise ValueError('Reader contract changed before execution')
    if not 1 <= len(rows) <= 2001: raise ValueError('Batch container budget')
    cache=schema_pool([],pool,all_schemas=True) if pool else {}
    reports=[];total=0
    for index,row in enumerate(rows):
        source=Path(row['path']);raw=source.read_bytes();total+=len(raw)
        if len(raw)>MAX_BYTES or total>1024**3 or len(raw)!=row['bytes'] or digest(raw)!=row['sha256']:
            raise ValueError('Batch input identity or budget changed')
        dest=Path(row['inspection']);dest.mkdir(exist_ok=False)
        receipt=dict(schemaVersion=1,status='started',source=dict(path=str(source),bytes=len(raw),sha256=digest(raw)),
                     processExited=True,sourceCodeExecuted=False)
        started=time.monotonic()
        try:
            typed=inspect_bytes(raw,pool,schema_cache=cache,parse_limits=limits,payload_root=dest)
            typed['source']={k:receipt['source'][k] for k in ('bytes','sha256')}
            typed_hash=write_document(dest/'typed-objects.json',typed)
            receipt.update(status='partial' if typed['summary']['unparsed'] else 'inspected',
                           summary=typed['summary'],provider=typed['provider'],typedObjectsSha256=typed_hash,parseLimits=limits,parseUsage=typed['parseUsage'],readerContractSha256=reader_fingerprint())
        except Exception as error:
            receipt.update(status='failed',error=dict(type=type(error).__name__,message=str(error)[:300]))
        receipt['performance']=runtime_stats(started)
        receipt['sourceUnchanged']=digest(source.read_bytes())==row['sha256']
        (dest/'inspection.json').write_text(json.dumps(receipt,indent=2)+'\n')
        reports.append(dict(path=str(source),inspection=str(dest),receipt=receipt))
        (output.parent/'batch-progress.json').write_text(json.dumps(dict(processed=index+1,total=len(rows)))+'\n')
    output.write_text(json.dumps(dict(schemaVersion=1,files=reports,schemaBundlesRead=len(pool['files'])if pool else 0,
                                     containersInspected=len(rows),sourceCodeExecuted=False),separators=(',',':'))+'\n')


def main():
    schema_job = None;limits=None
    if sys.argv[1] == '--inspect-with-schemas':
        job = json.loads(Path(sys.argv[2]).read_text())
        source, output = Path(job['source']), Path(sys.argv[3])
        schema_job = job['schemaPool'];limits=resolve_limits(job.get('parseLimits'))
        if job.get('readerContractSha256')!=reader_fingerprint():raise ValueError('Reader contract changed before execution')
    else: source, output = map(Path, sys.argv[1:])
    with source.open('rb') as stream:
        raw = stream.read(MAX_BYTES+1)
    if len(raw) > MAX_BYTES:
        raise ValueError('Input byte budget exceeded')
    started=time.monotonic()
    data = inspect_bytes(raw, schema_job,parse_limits=limits,payload_root=output.parent)
    data['source'] = dict(bytes=len(raw), sha256=digest(raw))
    write_document(output,data)
    (output.parent/'reader-runtime.json').write_text(json.dumps(runtime_stats(started)))


if __name__ == '__main__':
    if len(sys.argv)==4 and sys.argv[1]=='--inspect-batch':inspect_batch(Path(sys.argv[2]),Path(sys.argv[3]))
    elif len(sys.argv)==4 and sys.argv[1]=='--hydrate':hydrate_manifest(Path(sys.argv[2]),Path(sys.argv[3]))
    elif len(sys.argv)==4 and sys.argv[1]=='--export-selected-textures':export_selected_textures(Path(sys.argv[2]),Path(sys.argv[3]))
    elif len(sys.argv)==4 and sys.argv[1]=='--quarantine-invalid-textures':quarantine_invalid_textures(Path(sys.argv[2]),Path(sys.argv[3]))
    elif len(sys.argv)==4 and sys.argv[1]=='--index':index_manifest(Path(sys.argv[2]),Path(sys.argv[3]))
    else:main()
