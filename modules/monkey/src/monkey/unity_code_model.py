"""Proven TypeTree -> named C# serialized fields. Asset bundles contain no method bodies."""
import re
from pathlib import Path
from .io import safe,read,load,sha,new_output,write_json
from .sources.compiled import fail

CORE_FIELDS={'m_GameObject','m_Enabled','m_Script','m_Name','m_EditorHideFlags','m_EditorClassIdentifier','m_ObjectHideFlags','m_CorrespondingSourceObject','m_PrefabInstance','m_PrefabAsset'}
PRIMITIVES={'bool':'bool','char':'byte','SInt8':'sbyte','UInt8':'byte','short':'short','SInt16':'short','UInt16':'ushort',
            'unsigned short':'ushort','int':'int','SInt32':'int','UInt32':'uint','unsigned int':'uint','SInt64':'long',
            'long long':'long','UInt64':'ulong','unsigned long long':'ulong','float':'float','double':'double','string':'string'}
UNITY_TYPES={'Sprite','Texture2D','Texture','GameObject','Transform','RectTransform','MonoBehaviour','Component','Object',
             'AudioClip','AnimationClip','RuntimeAnimatorController','Material','Shader','Mesh','Font','Canvas'}
VALUE_TYPES={'Vector2f':'Vector2','Vector3f':'Vector3','Vector4f':'Vector4','Quaternionf':'Quaternion','ColorRGBA':'Color','Color32':'Color32'}


CS_KEYWORDS=set('abstract as base bool break byte case catch char checked class const continue decimal default delegate do double else enum event explicit extern false finally fixed float for foreach goto if implicit in int interface internal is lock long namespace new null object operator out override params private protected public readonly ref return sbyte sealed short sizeof stackalloc static string struct switch this throw true try typeof uint ulong unchecked unsafe ushort using virtual void volatile while'.split())

def identifier(value):
    # Escape actual keywords only; ordinary MonoScript class names stay literal.
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',value):
        fail('CSHARP_NAME_UNSUPPORTED',str(value),'Source identifier needs explicit name mapping')
    return '@'+value if value in CS_KEYWORDS else value


def field_type(node):
    typ=node['type']
    if typ == 'string' and node.get('children'):
        from .unity_semantics import array_data, SemanticError
        try:
            if array_data(node).get('type') != 'char': raise SemanticError('Non-character scalar string')
        except SemanticError as error:
            fail('UNITY_STRING_ARRAY_SCHEMA',node.get('name','?'),str(error))
    if typ in PRIMITIVES:return PRIMITIVES[typ]
    if typ in VALUE_TYPES:return 'UnityEngine.'+VALUE_TYPES[typ]
    match=re.fullmatch(r'PPtr<([^<>]+)>',typ)
    if match:
        name=match[1].removeprefix('$')
        if name in UNITY_TYPES:return 'UnityEngine.'+name
    if typ=='vector':
        arrays=[n for n in node.get('children',[]) if n['type']=='Array']
        if len(arrays)==1:
            values=[n for n in arrays[0].get('children',[]) if n['name']=='data']
            if len(values)==1:return field_type(values[0])+'[]'
    fail('CSHARP_FIELD_UNSUPPORTED',node.get('name','?'),'No proven C# mapping for embedded type '+str(typ))


def script_object(data, objects, obj, ptr):
    """Resolve only an exact same-container serialized-file external table entry."""
    file_id=obj['file']
    if ptr.get('fileId')!='0':
        source=next((f for f in data.get('files',[])if f['id']==file_id),None)
        entries=[e for e in source.get('externals',[])if e['fileId']==ptr.get('fileId')]if source else []
        if len(entries)!=1:return None
        name=entries[0]['path']
        if not isinstance(name,str):return None
        if name.startswith('archive:/'):
            parts=name.removeprefix('archive:/').split('/')
            if len(parts)!=2 or parts[0]!=parts[1]:return None
            name=parts[1]
        if '/'in name or '\\'in name:return None
        targets=[f for f in data['files']if f['name']==name]
        if len(targets)!=1:return None
        file_id=targets[0]['id']
    script=objects.get((file_id,ptr.get('pathId')))
    return script if script and script.get('type')=='MonoScript'and script.get('status')=='parsed'else None


def model(inspection,output,bulk=False):
    inspection=safe(inspection);receipt=load(read(inspection/'inspection.json'))
    raw=read(inspection/'typed-objects.json',max_bytes=128*1024*1024)
    if sha(raw)!=receipt.get('typedObjectsSha256'):fail('UNITY_TYPED_CHANGED',str(inspection),'Typed snapshot differs from receipt')
    data=load(raw,max_nodes=8_000_000);out=new_output(output,[inspection])
    objects={(o['file'],o['pathId']):o for o in data['objects']};schemas=data.get('embeddedSchemas',{});classes={};gaps=[];native_packages=[];logical_classes={}
    for obj in data['objects']:
        if obj['type']!='MonoBehaviour' or obj.get('status')!='parsed':continue
        shape=schemas.get(obj.get('embeddedSchemaId'))
        borrowed=False
        if shape is None and obj.get('typeTreeSource')=='exact-frozen-bundle'and obj.get('schemaProvenance'):
            shape=data.get('borrowedSchemas',{}).get(obj.get('borrowedSchemaId'));borrowed=shape is not None
        ptr=obj['data'].get('m_Script',{})
        script=script_object(data,objects,obj,ptr)
        if shape is None or script is None or script.get('status')!='parsed':
            gaps.append(dict(object=dict(file=obj['file'],pathId=obj['pathId']),reason='proven schema or exact MonoScript reference unavailable'));continue
        info=script['data'];name=info.get('m_ClassName');namespace=info.get('m_Namespace') or '';assembly=info.get('m_AssemblyName') or 'UnknownAssembly'
        if assembly.startswith(('UnityEngine.','UnityEditor.','Unity.'))or assembly in ('UnityEngine.dll','UnityEditor.dll'):
            native_packages.append(dict(name=name,namespace=namespace,assembly=assembly,object=dict(file=obj['file'],pathId=obj['pathId']),sourceScript=dict(file=script['file'],pathId=script['pathId']),reason='existing-native-package-type-do-not-shadow',native='not_verified'))
            continue
        game_object=obj['data'].get('m_GameObject',{})
        if not any(n['name']=='m_GameObject'for n in shape['children']) or game_object.get('pathId')in (None,'0'):
            gaps.append(dict(object=dict(file=obj['file'],pathId=obj['pathId']),reason='non-component base class unavailable; do not fabricate MonoBehaviour inheritance'));continue
        try:
            cs_name=identifier(name);parts=[identifier(p) for p in namespace.split('.')] if namespace else []
            fields=[dict(name=n['name'],csName=identifier(n['name']),csType=field_type(n),sourceType=n['type']) for n in shape['children'] if n['name'] not in CORE_FIELDS]
        except ValueError as error:
            gaps.append(dict(object=dict(file=obj['file'],pathId=obj['pathId']),reason=getattr(error,'code','unsupported'),detail=getattr(error,'message',str(error))));continue
        if not fields:
            gaps.append(dict(object=dict(file=obj['file'],pathId=obj['pathId']),reason='No recoverable fields or method bodies; no empty class emitted'));continue
        key=(script['file'],script['pathId'])
        original_key=key;logical=(assembly,namespace,name);script_hash=script.get('rawSha256')
        if bulk and logical in logical_classes:
            previous_key=logical_classes[logical];previous=classes[previous_key]
            if not script_hash or script_hash!=previous.get('scriptRawSha256')or previous['fields']!=fields:fail('CSHARP_CLASS_COLLISION',name,'Bulk alias requires byte-identical MonoScript and exact same proven fields')
            key=previous_key
        record=dict(name=name,namespace=namespace,assembly=assembly,sourceScript=dict(file=key[0],pathId=key[1]),
                    fields=fields,instances=[],scriptRawSha256=script_hash,sourceScripts=[],methodRecovery='unavailable-in-asset-bundle',status='schema_only',business='not_run')
        if key in classes:
            if classes[key]['fields']!=fields:fail('UNITY_SCHEMA_CONFLICT',name,'Same script identity has differing embedded schemas')
        else:classes[key]=record;logical_classes[logical]=key
        alias=dict(file=original_key[0],pathId=original_key[1],rawSha256=script_hash)
        if alias not in classes[key]['sourceScripts']:classes[key]['sourceScripts'].append(alias)
        classes[key]['instances'].append(dict(file=obj['file'],pathId=obj['pathId'],rawSha256=obj['rawSha256'],references=obj['references'],sourceScript=alias))
        classes[key]['instances'][-1]['schemaEvidence']=dict(kind='exact-frozen-bundle'if borrowed else'embedded',schemaId=obj.get('borrowedSchemaId')if borrowed else obj.get('embeddedSchemaId'),provenance=obj.get('schemaProvenance')if borrowed else None)
    occupied=set()
    for (file_id,path_id),c in classes.items():
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',c['assembly']):fail('CSHARP_ASSEMBLY_PATH',c['name'],'Unsafe assembly name')
        relative=Path('CSharp')/c['assembly'].removesuffix('.dll')/Path(*c['namespace'].split('.'))/(c['name']+'.cs')
        if str(relative).casefold() in occupied:fail('CSHARP_CLASS_COLLISION',str(relative),'Distinct script identities collide; assembly repair required')
        occupied.add(str(relative).casefold());path=out/relative;path.parent.mkdir(parents=True,exist_ok=True)
        lines=['// Proven TypeTree fields only. Original method bodies and custom inheritance are unavailable.',
               '// Source container SHA256: '+data['source']['sha256'],
               '// Source MonoScript file/pathID: '+file_id+'/'+path_id]
        if c['namespace']:lines+=['namespace '+'.'.join(identifier(p) for p in c['namespace'].split('.'))+' {']
        lines+=['public class '+identifier(c['name'])+' : UnityEngine.MonoBehaviour {']
        lines+=['    public '+f['csType']+' '+f['csName']+';' for f in c['fields']]
        lines+=['}']
        if c['namespace']:lines+=['}']
        path.write_text('\n'.join(lines)+'\n');c['target']=relative.as_posix();c['targetSha256']=sha(read(path))
    report=dict(schemaVersion=1,sourceSha256=data['source']['sha256'],typedSnapshotSha256=sha(raw),
                status='partial',classes=list(classes.values()),gaps=gaps,nativePackageTypes=native_packages,compiled='not_run',native='not_run',
                summary=dict(classes=len(classes),fields=sum(len(c['fields']) for c in classes.values()),methodsImplemented=0,instances=sum(len(c['instances']) for c in classes.values())))
    write_json(out/'unity-code-model.json',report)
    return dict(status='partial',summary=report['summary'],compiled='not_run',business='not_run',report=str(out/'unity-code-model.json'))
