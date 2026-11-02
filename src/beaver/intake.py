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


def build_plan(candidate, target, spec_path):
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
    requirements, conflicts = project_requirements(incoming, target, manifest['targetProfile'])
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
    for row in spec['additions']:
        src, dest = row['source'], row['target']
        if src not in files or src+'.meta' not in files:
            fail('INTAKE_SOURCE_PAIR', src, 'Selected manifest file and metadata pair required')
        g = guid(read(inside(incoming, src+'.meta')), src)
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
    covered = set()
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
    for row in spec['omittedCompilerInputs']:
        if row['path'] not in files:
            fail('INTAKE_COMPILER_OMISSION', row['path'], 'Omitted compiler input must exist in candidate')
        covered.add(row['path'])
    compiler_inputs = {p for p in files if p.startswith('Assets/') and Path(p).suffix.lower() in COMPILER}
    if compiler_inputs != covered or any(p.endswith('.dll') for p in compiler_inputs):
        fail('INTAKE_COMPILER_COVERAGE', str(incoming), 'Every compiler input must be explicitly reused or covered; DLL intake unsupported')
    selected_guids = new_guids | {r['sourceGuid'] for r in externals}
    for row in additions:
        # V1 supports GUID-serialized text assets and opaque raw image/font inputs.
        if Path(row['source']).suffix.lower() not in {'.png', '.ttf', '.otf'}:
            raw = read(incoming/row['source'], max_bytes=MANIFEST_BYTES)
            for g in REFERENCES.findall(raw):
                value = g.decode()
                if value != '0'*32 and value not in selected_guids:
                    fail('INTAKE_DEPENDENCY_CLOSURE', row['source'], 'Unselected or undeclared serialized GUID reference: '+value)
        for g in REFERENCES.findall(read(incoming/(row['source']+'.meta'))):
            value = g.decode()
            if value not in selected_guids | {'0'*32}:
                fail('INTAKE_IMPORTER_REFERENCE', row['source'], 'Importer reference outside selected closure')
    verifications = {v['asset']: v for v in spec['verifications']}
    prefabs = {r['source'] for r in additions if r['source'].endswith('.prefab')}
    if set(verifications) != prefabs:
        fail('INTAKE_PREFAB_EXPECTATIONS', str(incoming), 'Every added Prefab requires exact native object/field expectations')
    for v in verifications.values():
        for obj in v['objects']:
            for field in obj['fields']:
                if field['kind'] == 'object' and field['value']['guid'] not in selected_guids | {''}:
                    fail('INTAKE_EXPECTATION_REFERENCE', v['asset'], 'Object expectation references outside selected closure')
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
    return dict(schemaVersion=1, contract=CONTRACT, implementationSha256=identity(),
                candidateRoot=str(incoming), candidateManifestSha256=manifest_hash, namespace=manifest['namespace'],
                targetRoot=str(target), targetProfile=manifest['targetProfile'], targetBefore=before,
                targetDirectoriesBefore=directories,targetAuxiliary=auxiliary,
                targetBeforeSha256=sha(encoded(before)), specPath=str(spec_path), specSha256=digest_file(spec_path),
                spec=spec, additions=additions, externalScripts=externals, newDirectories=sorted(parents),
                sourceCandidateValidation={k:manifest.get(k) for k in ('native','diagnostics','staticPresentation','visibleEdits','player','business')},
                projectRequirements=requirements, existingAdoptionState='untouched',
                policy='create-only; retained source/meta unchanged; no baseline claim; independent native reopen; guarded rollback',
                native='not_run', visual='not_run', business='not_run')


def preview(candidate, target, spec, output):
    plan = build_plan(candidate, target, spec)
    out = new_output(output, [safe(candidate), safe(target), safe(spec)])
    write_json(out/'intake-plan.json', plan)
    digest = digest_file(out/'intake-plan.json')
    write_json(out/'plan-identity.json', dict(sha256=digest))
    return dict(status='planned', report=str(out/'intake-plan.json'), planSha256=digest,
                additions=len(plan['additions']), externalScripts=len(plan['externalScripts']), native='not_run')


def checked_plan(path, expected):
    path = safe(path)
    if not expected or digest_file(path) != expected:
        fail('INTAKE_PLAN_CHANGED', str(path), 'Explicit exact plan hash required')
    plan = load(read(path, max_bytes=MANIFEST_BYTES), max_nodes=MANIFEST_NODES)
    if plan.get('contract') != CONTRACT or plan.get('implementationSha256') != identity():
        fail('INTAKE_IMPLEMENTATION', str(path), 'Original exact intake implementation required')
    if digest_file(path) != load(read(path.parent/'plan-identity.json')).get('sha256'):
        fail('INTAKE_PLAN_CHANGED', str(path), 'Saved plan identity differs')
    return plan


def recheck(plan):
    fresh = build_plan(plan['candidateRoot'], plan['targetRoot'], plan['specPath'])
    if fresh != plan:
        fail('INTAKE_PRECONDITION_DRIFT', plan['targetRoot'], 'Candidate, spec, evidence or exact target before-state changed')

