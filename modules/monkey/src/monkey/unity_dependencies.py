"""Exact serialized-file closure within an explicit frozen Unity lookup pool."""
from pathlib import Path
from .io import read,load,sha,new_output,write_json
from .sources.compiled import fail


def closure(primary,indexed,pool):
    rows=indexed.get('containers',[])
    if len(rows)!=len(pool['files']):fail('UNITY_DEPENDENCY_INDEX','$','Frozen pool/index length differs')
    by_name={};aliases=[];alias_seen=set();primary_names={f['name']for f in primary['files']}
    for row,source in zip(rows,pool['files']):
        if row.get('status')!='indexed' or row.get('source')!={k:source[k]for k in ('sha256','bytes')}:
            fail('UNITY_DEPENDENCY_INDEX','$','Every pool container must have an exact successful metadata index')
        for file in row.get('files',[]):
            name=file.get('name')
            if not isinstance(name,str)or not name or len(name)>4096:fail('UNITY_DEPENDENCY_FILE_ID','$','Invalid serialized file identity')
            by_name.setdefault(name,[]).append((row,source))
    seen=set();selected={};edges=[];missing=[];pending=[(primary['source']['sha256'],primary['files'])]
    while pending:
        digest,files=pending.pop()
        if digest in seen:continue
        seen.add(digest);own={f['name']for f in files}
        for file in files:
            for reference in file.get('externals',[]):
                path=reference.get('path')
                if not isinstance(path,str)or len(path)>4096 or '\x00'in path:fail('UNITY_DEPENDENCY_FILE_ID','$','Invalid external file identity')
                name=path.replace('\\','/').split('/')[-1]
                if name in own:continue
                options=by_name.get(name,[])
                if name in primary_names:
                    if any(s['sha256']!=primary['source']['sha256']for _,s in options):fail('UNITY_DEPENDENCY_AMBIGUOUS',name,'Lookup container conflicts with the explicit primary identity')
                    edges.append(dict(containerSha256=digest,file=file['name'],externalPath=path,targetFile=name,targetContainerSha256=primary['source']['sha256']));continue
                if not options:
                    if len(edges)+len(missing)>=50000:fail('UNITY_DEPENDENCY_BUDGET','$','External edge budget exceeded')
                    missing.append(dict(containerSha256=digest,file=file['name'],path=path,reason='exact-serialized-file-not-in-pool'));continue
                hashes={source['sha256']for _,source in options}
                if len(hashes)!=1:fail('UNITY_DEPENDENCY_AMBIGUOUS',name,'Different frozen containers claim the same serialized-file identity')
                row,source=min(options,key=lambda pair:pair[1]['path'])
                if len(options)>1 and name not in alias_seen:
                    alias_seen.add(name);aliases.append(dict(file=name,selected=source['path'],equivalentPaths=sorted({s['path']for _,s in options}),sha256=source['sha256']))
                edges.append(dict(containerSha256=digest,file=file['name'],externalPath=path,targetFile=name,targetContainerSha256=source['sha256']))
                if source['sha256']!=primary['source']['sha256']:
                    selected[source['sha256']]=source
                    if source['sha256']not in seen:pending.append((source['sha256'],row['files']))
                if len(edges)+len(missing)>50000:fail('UNITY_DEPENDENCY_BUDGET','$','External edge budget exceeded')
    return dict(schemaVersion=1,status='partial'if missing else'resolved',sourceManifestSha256=pool['sourceManifestSha256'],
        lookupFiles=len(pool['files']),lookupBytes=sum(r['bytes']for r in pool['files']),
        dependencies=sorted(selected.values(),key=lambda r:r['path']),edges=edges,missing=missing,equivalentAliases=aliases,
        resolution='exact serialized-file names only; byte-identical container aliases allowed',sourceCodeExecuted=False)


def resolve(inspection,pool,manifest,provider_python,output,budget_seconds=600):
    from .unity_index import catalog
    out=new_output(output,[manifest,*[r['path']for r in pool['files']]])
    result=catalog(manifest,provider_python,out/'Index',budget_seconds)
    if result['status']!='indexed' or result.get('sourceManifestSha256')!=pool['sourceManifestSha256']:
        fail('UNITY_DEPENDENCY_INDEX',str(out),'Complete unchanged frozen metadata index required')
    raw=read(out/'Index/unity-index.json',max_bytes=128*1024*1024)
    if sha(raw)!=result['indexSha256']:fail('UNITY_DEPENDENCY_INDEX',str(out),'Index changed after receipt')
    indexed=load(raw,max_nodes=8_000_000)
    if indexed.get('sourceManifestSha256')!=pool['sourceManifestSha256']:fail('UNITY_DEPENDENCY_INDEX',str(out),'Index input identity differs')
    report=closure(inspection,indexed,pool)
    write_json(out/'closure.json',report)
    return report
