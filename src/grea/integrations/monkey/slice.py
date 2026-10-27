"""Compatibility contract extracted without changing existing tool IDs."""
import json,os
from grea.host.paths import Path
from grea.common import digest,hash_file,write_new,GreaError
from grea.safe_paths import canonical_path,disjoint,relative_name
from grea import runner,artifacts
from .identity import read


def collect_slice(workspace,version,resume_report=None):
    """Slice v1 is separate from package v1; only an executed resume can promote it."""
    root=canonical_path(workspace);base=read(root/'conversion.json');project=root/'project'
    if base.get('schemaVersion')!=1 or base.get('toolVersion')!=version or base.get('completed') is not True:raise ValueError('Unsupported or incomplete slice')
    if hash_file(project/'manifest.json')['sha256']!=base['candidateManifestSha256'] or hash_file(root/'inspect/source-manifest.json')['sha256']!=base['sourceManifestSha256']:raise ValueError('Slice stage identity changed')
    manifest=read(project/'manifest.json')
    if manifest.get('toolVersion')!=version or manifest.get('targetProfile')!=base['targetProfile']:raise ValueError('Slice target identity mismatch')
    if len(manifest['files'])>20000:raise ValueError('Slice file count limit')
    raw=base;native='not_run';evidence=[];native_hashes={}
    if resume_report is not None:
        report=canonical_path(resume_report)
        if not report.is_relative_to(root/'checks'):raise ValueError('Resume report outside owned checks')
        raw=read(report)
        for key in ('schemaVersion','toolVersion','candidateManifestSha256','sourceManifestSha256','targetProfile'):
            if raw.get(key)!=base.get(key):raise ValueError('Resume identity mismatch')
        if raw.get('resultKind')=='native' and raw.get('validation',{}).get('editor')=='pass':
            rb=read(project/'Analysis/editor-readback.json')
            if rb.get('unityVersion')!='6000.6.2f1' or rb.get('missingScripts')!=0 or rb.get('editableRoundtrip') is not True or not rb.get('nativeFiles'):raise ValueError('Native readback incomplete')
            if len(rb['nativeFiles'])>20000:raise ValueError('Native file count limit')
            remaining=512*1024**2
            for item in rb['nativeFiles']:
                file=project/relative_name(item['path'])
                if any(p.is_symlink() for p in (file,*file.parents)):raise ValueError('Linked native output')
                identity=hash_file(file,remaining);remaining-=identity['bytes']
                if identity['sha256']!=item['sha256']:raise ValueError('Native artifact changed after provider validation')
                if item['path'] in native_hashes:raise ValueError('Duplicate native identity')
                native_hashes[item['path']]=item['sha256']
            native='provider_verified_editor_readback';evidence=[hash_file(report),hash_file(project/'Analysis/editor-readback.json')]
    remaining=512*1024**2
    for item in manifest['files']:
        file=project/relative_name(item['path'])
        if any(p.is_symlink() for p in (file,*file.parents)):raise ValueError('Linked candidate output')
        identity=hash_file(file,remaining);remaining-=identity['bytes']
        if identity['sha256']!=native_hashes.get(item['path'],item['sha256']):raise ValueError('Candidate changed; explicit provider native resume or a new revision is required')
    status=raw.get('workflowStatus')
    if status not in ('needs_action','partial','blocked','failed','success'):raise ValueError('Unknown slice result')
    task=dict(project='project',taskId='grea-native-continuation',origin='grea_declared_boundary_not_translated_business',allowedPaths=['Assets/Game/'],nextAction='Declare a bounded module using original source evidence and actual native bindings; preserve generated ownership',verification=['source behavior contract','native compile','affected real input and persistence'])
    return dict(schema_version=1,provider='monkey',provider_version=version,status='partial' if native!='not_run' and status=='success' else 'needs_action' if status=='success' else status,result_kind='native' if native!='not_run' else 'candidate',provider_report=hash_file(root/'conversion.json'),projects=[dict(path='project',target_profile=base['targetProfile'],manifest_sha256=base['candidateManifestSha256'],source_manifest_sha256=base['sourceManifestSha256'],validation=raw.get('validation',{}))],detail_tasks=[task],next_action=raw.get('nextAction'),native_validation=native,native_evidence=evidence,limitations=['Native Editor readback is not real input, visual/business parity or Player acceptance.','The GREA continuation boundary is declared, not automatically translated source business. Generated graph and source text are data, not runtime code.'])
