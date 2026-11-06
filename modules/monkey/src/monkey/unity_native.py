"""Bounded native proof for dependency-closed Unity Sprite[] leaf Prefabs.

Source IDs resolve through exact serialized-file external tables. Native identities
are read, never rewritten. Unknown shapes stop before launching an Editor.
"""
from datetime import timedelta
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

from PIL import Image

from .io import safe, inside, read, load, sha, write_json, new_output
from .native import now, stamp, redact_log
from .sources.compiled import fail
from .providers.assetripper import fingerprint, TARGET_VERSION
from .recover_unity import CODE_SUFFIXES
from .layout.standard import VERSION
from .layout.standard import find_analysis

PROFILE = 'unity-leaf-prefab-sprite-array-v1'


def require(condition, message):
    if not condition:
        fail('UNITY_NATIVE_PROFILE_UNSUPPORTED', '$', message)


def document(path):
    return load(read(path, max_bytes=128*1024*1024), max_nodes=8_000_000)


def owned(project):
    raw = read(project/'recovery-manifest.json', max_bytes=128*1024*1024)
    manifest = load(raw, max_nodes=8_000_000)
    require(manifest.get('targetVersion') == TARGET_VERSION, 'Exact Unity target required')
    files = manifest.get('files', [])
    names = [r['path'] for r in files]
    require(len(names) == len(set(names)), 'Duplicate owned paths')
    actual = {p.relative_to(project).as_posix() for p in project.rglob('*') if safe(p).is_file()}
    require(actual == set(names)|{'recovery-manifest.json'}, 'Candidate has changed or unowned files')
    for row in files:
        p = inside(project, row['path'])
        require(p.stat().st_size == row['bytes'] and fingerprint(p) == row['sha256'], 'Owned file changed: '+row['path'])
    return sha(raw), files


def guid(project, asset):
    matches = re.findall(rb'^guid: ([0-9a-f]{32})\r?$', read(inside(project, asset+'.meta')), re.M)
    require(len(matches) == 1, 'Exact native metadata GUID required: '+asset)
    return matches[0].decode()


class SourceObjects:
    def __init__(self, docs):
        self.files = {}
        self.names = {}
        self.objects = {}
        for index, doc in enumerate(docs):
            for f in doc['files']:
                key = (index, f['id'])
                require(key not in self.files and f['name'] not in self.names, 'Ambiguous serialized file identity')
                self.files[key] = f
                self.names[f['name']] = key
            for o in doc['objects']:
                key = (index, o['file'], o['pathId'])
                require(key not in self.objects, 'Duplicate source object identity')
                self.objects[key] = o

    def resolve(self, origin, ptr, kind):
        require(isinstance(ptr, dict) and ptr.get('$type') == 'UnityPPtr', 'Typed original PPtr required')
        require(ptr.get('pathId') != '0', 'Null or missing source reference')
        owner = origin[:2]
        if ptr['fileId'] != '0':
            matches = [e for e in self.files[owner]['externals'] if e['fileId'] == ptr['fileId']]
            require(len(matches) == 1, 'Original external-file table entry unavailable')
            name = matches[0]['path'].rsplit('/', 1)[-1]
            require(name in self.names, 'Exact serialized-file dependency missing: '+name)
            owner = self.names[name]
        key = (*owner, ptr['pathId'])
        value = self.objects.get(key)
        require(value is not None and value.get('status') == 'parsed' and value['type'] == kind, 'Missing or unsupported '+kind+' reference')
        return key, value

    def unique_name(self, key):
        value = self.objects[key]
        name = value.get('name')
        require(isinstance(name, str) and name and '/' not in name and '\\' not in name, 'Unsupported source resource name')
        require(sum(o['type'] == value['type'] and o.get('name') == name for o in self.objects.values()) == 1,
                'Ambiguous source resource name: '+name)
        return name


def plan(project, format_profile='none'):
    project = safe(project)
    identity, files = owned(project)
    require(format_profile in ('none', 'grea'), 'Unknown format profile')
    assets = project/'Assets'
    quarantine = document(find_analysis(project,'unity-code-quarantine.json'))
    known = {r['path']:r['sha256'] for r in quarantine['schemaApplied']}
    require(len(known) == 1, 'Exactly one schema-derived class required')
    code = {p.relative_to(project).as_posix() for p in assets.rglob('*') if p.is_file() and p.suffix.lower() in CODE_SUFFIXES}
    require(code == set(known), 'Unknown executable source is present')
    require(all(fingerprint(inside(project, p)) == h for p,h in known.items()), 'Schema source changed')
    packages = document(project/'Packages/manifest.json')
    require(set(packages) == {'dependencies'} and all(k.startswith('com.unity.modules.') and v == '1.0.0' for k,v in packages['dependencies'].items()),
            'Only existing built-in engine packages supported by this native profile')
    model = document(find_analysis(project,'unity-code-model.json'))
    require(len(model['classes']) == 1, 'One class required')
    cls = model['classes'][0]
    fields = cls['fields']
    require(fields and all(f['name'] == f['csName'] and f['csType'] == 'UnityEngine.Sprite[]' for f in fields), 'Only unchanged Sprite[] fields supported')
    require(len(cls['instances']) == 1, 'One source component required')
    script = next(iter(known))
    require(known[script] == cls['targetSha256'], 'Generated schema/model identity differs')
    expected_assembly = cls['assembly'].removesuffix('.dll')
    asmdefs = list(assets.rglob('*.asmdef'))
    require(len(asmdefs) == 1 and document(asmdefs[0]) in ({'name':expected_assembly}, {'name':expected_assembly,'references':[],'allowUnsafeCode':True}), 'Unproven assembly definitions')
    docs = [document(find_analysis(project,'unity-typed-objects.json'))]
    docs += [document(p) for p in sorted([*(project/'Analysis/Evidence').glob('dependency-typed-*.json'),*(project/'Analysis').glob('dependency-typed-*.json')])]
    objects = SourceObjects(docs)
    primary = docs[0]['objects']
    require(len(primary) == 5 and sorted(o['type'] for o in primary) == ['AssetBundle','GameObject','MonoBehaviour','MonoScript','Transform'],
            'Only one original leaf Prefab, Transform and component supported')
    require(all(o.get('status') == 'parsed' for o in primary), 'Unknown primary object')
    instance = cls['instances'][0]
    component_key = (0,instance['file'],instance['pathId'])
    component = objects.objects[component_key]
    require(component['type'] == 'MonoBehaviour' and component.get('typeTreeSource') == 'embedded', 'Embedded original field values required')
    root_key, root = objects.resolve(component_key, component['data']['m_GameObject'], 'GameObject')
    transform = next(o for o in primary if o['type'] == 'Transform')
    transform_key = (0, transform['file'], transform['pathId'])
    require(objects.resolve(transform_key, transform['data']['m_GameObject'], 'GameObject')[0] == root_key and
            transform['data']['m_Children'] == [] and transform['data']['m_Father']['pathId'] == '0', 'Original hierarchy is not a leaf')
    component_keys = {objects.resolve(root_key, x['component'], 'Transform' if i == 0 else 'MonoBehaviour')[0] for i,x in enumerate(root['data']['m_Component'])}
    require(component_keys == {transform_key, component_key}, 'Unproven original component layout')
    prefabs = list(assets.rglob('*.prefab'))
    require(len(prefabs) == 1 and not list(assets.rglob('*.unity')), 'Only one native leaf Prefab supported')
    prefab = prefabs[0].relative_to(project).as_posix()
    require(prefabs[0].stem == root['data']['m_Name'], 'Prefab basename/root-name mismatch requires a different roundtrip profile')
    script_guid = guid(project, script)
    require(read(prefabs[0]).count(('guid: '+script_guid).encode()) == 1, 'Prefab schema binding is not unique')
    hydration = document(find_analysis(project,'texture-hydration.json'))
    textures = {}
    sprite_specs = []
    asset_paths = {}
    lengths = []
    relocation_path=find_analysis(project,'unity-relocation.json')
    relocations=document(relocation_path).get('moves',[]) if relocation_path.exists() else []

    def native_asset(key, suffix):
        name = objects.unique_name(key)
        matches = [p for p in assets.rglob('*'+suffix) if p.name == name+suffix]
        for move in relocations:
            if Path(move['source']).name!=name+suffix:continue
            target=inside(project,move['target'])
            require(target.is_file() and target.suffix==suffix and guid(project,move['target'])==move.get('guid'),'Relocated source asset identity differs')
            if target not in matches:matches.append(target)
        require(len(matches) == 1, 'Exact unique native filename unavailable: '+name+suffix)
        rel = matches[0].relative_to(project).as_posix()
        return rel, guid(project, rel)

    for field in fields:
        values = component['data'][field['name']]
        require(values is None or isinstance(values, list), 'Unsupported array representation')
        lengths.append(-1 if values is None else len(values))
        require(values is None or len(values) <= 10000, 'Array reference budget')
        for ptr in values or []:
            key, sprite = objects.resolve(component_key, ptr, 'Sprite')
            data = sprite['data']
            atlas_key, atlas = objects.resolve(key, data['m_SpriteAtlas'], 'SpriteAtlas')
            require(not atlas['data']['m_IsVariant'], 'Variant atlases unsupported')
            matches = [value for original_key,value in atlas['data']['m_RenderDataMap'] if original_key == data['m_RenderDataKey']]
            require(len(matches) == 1, 'Exact Sprite atlas render key is missing or ambiguous')
            rd = matches[0]
            from .unity_sprite import atlas_settings
            try:packing=atlas_settings(rd['settingsRaw'])
            except (ValueError,KeyError,TypeError) as error:require(False,'Unproven Sprite atlas settings: '+str(error))
            require(rd['downscaleMultiplier'] == 1 and rd['alphaTexture']['pathId'] == '0' and not rd['secondaryTextures'],
                    'Atlas alpha/downscale variant is not proven')
            texture_key, texture = objects.resolve(atlas_key, rd['texture'], 'Texture2D')
            asset, asset_guid = native_asset(key, '.asset')
            ids = re.findall(rb'^--- !u!213 &(-?[0-9]+)$', read(project/asset), re.M)
            require(len(ids) == 1, 'One native Sprite asset/local ID required')
            texture_path, texture_guid = native_asset(texture_key, '.png')
            if texture_key not in textures:
                source_file = objects.files[texture_key[:2]]['name']
                resolved = [r for r in hydration['consumed'] if r['file'] == source_file and r['pathId'] == texture_key[2]]
                require(len(resolved) == 1 and resolved[0]['normalization'] in ('BGRA-to-RGBA-no-flip-v1','DDS-DXT5-to-RGBA-no-flip-v1'), 'Canonical texture hydration proof required')
                with Image.open(project/texture_path) as im:
                    require(im.size == (texture['data']['m_Width'],texture['data']['m_Height']) and im.width*im.height <= 16*1024*1024, 'Native texture dimensions differ')
                    pixel_hash = sha(im.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes())
                require(pixel_hash == resolved[0]['rgbaRawSha256'], 'Native PNG pixels differ from exact source hydration')
                textures[texture_key] = dict(path=texture_path, guid=texture_guid, sourceFile=source_file, sourcePathId=texture_key[2], width=texture['data']['m_Width'],height=texture['data']['m_Height'],rgbaRawSha256=pixel_hash)
            rect = rd['textureRect']
            require(set(rect) == {'x','y','width','height'}, 'Unsupported atlas rect')
            mesh={}
            if packing['packingMode']=='Tight':
                source_file=objects.files[key[:2]]
                require(source_file.get('unityVersion')=='2021.3.30f1' and source_file.get('targetPlatform')=='20','Tight Sprite source version/platform requires a verified profile')
                from .unity_sprite import tight_geometry
                try:mesh=tight_geometry(data,rd,texture['data']['m_Width'],texture['data']['m_Height'])
                except (ValueError,KeyError,TypeError) as error:require(False,'Unsupported exact tight geometry: '+str(error))
            sprite_specs.append(dict(name=objects.unique_name(key),guid=asset_guid,fileId=ids[0].decode(),textureGuid=texture_guid,sourceFile=objects.files[key[:2]]['name'],sourcePathId=key[2],sourceRawSha256=sprite.get('rawSha256'),packingSettings=packing,**rect,**mesh))
            asset_paths[asset] = (asset_guid,'sprite')
            asset_paths[texture_path] = (texture_guid,'texture')
    require(sprite_specs, 'At least one resolved Sprite reference required')
    moves = []
    pins = []
    for path,(asset_guid,kind) in sorted(asset_paths.items()):
        meta = read(project/(path+'.meta')).decode('utf-8-sig')
        bundled = re.search(r'^\s*assetBundleName:\s*(.*?)\s*$', meta, re.M)
        if 'resources' in [p.lower() for p in Path(path).parts] or (bundled and bundled[1] not in ('',"''",'""')):
            pins.append(dict(path=path,reason='Resources or explicit bundle name preserves dynamic loading identity'))
            continue
    spec = dict(prefabPath=prefab,className='.'.join(x for x in (cls['namespace'],cls['name']) if x),scriptPath=script,
                fields=[f['name'] for f in fields],expectedArrayLengths=lengths,saveRoundtrip=True,expectedSpriteReferences=len(sprite_specs),
                verifySourceDescriptors=True,expectedScriptGuid=script_guid,expectedPrefabGuid=guid(project,prefab),expectedRootName=root['data']['m_Name'],
                expectedPosition=transform['data']['m_LocalPosition'],expectedScale=transform['data']['m_LocalScale'],expectedRotation=transform['data']['m_LocalRotation'],
                expectedActive=root['data']['m_IsActive'],expectedSprites=sprite_specs,expectedTextures=list(textures.values()),formatMoves=moves)
    seals = [dict(path=r['path'],guid=guid(project,r['path'][:-5])) for r in files if r['path'].startswith('Assets/') and r['path'].endswith('.meta')]
    return dict(schemaVersion=1,profile=PROFILE,candidateManifestSha256=identity,format=format_profile,spec=spec,sourceScript=cls['sourceScript'],
                textures=list(textures.values()),nativeIdentitySeals=seals,pinned=pins,scope='one original leaf Prefab, embedded Sprite[] fields, exact hydrated atlas references; methods/visual/gameplay pending')


def execute(project, output, editor, budget_seconds=1200, format_profile='none'):
    project = safe(project)
    editor = safe(editor)
    require(editor.is_file() and editor.name in ('Unity','Unity.exe'), 'Existing exact Unity executable required')
    require(type(budget_seconds) is int and 1<=budget_seconds<=1200, 'Expected native method budget 1..1200 seconds')
    prepared = plan(project,format_profile)
    rows = subprocess.check_output(['ps','-axo','pid=,comm='],text=True).splitlines()
    conflicts = [r for r in rows if r.strip().split(maxsplit=1)[-1].endswith(('/Contents/MacOS/Unity','/Contents/MacOS/CocosCreator','/Unity.exe','/CocosCreator.exe'))]
    require(not conflicts, 'Another main Editor is running; native resources unavailable')
    out = new_output(output,[project,editor])
    work = out/'UnityProject'
    shutil.copytree(project,work)
    require(owned(work)[0] == prepared['candidateManifestSha256'], 'Candidate changed during native copy')
    helper = Path(__file__).parent/'targets/UnitySourceVerifier.cs'
    dest = work/'Assets/Editor/Monkey/UnitySourceVerifier.cs'
    require(not dest.exists() and not (work/'Assets/MonkeyRecoveryVerification').exists(), 'Fresh helper/probe paths required')
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(helper,dest)
    anchor = now()
    deadline = anchor+timedelta(minutes=28)
    end = anchor+timedelta(minutes=30)
    spec = prepared['spec']
    spec.update(deadlineUtc=stamp(deadline),budgetSeconds=budget_seconds)
    write_json(find_analysis(work,'native-check-spec.json'),spec)
    prepared.update(stageAnchorUtc=stamp(anchor),deadlineUtc=stamp(deadline),windowEndUtc=stamp(end),helperSha256=fingerprint(helper))
    write_json(out/'native-plan.json',prepared)
    result = dict(schemaVersion=1,profile=PROFILE,status='started',processExited=False,startedUtc=stamp(anchor),candidateManifestSha256=prepared['candidateManifestSha256'],
                  visual='not_run',business='not_run',format=dict(profile=format_profile,applied=False))
    receipt = out/'execution-result.json'
    write_json(receipt,result)
    log = out/'import.log'
    console = out/'console.log'
    log.touch(mode=0o600);console.touch(mode=0o600)
    child = None
    interrupted = []
    handlers = {}
    try:
        with console.open('w') as stream:
            child = subprocess.Popen([str(editor),'-batchmode','-nographics','-quit','-projectPath',str(work),'-executeMethod','Monkey.UnityRecovery.SourceVerifier.Run','-logFile',str(log)],
                                     cwd=work,stdout=stream,stderr=subprocess.STDOUT)
            result['pid'] = child.pid
            write_json(receipt,result)
            for sig in (signal.SIGINT,signal.SIGTERM):
                handlers[sig] = signal.getsignal(sig)
                signal.signal(sig,lambda number,frame:interrupted.append(number))
            while child.poll() is None:
                if interrupted or now()>=deadline:
                    result['stopReason'] = 'operator_interrupt' if interrupted else 'fixed_deadline'
                    child.terminate()
                    break
                time.sleep(.5)
            if child.poll() is None:
                try: child.wait(timeout=max(.01,min(120,(end-now()).total_seconds())))
                except subprocess.TimeoutExpired: pass
            result.update(processExited=child.poll() is not None,exitCode=child.poll())
    finally:
        for sig,handler in handlers.items():signal.signal(sig,handler)
        if child is not None and child.poll() is None and 'stopReason' not in result:
            child.terminate()
            try:child.wait(timeout=max(.01,min(120,(end-now()).total_seconds())))
            except subprocess.TimeoutExpired:pass
        result.update(endedUtc=stamp(now()),redactedLog=redact_log(log))
        rb = find_analysis(work,'unity-source-readback.json')
        if rb.exists():
            try:result['readback'] = document(rb)
            except Exception as error:result['readbackError'] = str(error)[:4096]
        result['status'] = 'failed' if child is None or child.poll() is not None else 'pending_child_exit'
        if child is not None:
            result.update(processExited=child.poll() is not None,exitCode=child.poll())
        try:
            if child is not None and child.poll() == 0 and rb.exists():
                data = document(rb)
                result['readback'] = data
                checks = dict(status=data.get('status')=='resource_subset_verified',version=data.get('unityVersion')==TARGET_VERSION,
                              nodeCount=data.get('nodeCount')==1,component=data.get('classFound') is True,missingScripts=data.get('missingScripts')==0,
                          componentTypes=sorted(data.get('componentTypes',[]))==sorted(['UnityEngine.Transform',spec['className']]),
                              scriptClass=data.get('scriptClass')==spec['className'],scriptGuid=data.get('scriptGuid')==spec['expectedScriptGuid'],
                              prefabGuid=data.get('guid')==spec['expectedPrefabGuid'],saved=data.get('saved') is True,reloaded=data.get('prefabReloaded') is True,
                              referencesPreserved=data.get('referencesPreserved') is True,sourceDescriptors=data.get('sourceDescriptorsVerified') is True,
                              geometry=data.get('geometryPreserved') is True,spriteReferences=data.get('spriteReferences')==spec['expectedSpriteReferences'],
                              fields=[(r['name'],r['type'],r['arrayLength'],r['nullElements'])for r in data.get('fields',[])] ==
                                     [(name,'UnityEngine.Sprite[]',length,0)for name,length in zip(spec['fields'],spec['expectedArrayLengths'])],
                              typedMoves=data.get('movedAssets',[])==spec['formatMoves'])
                texture_rows=data.get('textureReadback')or[]
                checks['texturePixels']=len(texture_rows)==len(spec['expectedTextures'])and all(
                    actual.get('guid')==expected['guid']and actual.get('rgbaRawSha256')==expected['rgbaRawSha256']and actual.get('width')==expected['width']and actual.get('height')==expected['height']and actual.get('readableRestored')is True and actual.get('alphaDilationDisabled')is True and actual.get('compression')=='Uncompressed'
                    for actual,expected in zip(texture_rows,spec['expectedTextures']))
                moved = {r['from']:r['to'] for r in spec['formatMoves']}
                checks['allOriginalMetaGuids'] = all(guid(work,moved.get(r['path'][:-5],r['path'][:-5]))==r['guid'] for r in prepared['nativeIdentitySeals'])
                checks['sourceUnchanged'] = owned(project)[0] == prepared['candidateManifestSha256']
                result['checks'] = checks
                if all(checks.values()):
                    result['status'] = 'resource_subset_verified'
                    result['format'] = dict(profile=format_profile,applied=False,moved=0,pinned=len(prepared['pinned']))
        except Exception as error:
            result.update(status='verification_failed',error=str(error)[:4096])
        write_json(receipt,result)
    return result


def finish_conversion(conversion, settings, format_profile='none'):
    """Execute only after successful export. Failed proofs retain the none candidate."""
    from .sources.compiled import ParseError
    candidate = settings['candidate']/'UnityProject'
    out = settings['candidate']
    if conversion.get('completed') is not True:
        conversion['nativeExecution'] = dict(status='not_run',reason='CONVERSION_INCOMPLETE')
    else:
        try:
            proof = execute(candidate,settings['output'],settings['editors']['unity-6000.6.2f1-ugui'],settings['budget'],format_profile)
            conversion['nativeExecution'] = dict(status=proof['status'],processExited=proof['processExited'],report=str(settings['output']/'execution-result.json'),error=proof.get('error') or proof.get('readback',{}).get('error'))
            if proof['status'] == 'resource_subset_verified':
                conversion['validation']['editor'] = 'resource_subset_verified'
                conversion['projects'][0]['resourceStatus'] = 'leaf-prefab-sprite-references-save-reload-verified'
        except ParseError as error:
            conversion['nativeExecution'] = dict(status='blocked',reason=str(error))
    conversion['requestedFormat'] = format_profile
    if format_profile == 'grea':
        # Conversion already relocated the export into monkey-project/2.0.0; grea is a deprecated alias.
        conversion['format'] = dict(profile='grea',status='retired',applied=False,layout=VERSION)
    write_json(out/'conversion-result.json',conversion)
    return conversion
