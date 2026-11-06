"""Read-only, bounded diagnostics over existing recovery evidence.

This indexes evidence; it does not reparse bundles, validate all candidate bytes,
execute recovered programs, apply fields, or promote an Editor/Player result.
"""
from collections import Counter
from pathlib import Path
import re

from .io import safe,inside,read,load,sha,write_json,new_output
from .sources.compiled import fail

NAMES=('conversion-result.json','manifest.json','recovery-manifest.json','acquisition.json',
       'verification.json','execution-result.json','validation.json','field-plan.json',
       'SourceInspection/typed-objects.json','Analysis/Evidence/unity-typed-objects.json',
       'Analysis/Readback/editor-readback.json','Analysis/Tasks/handoff.json',
       'Analysis/Tasks/initial-handoff.json','Analysis/Tasks/full-resource-handoff.json',
       'Analysis/Evidence/spine-closures.json','Analysis/Mappings/resource-catalog.json')


def _clean(value):
    # Original diagnostics can contain CDN query credentials. Never reproduce them.
    return re.sub(r'https?://[^\s\]<>"\']+',lambda m:m[0].split('?',1)[0].split('#',1)[0].rsplit('@',1)[-1],str(value))[:1000]


def _scrub(value):
    if isinstance(value,str):return _clean(value)
    if isinstance(value,list):return [_scrub(x)for x in value]
    if isinstance(value,dict):return {str(k):_scrub(v)for k,v in value.items()}
    return value


def diagnose(source,output,evidence=(),max_issues=2000,max_document_bytes=32*1024*1024):
    if type(max_issues) is not int or not 1<=max_issues<=100000:fail('DIAGNOSTIC_LIMIT','issues','Expected 1..100000')
    if type(max_document_bytes) is not int or not 1024<=max_document_bytes<=128*1024*1024:fail('DIAGNOSTIC_LIMIT','documents','Expected 1 KiB..128 MiB')
    source=safe(source);extra=[safe(p)for p in evidence];pending=[];seen=set();documents=[];issues={};counts=Counter();used=0;omitted=0;target_mappings={};native_observations=[]
    def source_key(identity):
        return (identity.get('containerSha256'),identity.get('serializedFile',identity.get('file')),str(identity.get('pathId')))
    def enqueue(path):
        if path.exists() and path not in seen:seen.add(path);pending.append(path)
    if source.is_file():enqueue(source)
    else:
        for name in NAMES:enqueue(inside(source,name))
    for p in extra:enqueue(p)
    if not pending:fail('DIAGNOSTIC_INPUT',str(source),'No supported evidence found; provide an explicit JSON --evidence')
    def add(code,category,identity,target,impact,action,doc,severity='warning',details=None):
        nonlocal omitted
        key=sha(repr((code,sorted(identity.items()),target)).encode())[:24]
        if key in issues:
            if doc not in issues[key]['evidence']:issues[key]['evidence'].append(doc)
            return
        counts[category]+=1;counts['severity:'+severity]+=1
        if len(issues)>=max_issues:omitted+=1;return
        issues[key]=dict(issueId=key,code=code,category=category,severity=severity,source=identity,target=target,
                         impact=_clean(impact),nextAction=action,evidence=[doc],**(dict(details=details) if details else {}))
    while pending:
        path=pending.pop(0);size=path.stat().st_size
        label=path.relative_to(source).as_posix() if source.is_dir() and path.is_relative_to(source) else str(path)
        doc=dict(path=label,bytes=size)
        if size>max_document_bytes or used+size>256*1024*1024:
            documents.append(dict(doc,status='deferred-size-budget',hashReverified=False))
            add('DIAGNOSTIC_EVIDENCE_DEFERRED','evidence',dict(path=label),None,'Evidence not read within this bounded inspection',
                'Use a smaller frozen evidence slice or an explicit larger --max-document-bytes; do not treat this report as complete.',doc)
            continue
        try:raw=read(path,max_bytes=max_document_bytes);data=load(raw,max_nodes=8_000_000)
        except Exception as error:
            documents.append(dict(doc,status='invalid'))
            add('DIAGNOSTIC_EVIDENCE_INVALID','evidence',dict(path=label),None,type(error).__name__,
                'Preserve the evidence and correct its producer/schema; no candidate writes were attempted.',doc,'error');continue
        used+=len(raw);doc['sha256']=sha(raw);documents.append(dict(doc,status='read'))
        if not isinstance(data,dict):
            documents[-1]['status']='unsupported-schema'
            add('DIAGNOSTIC_SCHEMA_UNSUPPORTED','evidence',dict(path=label),None,'Expected a structured receipt',
                'Supply an existing monkey receipt or typed-object document.',doc);continue
        bad=[k for k in ('projects','diagnostics','files','objects','skeletons','shaders','sourceToTarget') if k in data and not isinstance(data[k],list)]
        if bad:
            documents[-1]['status']='unsupported-schema'
            add('DIAGNOSTIC_SCHEMA_UNSUPPORTED','evidence',dict(path=label),None,'Receipt collection has an unsupported shape: '+','.join(bad),
                'Preserve this receipt and use its documented producer schema; no inferred rows are indexed.',doc);continue
        if path.name=='conversion-result.json':
            for p in data.get('projects',[]):
                root=inside(path.parent,p['path'])
                for name in NAMES:enqueue(inside(root,name))
        for d in data.get('diagnostics',[]):
            if not isinstance(d,dict):continue
            code=str(d.get('code','UNCLASSIFIED_DIAGNOSTIC'))
            category=('field-writeback' if 'FIELD' in code else 'source-parsing' if any(x in code for x in ('PARSE','SCHEMA','TYPE')) else
                      'resource-closure' if any(x in code for x in ('REFERENCE','SPINE','SHADER','SPRITE','TEXTURE')) else 'native-import' if 'EDITOR' in code or 'NATIVE' in code else 'recovery')
            add(code,category,dict(sourceId=_clean(d.get('sourceId') or d.get('sourceRef') or d.get('location') or label)),d.get('target'),
                d.get('message') or d.get('rootCause') or code,'Inspect the bound producer diagnostic and source identity; use only the declared supported profile.',doc,d.get('severity') if d.get('severity') in ('info','warning','error') else 'warning')
        files={str(f['id']):f for f in data.get('files',[]) if isinstance(f,dict) and 'id'in f}
        objects={(o['file'],o['pathId']):o for o in data.get('objects',[]) if isinstance(o,dict) and 'file'in o and 'pathId'in o}
        for o in objects.values():
            identity=dict(containerSha256=data.get('source',{}).get('sha256',''),serializedFile=files.get(o['file'],{}).get('name',o['file']),pathId=o['pathId'])
            if o.get('status')=='unparsed':
                details=dict(type=o.get('type'),rawSha256=o.get('rawSha256'),requiredSchemaIdentity=o.get('requiredSchemaIdentity'),
                             referenceCoverage=o.get('referenceCoverage','unknown'),bodyWritable=False)
                ptr=o.get('nativePrefix',{}).get('fields',{}).get('m_Script',{});owner=o['file']
                if ptr.get('fileId')!='0':
                    external=[e for e in files.get(owner,{}).get('externals',[]) if e.get('fileId')==ptr.get('fileId')]
                    names={e['path'].rsplit('/',1)[-1]for e in external}
                    matches=[f['id']for f in files.values() if f.get('name')in names]
                    owner=matches[0] if len(matches)==1 else None
                script=objects.get((owner,ptr.get('pathId')),{}).get('data',{})
                if script.get('m_ClassName'):details['scriptClass']='.'.join(x for x in [script.get('m_Namespace'),script['m_ClassName']] if x)
                add('SOURCE_OBJECT_BODY_UNPARSED','source-parsing',identity,None,'Original object body cannot be safely emitted or written back',
                    'Provide a trusted exact version/platform/scriptId/typeHash schema or preserve this object as an explicit unsupported body. Prefix references do not authorize field writeback.',doc,details=details)
            elif o.get('borrowedSchemaId') and o.get('semanticValidation',{}).get('writable') is not True:
                add('FIELD_VALUES_REQUIRE_INDEPENDENT_REFERENCE','field-writeback',identity,None,'Schema shape is known; field-value fidelity and target identity are separate gates',
                    'Use unity-field-plan with an independently trusted snapshot and exact target GUID/localId/hash. Do not infer authorization from successful parsing.',doc,'info')
        for row in data.get('files',[]):
            if not isinstance(row,dict) or 'sourceKey'not in row:continue
            if row.get('status') not in ('downloaded','local_verified','reused_verified'):
                add('CDN_HTTP_404' if row.get('httpStatus')==404 else 'REMOTE_IDENTITY_MISMATCH' if row.get('status')=='identity_mismatch' else 'REMOTE_RESOURCE_UNAVAILABLE',
                    'source-acquisition',dict(sourceKey=row['sourceKey'],path=row.get('path','')),None,'Declared source resource unavailable: '+str(row.get('status')),
                    'Resume the exact manifest into a fresh acquisition layer; for 404 obtain the exact original version/cache. Never synthesize replacement bytes.',doc,
                    details={k:row[k]for k in ('httpStatus','expectedSha256','expectedBytes','attempts')if k in row})
        for row in data.get('skeletons',[]):
            native=row.get('nativeValidation')
            if native not in ('passed','pass','verified'):
                add('SPINE_RUNTIME_REQUIRED' if row.get('runtime')=='not_installed' else 'SPINE_VERSION_UNSUPPORTED' if row.get('runtime')=='source_version_requires_adapter' else 'SPINE_NATIVE_PLAYBACK_PENDING',
                    'resource-closure',dict(sourceId=row['sourceId']),row.get('skeletonPath'),'Recovered closure is not proof of native playback',
                    'Use the exact skeleton version and an already authorized compatible runtime; verify atlas/page identity and a native animation. Preserve unsupported versions.',doc,
                    details=dict(version=row.get('skeletonVersion'),runtime=row.get('runtime'),closureStatus=row.get('status')))
        for row in data.get('shaders',[]):
            if row.get('nativeShader')is not True:
                add('SHADER_TARGET_PROFILE_REQUIRED','resource-closure',dict(sourceId=row['sourceId']),row.get('files',[{}])[0].get('path') if row.get('files')else None,
                    'Source GLSL/effect files are preserved; target material compilation and visual behavior are unverified',
                    'Use an exact supported source shader profile, compile the target material and compare a fixed view; never substitute a generic shader for an unknown effect.',doc)
            elif row.get('nativeValidation')not in ('pass','passed','verified'):
                add('SHADER_NATIVE_VALIDATION_PENDING','resource-closure',dict(sourceId=row['sourceId']),row.get('nativeProfile',{}).get('outputs',{}).get('shader'),
                    'An exact-profile native candidate is generated; its material import, compilation and fixed-view result are separate gates',
                    'Run the manifest-bound resource probe in an authorized graphics-enabled Editor and retain the exact source/target hashes. Do not mark all shader variants validated.',doc)
        for row in data.get('sourceToTarget',[]):
            if not isinstance(row,dict) or not isinstance(row.get('source'),dict):continue
            identity=row['source'];target=row.get('target')
            if isinstance(target,dict) and target.get('path') and target.get('guid') and target.get('sha256'):
                target_mappings.setdefault(source_key(identity),[]).append(dict(target=target,evidence=doc))
            elif target is None:
                add('SOURCE_TARGET_MAPPING_UNRESOLVED','resource-closure',identity,None,'No exact target was recorded for the original asset identity',
                    'Inspect this exact source container/file/pathId and logical path; acquire missing original bytes or extend its supported converter. Do not bind by filename.',doc,
                    details=dict(mappingStatus=row.get('status'),targetBytesReverified=False))
        probes=data.get('resourceProbes')or{}
        if isinstance(probes,dict) and probes.get('profile')=='creator-spine-3.8-v1':
            for row in probes.get('spines',[]):
                if not isinstance(row,dict) or 'nativeStateAdvanced'not in row:continue
                native_observations.append(dict(sourceId=row.get('sourceId'),sourceSkeletonSha256=row.get('sourceSkeletonSha256'),
                    skeletonUuid=row.get('skeletonUuid'),profile=probes['profile'],poseChanged=row.get('poseChanged'),
                    nativeStateAdvanced=row.get('nativeStateAdvanced'),evidence=doc,assurance='indexed-existing-readback; not rerun or independently promoted'))
        for field,code,action in [('unresolvedAssetGuids','NATIVE_GUID_CLOSURE_INCOMPLETE','Use exact GUID and referring asset records; missing GUID count is not missing-script count.'),
                                  ('unparsedSourceObjects','SOURCE_OBJECT_SUMMARY_UNPARSED','Inspect the corresponding typed-object slice for exact class/script/type identity.'),
                                  ('implementedMethods','SOURCE_METHODS_UNRECOVERED','Continue from source-linked method evidence; declarations are not method implementations.')]:
            value=data.get(field)
            if type(value)is int and (value>0 if field!='implementedMethods'else value==0):
                add(code,'source-parsing' if field=='unparsedSourceObjects' else 'code-recovery' if field=='implementedMethods'else 'resource-closure',dict(receipt=label),None,
                    f'{field}={value}',action,doc,details=dict(reportedCount=value,aggregateOnly=True))
    out=new_output(output,[source,*extra]);rows=list(issues.values())
    for row in rows:
        matches=target_mappings.get(source_key(row['source']),[])
        unique={m['target']['path']:m for m in matches}
        if row['target']is None and len(unique)==1:
            match=next(iter(unique.values()));row['target']=match['target'];row['evidence'].append(match['evidence'])
            row['targetAssurance']='declared-exact-source-identity; target-bytes-not-reverified'
        elif row['target']is None:
            row['targetAssurance']='ambiguous-recorded-targets' if unique else 'no-exact-target-in-selected-evidence'
    report=dict(schemaVersion=1,tool='monkey-diagnostics-v1',status='attention_required' if any(r['severity']!='info'for r in rows) or omitted else 'no_reported_gaps',
                coverage=dict(complete=not omitted and all(d['status']=='read'for d in documents),documents=len(documents),bytesRead=used,
                              emittedIssues=len(rows),omittedIssues=omitted,allCandidateBytesReverified=False,nativeExecuted=False,
                              scope='selected-existing-evidence-only; dependency-typed slices require explicit selection',fullRecoveryCoverage=False),
                counts=dict(counts),documents=documents,issues=rows,nativeResourceObservations=native_observations)
    report=_scrub(report);rows=report['issues'];write_json(out/'diagnostics.json',report)
    text='# Recovery diagnostics\n\n'+report['status']+'; this indexes existing evidence, without reparsing original containers or validating all candidate bytes.\n\n'
    text+='| Code | Source | Target | Next action |\n|---|---|---|---|\n'
    for row in rows[:50]:text+='| '+' | '.join(_clean(str(x)).replace('|','\\|').replace('\n',' ') for x in [row['code'],row['source'],row['target']or'',row['nextAction']])+' |\n'
    if omitted or len(rows)>50:text+='\nSee diagnostics.json for bounded coverage, all emitted identities, and omissions.\n'
    (out/'DIAGNOSTICS.md').write_text(text,encoding='utf-8')
    return dict(status=report['status'],coverage=report['coverage'],counts=dict(counts),report=str(out/'diagnostics.json'))
