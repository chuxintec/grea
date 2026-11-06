"""Scoped native serialization readback and offscreen capture; no gameplay claims."""
from pathlib import Path
import re
import shutil
import subprocess
from .io import safe, inside, load, write_json, sha, read
from .errors import fail, BeaverError
from .native_environment import editor_environment
from .adoption import native_lock
from .transaction_fs import lock
from .unity import editor_path


def asset_path(value):
    if not isinstance(value, str) or not value.startswith('Assets/') or '\\' in value or any(p in ('', '.', '..') for p in value.split('/')) or value.endswith('.meta'):
        fail('READBACK_PATH', str(value), 'Canonical imported Assets file path required')
    return value


def validate(spec):
    if not isinstance(spec, dict) or spec.get('schemaVersion') != 1 or set(spec) - {'schemaVersion', 'assets', 'queries', 'aliases', 'capture'}:
        fail('READBACK_SPEC', 'spec', 'Expected schemaVersion 1 readback request')
    assets = spec.get('assets')
    if not isinstance(assets, list) or not 1 <= len(assets) <= 128 or any(not isinstance(a,str) for a in assets) or len(set(assets)) != len(assets):
        fail('READBACK_SELECTION', 'assets', 'Select 1..128 unique imported assets')
    for item in assets: asset_path(item)
    aliases = spec.get('aliases', [])
    if not isinstance(aliases, list) or len(aliases) > 64: fail('READBACK_ALIAS', 'aliases', 'At most 64 explicit aliases')
    names = set()
    for a in aliases:
        if not isinstance(a, dict) or set(a) != {'name', 'propertyPath'} or not all(isinstance(v, str) and v for v in a.values()) or a['name'] in names:
            fail('READBACK_ALIAS', 'aliases', 'Unique explicit name/propertyPath mappings required')
        names.add(a['name'])
    queries = spec.get('queries', [])
    if not isinstance(queries, list) or len(queries) > 1024: fail('READBACK_QUERY', 'queries', 'At most 1024 field queries')
    query_fields={'asset','nodePath','componentType','propertyPath'}
    for q in queries:
        if not isinstance(q, dict) or not query_fields<=set(q) or set(q)-query_fields-{'ownerIdentity'} or not all(isinstance(q[k],str) for k in query_fields) or q['asset'] not in assets or not q['propertyPath']:
            fail('READBACK_QUERY', 'queries', 'Explicit selected asset/nodePath/componentType/propertyPath required')
        if q['nodePath'] and any(p in ('', '.', '..') for p in q['nodePath'].split('/')): fail('READBACK_QUERY', 'nodePath', 'Canonical hierarchy path required')
        if 'ownerIdentity' in q:
            owner=q['ownerIdentity']
            if (not isinstance(owner,dict) or set(owner)!={'guid','localId'} or not isinstance(owner.get('guid'),str) or not re.fullmatch(r'[a-fA-F0-9]{32}',owner['guid'])
                    or type(owner.get('localId')) is not int or not -(2**63)<=owner['localId']<2**63 or owner['localId']==0):
                fail('READBACK_OWNER_SELECTOR','ownerIdentity','Expected an actual selected-asset GUID and nonzero signed 64-bit owner localId')
    capture = spec.get('capture')
    if capture is not None:
        allowed = {'asset', 'width', 'height', 'cameraPath', 'camera'}
        if not isinstance(capture, dict) or set(capture) - allowed or capture.get('asset') not in assets or not capture['asset'].endswith(('.prefab', '.unity')):
            fail('CAPTURE_SPEC', 'capture', 'Select one prefab/scene in assets')
        for k in ('width', 'height'):
            if type(capture.get(k)) is not int or not 1 <= capture[k] <= 4096: fail('CAPTURE_SIZE', k, '1..4096 pixels required')
        if capture['width'] * capture['height'] > 8_388_608: fail('CAPTURE_SIZE', 'capture', 'Capture limited to 8 megapixels')
        if ('cameraPath' in capture) == ('camera' in capture): fail('CAPTURE_CAMERA', 'capture', 'Choose exactly one existing cameraPath or explicit temporary camera')
        if 'cameraPath' in capture and (not isinstance(capture['cameraPath'], str) or not capture['cameraPath']): fail('CAPTURE_CAMERA', 'cameraPath', 'Exact hierarchy path required')
        if 'camera' in capture:
            import math
            c = capture['camera']
            if not isinstance(c, dict) or set(c) != {'position', 'euler', 'orthographic', 'size', 'background'} or type(c['orthographic']) is not bool: fail('CAPTURE_CAMERA', 'camera', 'Explicit position/euler/orthographic/size/background required')
            for k, n in (('position', 3), ('euler', 3), ('background', 4)):
                if not isinstance(c[k], list) or len(c[k]) != n or any(type(v) not in (int, float) or not math.isfinite(v) for v in c[k]): fail('CAPTURE_CAMERA', k, 'Finite vector required')
            if type(c['size']) not in (int, float) or not math.isfinite(c['size']) or c['size'] <= 0: fail('CAPTURE_CAMERA', 'size', 'Positive finite size required')
    return spec


def run_collector(project, request, output, editor, companion, entry, report_name, timeout=600, graphics=False):
    """Same locks, content guards and owned-helper cleanup as existing native tools."""
    from .batch import inventory, state, cleanup
    if type(timeout) is not int or not 1 <= timeout <= 1200: fail('READBACK_TIMEOUT', 'timeout', '1..1200 seconds required')
    if Path(companion).name != companion or Path(report_name).name != report_name: fail('READBACK_INTERNAL', 'collector', 'Packaged companion and report names required')
    project = safe(project); output = safe(output); editor = editor_path(editor)
    if output.exists() or output.is_relative_to(project) or project.is_relative_to(output): fail('READBACK_OUTPUT', str(output), 'Fresh output outside project required')
    selected = sorted(set(request.get('assets', []) + request.get('roots', [])))
    for rel in selected:
        asset_path(rel)
        if not inside(project, rel).is_file(): fail('READBACK_INPUT', rel, 'Existing regular imported file required')
    helper = inside(project, 'Assets/BeaverReadbackTools'); owned = {}; error = None; result = None
    with lock(project):
        native_lock(project)
        if helper.exists() or Path(str(helper) + '.meta').exists(): fail('READBACK_HELPER_CONFLICT', str(helper), 'Temporary helper path occupied')
        before = inventory(project)
        environment_paths = [p for p in before if p.startswith(('Packages/','ProjectSettings/'))]
        tracked = sorted(set(selected + [p + '.meta' for p in selected] + environment_paths))
        if companion == 'BeaverBuildFilter.cs':
            # A dependency closure is invalidated by unselected consumers too.
            # Bind all active source bytes before collection, not just after it.
            tracked = sorted(set(tracked + [p for p in before if p.startswith('Assets/') and not (p.endswith('.meta') and inside(project,p[:-5]).is_dir())]))
        source_before = state(project, tracked)
        output.mkdir(parents=True); stage = output / 'native'; stage.mkdir()
        try:
            (helper / 'Editor').mkdir(parents=True)
            dest = helper / 'Editor' / companion
            shutil.copyfile(Path(__file__).parent / 'targets' / companion, dest); owned[dest] = sha(dest.read_bytes())
            job = dict(request, projectRoot=str(project), stage=str(stage), reportName=report_name)
            if companion == 'BeaverReadback.cs':
                job['queries'] = [dict(q,hasOwnerIdentity='ownerIdentity' in q) for q in request.get('queries',[])]
                job['hasCapture'] = 'capture' in request and request['capture'] is not None
                if job['hasCapture']:
                    job['capture'] = dict(request['capture'], temporaryCamera='camera' in request['capture'])
            job_path = stage / 'job.json'; write_json(job_path, job)
            args = [str(editor), '-batchmode'] + ([] if graphics else ['-nographics']) + ['-projectPath', str(project), '-executeMethod', entry, '-logFile', str(stage / 'editor.log')]
            process = subprocess.run(args, env=editor_environment('BEAVER_NATIVE_JOB', job_path), capture_output=True, timeout=timeout)
            from .output_limits import MANIFEST_BYTES, MANIFEST_NODES
            result = load(read(stage / report_name, max_bytes=MANIFEST_BYTES), max_nodes=MANIFEST_NODES) if (stage / report_name).is_file() else None
            if process.returncode != 0 or result is None: fail('READBACK_EDITOR_FAILED', str(stage / 'editor.log'), 'Collector failed, exit=' + str(process.returncode))
            result['editorExitCode'] = process.returncode
        except BaseException as exc:
            error = BeaverError('READBACK_EDITOR_TIMEOUT', str(stage), 'Collector exceeded its budget; logs retained') if isinstance(exc, subprocess.TimeoutExpired) else exc
        finally:
            cleaned = cleanup(project, helper, owned) if helper.exists() else False
            after = inventory(project); source_after = state(project, tracked)
        changes = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
        guard = dict(sourceUnchanged=source_before == source_after, unplannedProjectChanges=changes, helperCleaned=cleaned)
        write_json(output / 'read-only-guard.json', guard)
        if not cleaned or changes or source_before != source_after: fail('READBACK_PROJECT_MODIFIED', str(output / 'read-only-guard.json'), 'Read-only collector guard failed')
        if error: raise error
        catalog = [row.get('path') for row in result.get('assets',[]) if isinstance(row,dict)]
        for rel in catalog: asset_path(rel)
        catalog_paths = sorted(set(catalog + [p+'.meta' for p in catalog]))
        if companion == 'BeaverBuildFilter.cs':
            if any(p not in source_before for p in catalog_paths): fail('READBACK_CATALOG_DRIFT', str(output), 'Native catalog includes assets absent from the pre-collection input state')
            bound_state = {p:source_before[p] for p in environment_paths+catalog_paths}
        else:
            bound_state = dict(source_before, **state(project,catalog_paths))
        result.update(guard, inputState=bound_state, nativeReadback='read_only_native_snapshot', visualAcceptance='not-established', gameplayAcceptance='not-established')
        write_json(output / report_name, result)
        return result


def inspect(project, spec_path, output, editor, timeout=600):
    spec = validate(load(read(spec_path)))
    report = run_collector(project, spec, output, editor, 'BeaverReadback.cs', 'BeaverReadback.Run', 'readback.json', timeout, graphics='capture' in spec)
    if report.get('contract') != 'beaver-native-readback/1' or report.get('schemaVersion') != 1 or report.get('errors') or {r.get('path') for r in report.get('assets',[])} != set(spec['assets']):
        fail('READBACK_RESULT', str(safe(output)/'readback.json'), 'Native collector result or selected asset identity is incomplete')
    if len(report.get('fields',[])) != len(spec.get('queries',[])):
        fail('READBACK_RESULT', str(safe(output)/'readback.json'), 'Native field query result count differs from request')
    for query,field in zip(spec.get('queries',[]),report.get('fields',[])):
        if 'ownerIdentity' not in query or field.get('status')!='observed':continue
        expected=query['ownerIdentity'];owner=field.get('owner')
        if (not isinstance(owner,dict) or owner.get('state')!='persistent' or not isinstance(owner.get('guid'),str)
                or owner['guid'].lower()!=expected['guid'].lower() or type(owner.get('localId')) is not int or owner['localId']!=expected['localId']
                or field.get('asset')!=query['asset'] or field.get('nodePath')!=query['nodePath'] or field.get('componentType')!=query['componentType']
                or field.get('requestedPath')!=query['propertyPath'] or (query['componentType'] and owner.get('type')!=query['componentType'])):
            fail('READBACK_OWNER_IDENTITY',str(safe(output)/'readback.json'),'Observed field did not retain the exact requested persistent owner; no fallback is permitted')
    capture = report.get('capture')
    if spec.get('capture') is not None and (not isinstance(capture,dict) or capture.get('status') != 'captured' or not capture.get('file')):
        fail('READBACK_RESULT', str(safe(output)/'readback.json'), 'Requested capture did not produce a frame')
    if isinstance(capture, dict) and capture.get('file'):
        p = inside(safe(output) / 'native', capture['file'])
        capture.update(sha256=sha(p.read_bytes()), bytes=p.stat().st_size, path=str(p))
        write_json(safe(output) / 'readback.json', report)
    return dict(report, report=str(safe(output) / 'readback.json'))
