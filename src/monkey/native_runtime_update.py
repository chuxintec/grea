"""Apply a known producer runtime-template revision to a fresh native selection.

The native assets stay byte-identical; the new code still needs native compilation
and consumer validation. This is not a general source patcher or an adoption tool.
"""
from copy import deepcopy
from pathlib import Path
import re
import shutil
import uuid

from . import __version__
from .io import encoded, inside, load, new_output, read, safe, sha, write_json
from .native_selection import _relative, _template_profile, _CURRENT_TEMPLATE_DEPENDENCIES
from .sources.compiled import fail


def upgrade(candidate, expected_manifest, output):
    root = safe(candidate)
    original = read(root / 'manifest.json', max_bytes=128 * 1024 * 1024)
    if sha(original) != expected_manifest:
        fail('CANDIDATE_SHA_MISMATCH', str(root), 'Frozen selection manifest differs')
    manifest = load(original, max_nodes=8_000_000)
    if (manifest.get('schemaVersion') != 1 or manifest.get('targetProfile') != 'unity-6000.6.2f1-ugui'
            or not manifest.get('sourceNativeReadbackSha256') or not manifest.get('selection', {}).get('prefabs')):
        fail('RUNTIME_UPDATE_REQUIRES_NATIVE_SELECTION', str(root), 'Use a saved native selection as the immutable input')
    files = {}; names = {}; folded = set()
    for row in manifest.get('files', []):
        relative = _relative(row.get('path'), 'files.path')
        if relative == 'manifest.json' or relative in files or relative.casefold() in folded:
            fail('INVALID_MANIFEST', relative, 'Duplicate, case-colliding or reserved path')
        folded.add(relative.casefold())
        path = inside(root, relative)
        raw = read(path, max_bytes=256 * 1024 * 1024)
        if sha(raw) != row.get('sha256') or len(raw) != row.get('bytes'):
            fail('CANDIDATE_DRIFT', relative, 'Frozen candidate file differs')
        files[relative] = dict(row)
        if relative.endswith('.cs'): names.setdefault(Path(relative).name, []).append(relative)
    for path in root.rglob('*'):
        if path.is_symlink(): fail('SYMLINK_PATH', str(path), 'Frozen selections cannot contain links')
        if path.is_file() and path.relative_to(root).as_posix() not in set(files) | {'manifest.json'}:
            fail('CANDIDATE_UNOWNED', str(path), 'Use a clean frozen selection, not a working Editor project')
    changed = {}; additions = {}
    for name in ('NativeStaticSortQueueProxyPresenter.cs', 'NativeStaticSortQueueProxyGraphic.cs'):
        matches = names.get(name, [])
        if len(matches) != 1:
            fail('RUNTIME_TEMPLATE_AMBIGUOUS', name, 'Exactly one producer-owned template is required')
        relative = matches[0]
        profile = _template_profile(relative, files[relative]['sha256'])
        if profile is None or profile[0] != name:
            fail('RUNTIME_TEMPLATE_CHANGED', relative, 'Refusing to overwrite an unknown or consumer-adapted script')
        if relative + '.meta' not in files:
            fail('COMPILE_METADATA_MISSING', relative, 'Existing script identity must be frozen')
        changed[relative] = read(Path(__file__).parent / 'targets' / name)
    parent = Path(names['NativeStaticSortQueueProxyPresenter.cs'][0]).parent
    for name in ('NativeStaticSortQueueRuntime.cs', 'NativeStaticSortQueueProxyRaycaster.cs',
                 'NativeStaticSortInputSurface.cs', 'NativeStaticButtonTargetContract.cs', 'NativeStaticButtonTarget.cs'):
        matches = names.get(name, [])
        if len(matches) > 1: fail('RUNTIME_TEMPLATE_AMBIGUOUS', name, 'Duplicate runtime helper')
        if matches:
            relative = matches[0]
            if _template_profile(relative, files[relative]['sha256']) is None:
                fail('RUNTIME_TEMPLATE_CHANGED', relative, 'Unknown runtime helper revision')
            if relative + '.meta' not in files: fail('COMPILE_METADATA_MISSING', relative, 'Missing script identity')
        else:
            relative = (parent / name).as_posix()
            guid = uuid.uuid5(uuid.NAMESPACE_URL, manifest['namespace'] + '/native-sort-runtime-v1/' + relative).hex
            additions[relative + '.meta'] = ('fileFormatVersion: 2\nguid: ' + guid + '\nMonoImporter:\n'
                '  externalObjects: {}\n  serializedVersion: 2\n  defaultReferences: []\n'
                '  executionOrder: 0\n  icon: {instanceID: 0}\n  userData: \n'
                '  assetBundleName: \n  assetBundleVariant: \n').encode()
            names[name] = [relative]
        changed[relative] = read(Path(__file__).parent / 'targets' / name)
    # Compile dependencies come from the exact templates bundled by this tool;
    # require all providers, including non-GUID input helper references.
    edges = {e['path']: deepcopy(e) for e in manifest.get('adoptionDependencies', {}).get('edges', [])}
    for relative in changed:
        requires = []
        for name in _CURRENT_TEMPLATE_DEPENDENCIES[Path(relative).name]:
            found = names.get(name, [])
            if len(found) != 1: fail('DECLARED_CODE_DEPENDENCY_MISSING', name, 'Freeze the complete declared helper closure first')
            requires.append(found[0])
        if requires: edges[relative] = dict(path=relative, requires=sorted(set(requires)), kind='csharp-compile')
    guid_owners = {}
    for relative in sorted(p for p in set(files) | set(additions) if p.endswith('.meta')):
        raw = additions.get(relative) or read(inside(root, relative), max_bytes=2 * 1024 * 1024)
        match = re.search(rb'(?m)^guid:\s*([0-9a-f]{32})\s*$', raw)
        if match:
            guid = match[1].decode()
            if guid in guid_owners: fail('DUPLICATE_TARGET_GUID', relative, 'Generated runtime identity collides')
            guid_owners[guid] = relative
    out = new_output(output, [root])
    for relative in files:
        target = inside(out, relative); target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(inside(root, relative), target)
    changes = []
    for relative, raw in {**changed, **additions}.items():
        old = files.get(relative)
        target = inside(out, relative); target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        digest = sha(raw)
        files[relative] = dict(path=relative, sha256=digest, bytes=len(raw), owner='generated')
        changes.append(dict(path=relative, beforeSha256=old['sha256'] if old else None, afterSha256=digest))
    proof_path = 'Analysis/Adoption/runtime-update.json'
    proof = dict(schema='monkey-native-runtime-update/1', toolVersion=__version__,
        inputManifestSha256=expected_manifest, changes=changes,
        changedCodeNativeValidation='pending', preservedNativeAssets='byte-identical',
        runtimeProfile='native-image-rawimage-tmp-existing-ordered-slots-v1',
        limitations=['Dynamic Spine and animation curves are not lowered.',
            'New source objects, reordered queues and changed mask geometry require a new native plan.',
            'Input requires one active authored GraphicRaycaster on the proxy Canvas.'])
    write_json(out / proof_path, proof)
    proof_raw = read(out / proof_path)
    files[proof_path] = dict(path=proof_path, sha256=sha(proof_raw), bytes=len(proof_raw), owner='generated')
    result = deepcopy(manifest)
    result.update(toolVersion=__version__, sourceSelectionManifestSha256=expected_manifest,
        runtimeUpdate=dict(evidencePath=proof_path, evidenceSha256=sha(proof_raw), nativeValidation='pending'),
        adoptionDependencies=dict(schemaVersion=1, coverage='producer-declared', edges=sorted(edges.values(), key=lambda e:e['path'])),
        files=[files[p] for p in sorted(files)])
    write_json(out / 'manifest.json', result)
    return result
