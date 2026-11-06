"""Freeze an additive native/code handoff layer without altering prior failure evidence."""
from pathlib import Path
import shutil
from .io import safe,inside,read,load,sha,new_output,write_json
from .providers.assetripper import fingerprint
from .sources.compiled import fail
from .layout.standard import find_analysis


def freeze(candidate,contract,verification,output,expected_manifest,apply_owned=False):
    root=safe(candidate);contract=safe(contract);verification=safe(verification)
    original=read(root/'manifest.json',max_bytes=128*1024**2)
    if sha(original)!=expected_manifest:fail('BULK_FREEZE_MANIFEST_CHANGED',str(root),'Exact owned candidate manifest required')
    identity=load(read(contract,max_bytes=128*1024**2),max_nodes=16_000_000,max_depth=128);checked=load(read(verification,max_bytes=128*1024**2),max_nodes=8_000_000)
    if identity.get('sourceManifestSha256')!=expected_manifest or checked.get('candidateManifestSha256')!=expected_manifest or checked.get('diagnostics')or checked.get('staticValidation')!='pass'or checked.get('editorValidation')not in ('pass','partial'):fail('BULK_FREEZE_PROOF',str(root),'Exact native identity contract and zero-diagnostic static/editor verification required')
    finish=load(read(find_analysis(root,'bulk-finish-readback.json')));raw=read(find_analysis(root,'editor-readback.json'),max_bytes=128*1024**2)
    if finish.get('status')!='completed'or identity['nativeReadbackSha256']!=sha(raw):fail('BULK_FREEZE_NATIVE',str(root),'Successful source-bound incremental proof required')
    for row in [*identity['prefabs'],*[r for r in identity['sourceScenes']if r['status']!='excluded']]:
        if fingerprint(inside(root,row['path']))!=row['sha256']:fail('BULK_FREEZE_ASSET_CHANGED',row['path'],'Saved native asset changed')
    for row in identity['sprites']:
        if fingerprint(inside(root,row['path']+'.meta'))!=row['importerMetaSha256']:fail('BULK_FREEZE_IMPORTER_CHANGED',row['path'],'Actual Sprite importer changed')
    named=load(read(find_analysis(root,'named-code-handoff.json'),max_bytes=128*1024**2),max_nodes=8_000_000)
    if named.get('methodsImplemented')!=0 or named.get('sourceExecuted')is not False:fail('BULK_FREEZE_CODE_STATUS',str(root),'Named TODO drafts must retain explicit implementation status')
    additions=['Analysis/Readback/native-identity-contract.json','Analysis/Readback/initial-editor-verification.json','Analysis/Tasks/initial-handoff.json','Docs/BULK-INITIAL-HANDOFF.md']
    if any(inside(root,r).exists()for r in additions):fail('BULK_FREEZE_EXISTS',str(root),'Never overwrite a frozen/manual handoff layer')
    out=new_output(output,[root,contract,verification]);(out/'original-manifest.json').write_bytes(original)
    report=dict(schemaVersion=1,status='editable-initial',previousManifestSha256=expected_manifest,nativeReadbackSha256=sha(raw),incrementalReadbackSha256=fingerprint(find_analysis(root,'bulk-finish-readback.json')),nativeContractSha256=fingerprint(contract),verificationSha256=fingerprint(verification),counts=dict(identity['counts'],codeModules=named['modules'],namedMethods=named['namedMembers'],fieldDeclarations=named['fieldDeclarations'],implementedMethods=0),sourceLimitations='Analysis/Readback/editor-readback.json diagnostics retained verbatim',business='not_run',player='not_run',visual='not_run',codeCompiled=False)
    write_json(out/'initial-handoff.json',report)
    if not apply_owned:return dict(status='planned',report=str(out/'initial-handoff.json'))
    shutil.copy2(contract,root/additions[0]);shutil.copy2(verification,root/additions[1]);write_json(root/additions[2],report)
    (root/additions[3]).write_text('''# Editable bulk initial handoff

Open this folder in Unity 6000.6.2f1. Start with Docs/AI-ENTRY.md and Analysis/Tasks/initial-handoff.json.
Source SceneAssets are Assets/Game/Scenes/Sources/main/main.unity and room16_test.unity; the latter remains an original test scene, not completed mainline gameplay. The mini-game Scene is excluded with original evidence retained.
Analysis/Readback/native-identity-contract.json binds source IDs to actual Sprite/Prefab/Scene GUIDs and local fileIDs, importer settings, geometry and saved PPtrs. Preserve existing game-side manual border/geometry; byte or GUID equality alone does not authorize replacement.
SourceRecovery/CodeDrafts/NamedCSharp contains named, noncompiled TODO drafts; Analysis/Code/named-code-handoff.json links literal source modules, members and exact byte/hash evidence. No original business method is claimed implemented.
Analysis/Readback/editor-readback.json retains original source limitations. Analysis/Readback/bulk-finish-readback.json is the separate successful incremental layer. Previous failed checks remain in the execution journals; this initial project does not imply Player, gameplay or pixel parity acceptance.
''')
    manifest=load(original,max_nodes=16_000_000,max_depth=128);manifest['bulkInitialHandoff']=report
    manifest['coverage']['nativeObjects']='actual-native-readback';manifest['editorValidation']=checked['editorValidation'];manifest['resultKind']='editable-initial';manifest['status']='partial'
    # Library/Temp and local logs are rebuildable execution state, not shipped project files.
    files=[]
    for directory in ['Assets','Packages','ProjectSettings','Analysis','Docs','SourceRecovery']:
        for path in sorted((root/directory).rglob('*')):
            if path.is_file():
                safe(path);files.append(dict(path=path.relative_to(root).as_posix(),sha256=fingerprint(path),bytes=path.stat().st_size,owner='manual'if path.relative_to(root).as_posix().startswith('Assets/Manual/')else'generated'))
    if (root/'AGENTS.md').is_file():files.append(dict(path='AGENTS.md',sha256=fingerprint(root/'AGENTS.md'),bytes=(root/'AGENTS.md').stat().st_size,owner='generated'))
    manifest['files']=files;manifest['nativeProjectFiles']=dict(count=len(files),bytes=sum(r['bytes']for r in files),excludes=['Library','Temp','Logs','UserSettings'])
    write_json(root/'manifest.json',manifest)
    result=dict(status='frozen-initial',manifestSha256=fingerprint(root/'manifest.json'),files=len(files),bytes=manifest['nativeProjectFiles']['bytes'],counts=report['counts'],candidate=str(root),report=str(out/'freeze-result.json'))
    write_json(out/'freeze-result.json',result);return result
