"""Baseline-free, create-only intake plans; existing adoption is unchanged."""
from pathlib import Path
import re
import unicodedata

from .io import safe, inside, read, load, sha, encoded, write_json, new_output
from .errors import fail
from .output_limits import digest_file, MANIFEST_BYTES, MANIFEST_NODES
from .candidate_snapshot import snapshot, verify
from .intake_contract import validate_spec
from .unity import source_files, source_directories
from .implementation import identity

CONTRACT = 'beaver-additive-intake/1'
CONTRACT_V2 = 'beaver-additive-intake/2'
CONTRACT_V3 = 'beaver-additive-intake/3'
CONTRACT_V4 = 'beaver-additive-intake/4'
CONTRACT_V5 = 'beaver-additive-intake/5'
GUID = re.compile(rb'^guid:\s*([a-f0-9]{32})\s*$', re.M)
REFERENCES = re.compile(rb'\bguid:\s*([a-f0-9]{32})\b')
COMPILER = {'.cs', '.asmdef', '.asmref', '.rsp', '.dll'}


def folded(path):
    return unicodedata.normalize('NFC', path).casefold()


def resource_key(path):
    return folded(path.split('/Resources/', 1)[1].rsplit('.', 1)[0]) if '/Resources/' in path else None


def guid(raw, where):
    match = GUID.search(raw)
    if not match:
        fail('INTAKE_META', where, 'Exact imported asset GUID required')
    return match.group(1).decode()


def pinned(path, expected):
    path = safe(path)
    if not path.is_file() or digest_file(path) != expected:
        fail('INTAKE_INPUT_DRIFT', str(path), 'Pinned input changed or is missing')
    return path


def resolution_context(package_evidence, expected_package_evidence):
    if bool(package_evidence) != bool(expected_package_evidence):
        fail('INTAKE_PACKAGE_EVIDENCE', str(package_evidence), 'Resolution file and exact SHA-256 are required together')
    if not package_evidence:return None,None
    context_path=pinned(package_evidence,expected_package_evidence)
    context=load(read(context_path,max_bytes=MANIFEST_BYTES),max_nodes=MANIFEST_NODES)
    if not isinstance(context,dict) or set(context)!={'contract','sourceProject','editorPath','evidence'} or context['contract']!='beaver-unity-package-resolution/1':
        fail('INTAKE_PACKAGE_EVIDENCE',str(context_path),'Closed explicit source/Editor/evidence context required')
    if any(not isinstance(context[k],str) or not Path(context[k]).is_absolute() for k in ('sourceProject','editorPath')):
        fail('INTAKE_PACKAGE_EVIDENCE',str(context_path),'Explicit absolute source project and Editor paths required')
    return context,context_path


def build_plan(candidate, target, spec_path, package_evidence=None, expected_package_evidence=None):
    incoming, manifest, files, manifest_hash = snapshot(candidate)
    verify(incoming, files)
    spec_path = safe(spec_path)
    spec = validate_spec(load(read(spec_path, max_bytes=MANIFEST_BYTES), max_nodes=MANIFEST_NODES))
    if manifest_hash != spec['candidateManifestSha256']:
        fail('INTAKE_CANDIDATE_DRIFT', str(incoming), 'Candidate manifest differs from reviewed input')
    if manifest['targetProfile'] != 'unity-6000.6.2f1-ugui':
        fail('INTAKE_PROFILE', str(incoming), 'Unity 6000.6.2f1 only')
    target = safe(target)
    if incoming == target or incoming.is_relative_to(target) or target.is_relative_to(incoming):
        fail('OUTPUT_OVERLAP', str(target), 'Independent candidate and target required')
    if not (target/'Assets').is_dir():
        fail('INTAKE_TARGET', str(target), 'Existing owned Unity project required')
    from .adoption import project_requirements
    resolution, context_path = resolution_context(package_evidence, expected_package_evidence)
    requirements, conflicts = project_requirements(incoming, target, manifest['targetProfile'], resolution=resolution)
    if conflicts:
        fail('INTAKE_REQUIREMENTS', str(target), 'Editor/package requirements differ; do not install or change settings')
    before = source_files(target)
    directories = source_directories(target)
    case_directories = {folded(p):p for p in directories}
    if len(case_directories)!=len(directories) or any(p=='Assets/BeaverIntakeTools' or p.startswith('Assets/BeaverIntakeTools/') for p in directories):
        fail('INTAKE_TARGET_ALIAS',str(target),'Directory alias or reserved helper directory exists')
    auxiliary = {p:(digest_file(target/p) if (target/p).is_file() else None) for p in ('.beaver/adoption/state.json','.monkey/adoption/state.json')}
    case_paths = {folded(p): p for p in before}
    if len(case_paths) != len(before):
        fail('INTAKE_TARGET_ALIAS', str(target), 'Target contains case/Unicode aliases')
    existing_guids = {}
    for p in before:
        if p.startswith('Assets/') and p.endswith('.meta'):
            match = GUID.search(read(inside(target, p)))
            if match:
                existing_guids.setdefault(match.group(1).decode(), []).append(p[:-5])
    candidate_guids = {}
    for p in files:
        if p.startswith('Assets/') and p.endswith('.meta') and p[:-5] in files:
            g = guid(read(inside(incoming, p)), p)
            if g in candidate_guids:
                fail('INTAKE_CANDIDATE_GUID', p, 'Duplicate candidate asset GUID')
            candidate_guids[g] = p[:-5]
    additions = []
    new_guids = set()
    targets = set()
    keys = {resource_key(p) for p in before if not p.endswith('.meta') and resource_key(p)}
    new_scripts = spec.get('newScripts', [])
    from .intake_assemblies import validate as validate_assemblies
    retained_assemblies = validate_assemblies(spec, incoming, files, target, before, existing_guids) if spec['schemaVersion'] >= 5 else []
    for row in spec['additions'] + new_scripts:
        src, dest = row['source'], row['target']
        if src not in files or src+'.meta' not in files:
            fail('INTAKE_SOURCE_PAIR', src, 'Selected manifest file and metadata pair required')
        g = guid(read(inside(incoming, src+'.meta')), src)
        if row in new_scripts:
            if g != row['guid'] or files[src]['sha256'] != row['sha256'] or files[src+'.meta']['sha256'] != row['metaSha256']:
                fail('INTAKE_NEW_SCRIPT_PIN', src, 'Reviewed exact compiler source/meta/GUID required')
            for path in before if spec['schemaVersion'] < 5 else []:
                if path.endswith(('.asmdef','.asmref')) and dest.startswith(str(Path(path).parent)+'/'):
                    fail('INTAKE_NEW_SCRIPT_DOMAIN', dest, 'New scripts require default Assembly-CSharp, not an existing assembly scope')
        if g in existing_guids or g in new_guids:
            fail('INTAKE_GUID_OCCUPIED', g, 'New asset GUID is already owned; declare external script reuse separately')
        if folded(dest) in case_paths or folded(dest+'.meta') in case_paths or (target/dest).exists():
            fail('INTAKE_DESTINATION', dest, 'New destination and metadata must be absent')
        parent = Path(dest).parent
        while parent.as_posix() != 'Assets':
            if folded(parent.as_posix()) in case_paths:
                fail('INTAKE_PARENT_FILE', str(parent), 'Destination ancestor is an existing file')
            if folded(parent.as_posix()) in case_directories and case_directories[folded(parent.as_posix())]!=parent.as_posix():
                fail('INTAKE_TARGET_ALIAS',str(parent),'Destination aliases an existing directory')
            parent = parent.parent
        key = resource_key(dest)
        if key and key in keys:
            fail('INTAKE_RESOURCE_KEY', dest, 'Resources key already exists in target or additions')
        if key: keys.add(key)
        new_guids.add(g); targets.add(dest)
        additions.append(dict(source=src, target=dest, guid=g, file=files[src], meta=files[src+'.meta']))
    externals = []
    covered = {r['source'] for r in new_scripts}
    for row in spec['externalScripts']:
        src, dest = row['source'], row['target']
        if src not in files or src+'.meta' not in files or guid(read(incoming/(src+'.meta')), src) != row['sourceGuid']:
            fail('INTAKE_SCRIPT_SOURCE', src, 'Exact candidate MonoScript file/meta GUID required')
        if existing_guids.get(row['targetGuid']) != [dest]:
            fail('INTAKE_SCRIPT_IDENTITY', dest, 'Exactly one retained target GUID/path required')
        for path, expected in [(dest, row['targetSha256']), (dest+'.meta', row['targetMetaSha256'])]:
            if before.get(path, {}).get('sha256') != expected:
                fail('INTAKE_SCRIPT_DRIFT', path, 'Reviewed retained script bytes differ')
        externals.append(row); covered.add(src)
    from .intake_external import assets, package_scripts
    external_assets = assets(spec, incoming, files, before, existing_guids, guid)
    packages = package_scripts(spec, target, existing_guids, requirements=requirements)
    for row in packages:
        source = candidate_guids.get(row['guid'])
        if source and source.endswith('.cs'):
            covered.add(source)
    for row in spec['omittedCompilerInputs']:
        if row['path'] not in files:
            fail('INTAKE_COMPILER_OMISSION', row['path'], 'Omitted compiler input must exist in candidate')
        covered.add(row['path'])
    compiler_inputs = {p for p in files if p.startswith('Assets/') and Path(p).suffix.lower() in COMPILER}
    if compiler_inputs != covered or any(p.endswith('.dll') for p in compiler_inputs):
        fail('INTAKE_COMPILER_COVERAGE', str(incoming), 'Every compiler input must be explicitly reused or covered; DLL intake unsupported')
    selected_guids = new_guids | {r['sourceGuid'] for r in externals} | {r['guid'] for r in external_assets + packages}
    from .intake_engine import declarations, text_references, expected_reference
    engine_objects = spec.get('engineObjects', [])
    engine = declarations(engine_objects, selected_guids)
    engine_used = set()
    for row in additions + external_assets:
        if Path(row['source']).suffix.lower() not in {'.png', '.ttf', '.otf'}:
            engine_used |= text_references(read(incoming/row['source'], max_bytes=MANIFEST_BYTES), row['source'], selected_guids, engine, strict=spec['schemaVersion']>=4)
        text_references(read(incoming/(row['source']+'.meta')), row['source'], selected_guids, engine, importer=True, strict=spec['schemaVersion']>=4)
    if set(engine) != engine_used:
        fail('INTAKE_ENGINE_UNUSED', 'engineObjects', 'Every declared engine identity must occur as an exact selected serialized PPtr')
    verifications = {v['asset']: v for v in spec['verifications']}
    prefabs = {r['source'] for r in additions if r['source'].endswith('.prefab')}
    if set(verifications) != prefabs:
        fail('INTAKE_PREFAB_EXPECTATIONS', str(incoming), 'Every added Prefab requires exact native object/field expectations')
    for v in verifications.values():
        for obj in v['objects']:
            for field in obj['fields']:
                if field['kind'] == 'object':
                    expected_reference(field['value'], v['asset'], selected_guids, engine)
    for row in external_assets:
        for obj in row['objects']:
            for field in obj['fields']:
                if field['kind'] == 'object':
                    expected_reference(field['value'], row['source'], selected_guids, engine, strict=spec['schemaVersion']>=4)
    for r in spec['protectedAssets']:
        for path, expected in [(r['path'], r['sha256']), (r['path']+'.meta', r['metaSha256'])]:
            if before.get(path, {}).get('sha256') != expected:
                fail('INTAKE_PROTECTED_DRIFT', path, 'Protected before-image differs')
    for r in spec['evidence']: pinned(r['path'], r['sha256'])
    parents = set()
    for row in additions:
        p = Path(row['target']).parent
        while p.as_posix() != 'Assets':
            if not inside(target, p.as_posix()).exists(): parents.add(p.as_posix())
            p = p.parent
    plan = dict(schemaVersion=spec['schemaVersion'], contract={1:CONTRACT,2:CONTRACT_V2,3:CONTRACT_V3,4:CONTRACT_V4,5:CONTRACT_V5}[spec['schemaVersion']], implementationSha256=identity(),
                candidateRoot=str(incoming), candidateManifestSha256=manifest_hash, namespace=manifest['namespace'],
                targetRoot=str(target), targetProfile=manifest['targetProfile'], targetBefore=before,
                targetDirectoriesBefore=directories,targetAuxiliary=auxiliary,
                targetBeforeSha256=sha(encoded(before)), specPath=str(spec_path), specSha256=digest_file(spec_path),
                spec=spec, additions=additions, externalScripts=externals, newDirectories=sorted(parents),
                sourceCandidateValidation={k:manifest.get(k) for k in ('native','diagnostics','staticPresentation','visibleEdits','player','business')},
                projectRequirements=requirements, existingAdoptionState='untouched',
                policy='create-only; retained source/meta unchanged; no baseline claim; independent native reopen; guarded rollback',
                native='not_run', visual='not_run', business='not_run')
    if package_evidence:
        plan['packageResolution'] = dict(path=str(context_path), sha256=expected_package_evidence)
    if spec['schemaVersion']>=2:
        from .intake_external import package_inputs
        plan.update(externalAssets=external_assets, packageScripts=packages, packageInputs=package_inputs(packages))
    if spec['schemaVersion']>=3:
        plan['newScripts'] = new_scripts
    if spec['schemaVersion']>=4:
        plan['engineObjects'] = engine_objects
    if spec['schemaVersion']>=5:
        plan['retainedAssemblies'] = retained_assemblies
    return plan


def plan_from_args(args):
    return preview(args.candidate, args.target, args.spec, args.out,
                   args.package_evidence, args.expected_package_evidence)


def preview(candidate, target, spec, output, package_evidence=None, expected_package_evidence=None):
    plan = build_plan(candidate, target, spec, package_evidence, expected_package_evidence)
    resolution,_ = resolution_context(package_evidence,expected_package_evidence)
    out = new_output(output, [safe(candidate), safe(target), safe(spec)] + ([safe(resolution['sourceProject']),safe(resolution['editorPath'])] if resolution else []))
    write_json(out/'intake-plan.json', plan)
    digest = digest_file(out/'intake-plan.json')
    write_json(out/'plan-identity.json', dict(sha256=digest))
    result = dict(status='planned', report=str(out/'intake-plan.json'), planSha256=digest,
                  additions=len(plan['additions']), externalScripts=len(plan['externalScripts']), native='not_run')
    if plan['schemaVersion']>=2:
        result.update(externalAssets=len(plan['externalAssets']), packageScripts=len(plan['packageScripts']))
    if plan['schemaVersion']>=3:
        result.update(newScripts=len(plan['newScripts']),maximumNativePhases=5 if plan['newScripts'] else 3)
    if plan['schemaVersion']>=4:
        result.update(engineObjects=len(plan['engineObjects']))
    if plan['schemaVersion']>=5:
        result.update(retainedAssemblies=len(plan['retainedAssemblies']),scriptPolicy='schema-only-retained-assembly/1')
    return result


def checked_plan(path, expected):
    path = safe(path)
    if not expected or digest_file(path) != expected:
        fail('INTAKE_PLAN_CHANGED', str(path), 'Explicit exact plan hash required')
    plan = load(read(path, max_bytes=MANIFEST_BYTES), max_nodes=MANIFEST_NODES)
    if plan.get('contract') not in (CONTRACT, CONTRACT_V2, CONTRACT_V3, CONTRACT_V4, CONTRACT_V5) or plan.get('implementationSha256') != identity():
        fail('INTAKE_IMPLEMENTATION', str(path), 'Original exact intake implementation required')
    if digest_file(path) != load(read(path.parent/'plan-identity.json')).get('sha256'):
        fail('INTAKE_PLAN_CHANGED', str(path), 'Saved plan identity differs')
    return plan


def recheck(plan):
    resolution = plan.get('packageResolution', {})
    fresh = build_plan(plan['candidateRoot'], plan['targetRoot'], plan['specPath'], resolution.get('path'), resolution.get('sha256'))
    if fresh != plan:
        fail('INTAKE_PRECONDITION_DRIFT', plan['targetRoot'], 'Candidate, spec, evidence or exact target before-state changed')

