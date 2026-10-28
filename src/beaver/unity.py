"""Bounded native Unity jobs, immutable plans and create-only build artifacts."""
from pathlib import Path
from datetime import datetime, timezone
import os
import plistlib
import re
import signal
import subprocess
import time
import unicodedata
from .io import safe, inside, read, load, sha, encoded, write_json, new_output
from .errors import fail,BeaverError
from .output_limits import digest_file,copy_verified
from .adoption import project_files, native_lock
from .transaction_fs import lock
from .context import inspect
from .output_limits import BUILD_FILE_BYTES

HELPER_ROOT = "Assets/BeaverTools"
HELPER = HELPER_ROOT + "/Editor/BeaverNative.cs"
VERSION = "6000.6.2f1"
MOVE_MANIFEST_ENTRIES = 10000
MOVE_MANIFEST_BYTES = 256 * 1024**2
META_GUID = re.compile(rb'^guid:\s*([a-f0-9]{32})\s*$',re.M)
SHA256_HEX = re.compile(r'^[a-f0-9]{64}$')


def identity():
    from .implementation import identity as package_identity
    return package_identity()


def asset_path(value, suffix):
    if not isinstance(value, str) or not value.startswith("Assets/") or not value.endswith(suffix) or "\\" in value or any(p in ("", ".", "..") for p in value.split("/")):
        fail("UNITY_ASSET_PATH", str(value), "Expected canonical Assets path with " + suffix)
    if value == HELPER_ROOT or value.startswith(HELPER_ROOT + "/"):
        fail("UNITY_RESERVED_PATH", value, "Reserved temporary Editor helper root")


def asset_folder_path(value):
    if not isinstance(value, str) or not value.startswith("Assets/") or "\\" in value or any(p in ("", ".", "..") for p in value.split("/")):
        fail("UNITY_ASSET_PATH", str(value), "Expected canonical folder path below Assets")
    if value == HELPER_ROOT or value.startswith(HELPER_ROOT + "/"):
        fail("UNITY_RESERVED_PATH", value, "Reserved temporary Editor helper root")


def unity_asset_file_path(value):
    if not isinstance(value,str) or not value.startswith('Assets/') or value.endswith('.meta') or '\\' in value or any(p in ('','.','..') for p in value.split('/')):
        fail('UNITY_ASSET_PATH',str(value),'Expected canonical imported file path below Assets')
    if value==HELPER_ROOT or value.startswith(HELPER_ROOT+'/'):
        fail('UNITY_RESERVED_PATH',value,'Reserved temporary Editor helper root')


def meta_guid(raw,path):
    found=META_GUID.findall(raw)
    if len(found)!=1:
        fail('ASSET_RETIRE_META_GUID',path,'Expected one static 32-character Unity GUID in metadata')
    return found[0].decode('ascii')


def resource_key(path):
    parts=Path(path).parts
    roots=[index for index,part in enumerate(parts[:-1]) if part=='Resources']
    if not roots:return None
    if len(roots)!=1:
        fail('ASSET_RETIRE_RESOURCE_PATH',path,'Nested Resources roots are ambiguous')
    relative=Path(*parts[roots[0]+1:])
    return relative.with_suffix('').as_posix()


def source_only_evidence(project, spec_path, files, path, guid, declaration, cache):
    """Bind one explicit no-persistent-object collector row to current bytes."""
    from . import build_filter
    raw_ref=declaration['sourceIdentityEvidence']
    snapshot_path=Path(raw_ref['snapshotPath'])
    if not snapshot_path.is_absolute():snapshot_path=Path(spec_path).parent/snapshot_path
    snapshot_path=safe(snapshot_path)
    expected_sha=raw_ref['snapshotSha256'];absolute=str(snapshot_path);cache_key=(absolute,expected_sha)
    if any(cached_path==absolute and cached_sha!=expected_sha for cached_path,cached_sha in cache):
        fail('ASSET_RETIRE_SOURCE_EVIDENCE_HASH',absolute,'One plan cannot bind different snapshot hashes for the same evidence path')
    cached=cache.get(cache_key)
    if cached is None:
        snapshot_raw=read(snapshot_path,max_bytes=128*1024**2)
        snapshot=load(snapshot_raw,max_nodes=8_000_000)
        snapshot_sha=sha(snapshot_raw)
        if snapshot_sha!=expected_sha:
            fail('ASSET_RETIRE_SOURCE_EVIDENCE_HASH',absolute,'Collector snapshot digest differs from the explicit evidence reference')
        if not isinstance(snapshot,dict) or not isinstance(snapshot.get('target'),str) or not isinstance(snapshot.get('pipeline'),str):
            fail('ASSET_RETIRE_SOURCE_EVIDENCE_SCHEMA',absolute,'Collector snapshot needs explicit target and pipeline')
        validated,_,_=build_filter._snapshot(snapshot,dict(platform=snapshot['target'],pipeline=snapshot['pipeline']),require_runner=True)
        raw_rows={row['path']:row for row in snapshot['assets']}
        cached=(snapshot_sha,snapshot,validated,raw_rows)
        cache[cache_key]=cached
    snapshot_sha,snapshot,validated,raw_rows=cached
    target=validated.get(path)
    if target is None or target.get('status')!='unknown' or target.get('identityStatus')!='no-persistent-object' or target.get('objectCount')!=0 or target.get('localIds')!=[] or target.get('types')!=[]:
        fail('ASSET_RETIRE_SOURCE_EVIDENCE_STATE',path,'Collector must classify this exact asset as unknown with zero objects and no persistent IDs/types')
    target_guid=target.get('guid')
    if not target.get('error') or not isinstance(target_guid,str) or target_guid.lower()!=guid.lower():
        fail('ASSET_RETIRE_SOURCE_EVIDENCE_GUID',path,'Collector row must retain the exact current native/meta GUID and a failure reason')
    row=raw_rows.get(path)
    if row is None:fail('ASSET_RETIRE_SOURCE_EVIDENCE_ROW',path,'Exact collector target row is missing')
    target_inputs=[]
    for relative in (path,path+'.meta'):
        recorded=snapshot.get('inputState',{}).get(relative);current=files.get(relative)
        if not isinstance(recorded,dict) or set(recorded)!={'sha256','bytes'} or current is None or recorded!=dict(sha256=current['sha256'],bytes=current['bytes']):
            fail('ASSET_RETIRE_SOURCE_EVIDENCE_INPUT',relative,'Collector input hash/bytes do not match the current source and metadata')
        target_inputs.append(dict(path=relative,sha256=recorded['sha256'],bytes=recorded['bytes']))
    return dict(snapshotPath=str(snapshot_path),snapshotSha256=snapshot_sha,assetPath=path,
                targetRecordSha256=sha(encoded(row)),targetRecord=row,targetInputs=target_inputs)


def folder_move_manifest(project, files, source, target):
    """Bind a directory move to the complete imported subtree and its file hashes."""
    root=inside(project,source)
    if not root.is_dir():
        fail('ASSET_MOVE_SOURCE',source,'Expected an imported Unity folder')
    entries=[];total=0
    directories=[root,*sorted(p for p in root.rglob('*') if p.is_dir())]
    for directory in directories:
        rel=directory.relative_to(project).as_posix()
        meta=rel+'.meta'
        if meta not in files:
            fail('ASSET_MOVE_INCOMPLETE_META',meta,'Every moved folder must have its existing Unity meta file')
        entries.append(dict(source=rel,target=target+rel[len(source):],kind='folder'))
    prefix=source+'/'
    paths=[p for p in files if p==source+'.meta' or p.startswith(prefix)]
    if source+'.meta' not in files:
        fail('ASSET_MOVE_INCOMPLETE_META',source+'.meta','Source folder meta is required')
    for path in paths:
        rel=path[len(source):]
        if path.endswith('.meta'):
            # Folder .meta files have a matching directory entry; retain them as
            # ordinary manifest files so transaction audit sees exact bytes.
            kind='meta'
        else:
            kind='asset'
            if path+'.meta' not in files:
                fail('ASSET_MOVE_INCOMPLETE_META',path+'.meta','Every moved asset must have its existing Unity meta file')
        row=files[path]
        total+=row['bytes']
        entries.append(dict(source=path,target=target+rel,kind=kind,sha256=row['sha256'],bytes=row['bytes']))
    # Directories are represented by their own paths and their meta file rows.
    # Reject symlinks and anything that Unity has not imported with a .meta.
    if len(entries)>MOVE_MANIFEST_ENTRIES or total>MOVE_MANIFEST_BYTES:
        fail('ASSET_MOVE_BUDGET',source,'Folder manifest exceeds 10000 entries or 256 MiB; split into reviewed independent subtrees')
    entries.sort(key=lambda row:(row['source'].casefold(),row['source']))
    return dict(source=source,target=target,entries=entries,bytes=total)


def validate_spec(doc):
    operation = doc.get("operation")
    allowed = {"schemaVersion", "operation"}
    if operation == "ui.create":
        allowed |= {"prefabPath", "scenePath", "fontAssetPath", "sourceFontPath", "tmpSettingsPath", "width", "height", "nodes"}
        asset_path(doc.get("prefabPath"), ".prefab")
        asset_path(doc.get("scenePath"), ".unity")
        asset_path(doc.get("fontAssetPath"), ".asset")
        font=doc.get('sourceFontPath')
        if not isinstance(font,str) or not font.endswith(('.ttf','.otf')):
            fail('UI_SOURCE_FONT','spec','Explicit project font source required; no guessed font or modal import')
        asset_path(font,Path(font).suffix)
        if 'tmpSettingsPath' in doc:
            asset_path(doc['tmpSettingsPath'],'.asset')
            if not doc['tmpSettingsPath'].endswith('/Resources/TMP Settings.asset'):
                fail('UI_TMP_SETTINGS','spec','Explicit TMP Settings asset must be in a Resources folder')
        if any(type(doc.get(k)) is not int or not 64 <= doc[k] <= 8192 for k in ("width", "height")):
            fail("UI_RESOLUTION", "spec", "Explicit reference dimensions 64..8192 required")
        nodes = doc.get("nodes")
        if not isinstance(nodes, list) or not 1 <= len(nodes) <= 1000:
            fail("UI_NODES", "spec", "Expected 1..1000 ordered nodes")
        ids, paths = set(), set()
        for n in nodes:
            if set(n) - {"id", "name", "parent", "kind", "text", "x", "y", "width", "height", "fontSize", "color", "spriteGuid", "spriteLocalId"}:
                fail("UI_NODE_FIELD", "spec", "Unknown node field")
            if n.get("kind") not in ("panel", "list", "button", "text", "image") or not isinstance(n.get("id"), str) or not n['id'] or n['id'] in ids:
                fail("UI_NODE", "spec", "Unknown kind or duplicate/missing ID")
            if n.get("parent", "") not in ids | {""}:
                fail("UI_PARENT", n['id'], "Parent must precede child")
            if not isinstance(n.get("name"), str) or not n['name'] or any(c in n['name'] for c in ('/', '\\', '\t', '\n')):
                fail("UI_NAME", n['id'], "Expected simple nonempty node name")
            key=(n.get('parent',''), n['name'])
            if key in paths:
                fail("UI_NAME_COLLISION", n['id'], "Sibling names must be unique")
            paths.add(key)
            if any(type(n.get(k)) not in (int, float) or n[k] <= 0 for k in ("width", "height")):
                fail("UI_SIZE", n['id'], "Positive explicit node size required")
            for k in ('x','y','fontSize'):
                if k in n and type(n[k]) not in (int,float):
                    fail("UI_VALUE", n['id'], "Numeric layout value required")
            if 'color' in n and (not isinstance(n['color'],list) or len(n['color'])!=4 or any(type(x) not in (int,float) or not 0<=x<=1 for x in n['color'])):
                fail("UI_COLOR", n['id'], "Expected RGBA float array 0..1")
            if 'spriteGuid' in n:
                import re
                if not re.fullmatch('[a-f0-9]{32}',n['spriteGuid']) or type(n.get('spriteLocalId')) is not int:
                    fail("UI_SPRITE_ID",n['id'],"Explicit GUID and localID required")
            ids.add(n['id'])
    elif operation == "prefab.edit":
        allowed |= {"prefabPath", "edits"}
        asset_path(doc.get("prefabPath"), ".prefab")
        if not isinstance(doc.get("edits"), list) or not 1 <= len(doc["edits"]) <= 1000:
            fail("PREFAB_EDITS", "spec", "Expected explicit edits")
        for e in doc['edits']:
            if set(e)-{'nodePath','component','property','kind','value','targetNode','targetComponent','assetGuid','localId'} or e.get('kind') not in ('string','bool','int','float','object'):
                fail('PREFAB_EDIT_FIELD','spec','Unknown edit field or value kind')
            if not all(isinstance(e.get(k),str) and e[k] for k in ('component','property')) or not isinstance(e.get('nodePath',''),str):
                fail('PREFAB_EDIT_SHAPE','spec','Explicit component, node path and property required')
            if e['kind']!='object' and not isinstance(e.get('value'),str):
                fail('PREFAB_EDIT_VALUE','spec','Scalar edit value is an explicit invariant string')
            if e['kind']=='object' and not (e.get('assetGuid') or 'targetNode' in e):
                fail('PREFAB_EDIT_REFERENCE','spec','Explicit asset GUID/localID or prefab node reference required')
            if e.get('property','').split('.')[0] in ('m_Script','m_GameObject','m_Father','m_Children','m_CorrespondingSourceObject','m_PrefabInstance','m_PrefabAsset'):
                fail('PREFAB_IDENTITY_FIELD',e.get('property'),'Identity and hierarchy fields are not editable in this subset')
    elif operation == "build.macos":
        allowed |= {"scenes", "productName"}
        if not isinstance(doc.get("scenes"), list) or not doc["scenes"]:
            fail("BUILD_SCENES", "spec", "Explicit nonempty scene paths required")
        for p in doc["scenes"]:
            asset_path(p, ".unity")
        import re
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", doc.get("productName", "")):
            fail("BUILD_PRODUCT", "spec", "Expected simple app artifact name")
    elif operation == "prefab.inspect":
        allowed |= {"prefabPath"}
        asset_path(doc.get('prefabPath'),'.prefab')
    elif operation == 'validate.play':
        allowed |= {'scenePath','durationSeconds'}
        asset_path(doc.get('scenePath'),'.unity')
        if type(doc.get('durationSeconds')) is not int or not 1<=doc['durationSeconds']<=30:
            fail('PLAY_DURATION','spec','Explicit duration 1..30 seconds required')
    elif operation == 'project.import':
        pass
    elif operation == 'sprite.configure':
        allowed |= {'assetPath','pixelsPerUnit','pivot','maxSize','alphaIsTransparency'}
        asset_path(doc.get('assetPath'),'.png')
        if type(doc.get('pixelsPerUnit')) not in (int,float) or not 1<=doc['pixelsPerUnit']<=4096:
            fail('SPRITE_PPU','spec','Explicit pixelsPerUnit 1..4096')
        if not isinstance(doc.get('pivot'),list) or len(doc['pivot'])!=2 or any(type(x) not in (int,float) or not 0<=x<=1 for x in doc['pivot']):
            fail('SPRITE_PIVOT','spec','Explicit normalized pivot')
        if doc.get('maxSize') not in (32,64,128,256,512,1024,2048,4096,8192) or type(doc.get('alphaIsTransparency'))is not bool:
            fail('SPRITE_IMPORT','spec','Explicit maxSize and alphaIsTransparency required')
    elif operation == 'assets.move':
        allowed |= {'moves','directoryMoves'}
        file_moves=doc.get('moves',[]);directory_moves=doc.get('directoryMoves',[])
        if not isinstance(file_moves,list) or not isinstance(directory_moves,list) or not (file_moves or directory_moves) or len(file_moves)>10000 or len(directory_moves)>100:
            fail('ASSET_MOVES','spec','Expected 1..10000 file moves and/or 1..100 directory moves')
        sources=set();targets=set()
        for move in file_moves:
            if set(move)!={'source','target'}:
                fail('ASSET_MOVE','spec','Expected source and target only')
            for key in ('source','target'):
                asset_path(move[key],Path(move[key]).suffix)
                if move[key].endswith('.meta'):
                    fail('ASSET_MOVE_META',move[key],'Move the native asset, never its meta separately')
            if move['source'] in sources or move['target'] in targets or Path(move['source']).suffix!=Path(move['target']).suffix:
                fail('ASSET_MOVE_AMBIGUOUS','spec','Duplicate endpoints or extension change')
            sources.add(move['source']);targets.add(move['target'])
        for move in directory_moves:
            if set(move)!={'source','target'}:
                fail('ASSET_MOVE','spec','Expected source and target only for each directory move')
            for key in ('source','target'):asset_folder_path(move[key])
            if move['source']==move['target'] or move['source'] in sources or move['target'] in targets:
                fail('ASSET_MOVE_AMBIGUOUS','spec','Duplicate move endpoints')
            sources.add(move['source']);targets.add(move['target'])
        if sources & targets:
            fail('ASSET_MOVE_CYCLE','spec','Overlapping move endpoints require separate reviewed batches')
        endpoints=list(sources)+list(targets)
        for i,left in enumerate(endpoints):
            for right in endpoints[i+1:]:
                if left.startswith(right+'/') or right.startswith(left+'/'):
                    fail('ASSET_MOVE_OVERLAP','spec','Nested source/target paths require separate reviewed batches')
    elif operation == 'assets.retire':
        allowed |= {'retire','protectedRoots','resources'}
        items=doc.get('retire');roots=doc.get('protectedRoots');resources=doc.get('resources',[])
        if not isinstance(items,list) or not 1<=len(items)<=MOVE_MANIFEST_ENTRIES:
            fail('ASSET_RETIRE_ITEMS','spec','Expected 1..10000 explicit file retirement declarations')
        if not isinstance(roots,list) or not roots or len(roots)>1000:
            fail('ASSET_RETIRE_PROTECTED_ROOTS','spec','At least one explicit scene/config/code protected root is required')
        if not isinstance(resources,list) or len(resources)>MOVE_MANIFEST_ENTRIES:
            fail('ASSET_RETIRE_RESOURCES','spec','Expected an explicit bounded Resources key declaration list')
        selected=set()
        for item in items:
            base_fields={'path','role','reason','sourceEvidence'}
            allowed_item=base_fields|{'identityPolicy','sourceIdentityEvidence'}
            if not isinstance(item,dict) or not base_fields<=set(item) or set(item)-allowed_item:
                fail('ASSET_RETIRE_DECLARATION','spec','Each retirement requires path, role, reason and sourceEvidence')
            unity_asset_file_path(item.get('path'))
            policy=item.get('identityPolicy','native-object')
            if policy not in ('native-object','source-evidence-only'):
                fail('ASSET_RETIRE_IDENTITY_POLICY',item['path'],'Expected native-object or explicit source-evidence-only identity policy')
            if policy=='source-evidence-only':
                evidence=item.get('sourceIdentityEvidence')
                if 'identityPolicy' not in item or not isinstance(evidence,dict) or set(evidence)!={'snapshotPath','snapshotSha256','assetPath'}:
                    fail('ASSET_RETIRE_SOURCE_EVIDENCE',item['path'],'source-evidence-only requires identityPolicy and exactly snapshotPath, snapshotSha256, assetPath')
                if not isinstance(evidence.get('snapshotPath'),str) or not evidence['snapshotPath'].strip() or \
                   not isinstance(evidence.get('snapshotSha256'),str) or not SHA256_HEX.fullmatch(evidence['snapshotSha256']) or \
                   evidence.get('assetPath')!=item['path']:
                    fail('ASSET_RETIRE_SOURCE_EVIDENCE',item['path'],'Collector evidence reference must bind a SHA-256 snapshot and the exact selected path')
            elif 'sourceIdentityEvidence' in item:
                fail('ASSET_RETIRE_SOURCE_EVIDENCE',item['path'],'Collector source-only evidence is not accepted by native-object policy')
            if item['path'] in selected:fail('ASSET_RETIRE_DUPLICATE',item['path'],'Duplicate retirement path')
            selected.add(item['path'])
            for key in ('role','reason','sourceEvidence'):
                value=item.get(key)
                if not isinstance(value,str) or not value.strip() or len(value)>4096:
                    fail('ASSET_RETIRE_DECLARATION',item['path'],'Explicit nonempty role, reason and source evidence are required')
        seen_roots=set()
        for path in roots:
            unity_asset_file_path(path)
            if path in seen_roots:fail('ASSET_RETIRE_PROTECTED_ROOTS',path,'Duplicate protected root')
            seen_roots.add(path)
        if selected & seen_roots:
            fail('ASSET_RETIRE_PROTECTED_ROOTS','spec','A protected root cannot also be selected for retirement')
        seen_resources=set()
        for row in resources:
            if not isinstance(row,dict) or set(row)!={'key','path','guid','reason','sourceEvidence'}:
                fail('ASSET_RETIRE_RESOURCE_DECLARATION','spec','Each Resources retirement requires key, path, GUID, reason and sourceEvidence')
            if not isinstance(row.get('key'),str) or not row['key'] or row['key'].startswith('/') or '\\' in row['key'] or any(part in ('','.','..') for part in row['key'].split('/')):
                fail('ASSET_RETIRE_RESOURCE_DECLARATION','spec','Resources key must be a canonical extensionless key')
            unity_asset_file_path(row.get('path'))
            import re
            if not isinstance(row.get('guid'),str) or not re.fullmatch('[a-f0-9]{32}',row['guid']):
                fail('ASSET_RETIRE_RESOURCE_DECLARATION','spec','Resources retirement requires a lowercase GUID')
            identity=(row['key'],row['path'],row['guid'])
            if identity in seen_resources:fail('ASSET_RETIRE_RESOURCE_DECLARATION',row['path'],'Duplicate Resources key/path/GUID declaration')
            seen_resources.add(identity)
            for key in ('reason','sourceEvidence'):
                value=row.get(key)
                if not isinstance(value,str) or not value.strip() or len(value)>4096:
                    fail('ASSET_RETIRE_RESOURCE_DECLARATION',row['path'],'Explicit nonempty reason and source evidence are required')
    else:
        fail("UNITY_OPERATION", str(operation), "Unsupported native operation")
    if set(doc) - allowed or doc.get("schemaVersion") != 1:
        fail("UNITY_SPEC", "spec", "Unknown fields or schema version")


def source_files(project):
    files = project_files(project, "unity-6000.6.2f1-ugui")
    for name in ("ProjectSettings", "Packages"):
        for p in sorted(inside(project, name).rglob("*")):
            if p.is_symlink():
                fail("SYMLINK_PATH", str(p), "Source settings contain symlink")
            if p.is_file():
                rel = p.relative_to(project).as_posix()
                files[rel] = dict(path=rel, sha256=digest_file(p), bytes=p.stat().st_size)
    return files


def plan(project, spec, output):
    project = safe(project)
    context = inspect(project)
    if (context['engine'], context['editorVersion']) != ('unity', VERSION):
        fail('UNITY_VERSION', str(project), 'Only existing Unity '+VERSION+' supported; no upgrades')
    raw = read(spec)
    doc = load(raw)
    validate_spec(doc)
    files = source_files(project)
    extra_inputs=[];source_evidence_cache={}
    if doc['operation'] == 'ui.create':
        if doc['sourceFontPath'] not in files:
            fail('UI_FONT_MISSING',doc['sourceFontPath'],'Import an authorized font into the project first')
        if doc['sourceFontPath']+'.meta' not in files:
            fail('UI_FONT_NOT_IMPORTED',doc['sourceFontPath'],'Use project.import before creating a native UI from this font')
        for k in ('prefabPath','scenePath','fontAssetPath','tmpSettingsPath'):
            if k not in doc:continue
            if doc[k] in files or doc[k]+'.meta' in files:
                fail('UNITY_OUTPUT_EXISTS',doc[k],'Create-only output already exists')
    elif doc['operation']=='assets.move':
        for move in doc.get('moves',[]):
            if move['source'] not in files or move['source']+'.meta' not in files:
                fail('ASSET_MOVE_SOURCE',move['source'],'Expected imported file with meta')
            if inside(project,move['target']).exists() or inside(project,move['target']+'.meta').exists():
                fail('ASSET_MOVE_DESTINATION',move['target'],'Destination occupied')
        move_manifest=[]
        for move in doc.get('directoryMoves',[]):
            manifest=folder_move_manifest(project,files,move['source'],move['target'])
            if inside(project,move['target']).exists() or inside(project,move['target']+'.meta').exists():
                fail('ASSET_MOVE_DESTINATION',move['target'],'Destination folder or meta is occupied')
            move_manifest.append(manifest)
        selected={path for move in doc.get('moves',[]) for path in (move['source'],move['source']+'.meta')}
        selected.update(row['source'] for manifest in move_manifest for row in manifest['entries'] if 'sha256' in row)
        manifest_entries=sum(len(manifest['entries']) for manifest in move_manifest)+2*len(doc.get('moves',[]))
        selected_bytes=sum(files[path]['bytes'] for path in selected)
        if manifest_entries>MOVE_MANIFEST_ENTRIES or selected_bytes>MOVE_MANIFEST_BYTES:
            fail('ASSET_MOVE_BUDGET','spec','Complete move transaction exceeds 10000 manifest entries or 256 MiB; split into reviewed independent subtrees')
        moved_file_paths={row['source'] for manifest in move_manifest for row in manifest['entries'] if 'sha256' in row}
        moved_file_paths.update(path for move in doc.get('moves',[]) for path in (move['source'],move['source']+'.meta'))
        target_paths={row['target'] for manifest in move_manifest for row in manifest['entries']}
        target_paths.update(path for move in doc.get('moves',[]) for path in (move['target'],move['target']+'.meta'))
        folded={}
        fold=lambda path:unicodedata.normalize('NFC',path).casefold()
        for path in files:folded.setdefault(fold(path),[]).append(path)
        existing_dirs=[]
        for path in inside(project,'Assets').rglob('*'):
            if path.is_dir():existing_dirs.append(path.relative_to(project).as_posix())
        moving_paths=set(moved_file_paths)
        moving_paths.update(row['source'] for manifest in move_manifest for row in manifest['entries'])
        source_paths={fold(path) for path in moving_paths}
        target_folds=[]
        for target in target_paths:
            target_fold=fold(target)
            if target_fold in target_folds:
                fail('ASSET_MOVE_CASE_COLLISION',target,'Multiple destinations collide by case/Unicode fold')
            target_folds.append(target_fold)
            if target_fold in source_paths:
                fail('ASSET_MOVE_CASE_COLLISION',target,'Destination collides with a moving source by case/Unicode fold')
            collision=[path for path in folded.get(target_fold,[]) if path not in moved_file_paths]
            if collision:
                fail('ASSET_MOVE_CASE_COLLISION',target,'Destination collides with an existing path by case/Unicode fold')
            prefixes={parent.as_posix() for parent in Path(target).parents if parent.as_posix() not in ('.','Assets')}
            for prefix in prefixes:
                if any(fold(existing)==fold(prefix) and existing!=prefix for existing in existing_dirs):
                    fail('ASSET_MOVE_CASE_COLLISION',prefix,'Destination parent casing differs from an existing Unity folder')
    elif doc['operation']=='assets.retire':
        retire_manifest=[];protected_manifest=[];selected_paths=set()
        for declaration in doc['retire']:
            path=declaration['path'];asset=inside(project,path);meta_path=path+'.meta'
            if path not in files or meta_path not in files or not asset.is_file():
                fail('ASSET_RETIRE_SOURCE',path,'Expected an imported file with its .meta; directory retirement is unsupported')
            meta=inside(project,meta_path);guid=meta_guid(read(meta),meta_path)
            policy=declaration.get('identityPolicy','native-object')
            manifest=dict(path=path,role=declaration['role'],reason=declaration['reason'],sourceEvidence=declaration['sourceEvidence'],
                          identityPolicy=policy,hasSourceIdentityEvidence=policy=='source-evidence-only',
                          sha256=files[path]['sha256'],bytes=files[path]['bytes'],metaPath=meta_path,
                          metaSha256=files[meta_path]['sha256'],metaBytes=files[meta_path]['bytes'],guid=guid)
            if policy=='source-evidence-only':
                evidence=source_only_evidence(project,spec,files,path,guid,declaration,source_evidence_cache)
                manifest['sourceIdentityEvidence']=evidence
                extra_inputs.append(safe(evidence['snapshotPath']))
            retire_manifest.append(manifest)
            selected_paths.add(path)
        for path in doc['protectedRoots']:
            asset=inside(project,path);meta_path=path+'.meta'
            if path not in files or meta_path not in files or not asset.is_file():
                fail('ASSET_RETIRE_PROTECTED_ROOT',path,'Protected root must be an imported file with its .meta')
            if path in selected_paths:fail('ASSET_RETIRE_PROTECTED_ROOT',path,'Protected root cannot be selected for retirement')
            meta=inside(project,meta_path);guid=meta_guid(read(meta),meta_path)
            protected_manifest.append(dict(path=path,sha256=files[path]['sha256'],bytes=files[path]['bytes'],metaPath=meta_path,
                                           metaSha256=files[meta_path]['sha256'],metaBytes=files[meta_path]['bytes'],guid=guid))
        declarations={row['path']:row for row in doc.get('resources',[])}
        resource_keys=set()
        for item in retire_manifest:
            key=resource_key(item['path']);declaration=declarations.get(item['path'])
            if key is None and declaration is not None:
                fail('ASSET_RETIRE_RESOURCE_DECLARATION',item['path'],'Resources declaration does not refer to a Resources asset')
            if key is not None:
                if declaration is None or declaration['key']!=key or declaration['guid']!=item['guid']:
                    fail('ASSET_RETIRE_RESOURCE_DECLARATION',item['path'],'Each Resources asset needs its exact key/path/GUID retirement declaration')
                if key.casefold() in resource_keys:fail('ASSET_RETIRE_RESOURCE_AMBIGUOUS',key,'Multiple selected files map to one case-insensitive Resources key')
                resource_keys.add(key.casefold())
        if set(declarations)!=set(item['path'] for item in retire_manifest if resource_key(item['path']) is not None):
            fail('ASSET_RETIRE_RESOURCE_DECLARATION','spec','Resources declarations must match selected Resources assets exactly')
        if resource_keys:
            for path in files:
                if path.endswith('.meta'):continue
                try:key=resource_key(path)
                except BeaverError:continue
                if key is not None and key.casefold() in resource_keys and path not in selected_paths:
                    fail('ASSET_RETIRE_RESOURCE_AMBIGUOUS',key,'Another asset still maps to the explicitly retired Resources key: '+path)
        backup_bytes=sum(row['bytes']+row['metaBytes'] for row in retire_manifest)
        if len(retire_manifest)*2>MOVE_MANIFEST_ENTRIES or backup_bytes>MOVE_MANIFEST_BYTES:
            fail('ASSET_RETIRE_BUDGET','spec','Retirement exceeds 10000 file/meta entries or 256 MiB; split into reviewed groups')
    elif doc['operation']=='project.import':
        pass
    elif doc['operation']=='sprite.configure':
        if doc['assetPath'] not in files:
            fail('SPRITE_MISSING',doc['assetPath'],'Source PNG missing')
    else:
        for rel in (doc.get('scenes') or [doc.get('prefabPath') or doc['scenePath']]):
            if rel not in files:
                fail('UNITY_INPUT_MISSING',rel,'Native source asset is missing')
    out = new_output(output,[project,safe(spec),*extra_inputs])
    data = dict(contract='beaver-unity/1',schemaVersion=1,implementationSha256=identity(),
                projectRoot=str(project),engine='unity',editorVersion=VERSION,
                writableRoots=['Assets'] if doc['operation'] != 'build.macos' else [],
                before=files,spec=doc,specSha256=sha(raw),
                sourceSha256=sha(encoded(files)),native='not_run')
    if doc['operation']=='assets.move':data['folderMoveManifest']=move_manifest
    if doc['operation']=='assets.retire':
        data['retireManifest']=retire_manifest;data['protectedManifest']=protected_manifest
    data['editorInitializationFiles']=['ProjectSettings/SceneTemplateSettings.json'] if doc['operation']=='ui.create' and 'ProjectSettings/SceneTemplateSettings.json' not in files else []
    data['nativeInitializationPaths']=[]
    if doc['operation']=='project.import':
        for p in inside(project,'Assets').rglob('*'):
            if p.is_symlink():fail('SYMLINK_PATH',str(p),'Native import input contains a symbolic link')
            rel=p.relative_to(project).as_posix()
            if not rel.endswith('.meta') and not inside(project,rel+'.meta').exists():data['nativeInitializationPaths'].append(rel+'.meta')
    write_json(out/'unity-plan.json',data)
    digest=sha(encoded(data))
    write_json(out/'plan-identity.json',dict(sha256=digest))
    return dict(status='planned',report=str(out/'unity-plan.json'),planSha256=digest,sourceSha256=data['sourceSha256'])


def editor_path(path):
    from .native_environment import editor_environment
    editor_environment('BEAVER_NATIVE_JOB', path)
    path = safe(path)
    if path.name not in ('Unity','Unity.exe') or not path.is_file() or not os.access(path,os.X_OK):
        fail('UNITY_EDITOR',str(path),'Expected executable Unity Editor')
    if path.parent.name == 'MacOS':
        metadata=path.parent.parent/'Info.plist'
        if plistlib.loads(read(metadata)).get('CFBundleVersion') != VERSION:
            fail('UNITY_EDITOR_VERSION',str(path),'Wrong Editor version')
    return path


def run(editor, project, stage, mode, plan, timeout):
    from .native_environment import editor_environment
    if type(timeout) is not int or not 1 <= timeout <= 1200:
        fail('UNITY_TIMEOUT',str(timeout),'Expected 1..1200 seconds')
    job=dict(plan['spec'],targetRoot=str(project),stage=str(stage),mode=mode,
             planSha256=sha(encoded(plan)),sourceSha256=plan['sourceSha256'])
    if plan['spec']['operation']=='assets.move':job['folderMoveManifest']=plan.get('folderMoveManifest',[])
    if plan['spec']['operation']=='assets.retire':
        job['retireManifest']=plan.get('retireManifest',[]);job['protectedManifest']=plan.get('protectedManifest',[])
    jobfile=stage/('job-'+mode+'.json')
    write_json(jobfile,job)
    args=[str(editor),'-batchmode','-nographics','-projectPath',str(project),'-executeMethod','BeaverNative.Run','-logFile',str(stage/(mode+'.log'))]
    with (stage/(mode+'-console.log')).open('w') as log:
        process=subprocess.Popen(args,cwd=project,env=editor_environment('BEAVER_NATIVE_JOB',jobfile),stdout=log,stderr=subprocess.STDOUT)
        write_json(stage/'process.json',dict(pid=process.pid,mode=mode,owned=True,exited=False))
        try:
            code=process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired,KeyboardInterrupt):
            process.terminate()
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill();process.wait(timeout=10)
            write_json(stage/'process.json',dict(pid=process.pid,mode=mode,owned=True,exited=True,exitCode=process.returncode))
            fail('UNITY_TIMEOUT',str(stage),'Owned Editor terminated; inspect journal before recovery')
    write_json(stage/'process.json',dict(pid=process.pid,mode=mode,owned=True,exited=True,exitCode=code))
    path=stage/('native-'+mode+'.json')
    report=load(read(path)) if path.exists() else {}
    if code != 0 or report.get('status') != 'verified' or report.get('planSha256') != job['planSha256']:
        fail('UNITY_NATIVE_FAILED',str(stage),'Inspect native report and logs; no success inferred from process exit')
    return report


def _install_native_helper(project):
    helper=inside(project,HELPER)
    if inside(project,HELPER_ROOT).exists() or inside(project,HELPER_ROOT+'.meta').exists():
        fail('UNITY_HELPER_CONFLICT',HELPER_ROOT,'Reserved temporary helper root occupied')
    source=Path(__file__).parent/'targets/BeaverNative.cs'
    helper.parent.mkdir(parents=True);helper.write_bytes(source.read_bytes())
    return helper,digest_file(helper)


def _remove_native_helper(project,helper,fingerprint):
    if not helper.exists() or digest_file(helper)!=fingerprint:return False
    directory=helper.parent.parent
    allowed={HELPER,HELPER+'.meta',HELPER_ROOT+'/Editor.meta'}
    owned=all(not p.is_symlink() and (not p.is_file() or p.relative_to(project).as_posix() in allowed) for p in directory.rglob('*'))
    if not owned:return False
    for p in sorted(directory.rglob('*'),key=lambda p:len(p.parts),reverse=True):
        p.unlink() if p.is_file() else p.rmdir()
    directory.rmdir()
    meta=inside(project,HELPER_ROOT+'.meta')
    if meta.exists():meta.unlink()
    return True


def validate_retire_source_evidence(item,location='retirement plan'):
    policy=item.get('identityPolicy','native-object');has_evidence='sourceIdentityEvidence' in item
    if policy not in ('native-object','source-evidence-only'):
        fail('ASSET_RETIRE_IDENTITY_POLICY',location,'Unknown retirement identity policy in manifest')
    if type(item.get('hasSourceIdentityEvidence')) is not bool or item['hasSourceIdentityEvidence']!=has_evidence:
        fail('ASSET_RETIRE_SOURCE_EVIDENCE',location,'Manifest evidence-presence flag must equal the bound evidence object')
    if policy!='source-evidence-only':
        if has_evidence or item['hasSourceIdentityEvidence']:
            fail('ASSET_RETIRE_SOURCE_EVIDENCE',location,'Native-object policy cannot carry source-only evidence')
        return
    evidence=item.get('sourceIdentityEvidence')
    expected_fields={'snapshotPath','snapshotSha256','assetPath','targetRecordSha256','targetRecord','targetInputs'}
    if not isinstance(evidence,dict) or set(evidence)!=expected_fields or evidence.get('assetPath')!=item.get('path') or \
       not isinstance(evidence.get('snapshotPath'),str) or not evidence['snapshotPath'] or \
       not isinstance(evidence.get('snapshotSha256'),str) or not SHA256_HEX.fullmatch(evidence['snapshotSha256']):
        fail('ASSET_RETIRE_SOURCE_EVIDENCE',location,'Immutable collector evidence manifest is incomplete')
    record=evidence.get('targetRecord')
    record_fields={'path','guid','localIds','types','status','identityStatus','objectCount','error'}
    if not isinstance(record,dict) or set(record)!=record_fields or record.get('path')!=item.get('path') or \
       str(record.get('guid','')).lower()!=str(item.get('guid','')).lower() or record.get('status')!='unknown' or \
       record.get('identityStatus')!='no-persistent-object' or record.get('objectCount')!=0 or \
       record.get('localIds')!=[] or record.get('types')!=[] or not isinstance(record.get('error'),str) or not record['error'].strip() or \
       evidence.get('targetRecordSha256')!=sha(encoded(record)):
        fail('ASSET_RETIRE_SOURCE_EVIDENCE',location,'Collector target record/hash is invalid or does not prove zero persistent objects')
    inputs=evidence.get('targetInputs')
    expected={item['path']:dict(sha256=item['sha256'],bytes=item['bytes']),
              item['metaPath']:dict(sha256=item['metaSha256'],bytes=item['metaBytes'])}
    if not isinstance(inputs,list) or len(inputs)!=2 or any(not isinstance(row,dict) or set(row)!={'path','sha256','bytes'} for row in inputs) or \
       {row['path']:dict(sha256=row['sha256'],bytes=row['bytes']) for row in inputs}!=expected:
        fail('ASSET_RETIRE_SOURCE_EVIDENCE',location,'Collector target file/meta hashes and byte counts differ from the retirement plan')


def validate_retire_identity_rows(manifest,rows,location='native',witnessed=None):
    if not isinstance(rows,list) or len(rows)!=len(manifest):
        fail('ASSET_RETIRE_IDENTITY',location,'Native retirement identity list differs from selected manifest')
    if witnessed is not None and (not isinstance(witnessed,list) or len(witnessed)!=len(manifest)):
        fail('ASSET_RETIRE_IDENTITY',location,'Witnessed retirement identity list is incomplete')
    for index,item in enumerate(manifest):
        row=rows[index];policy=item.get('identityPolicy','native-object')
        validate_retire_source_evidence(item,location)
        if not isinstance(row,dict) or row.get('path')!=item['path'] or row.get('guid')!=item['guid'] or row.get('identityPolicy')!=policy or not isinstance(row.get('localIds'),list):
            fail('ASSET_RETIRE_IDENTITY',location,'Native identity row does not match selected path, GUID, and policy')
        if policy=='source-evidence-only':
            evidence=item['sourceIdentityEvidence']
            if row.get('identityStatus')!='no-persistent-object' or row.get('nativeObjectCount')!=0 or row['localIds']!=[] or \
               row.get('sourceEvidenceSnapshotSha256')!=evidence['snapshotSha256'] or row.get('sourceEvidenceTargetRecordSha256')!=evidence['targetRecordSha256']:
                fail('ASSET_RETIRE_IDENTITY',location,'Source-evidence-only identity must report zero native objects, empty IDs, and matching collector hashes')
        else:
            if row.get('identityStatus')!='verified' or type(row.get('nativeObjectCount')) is not int or row['nativeObjectCount']<=0 or \
               not row['localIds'] or row['nativeObjectCount']!=len(row['localIds']) or \
               row.get('sourceEvidenceSnapshotSha256') not in (None,'') or row.get('sourceEvidenceTargetRecordSha256') not in (None,''):
                fail('ASSET_RETIRE_IDENTITY',location,'Native-object policy requires verified persistent IDs for every object')
            for identity in row['localIds']:
                fields=identity.split(':',2) if isinstance(identity,str) else []
                try:local_id=int(fields[1]) if len(fields)==3 else 0
                except ValueError:local_id=0
                if len(fields)!=3 or fields[0].lower()!=item['guid'].lower() or local_id==0 or not fields[2]:
                    fail('ASSET_RETIRE_IDENTITY',location,'Native localID checkpoint is malformed or belongs to another GUID')
        if witnessed is not None:
            prior=witnessed[index]
            for key in ('path','guid','identityPolicy','identityStatus','nativeObjectCount','localIds','sourceEvidenceSnapshotSha256','sourceEvidenceTargetRecordSha256'):
                current=row.get(key);previous=prior.get(key)
                if key in ('sourceEvidenceSnapshotSha256','sourceEvidenceTargetRecordSha256') and policy=='native-object':
                    current=current or '';previous=previous or ''
                if current!=previous:
                    fail('ASSET_RETIRE_IDENTITY',location,'Post-restore identity differs from the witnessed pre-delete state')


def apply(plan_path, output, editor, expected, timeout=600):
    path=safe(plan_path)
    raw=read(path,max_bytes=128*1024**2)
    data=load(raw,max_nodes=8_000_000)
    if sha(raw)!=expected or load(read(path.parent/'plan-identity.json')).get('sha256')!=expected:
        fail('UNITY_PLAN_CHANGED',str(path),'Expected exact plan identity')
    if data.get('contract')!='beaver-unity/1' or data.get('implementationSha256')!=identity():
        fail('UNITY_PLAN_IMPLEMENTATION',str(path),'Generate plan with the current implementation')
    validate_spec(data['spec'])
    if data['spec']['operation']=='assets.retire':
        for item in data.get('retireManifest',[]):validate_retire_source_evidence(item,str(path))
    project=safe(data['projectRoot']); editor=editor_path(editor)
    stage=new_output(output,[project,path.parent])
    write_json(stage/'unity-plan.json',data)
    journal=dict(status='prepared',planSha256=expected,projectRoot=str(project),operation=data['spec']['operation'],startedAt=datetime.now(timezone.utc).isoformat())
    write_json(stage/'journal.json',journal)
    with lock(project):
        native_lock(project)
        if source_files(project)!=data['before']:
            fail('UNITY_SOURCE_DRIFT',str(project),'Project changed after plan')
        if data['spec']['operation'] in ('assets.move','assets.retire'):
            backup_paths={path for move in data['spec'].get('moves',[]) for path in (move['source'],move['source']+'.meta')}
            backup_paths.update(row['source'] for manifest in data.get('folderMoveManifest',[]) for row in manifest['entries'] if 'sha256' in row)
            backup_paths.update(path for item in data.get('retireManifest',[]) for path in (item['path'],item['metaPath']))
            images=[]
            try:
                for rel in sorted(backup_paths):
                    row=data['before'][rel];source=inside(project,rel);destination=inside(stage/'before',rel)
                    copy_verified(source,destination,row['sha256'],row['bytes'])
                    images.append(dict(path=rel,sha256=row['sha256'],bytes=row['bytes']))
            except BaseException as error:
                journal.update(status='before-image-failed',beforeImages=images,diagnostic=str(error));write_json(stage/'journal.json',journal)
                raise
            journal.update(status='before-images-complete',beforeImages=images,checkpoint='source-bytes-verified')
            write_json(stage/'journal.json',journal)
        helper=inside(project,HELPER)
        if inside(project,HELPER_ROOT).exists() or inside(project,HELPER_ROOT+'.meta').exists():
            fail('UNITY_HELPER_CONFLICT',HELPER_ROOT,'Reserved helper root occupied')
        for key in ('prefabPath',):
            rel=data['spec'].get(key)
            if rel and rel in data['before']:
                for suffix in ('','.meta'):
                    source=inside(project,rel+suffix)
                    if source.exists():
                        dest=stage/'before'/(rel+suffix);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(read(source,max_bytes=512*1024**2))
        helper,fingerprint=_install_native_helper(project)
        try:
            applied=run(editor,project,stage,'apply',data,timeout)
            journal.update(status='native-apply-complete-pending-reopen',nativeApplyReadback=applied)
            write_json(stage/'journal.json',journal)
            reopened=run(editor,project,stage,'verify',data,timeout) if data['spec']['operation'] not in ('build.macos','validate.play') else applied
            journal.update(status='native-complete-pending-source-audit',nativeReadback=reopened)
        except BaseException:
            journal['status']='recovery-required'
            raise
        finally:
            _remove_native_helper(project,helper,fingerprint)
            write_json(stage/'journal.json',journal)
        after=source_files(project)
        changes=[dict(path=p,before=data['before'].get(p),after=after.get(p)) for p in sorted(set(data['before'])|set(after)) if data['before'].get(p)!=after.get(p)]
        journal.update(after=after,changes=changes,sourceSha256After=sha(encoded(after)))
        write_json(stage/'journal.json',journal)
        def audit_fail(code,location,message):
            journal.update(status='recovery-required',diagnostic=dict(code=code,location=location,message=message))
            write_json(stage/'journal.json',journal)
            fail(code,str(stage),message+' ('+location+')')
        if data['spec']['operation']=='build.macos' and changes:
            audit_fail('BUILD_SOURCE_DRIFT',str(project),'Build changed source; artifact is not certified')
        if data['spec']['operation']=='ui.create':
            allowed={data['spec'][k]+suffix for k in ('prefabPath','scenePath','fontAssetPath','tmpSettingsPath') if k in data['spec'] for suffix in ('','.meta')}
            for path_value in list(allowed):
                for parent in Path(path_value).parents:
                    if parent.as_posix() not in ('.','Assets'):allowed.add(parent.as_posix()+'.meta')
            for row in changes:
                if row['before'] is None and row['path'] in data.get('editorInitializationFiles',[]):continue
                if row['before'] is not None or row['path'] not in allowed:
                    audit_fail('UNITY_UNEXPECTED_CHANGE',row['path'],'Unexpected source mutation; inspect transaction')
        if data['spec']['operation']=='prefab.edit':
            allowed={data['spec']['prefabPath'],data['spec']['prefabPath']+'.meta'}
            if any(row['path'] not in allowed for row in changes):
                audit_fail('UNITY_UNEXPECTED_CHANGE',str(project),'Prefab edit changed another source file')
        if data['spec']['operation']=='prefab.inspect' and changes:
            audit_fail('UNITY_UNEXPECTED_CHANGE',str(project),'Inspection changed a source file')
        if data['spec']['operation']=='validate.play' and changes:
            audit_fail('UNITY_UNEXPECTED_CHANGE',str(project),'Play probe changed a source file')
        if data['spec']['operation']=='project.import':
            allowed=set(data['nativeInitializationPaths'])
            if any(row['before'] is not None or row['path'] not in allowed for row in changes):
                audit_fail('UNITY_UNEXPECTED_CHANGE',str(project),'Native import changed existing source; inspect the transaction')
        if data['spec']['operation']=='sprite.configure':
            if any(row['path']!=data['spec']['assetPath']+'.meta' for row in changes):
                audit_fail('UNITY_UNEXPECTED_CHANGE',str(project),'Sprite configuration changed other source')
        if data['spec']['operation']=='assets.move':
            allowed={move[k]+suffix for move in data['spec'].get('moves',[]) for k in ('source','target') for suffix in ('','.meta')}
            for manifest in data.get('folderMoveManifest',[]):
                allowed.update(row['source'] for row in manifest['entries'])
                allowed.update(row['target'] for row in manifest['entries'])
            for move in [*data['spec'].get('moves',[]),*data['spec'].get('directoryMoves',[])]:
                for parent in Path(move['target']).parents:
                    if parent.as_posix() not in ('.','Assets'):allowed.add(parent.as_posix()+'.meta')
            for row in changes:
                if row['path'] not in allowed:
                    audit_fail('UNITY_UNEXPECTED_CHANGE',row['path'],'Move changed another source file')
            if applied.get('moves')!=reopened.get('moves') or applied.get('moveIdentities',[])!=reopened.get('moveIdentities',[]):
                audit_fail('UNITY_MOVE_READBACK',str(stage),'Move GUID/localIDs differ after reopen')
        if data['spec']['operation']=='assets.retire':
            selected=[item['path'] for item in data['retireManifest']]
            allowed={path for item in data['retireManifest'] for path in (item['path'],item['metaPath'])}
            for row in changes:
                if row['path'] not in allowed or row['after'] is not None:
                    audit_fail('ASSET_RETIRE_SOURCE_AUDIT',row['path'],'Retirement may only delete its exact planned asset and meta paths')
            if {row['path'] for row in changes}!=allowed:
                audit_fail('ASSET_RETIRE_SOURCE_AUDIT',str(stage),'Retirement did not delete every selected asset and meta exactly once')
            if applied.get('deletedPaths')!=selected or reopened.get('deletedPaths')!=selected or applied.get('deleteInProgress') or reopened.get('deleteInProgress'):
                audit_fail('ASSET_RETIRE_CHECKPOINT',str(stage),'Native deletion checkpoint is incomplete or uncertain')
            validate_retire_identity_rows(data['retireManifest'],applied.get('retiredAssets'),str(stage))
            validate_retire_identity_rows(data['retireManifest'],reopened.get('retiredAssets'),str(stage),witnessed=applied.get('retiredAssets'))
            if applied.get('retiredAssets')!=reopened.get('retiredAssets') or applied.get('protectedRoots')!=reopened.get('protectedRoots') or \
               applied.get('dependencyPaths')!=reopened.get('dependencyPaths') or applied.get('dependencyClosures')!=reopened.get('dependencyClosures') or \
               (applied.get('resources') or [])!=(reopened.get('resources') or []) or \
               applied.get('resourcesDynamicUseNotProvable') is not True or reopened.get('resourcesDynamicUseNotProvable') is not True:
                audit_fail('ASSET_RETIRE_READBACK',str(stage),'Retirement or protected-root identity readback differs after reopen')
        if data['spec']['operation']=='build.macos':
            try:
                artifacts=[]
                for p in sorted((stage/'player').rglob('*')):
                    if p.is_symlink():artifacts.append(dict(path=p.relative_to(stage).as_posix(),symlink=os.readlink(p)))
                    elif p.is_file():artifacts.append(dict(path=p.relative_to(stage).as_posix(),sha256=digest_file(p,max_bytes=BUILD_FILE_BYTES),bytes=p.stat().st_size))
                if not artifacts:fail('BUILD_EMPTY',str(stage),'No actual build artifact')
                write_json(stage/'artifact-manifest.json',dict(schemaVersion=1,artifactPolicy='beaver-unity-build/2',sourceSha256=data['sourceSha256'],planSha256=expected,files=artifacts))
                from .payload import verify_manifest
                journal['artifactVerification']=verify_manifest(stage,stage/'artifact-manifest.json',scope='player',allow_links=True,artifact=True)
            except (BeaverError,OSError,ValueError) as error:
                journal.update(status='artifact-verification-failed',artifactError=str(error))
                write_json(stage/'journal.json',journal)
                fail('BUILD_ARTIFACT_FAILED',str(stage),str(error))
        journal['status']='complete'
        write_json(stage/'journal.json',journal)
    return dict(status='verified',report=str(stage/'journal.json'),transaction=str(stage),changes=changes,
                nativeReadback=journal['nativeReadback'],sourceSha256=data['sourceSha256'])


def recover(transaction, editor, expected, timeout=600):
    """Restore witnessed assets.retire deletions from verified transaction images."""
    stage=safe(transaction)
    plan_path=inside(stage,'unity-plan.json');raw=read(plan_path,max_bytes=128*1024**2);data=load(raw,max_nodes=8_000_000)
    if sha(encoded(data))!=expected or data.get('contract')!='beaver-unity/1' or data.get('implementationSha256')!=identity():
        fail('UNITY_RECOVERY_PLAN','transaction','Expected current immutable retirement transaction plan')
    if data.get('spec',{}).get('operation')!='assets.retire':
        fail('UNITY_RECOVERY_OPERATION','transaction','Only assets.retire transactions can be recovered here')
    validate_spec(data['spec'])
    for item in data.get('retireManifest',[]):validate_retire_source_evidence(item,str(plan_path))
    journal_path=inside(stage,'journal.json');journal=load(read(journal_path))
    if journal.get('planSha256')!=expected or journal.get('operation')!='assets.retire' or journal.get('status') not in ('complete','recovery-required'):
        fail('ASSET_RETIRE_RECOVERY_BLOCKED',str(stage),'Transaction state is complete, mismatched or not a retirement recovery case')
    project=safe(data['projectRoot']);editor=editor_path(editor)
    report_path=inside(stage,'native-apply.json')
    if not report_path.is_file():fail('ASSET_RETIRE_RECOVERY_BLOCKED',str(stage),'No native deletion checkpoint; do not infer which assets were deleted')
    native=load(read(report_path));selected=[row['path'] for row in data.get('retireManifest',[])]
    deleted=native.get('deletedPaths')
    if native.get('operation')!='assets.retire' or native.get('planSha256')!=sha(encoded(data)):
        fail('ASSET_RETIRE_RECOVERY_BLOCKED',str(report_path),'Native checkpoint belongs to another operation or plan')
    if not isinstance(deleted,list) or not deleted or len(deleted)!=len(set(deleted)) or any(path not in selected for path in deleted):
        fail('ASSET_RETIRE_RECOVERY_BLOCKED',str(report_path),'No valid witnessed deletion checkpoint')
    if journal.get('status')=='complete' and (native.get('status')!='verified' or deleted!=selected):
        fail('ASSET_RETIRE_RECOVERY_BLOCKED',str(report_path),'Completed journal lacks a complete verified native deletion checkpoint')
    if native.get('deleteInProgress'):
        fail('ASSET_RETIRE_RECOVERY_BLOCKED',str(report_path),'Deletion was in progress without a conclusive post-delete checkpoint')
    identities=native.get('retiredAssets')
    validate_retire_identity_rows(data['retireManifest'],identities,str(report_path))
    protected=native.get('protectedRoots')
    if not isinstance(protected,list) or [row.get('path') for row in protected]!=[row['path'] for row in data['protectedManifest']]:
        fail('ASSET_RETIRE_RECOVERY_BLOCKED',str(report_path),'Protected-root identity checkpoint is incomplete')
    for row,expected_root in zip(protected,data['protectedManifest']):
        if row.get('guid')!=expected_root['guid'] or row.get('sha256')!=expected_root['sha256'] or row.get('metaSha256')!=expected_root['metaSha256'] or not row.get('localIds'):
            fail('ASSET_RETIRE_RECOVERY_BLOCKED',str(report_path),'Protected-root bytes/GUID/localID checkpoint differs')
    if native.get('resourcesDynamicUseNotProvable') is not True:
        fail('ASSET_RETIRE_RECOVERY_BLOCKED',str(report_path),'Resources dynamic-use boundary is absent from native checkpoint')
    if not isinstance(native.get('dependencyPaths'),list):
        fail('ASSET_RETIRE_RECOVERY_BLOCKED',str(report_path),'Protected static dependency closure checkpoint is missing')
    if not isinstance(native.get('dependencyClosures'),list) or [row.get('root') for row in native['dependencyClosures']]!=[row['path'] for row in data['protectedManifest']]:
        fail('ASSET_RETIRE_RECOVERY_BLOCKED',str(report_path),'Per-root static dependency checkpoint is incomplete')
    if (native.get('resources') or [])!=data['spec'].get('resources',[]):
        fail('ASSET_RETIRE_RECOVERY_BLOCKED',str(report_path),'Resources retirement declarations differ from the plan')
    before_root=inside(stage,'before')
    for item in data['retireManifest']:
        for path,digest,size in ((item['path'],item['sha256'],item['bytes']),
                                 (item['metaPath'],item['metaSha256'],item['metaBytes'])):
            image=inside(before_root,path)
            if not image.is_file() or image.stat().st_size!=size or digest_file(image)!=digest:
                fail('ASSET_RETIRE_RECOVERY_BLOCKED',path,'Before-image missing or differs from its planned hash')
    expected_by_path=data['before'];deleted_set=set(deleted)
    backup_paths={path for item in data['retireManifest'] for path in (item['path'],item['metaPath'])}
    restored_checkpoint=journal.get('recoveryRestoredPaths',[])
    if not isinstance(restored_checkpoint,list) or any(path not in backup_paths for path in restored_checkpoint):
        fail('ASSET_RETIRE_RECOVERY_BLOCKED',str(stage),'Recovery copy checkpoint is invalid')
    restored_checkpoint=set(restored_checkpoint)
    with lock(project):
        native_lock(project)
        current=source_files(project);expected_current=dict(expected_by_path)
        for item in data['retireManifest']:
            pair=(item['path'],item['metaPath'])
            if item['path'] not in deleted_set:
                for path in pair:
                    if current.get(path)!=expected_by_path.get(path):
                        fail('ASSET_RETIRE_RECOVERY_BLOCKED',path,'An uncheckpointed asset changed or is absent')
                continue
            for path in pair:
                found=current.get(path);original=expected_by_path.get(path)
                if found is not None and found!=original:
                    fail('ASSET_RETIRE_RECOVERY_BLOCKED',path,'Existing bytes differ; refusing to overwrite a later edit or manual meta')
                if found is not None and path not in restored_checkpoint:
                    fail('ASSET_RETIRE_RECOVERY_BLOCKED',path,'A checkpointed deletion was recreated outside this recovery transaction')
                if found is None:expected_current.pop(path,None)
        if current!=expected_current:
            fail('ASSET_RETIRE_RECOVERY_BLOCKED',str(project),'Full project source guard differs outside witnessed deletions')
        # The full before-image set is preflighted before the first filesystem restore.
        todo=[]
        for item in data['retireManifest']:
            if item['path'] not in deleted_set:continue
            for path in (item['path'],item['metaPath']):
                if path not in current:
                    original=expected_by_path[path];todo.append((path,original))
        journal.update(status='restoring-before-images',recoveryCheckpoint='all-targets-preflighted',recoveryDeletedPaths=deleted)
        write_json(journal_path,journal)
        helper=None;fingerprint=None
        try:
            restored=list(restored_checkpoint)
            for path,row in todo:
                image=inside(before_root,path);target=inside(project,path)
                copy_verified(image,target,row['sha256'],row['bytes'],atomic=False)
                restored.append(path);journal.update(recoveryRestoredPaths=restored,recoveryCheckpoint='before-image-copied')
                write_json(journal_path,journal)
            # Separate Editor invocations refresh and verify persisted Unity IDs.
            helper,fingerprint=_install_native_helper(project)
            try:
                recovered=run(editor,project,stage,'recover',data,timeout)
                reopened=run(editor,project,stage,'recover-verify',data,timeout)
            finally:
                _remove_native_helper(project,helper,fingerprint)
            validate_retire_identity_rows(data['retireManifest'],recovered.get('retiredAssets'),str(stage),witnessed=identities)
            validate_retire_identity_rows(data['retireManifest'],reopened.get('retiredAssets'),str(stage),witnessed=identities)
            if recovered.get('recoveredPaths')!=deleted or reopened.get('recoveredPaths')!=deleted or \
               recovered.get('retiredAssets')!=reopened.get('retiredAssets') or recovered.get('protectedRoots')!=reopened.get('protectedRoots') or \
               recovered.get('dependencyPaths')!=reopened.get('dependencyPaths') or recovered.get('dependencyClosures')!=reopened.get('dependencyClosures') or \
               (recovered.get('resources') or [])!=(reopened.get('resources') or []):
                fail('ASSET_RETIRE_RECOVERY_READBACK',str(stage),'Native restore GUID/localID readback differs after reopen')
            if source_files(project)!=data['before']:
                fail('ASSET_RETIRE_RECOVERY_SOURCE_AUDIT',str(project),'Restored source tree differs from the original full-root snapshot')
            journal.update(status='recovered',recoveryCheckpoint='native-reopen-source-audit-complete',recoveryNativeReadback=reopened,
                           recoveredAt=datetime.now(timezone.utc).isoformat())
            write_json(journal_path,journal)
        except BaseException as error:
            if helper is not None and fingerprint is not None:_remove_native_helper(project,helper,fingerprint)
            journal.update(status='recovery-required',recoveryError=str(error),recoveryCheckpoint=journal.get('recoveryCheckpoint','preflight-failed'))
            write_json(journal_path,journal)
            raise
    return dict(status='recovered',report=str(journal_path),transaction=str(stage),restoredFiles=len(todo),
                deletedPaths=deleted,nativeReadback=journal['recoveryNativeReadback'])
