"""Closed build font policy and interrupted-build recovery guards."""
import re
from .errors import fail
from .io import inside,read,load,write_json
from .output_limits import digest_file


def validate(policy):
    if not isinstance(policy,dict) or set(policy)!={'schemaVersion','fonts'} or type(policy['schemaVersion']) is not int or policy['schemaVersion']!=1:
        fail('BUILD_FONT_POLICY','spec','Expected schemaVersion=1 and fonts')
    fonts=policy['fonts']
    if not isinstance(fonts,list) or not 1<=len(fonts)<=128:fail('BUILD_FONT_POLICY','spec','Expected 1..128 explicit fonts')
    seen=set()
    for row in fonts:
        if not isinstance(row,dict) or set(row)!={'path','guid','sourceSha256','metaSha256','normalizeDynamicAtlas'}:fail('BUILD_FONT_POLICY','spec','Unknown or missing font fields')
        p=row['path']
        if not isinstance(p,str) or not p.startswith('Assets/') or not p.endswith('.asset') or '\\' in p or ':' in p or any(x in ('','.','..') for x in p.split('/')) or any(ord(c)<32 for c in p):fail('BUILD_FONT_PATH',str(p),'Expected explicit asset path')
        if p.casefold() in seen:fail('BUILD_FONT_POLICY',p,'Duplicate font')
        seen.add(p.casefold())
        for k,n in [('guid',32),('sourceSha256',64),('metaSha256',64)]:
            if not isinstance(row[k],str) or not re.fullmatch('[0-9a-f]{'+str(n)+'}',row[k]):fail('BUILD_FONT_IDENTITY',p,'Expected exact lowercase identity')
        if type(row['normalizeDynamicAtlas']) is not bool:fail('BUILD_FONT_POLICY',p,'Normalization must be boolean')


def check_sources(project,policy,files):
    validate(policy)
    for row in policy['fonts']:
        p=row['path']
        if files.get(p,{}).get('sha256')!=row['sourceSha256'] or files.get(p+'.meta',{}).get('sha256')!=row['metaSha256']:fail('BUILD_FONT_SOURCE',p,'Font source or metadata differs')
        meta=read(inside(project,p+'.meta'))
        if not re.search(rb'^guid:\s*'+row['guid'].encode()+rb'\s*$',meta,re.M):fail('BUILD_FONT_GUID',p,'Font metadata GUID differs')


def recover(stage,data,editor,expected,timeout):
    from . import unity
    from .transaction_fs import lock
    project=unity.safe(data['projectRoot']);editor=unity.editor_path(editor)
    journal=load(read(stage/'journal.json'));process=load(read(stage/'process.json'))
    if journal.get('planSha256')!=expected or journal.get('status')!='recovery-required' or process.get('exited') is not True:fail('BUILD_FONT_RECOVERY',str(stage),'Exited recoverable build required')
    with lock(project):
        unity.native_lock(project)
        checkpoint=load(read(stage/'font-checkpoint.json'))
        if checkpoint.get('planSha256')!=expected or checkpoint.get('mutationInProgress'):fail('BUILD_FONT_RECOVERY',str(stage),'Missing conclusive mutation checkpoint')
        rows=checkpoint.get('fonts',[]);policy=data['spec']['tmpFontPolicy'];validate(policy)
        if [r.get('path') for r in rows]!=[r['path'] for r in policy['fonts']]:fail('BUILD_FONT_RECOVERY',str(stage),'Checkpoint font set differs')
        allowed={r['path']+s for r in rows for s in ('','.meta')};current=unity.source_files(project)
        if {k:v for k,v in current.items() if k not in allowed}!={k:v for k,v in data['before'].items() if k not in allowed}:fail('BUILD_FONT_RECOVERY',str(stage),'Unrelated source changed')
        for row,declared in zip(rows,policy['fonts']):
            for suffix,key,observed in [('', 'sourceSha256','observedSha256'),('.meta','metaSha256','observedMetaSha256')]:
                p=row['path']+suffix;backup=inside(stage/'before',p)
                if not backup.is_file() or digest_file(backup)!=declared[key]:fail('BUILD_FONT_RECOVERY',p,'Before-image differs')
                if current.get(p,{}).get('sha256') not in (declared[key],row.get(observed)):fail('BUILD_FONT_RECOVERY',p,'Later source edit')
        helper,fingerprint=unity._install_native_helper(project)
        try:
            result=unity.run(editor,project,stage,'recover',data,timeout)
        finally:unity._remove_native_helper(project,helper,fingerprint)
        if unity.source_files(project)!=data['before']:fail('BUILD_FONT_RECOVERY',str(stage),'Restored source differs')
        journal.update(status='recovered',nativeRecovery=result);write_json(stage/'journal.json',journal)
        return dict(status='recovered',report=str(stage/'journal.json'),transaction=str(stage))


def validate_readback(policy,report):
    rows=report.get('fontInputs')
    if report.get('fontSourcesRestored') is not True or not isinstance(rows,list) or len(rows)!=len(policy['fonts']):fail('BUILD_FONT_READBACK','native','Font restoration evidence missing')
    for declared,row in zip(policy['fonts'],rows):
        for key in ('path','sourceSha256','metaSha256'):
            if row.get(key)!=declared[key]:fail('BUILD_FONT_READBACK',declared['path'],'Font input identity differs')
        if row.get('restoredSha256')!=declared['sourceSha256'] or not re.fullmatch('[0-9a-f]{64}',row.get('buildSha256','')):fail('BUILD_FONT_READBACK',declared['path'],'Build/restoration identity missing')
