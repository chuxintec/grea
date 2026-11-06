"""Read-only inspection of frozen method maps, table ZIPs and resource aliases."""
import tempfile
import zipfile
from . import __version__
from .io import safe,inside,encoded,new_output,write_json
from .evidence_stream import opened,JsonRows,checksum,zip_index
from .output_limits import WHOLE_BYTES,WHOLE_FILES
from .sources.containers import relative
from .sources.compiled import fail
from .owned_fs import RootReader

RESULT_BYTES=32*1024**2


def limit_value(limit):
    if type(limit) is not int or not 1<=limit<=1000:fail('QUERY_LIMIT','$','Limit must be 1..1000')


def report(output,kind,sources,result,inputs):
    result=dict(schemaVersion=1,toolVersion=__version__,operation=kind,sourceCodeExecuted=False,
                sources=sources,**result)
    if len(encoded(result))>RESULT_BYTES:fail('QUERY_RESULT_BUDGET','$','Query result exceeds 32MiB')
    out=new_output(output,[safe(p) for p in inputs if p]);write_json(out/'inspection.json',result)
    return result


def query_methods(source,expected,output,*,member=None,type_name='',method='',module=None,function=None,limit=20):
    limit_value(limit)
    if function is not None and (type(function) is not int or function<0):fail('METHOD_FUNCTION','$','Expected a nonnegative function index')
    selected=[];matched=0;selected_bytes=0
    with opened(source,expected,member) as stream:
        cursor=JsonRows(stream)
        for row in cursor.rows():
            if (not isinstance(row,dict) or any(not isinstance(row.get(k),str) for k in ('type','name','module'))
                    or type(row.get('function')) is not int or row['function']<0):
                fail('METHOD_MAP_ROW',str(cursor.count),'Expected module/type/name and exact function index')
            if (type_name.casefold() not in row['type'].casefold() or method.casefold() not in row['name'].casefold()
                    or (module is not None and row['module']!=module) or (function is not None and row['function']!=function)):continue
            matched+=1
            if len(selected)<limit:
                selected_bytes+=len(encoded(row))
                if selected_bytes>RESULT_BYTES//2:fail('QUERY_RESULT_BUDGET','$','Selected method rows exceed budget')
                selected.append(row)
        identity=stream.identity()
    return report(output,'query-methods',[identity],dict(status='verified-metadata',rows=selected,totalRows=cursor.count,
        matches=matched,returned=len(selected),limited=matched>len(selected),methodBodiesRecovered=0,
        limitations=['Function/module mappings are metadata, not recovered C# bodies or proof of original module provenance.']),[source])


def table_manifest(path,expected):
    rows={};folded=set();parents=set();total=0
    import unicodedata
    with opened(path,expected) as stream:
        for row in JsonRows(stream).rows('files'):
            if not isinstance(row,dict):fail('TABLE_MANIFEST','$','Expected table row')
            name=relative(row.get('name',''));key=unicodedata.normalize('NFC',name).casefold()
            size=row.get('bytes');checksum(row.get('sha256'))
            parts=key.split('/');ancestors={'/'.join(parts[:i]) for i in range(1,len(parts))}
            if key in folded or key in parents or ancestors & folded or type(size) is not int or not 0<=size<=512*1024**2:
                fail('TABLE_MANIFEST',name,'Duplicate table name or invalid size')
            folded.add(key);parents.update(ancestors);rows[name]=row;total+=size
            if len(rows)>WHOLE_FILES or total>WHOLE_BYTES:fail('TABLE_MANIFEST_BUDGET','$','Table manifest exceeds policy')
        identity=stream.identity()
    return rows,identity


def query_tables(manifest,expected_manifest,output,*,source=None,expected=None,member=None,contains='',extract=None,limit=30):
    limit_value(limit);rows,identity=table_manifest(manifest,expected_manifest)
    matches=[r for n,r in rows.items() if contains.casefold() in n.casefold()]
    result=dict(status='verified-manifest',totalTables=len(rows),matches=len(matches),returned=min(limit,len(matches)),
                limited=len(matches)>limit,rows=matches[:limit],contentVerified=False,
                limitations=['Table names/variants remain distinct; listing verifies manifest metadata, not every table payload.'])
    sources=[identity];out=None
    if extract is not None:
        if extract not in rows:fail('TABLE_NOT_FOUND',str(extract),'Exact manifest table name required')
        if not source or not expected:fail('TABLE_SOURCE','$','Extraction requires exact source/member SHA256')
        # Only one nested archive is spooled; no table directory or original project is expanded.
        with tempfile.TemporaryFile() as frozen,opened(source,expected,member) as stream:
            while True:
                raw=stream.read()
                if not raw:break
                frozen.write(raw)
            sources.append(stream.identity());frozen.seek(0)
            with zipfile.ZipFile(frozen) as archive:
                index=zip_index(archive)
                if set(index)!=set(rows) or any(index[n].file_size!=r['bytes'] for n,r in rows.items()):
                    fail('TABLE_ARCHIVE_MANIFEST','$','Archive entries differ from the complete table manifest')
                row=rows[extract]
                # Reuse the bounded stream verifier, then publish a single create-only result.
                from .evidence_stream import VerifiedStream
                with archive.open(index[extract]) as raw,tempfile.TemporaryFile() as payload:
                    view=VerifiedStream(raw,row['bytes'],row['sha256'],extract)
                    while True:
                        chunk=view.read()
                        if not chunk:break
                        payload.write(chunk)
                    result.update(status='verified-selected-table',contentVerified=True,selected=row)
                    payload.seek(0)
                    if len(encoded(dict(sources=sources,**result)))>RESULT_BYTES:fail('QUERY_RESULT_BUDGET','$','Result exceeds budget')
                    out=new_output(output,[safe(manifest),safe(source)])
                    target=inside(out,'payload/'+extract);target.parent.mkdir(parents=True,exist_ok=True)
                    with target.open('xb') as dest:
                        for chunk in iter(lambda:payload.read(1024**2),b''):dest.write(chunk)
                    result['extractedPath']=target.relative_to(out).as_posix()
    elif source or expected or member:
        fail('TABLE_QUERY_ARGUMENTS','$','Source/archive identity is used only with explicit --extract')
    if out is not None:
        result=dict(schemaVersion=1,toolVersion=__version__,operation='query-tables',sourceCodeExecuted=False,sources=sources,**result)
        write_json(out/'inspection.json',result);return result
    return report(output,'query-tables',sources,result,[manifest])


def inspect_aliases(source,expected,output,*,member=None,alias=None,limit=20,content_source=None,content_prefix=''):
    limit_value(limit);urls={};paths={};content={}
    if content_source and alias is None:fail('ALIAS_SELECTION','$','Select one exact alias before payload verification')
    if content_prefix:content_prefix=relative(content_prefix).rstrip('/')+'/'
    with opened(source,expected,member) as stream:
        cursor=JsonRows(stream)
        for row in cursor.rows('entries'):
            if not isinstance(row,dict):fail('RESOURCE_ALIAS','$','Expected alias row')
            url=row.get('url');path=relative(row.get('path',''));size=row.get('bytes');digest=checksum(row.get('sha256'))
            if not isinstance(url,str) or not url or len(url)>16384 or any(ord(c)<32 for c in url) or type(size) is not int or not 0<=size<=512*1024**2:
                fail('RESOURCE_ALIAS',str(url),'Invalid URL alias or content size')
            signature=(digest,size)
            if url in urls or (path in paths and paths[path]!=signature):fail('RESOURCE_ALIAS_CONFLICT',url,'Duplicate URL or conflicting content identity')
            if digest in content and content[digest]['bytes']!=size:fail('RESOURCE_ALIAS_CONFLICT',url,'Same content hash has conflicting size')
            urls[url]=dict(url=url,path=path,bytes=size,sha256=digest);paths[path]=signature
            group=content.setdefault(digest,dict(bytes=size,aliases=0));group['aliases']+=1
            if len(urls)>WHOLE_FILES:fail('RESOURCE_ALIAS_BUDGET','$','Too many URL aliases')
        identity=stream.identity()
    if alias is not None and alias not in urls:fail('RESOURCE_ALIAS_NOT_FOUND',alias,'Exact URL key required; no normalization/version guessing')
    chosen=urls.get(alias);matched=[r for r in urls.values() if chosen is None or r['sha256']==chosen['sha256']]
    result=dict(status='verified-alias-index',routes=len(urls),uniqueContent=len(content),
                aliasGroups=sum(v['aliases']>1 for v in content.values()),rows=matched[:limit],matches=len(matched),
                returned=min(limit,len(matched)),limited=len(matched)>limit,contentVerified=False,
                limitations=['URL keys are exact data, never fetched or decoded; only explicitly verified payload content is proven.'])
    sources=[identity]
    if content_source:
        location=content_prefix+chosen['path'];base=safe(content_source)
        if base.is_dir():
            with RootReader(base) as view:digest,size=view.digest(location)
            if digest!=chosen['sha256'] or size!=chosen['bytes']:fail('RESOURCE_CONTENT_DRIFT',alias,'Selected content differs')
            proof=dict(source=str(base)+'/'+location,sha256=digest,bytes=size,verified=True)
        else:
            with opened(base,chosen['sha256'],location) as stream:
                while stream.read():pass
                proof=stream.identity()
            if proof['bytes']!=chosen['bytes']:fail('RESOURCE_CONTENT_DRIFT',alias,'Selected content size differs')
        sources.append(proof);result.update(status='verified-selected-alias-content',contentVerified=True,selected=chosen)
    return report(output,'inspect-aliases',sources,result,[source,content_source])
