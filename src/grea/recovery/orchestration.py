"""One-command package conversion's optional sequential native stage.

Each Editor gets its own fresh workspace and absolute bounded window. Source
conversion receipts remain frozen; business/visual gaps are never promoted.
"""
from datetime import timedelta
from pathlib import Path

from .io import safe, inside,read,stage_manifest,new_output, write_json
from .native import native_import, now, stamp
from .package import TARGETS
from .sources.compiled import fail
from .sources.containers import fingerprint
from .targets import unity, cocos


def options(output, target, native_output, unity_editor, creator_editor, budget, source_roots):
    if type(budget) is not int or not 1 <= budget <= 1200:
        fail('NATIVE_METHOD_BUDGET', str(budget), 'Expected 1..1200 seconds per Editor')
    profiles = [unity.PROFILE, cocos.PROFILE] if target == 'both' else [TARGETS[target]]
    editors = {unity.PROFILE: unity_editor, cocos.PROFILE: creator_editor}
    for profile, editor in editors.items():
        if profile in profiles:
            if not editor:
                fail('NATIVE_EDITOR_REQUIRED', profile, 'Provide the exact installed Editor executable')
            executable = safe(editor)
            names = ('Unity', 'Unity.exe') if profile == unity.PROFILE else ('CocosCreator', 'CocosCreator.exe')
            if not executable.is_file() or executable.name not in names:
                fail('NATIVE_EDITOR_INVALID', str(executable), 'Expected an existing matching Editor executable')
            editors[profile] = str(executable)
        elif editor:
            fail('NATIVE_EDITOR_UNUSED', profile, 'Editor does not match the requested target')
    candidate = safe(output)
    destination = safe(native_output or candidate.with_name(candidate.name + '-native'))
    if destination.exists():
        fail('NATIVE_WORKSPACE_EXISTS', str(destination), 'Choose a new native output; existing work is preserved')
    protected = [candidate, *map(safe, source_roots)]
    if any(destination == root or destination.is_relative_to(root) or root.is_relative_to(destination) for root in protected):
        fail('NATIVE_WORKSPACE_OVERLAP', str(destination), 'Native output must be separate from inputs and candidate')
    return dict(output=destination, candidate=candidate, profiles=profiles, editors=editors, budget=budget)


def run(conversion, settings):
    if conversion.get('completed') is not True:
        return dict(status='not_run', reason='CONVERSION_INCOMPLETE')
    rows = {p['targetProfile']: p for p in conversion['projects']}
    if set(rows) != set(settings['profiles']):
        fail('NATIVE_TARGET_SET', str(settings['candidate']), 'Conversion targets differ from the requested native stages')
    projects = []
    for profile in settings['profiles']:
        row = rows[profile]
        name = 'UnityProject' if profile == unity.PROFILE else 'CocosProject'
        if row['path'] != name:
            fail('NATIVE_PROJECT_PATH', row['path'], 'Expected the generated package project directory')
        root = settings['candidate'] / name
        identity = fingerprint(root / 'manifest.json')
        if identity != row.get('manifestSha256'):
            fail('NATIVE_SOURCE_IDENTITY', str(root), 'Generated candidate manifest differs from conversion receipt')
        # Check every target entrypoint before launching the first Editor. A file
        # accounting fallback may be complete even when native emission failed.
        from .layout import locate
        manifest=stage_manifest(root)
        entry=locate(manifest,'importer') if profile==unity.PROFILE else 'extensions/monkey-import/execution.js'
        marker=b'public static void ImportBatchAsync()' if profile==unity.PROFILE else b'MONKEY_NATIVE_EXECUTE'
        records=[f for f in manifest['files']if f['path']==entry]
        helper=inside(root,entry)
        if len(records)!=1 or not helper.is_file() or fingerprint(helper)!=records[0]['sha256'] or marker not in read(helper):
            fail('NATIVE_ENTRYPOINT_MISSING',str(root),'One requested native target was not emitted; preserve conversion and repair offline before any Editor launch')
        projects.append((profile, name, root, identity))
    out = new_output(settings['output'], [settings['candidate']])
    report = dict(schemaVersion=1, status='running', startedUtc=stamp(now()),
                  windowSecondsPerEditor=1800, cleanupSeconds=120, methodBudgetSeconds=settings['budget'],
                  visual='not_run', business='not_run', stages=[])
    receipt = out / 'native-orchestration.json'
    write_json(receipt, report)
    for profile, name, root, identity in projects:
        anchor = now()
        stage = dict(targetProfile=profile, candidateManifestSha256=identity, startedUtc=stamp(anchor),
                     deadlineUtc=stamp(anchor + timedelta(minutes=28)), windowEndUtc=stamp(anchor + timedelta(minutes=30)),
                     status='running')
        report['stages'].append(stage)
        write_json(receipt, report)
        try:
            result = native_import(root, out / name, settings['editors'][profile], identity,
                                   settings['budget'], stage['deadlineUtc'], stage['windowEndUtc'], True)
            stage.update(result=result, status='returned')
        except Exception as error:
            stage.update(status='failed', reason=str(error)[:4096])
            report['status'] = 'stopped'
            break
        verification = result.get('verification', {})
        if (result.get('processExited') is not True or
                result.get('nativeProgress', {}).get('status') not in ('completed', 'completed_partial') or
                verification.get('diagnostics') != 0 or verification.get('editor') not in ('pass', 'partial')):
            report['status'] = 'stopped'
            break
        write_json(receipt, report)
    else:
        report['status'] = 'completed_native_stages'
    report['endedUtc'] = stamp(now())
    write_json(receipt, report)
    return dict(status=report['status'], stages=report['stages'], report=str(receipt), visual='not_run', business='not_run')
