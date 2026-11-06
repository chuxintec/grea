"""Declared binary config assets -> JSON tables and reconstructable source index."""
import re
from pathlib import Path
from .bon import decode,BonError
from ..io import sha,encoded,write_json
from ..layout import casing
from ..layout.standard import find_analysis
from ..targets import unity,cocos

CODEC='bon-tagged-le-v1'


def codec_evidence(rows,read_source):
    """Positive static evidence for this dialect, not extension/magic guessing."""
    evidence=[]
    for row in rows:
        if row.get('suffix')!='.js':continue
        raw=read_source(row)
        if (re.search(rb'globalThis\.bon\s*=\s*\{encode:',raw)
            and all(token in raw for token in (b'case 1:return this.dr.readInt32()',
                b'case 2:return this.dr.readInt64()',b'case 99:return this.strArr[this.dr.read7BitInt()]'))):
            evidence.append(dict(path=row['path'],sha256=sha(raw),codec=CODEC))
    return evidence


def export_tables(project,assets,rows,read_source,naming,namespace):
    project=Path(project);by_path={r['path']:r for r in rows}
    candidates=[a for a in assets if a.get('sourceType')=='cc.BufferAsset'
        and isinstance(a.get('logicalKey'),list) and isinstance(a['logicalKey'][0],str)
        and a['logicalKey'][0].split('/')[0].lower() in ('config','configs')]
    evidence=codec_evidence(rows,read_source) if candidates else []
    packs=[];pending=[]
    for asset in sorted(candidates,key=lambda a:a['sourceId']):
        pack=dict(sourceId=asset['sourceId'],bundle=asset['bundle'],logicalKey=asset['logicalKey'][0],
                  status='needs_adapter',tables=[],runtimeBinding='not_verified')
        packs.append(pack)
        sources=[by_path[p] for p in asset['sourceFiles'] if p in by_path and Path(p).suffix.lower()=='.bin']
        if len(sources)!=1:pack['reason']='Expected exactly one declared binary config source';continue
        source=sources[0];pack.update(sourcePath=source['path'],sourceSha256=source['sha256'],sourceBytes=source['bytes'])
        if not evidence:pack['reason']='No supported static BON decoder evidence in supplied inputs';continue
        raw=read_source(source)
        if sha(raw)!=source['sha256']:raise ValueError('Config source hash changed: '+source['path'])
        try:data=decode(raw)
        except BonError as error:pack['reason']=str(error);continue
        pack.update(status='json_exported',codec=CODEC,bytesConsumed=len(raw),rootType='object',tableCount=len(data))
        # Regional variants stay separate. Never merge/select overrides implicitly.
        group=asset['logicalKey'][0].split('/')[-1]
        if group.lower()=='config':group='Base'
        for key,value in data.items():
            identity=asset['sourceId']+'/table/'+key
            metadata=dict(bundle=asset['bundle'],logicalPath='Config/'+group+'/'+casing.pascal(key),sourceName=key)
            pending.append((identity,metadata,value,pack,key))
    naming.reserve([(sid,'config','.json','',meta,None) for sid,meta,_,_,_ in pending])
    for sid,meta,value,pack,key in pending:
        path=naming.path(sid,'config','.json',metadata=meta);raw=encoded(value)
        target=project/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        uid=unity.guid(namespace,sid) if naming.engine=='unity' else cocos.identity(namespace,sid)
        if naming.engine=='unity':Path(str(target)+'.meta').write_text('fileFormatVersion: 2\nguid: '+uid+'\n',encoding='utf-8')
        else:write_json(Path(str(target)+'.meta'),cocos.meta(uid,'json','2.0.1'))
        pack['tables'].append(dict(key=key,jsonPointer='/'+key.replace('~','~0').replace('/','~1'),path=path,
            sha256=sha(raw),bytes=len(raw),targetId=uid,entries=len(value) if isinstance(value,(dict,list)) else None))
    result=dict(schemaVersion=1,codecEvidence=evidence,packs=packs,
        exportedPacks=sum(p['status']=='json_exported' for p in packs),
        exportedTables=sum(len(p['tables']) for p in packs),needsAdapter=sum(p['status']=='needs_adapter' for p in packs),
        semantics='Each JSON is one original top-level value. Reconstruct root using table.key. No locale merging or key/value translation.')
    write_json(find_analysis(project,'config.json'),result)
    lines=['# 游戏配置表 JSON','','索引：`../Analysis/Mappings/config.json`。按源包分别保存；地区覆盖和语言表未合并。',
        '每个 JSON 对应原 BON 的一个顶层键；键名、ID、数值、中文内容保持原值。原始二进制仍在资源台账中。',
        '以下仅证明静态配置解码和导出，游戏运行时加载尚未绑定。','','| 来源 | 状态 | JSON 表数 |','| --- | --- | ---: |']
    for pack in packs:lines.append(f"| {pack['bundle']} / {pack['logicalKey']} | {pack['status']} | {len(pack['tables'])} |")
    for pack in packs:
        if pack['tables']:
            lines+=['',f"## {pack['bundle']} / {pack['logicalKey']}",'']
            for table in pack['tables']:
                lines.append('- ['+table['key'].replace('[','\\[').replace(']','\\]')+'](../'+table['path']+')')
    (project/'Docs').mkdir(exist_ok=True)
    (project/'Docs/CONFIGURATION.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result
