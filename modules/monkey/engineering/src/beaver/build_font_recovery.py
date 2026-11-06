"""Explicit reviewed before-image restoration for a pinned post-exit build drift.

This is separate from ordinary current-implementation recovery. The review is an
explicit caller input, not inferred ownership of unknown post-exit bytes.
"""
import re
from .io import safe,read,load,sha,encoded,inside,write_json
from .errors import fail
from .output_limits import digest_file
from .transaction_fs import lock,atomic


FIX11_IMPLEMENTATION = "44a1280aa75d7b720fa0bdfada800441e09dc76c95911ed1b00e2993725f766c"


def recover_reviewed(transaction,expected,review_path,output):
    from .unity import source_files,native_lock
    stage=safe(transaction);approval=safe(review_path);raw=read(approval);review=load(raw);expected_approval=sha(raw)
    keys={'schemaVersion','contract','transactionRoot','planSha256','sourceImplementationSha256','journalSha256','processSha256','reviewReference','reason','files'}
    if not isinstance(review,dict) or set(review)!=keys or type(review['schemaVersion']) is not int or review['schemaVersion']!=1 or review['contract']!='beaver-build-font-post-exit-recovery/1':
        fail('BUILD_FONT_REVIEW',str(approval),'Expected exact versioned recovery review')
    if review['planSha256']!=expected or review['sourceImplementationSha256']!=FIX11_IMPLEMENTATION:fail('BUILD_FONT_REVIEW_IDENTITY',str(approval),'Only explicitly pinned fix11 post-exit recovery is supported')
    for key in ['planSha256','sourceImplementationSha256','journalSha256','processSha256']:
        if not isinstance(review[key],str) or not re.fullmatch('[0-9a-f]{64}',review[key]):fail('BUILD_FONT_REVIEW',key,'Expected exact hash')
    if review['transactionRoot']!=str(stage) or any(not isinstance(review[k],str) or not review[k].strip() for k in ('reviewReference','reason')):fail('BUILD_FONT_REVIEW',str(stage),'Exact transaction and explicit caller review reference/reason required')
    plan_raw=read(stage/'unity-plan.json',max_bytes=128*1024**2);data=load(plan_raw,max_nodes=8_000_000)
    if sha(plan_raw)!=review['planSha256'] or data.get('implementationSha256')!=review['sourceImplementationSha256'] or data.get('contract')!='beaver-unity/1' or data.get('spec',{}).get('operation')!='build.macos':fail('BUILD_FONT_REVIEW',str(stage),'Pinned build plan differs')
    for name,key in [('journal.json','journalSha256'),('process.json','processSha256')]:
        if digest_file(stage/name)!=review[key]:fail('BUILD_FONT_REVIEW',name,'Pinned transaction evidence differs')
    journal=load(read(stage/'journal.json',max_bytes=128*1024**2),max_nodes=8_000_000);process=load(read(stage/'process.json'))
    if journal.get('planSha256')!=review['planSha256'] or journal.get('status')!='recovery-required' or journal.get('diagnostic',{}).get('code')!='BUILD_SOURCE_DRIFT' or process.get('owned') is not True or process.get('exited') is not True or process.get('exitCode')!=0:
        fail('BUILD_FONT_REVIEW',str(stage),'Expected recorded post-exit build source drift')
    rows=review['files'];fonts={row['path'] for row in data['spec'].get('tmpFontPolicy',{}).get('fonts',[])}
    if not isinstance(rows,list) or not 1<=len(rows)<=256:fail('BUILD_FONT_REVIEW','files','Explicit bounded font file set required')
    selected=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'path','beforeSha256','afterSha256'}:fail('BUILD_FONT_REVIEW','files','Unknown file row')
        path=row['path']
        if not isinstance(path,str) or path in selected or path not in fonts|{f+'.meta' for f in fonts}:fail('BUILD_FONT_REVIEW',str(path),'Only exact declared font source/meta paths may be reviewed')
        selected.add(path)
        if data['before'].get(path,{}).get('sha256')!=row['beforeSha256'] or journal.get('after',{}).get(path,{}).get('sha256')!=row['afterSha256'] or row['beforeSha256']==row['afterSha256']:
            fail('BUILD_FONT_REVIEW',path,'Before/after identities differ from pinned evidence')
        if not inside(stage/'before',path).is_file() or digest_file(inside(stage/'before',path))!=row['beforeSha256']:fail('BUILD_FONT_REVIEW',path,'Before-image differs')
    project=safe(data['projectRoot']);out=safe(output)
    if out.exists() or out.is_relative_to(project) or project.is_relative_to(out) or out.is_relative_to(stage) or stage.is_relative_to(out):fail('BUILD_FONT_REVIEW',str(out),'Fresh independent receipt directory required')
    with lock(project):
        native_lock(project)
        if digest_file(stage/"unity-plan.json")!=review["planSha256"] or digest_file(stage/"journal.json")!=review["journalSha256"] or digest_file(stage/"process.json")!=review["processSha256"]:fail("BUILD_FONT_REVIEW",str(stage),"Pinned evidence changed before lock acquisition")
        current=source_files(project)
        if {k:v for k,v in current.items() if k not in selected}!={k:v for k,v in data['before'].items() if k not in selected}:fail('BUILD_FONT_REVIEW',str(project),'Unreviewed source drift')
        for row in rows:
            if current.get(row['path'],{}).get('sha256') not in (row['beforeSha256'],row['afterSha256']):fail('BUILD_FONT_REVIEW',row['path'],'Later edit differs from explicit reviewed after-image')
        out.mkdir(parents=True);receipt=dict(contract=review['contract'],approvalSha256=expected_approval,planSha256=review['planSha256'],sourceImplementationSha256=review['sourceImplementationSha256'],status='restoring',restored=[],artifactCertified=False)
        write_json(out/'recovery-result.json',receipt)
        for row in rows:
            path=row['path'];dest=inside(project,path)
            if digest_file(dest) not in (row['beforeSha256'],row['afterSha256']):fail('BUILD_FONT_REVIEW',path,'Source changed after preflight')
            backup=inside(stage/'before',path);payload=read(backup,max_bytes=512*1024**2)
            if sha(payload)!=row['beforeSha256']:fail('BUILD_FONT_REVIEW',path,'Before-image changed after preflight')
            atomic(dest,payload);receipt['restored'].append(path);write_json(out/'recovery-result.json',receipt)
        if source_files(project)!=data['before']:fail('BUILD_FONT_REVIEW',str(project),'Restored full source differs')
        receipt.update(status='restored',sourceSha256=sha(encoded(data['before'])),editorStarted=False)
        write_json(out/'recovery-result.json',receipt)
        return dict(receipt,report=str(out/'recovery-result.json'))
