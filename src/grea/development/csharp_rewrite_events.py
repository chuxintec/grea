"""Source-pinned persistent Button event plans for compiled C# rewrite plans."""
from pathlib import Path
import re

from . import csharp_rewrite
from .errors import BeaverError, fail
from .io import encoded, inside, load, new_output, read, safe, sha, write_json
from .unity import meta_guid

EVENTS = 'beaver-csharp-rewrite-events/1'
EVENT_PLAN = 'beaver-csharp-rewrite-event-plan/1'
SHA256 = re.compile(r'^[a-f0-9]{64}$')
GUID = re.compile(r'^[a-f0-9]{32}$')
BUTTON = 'UnityEngine.UI.Button'


def _closed(value, keys, where):
    if not isinstance(value, dict) or set(value) != set(keys):
        fail('REWRITE_EVENT_CONTRACT', where, 'Exact fields required: ' + ', '.join(sorted(keys)))


def _int64(value, where):
    if type(value) is not int or value == 0 or not -(2 ** 63) <= value < 2 ** 63:
        fail('REWRITE_EVENT_NATIVE_ID', where, 'Nonzero signed 64-bit persistent localID required')


def _node_path(value, where, allow_root=False):
    if not isinstance(value, str) or (not allow_root and not value):
        fail('REWRITE_EVENT_NODE_PATH', where, 'Explicit canonical hierarchy path required')
    if value and ('\\' in value or value.startswith('/') or any(part in ('', '.', '..') for part in value.split('/'))):
        fail('REWRITE_EVENT_NODE_PATH', where, 'Canonical relative hierarchy path required')


def _pointer(document, pointer):
    if not isinstance(pointer, str) or (pointer and not pointer.startswith('/')):
        fail('REWRITE_EVENT_SOURCE_POINTER', 'jsonPointer', 'RFC6901 absolute JSON pointer required')
    if pointer == '':
        return document
    value = document
    for raw in pointer[1:].split('/'):
        if re.search(r'~(?![01])', raw):
            fail('REWRITE_EVENT_SOURCE_POINTER', pointer, 'Invalid RFC6901 escape')
        token = raw.replace('~1', '/').replace('~0', '~')
        if isinstance(value, list):
            if not re.fullmatch(r'0|[1-9][0-9]*', token):
                fail('REWRITE_EVENT_SOURCE_POINTER', pointer, 'Array index must be canonical decimal')
            index = int(token)
            if index >= len(value):
                fail('REWRITE_EVENT_SOURCE_POINTER', pointer, 'Array index is outside source evidence')
            value = value[index]
        elif isinstance(value, dict) and token in value:
            value = value[token]
        else:
            fail('REWRITE_EVENT_SOURCE_POINTER', pointer, 'Pointer does not resolve in source evidence')
    return value


def _source(row, seen_records, seen_pointers, include_record=False):
    _closed(row, ('path', 'sha256', 'recordId', 'jsonPointer', 'recordSha256'), 'source')
    if not isinstance(row['path'], str) or not Path(row['path']).is_absolute():
        fail('REWRITE_EVENT_SOURCE', 'source.path', 'Absolute source evidence path required')
    if not isinstance(row['sha256'], str) or not SHA256.fullmatch(row['sha256']):
        fail('REWRITE_EVENT_SOURCE', 'source.sha256', 'Exact full source SHA256 required')
    if not isinstance(row['recordId'], str) or not row['recordId'].strip():
        fail('REWRITE_EVENT_SOURCE_ID', 'source.recordId', 'Nonempty source record ID required')
    if not isinstance(row['recordSha256'], str) or not SHA256.fullmatch(row['recordSha256']):
        fail('REWRITE_EVENT_SOURCE_RECORD', 'source.recordSha256', 'Exact full source record SHA256 required')
    path = safe(row['path'])
    raw = read(path)
    if sha(raw) != row['sha256']:
        fail('REWRITE_EVENT_SOURCE_DRIFT', str(path), 'Source evidence bytes differ from the declared SHA256')
    document = load(raw)
    record = _pointer(document, row['jsonPointer'])
    if sha(encoded(record)) != row['recordSha256']:
        fail('REWRITE_EVENT_SOURCE_RECORD_DRIFT', row['recordId'], 'Resolved source record differs from its canonical JSON SHA256')
    record_key = row['recordId']
    pointer_key = (str(path), row['jsonPointer'])
    if record_key in seen_records:
        fail('REWRITE_EVENT_SOURCE_ID_DUPLICATE', row['recordId'], 'Source record ID must be unique in the event group')
    if pointer_key in seen_pointers:
        fail('REWRITE_EVENT_SOURCE_ALIAS', row['jsonPointer'], 'One source record cannot be counted again under another ID')
    seen_records.add(record_key)
    seen_pointers.add(pointer_key)
    source = dict(path=str(path), sha256=row['sha256'], recordId=row['recordId'],
                  jsonPointer=row['jsonPointer'], recordSha256=row['recordSha256'])
    return (source, document, record) if include_record else source


def _plan_data(plan_path, expected_plan):
    path = safe(plan_path)
    raw = read(path, max_bytes=64 * 1024**2)
    data = load(raw)
    if not isinstance(expected_plan, str) or not SHA256.fullmatch(expected_plan) or sha(raw) != expected_plan:
        fail('REWRITE_EVENT_PLAN_SHA', str(path), 'Exact existing rewrite-plan SHA256 required')
    if data.get('contract') != csharp_rewrite.PLAN or data.get('status') != 'planned':
        fail('REWRITE_EVENT_PLAN', str(path), 'Existing compiled rewrite-plan/1 required')
    if data.get('implementationSha256') != csharp_rewrite.identity():
        fail('REWRITE_EVENT_PRODUCER', str(path), 'Rewrite plan was not produced by this implementation')
    compile_pin = data.get('compileReport')
    required = {'path', 'sha256', 'producerImplementationSha256', 'workspaceSha256', 'fileEdits'}
    if not isinstance(compile_pin, dict) or set(compile_pin) != required:
        fail('REWRITE_EVENT_COMPILE_PIN', str(path), 'Recreate the rewrite plan with a producer-pinned compile report')
    compile_path = safe(compile_pin['path'])
    if not compile_path.is_relative_to(path.parent) or compile_path == path:
        fail('REWRITE_EVENT_COMPILE_PIN', str(compile_path), 'Pinned compile report must be inside the rewrite-plan output')
    compile_raw = read(compile_path, max_bytes=64 * 1024**2)
    if sha(compile_raw) != compile_pin['sha256']:
        fail('REWRITE_EVENT_COMPILE_DRIFT', str(compile_path), 'Pinned compile report bytes changed')
    if compile_pin['producerImplementationSha256'] != data['implementationSha256']:
        fail('REWRITE_EVENT_COMPILE_PRODUCER', str(compile_path), 'Compile report producer differs from the rewrite plan')
    compiled = load(compile_raw)
    if not isinstance(compiled, dict) or compiled.get('status') != 'ok':
        fail('REWRITE_EVENT_COMPILE_STATUS', str(compile_path), 'Pinned successful Roslyn semantic report required')
    expected_edits = sorted((row['path'], row['sha256']) for row in data.get('fileEdits', []))
    pinned_edits = sorted((row.get('path'), row.get('sha256')) for row in compile_pin['fileEdits']
                          if isinstance(row, dict))
    if len(pinned_edits) != len(compile_pin['fileEdits']) or pinned_edits != expected_edits:
        fail('REWRITE_EVENT_COMPILE_FILES', str(compile_path), 'Compile report pin must cover the exact rewritten source bytes')
    if compile_pin['workspaceSha256'] != data.get('workspace', {}).get('sha256'):
        fail('REWRITE_EVENT_COMPILE_WORKSPACE', str(compile_path), 'Compile report is not bound to this rewrite workspace')
    return path, data, compile_path, compiled


def _compiled_type(compiled, script):
    matches = [t for assembly in compiled.get('assemblies', []) if assembly.get('name') == script['assembly']
               for source in assembly.get('sourceSemantics', []) if source.get('path') == script['path']
               for t in source.get('types', []) if t.get('fullName') == script['fullType']]
    if len(matches) != 1:
        fail('REWRITE_EVENT_TYPE', script['fullType'], 'Unique type in the pinned compile report required')
    return matches[0]


def _event(row, data, compiled, seen_destinations, seen_sources):
    required_fields = {'source', 'prefab', 'button', 'target'}
    if not isinstance(row, dict) or set(row) - (required_fields | {'inputPolicy'}) or not required_fields <= set(row):
        fail('REWRITE_EVENT_CONTRACT', 'event', 'Expected source/prefab/button/target and optional inputPolicy only')
    input_policy = row.get('inputPolicy')
    if input_policy not in (None, 'enable-source-button'):
        fail('REWRITE_EVENT_INPUT_POLICY', str(input_policy), 'Only enable-source-button inputPolicy is supported')
    source, source_document, source_record = _source(row['source'], *seen_sources, include_record=True)
    prefab = row['prefab']; button = row['button']; target = row['target']
    source_pins = [pin for pin in data.get('pins', []) if safe(pin.get('path', '')) == safe(source['path'])]
    if len(source_pins) != 1 or source_pins[0].get('sha256') != source['sha256']:
        fail('REWRITE_EVENT_SOURCE_UNPINNED', source['path'], 'Source file and SHA must be pinned by the rewrite workspace')
    _closed(prefab, ('path', 'guid'), 'event.prefab')
    _closed(button, ('nodePath', 'componentType', 'nodeLocalId', 'componentLocalId'), 'event.button')
    _closed(target, ('nodePath', 'componentType', 'fullType', 'assembly', 'scriptPath', 'scriptGuid',
                     'method', 'nodeLocalId', 'componentLocalId'), 'event.target')
    asset_path = prefab['path']
    if (not isinstance(asset_path, str) or not asset_path.startswith('Assets/') or not asset_path.endswith('.prefab')
            or '\\' in asset_path or any(part in ('', '.', '..') for part in asset_path.split('/'))):
        fail('REWRITE_EVENT_PREFAB', str(asset_path), 'Canonical existing Prefab path required')
    if not isinstance(prefab['guid'], str) or not GUID.fullmatch(prefab['guid']):
        fail('REWRITE_EVENT_PREFAB', asset_path, 'Exact Prefab GUID required')
    _node_path(button['nodePath'], asset_path + ':button.nodePath')
    _node_path(target['nodePath'], asset_path + ':target.nodePath', allow_root=True)
    if button['componentType'] != BUTTON:
        fail('REWRITE_EVENT_BUTTON', asset_path, 'Exact non-root UnityEngine.UI.Button node required')
    if input_policy == 'enable-source-button':
        parts = source['jsonPointer'].split('/')
        if (len(parts) < 3 or parts[-2] != 'clickEvents'
                or not re.fullmatch(r'0|[1-9][0-9]*', parts[-1])):
            fail('REWRITE_EVENT_INPUT_POLICY', source['recordId'], 'Policy requires a source pointer ending at clickEvents/<index>')
        component = _pointer(source_document, '/'.join(parts[:-2]))
        if not isinstance(component, dict) or component.get('__type__') != 'cc.Button':
            fail('REWRITE_EVENT_INPUT_POLICY', source['recordId'], 'The clickEvents parent record must be a cc.Button')
        for field in ('_enabled', '_interactable', 'interactable'):
            if field in component and type(component[field]) is not bool:
                fail('REWRITE_EVENT_INPUT_POLICY', source['recordId'], field + ' must be boolean when present')
            if component.get(field) is False:
                fail('REWRITE_EVENT_INPUT_POLICY', source['recordId'], 'Source Button is disabled by ' + field)
        if source_record.get('handler') != target.get('method'):
            fail('REWRITE_EVENT_INPUT_POLICY', source['recordId'], 'Source click handler must equal the compiled target method')
    if any(not isinstance(target[k], str) or not target[k] for k in ('componentType', 'fullType', 'assembly', 'scriptPath', 'scriptGuid', 'method')):
        fail('REWRITE_EVENT_TARGET', asset_path, 'Explicit existing compiled target type, script and method required')
    if target['componentType'] != target['fullType']:
        fail('REWRITE_EVENT_TARGET', asset_path, 'Target componentType must equal the compiled full type')
    if not GUID.fullmatch(target['scriptGuid']):
        fail('REWRITE_EVENT_TARGET', asset_path, 'Exact target script GUID required')
    for key in ('button.nodeLocalId', 'button.componentLocalId', 'target.nodeLocalId', 'target.componentLocalId'):
        parent, field = key.split('.')
        _int64(row[parent][field], asset_path + ':' + key)
    event_key = (asset_path, button['componentLocalId'])
    if event_key in seen_destinations:
        fail('REWRITE_EVENT_DUPLICATE', asset_path + ':' + button['nodePath'], 'Only one event binding per Button is supported')
    seen_destinations.add(event_key)

    project = safe(data['projectRoot'])
    prefab_meta = inside(project, asset_path + '.meta')
    if meta_guid(read(prefab_meta), asset_path) != prefab['guid']:
        fail('REWRITE_EVENT_PREFAB_DRIFT', asset_path, 'Prefab GUID differs from existing project metadata')

    scripts = [s for s in data.get('compatibility', []) if s.get('fullType') == target['fullType']]
    if len(scripts) != 1:
        fail('REWRITE_EVENT_SCRIPT', target['fullType'], 'Target must be one of the rewritten types')
    script = scripts[0]
    if any(script.get(k) != target[v] for k, v in (('path', 'scriptPath'), ('assembly', 'assembly'), ('guid', 'scriptGuid'))):
        fail('REWRITE_EVENT_SCRIPT', target['fullType'], 'Target script path, assembly and GUID must match the compiled rewrite type')
    edit = [f for f in data.get('fileEdits', []) if f.get('path') == script['path']]
    if len(edit) != 1:
        fail('REWRITE_EVENT_SCRIPT', script['path'], 'Target method must be in an actual changed source file')
    semantic = _compiled_type(compiled, script)
    methods = [m for m in semantic.get('eventMethods', [])
               if m.get('name') == target['method'] and m.get('returnType') == 'System.Void'
               and m.get('parameters') == [] and m.get('genericArity') == 0]
    if len(methods) != 1:
        fail('REWRITE_EVENT_METHOD', target['method'], 'Pinned compile must expose one public instance void() method')
    native = [i for i in data.get('instances', []) if i.get('prefabPath') == asset_path
              and i.get('prefabGuid') == prefab['guid'] and i.get('fullType') == target['fullType']
              and i.get('nodeLocalId') == target['nodeLocalId']
              and i.get('componentLocalId') == target['componentLocalId']]
    if len(native) != 1:
        fail('REWRITE_EVENT_TARGET_NATIVE', asset_path, 'Target must match one exact native instance in the rewrite-plan baseline')

    action = dict(kind='binding.event.enable' if input_policy == 'enable-source-button' else 'binding.event',
                  path=button['nodePath'], component=BUTTON,
                  property='onClick', value='empty', method=target['method'],
                  targetNode=target['nodePath'], targetComponent=target['componentType'])
    base_inspect = dict(kind='prefab.event.inspect', assetPath=asset_path,
                        path=button['nodePath'], targetNode=target['nodePath'],
                        targetComponent=target['componentType'], method=target['method'],
                        buttonLocalId=button['componentLocalId'], targetLocalId=target['componentLocalId'],
                        prefabGuid=prefab['guid'], buttonNodeLocalId=button['nodeLocalId'],
                        targetNodeLocalId=target['nodeLocalId'], targetAssembly=target['assembly'],
                        scriptGuid=target['scriptGuid'])
    inspect1 = dict(base_inspect, expectedCount=1)
    if input_policy == 'enable-source-button':
        inspect1['requireInteractable'] = True
    return dict(source=source, prefab=prefab, button=button, target=target, inputPolicy=input_policy,
                action=action, inspect0=dict(base_inspect, expectedCount=0),
                inspect1=inspect1, expectedCount=0)


def _production_plan(project, spec, output):
    from .production import plan as native_plan
    spec_path = output.parent / (output.name + '-spec.json')
    write_json(spec_path, spec)
    return native_plan(project, spec_path, output)


def plan(rewrite_plan_path, expected_rewrite_plan, events_path, expected_events, output,
         editor_path, apply_out=None):
    rewrite_path, rewrite, compile_path, compiled = _plan_data(rewrite_plan_path, expected_rewrite_plan)
    csharp_rewrite._check_pins(rewrite.get('pins', []))
    events_file = safe(events_path)
    event_raw = read(events_file, max_bytes=16 * 1024**2)
    if not isinstance(expected_events, str) or not SHA256.fullmatch(expected_events) or sha(event_raw) != expected_events:
        fail('REWRITE_EVENT_INPUT_SHA', str(events_file), 'Exact events JSON SHA256 required')
    events_data = load(event_raw)
    _closed(events_data, ('contract', 'events'), 'events')
    if events_data['contract'] != EVENTS or not isinstance(events_data['events'], list) or not 1 <= len(events_data['events']) <= 128:
        fail('REWRITE_EVENT_INPUT', str(events_file), 'beaver-csharp-rewrite-events/1 with 1..128 events required')
    if not isinstance(editor_path, str) or not Path(editor_path).is_absolute():
        fail('REWRITE_EVENT_EDITOR', 'editorPath', 'Explicit absolute Unity Editor executable path required for emitted apply argv')

    seen_destinations, seen_records, seen_pointers = set(), set(), set()
    prepared, results = [], []
    for index, row in enumerate(events_data['events']):
        try:
            result = _event(row, rewrite, compiled, seen_destinations, (seen_records, seen_pointers))
            prepared.append(result)
            results.append(dict(index=index, sourceRecordId=result['source']['recordId'], expectedCount=0,
                                planned=False, failed=False, reason=None))
        except (BeaverError, KeyError, TypeError, ValueError) as error:
            record_id = row.get('source', {}).get('recordId') if isinstance(row, dict) and isinstance(row.get('source'), dict) else None
            message = str(error)
            if isinstance(error, BeaverError):
                message = error.message if hasattr(error, 'message') else str(error)
            results.append(dict(index=index, sourceRecordId=record_id, expectedCount=0,
                                planned=False, failed=True, reason=message))
    stage = new_output(output, inputs=[safe(rewrite['projectRoot']), rewrite_path, events_file, compile_path,
                                       *[safe(row['source']['path']) for row in events_data['events']
                                         if isinstance(row, dict) and isinstance(row.get('source'), dict)
                                         and isinstance(row['source'].get('path'), str)]])
    base = dict(contract=EVENT_PLAN, status='blocked' if any(r['failed'] for r in results) else 'planned',
                implementationSha256=csharp_rewrite.identity(),
                projectRoot=str(safe(rewrite['projectRoot'])),
                rewritePlan=dict(path=str(rewrite_path), sha256=expected_rewrite_plan,
                                 compileReport=dict(path=str(compile_path), sha256=rewrite['compileReport']['sha256'])),
                eventsInput=dict(path=str(events_file), sha256=expected_events), events=results,
                native='not_run', behavior='not_verified', formalAdoption='not_permitted_by_plan',
                limitations=['Planning only; no Editor, native write, runtime event, or cold reopen was run.',
                             'Native button/component IDs and zero/one persistent listener states require the emitted Editor inspections.'])
    if any(r['failed'] for r in results):
        for result in results:
            if not result['failed']:
                result['failed'] = True
                result['reason'] = 'Atomic event group blocked because another row failed preflight.'
        write_json(stage / 'rewrite-event-plan.json', base)
        return dict(status='blocked', report=str(stage / 'rewrite-event-plan.json'), native='not_run')

    original_native_path = safe(rewrite['production']['report'])
    original_native_raw = read(original_native_path, max_bytes=64 * 1024**2)
    original_native = load(original_native_raw)
    if sha(encoded(original_native)) != rewrite['production']['planSha256']:
        fail('REWRITE_EVENT_PRODUCTION_PLAN', str(original_native_path), 'Original rewrite production-plan SHA drift')
    original_spec = original_native.get('spec')
    if not isinstance(original_spec, dict) or original_spec.get('schemaVersion') != 3 or original_spec.get('operation') != 'production':
        fail('REWRITE_EVENT_PRODUCTION_SPEC', str(original_native_path), 'Original production v3 spec required')
    spec = dict(original_spec)
    spec['steps'] = list(original_spec['steps'])
    grouped = {}
    for event in prepared:
        path = event['prefab']['path']
        spec['steps'].extend([event['inspect0'], dict(kind='prefab.patch', assetPath=path, actions=[event['action']]), event['inspect1']])
        grouped.setdefault(path, 0)
        grouped[path] += 1

    source_pins = []
    for event in prepared:
        pin = dict(path=event['source']['path'], sha256=event['source']['sha256'],
                   recordId=event['source']['recordId'], jsonPointer=event['source']['jsonPointer'],
                   recordSha256=event['source']['recordSha256'])
        if pin not in source_pins:
            source_pins.append(pin)
    def output_path(value, suffix):
        candidate = safe(value) if value else stage.parent / (stage.name + suffix)
        if candidate.exists():
            fail('REWRITE_EVENT_OUTPUT_EXISTS', str(candidate), 'Each emitted command requires a fresh output directory')
        return str(candidate)

    apply_directory = output_path(apply_out, '-apply')
    sibling_outputs = [Path(apply_directory + suffix) for suffix in ('-recover', '-cold-verify', '-recovered-verify')]
    all_outputs = [Path(apply_directory), *sibling_outputs]
    if len(set(all_outputs)) != len(all_outputs):
        fail('REWRITE_EVENT_OUTPUT_COLLISION', str(apply_directory), 'Apply, recover and verification outputs must be distinct')
    protected = [stage, safe(rewrite['projectRoot']), rewrite_path, events_file, compile_path, original_native_path,
                 *[safe(row['path']) for row in source_pins]]
    for candidate in all_outputs:
        if candidate.exists() or any(candidate == item or candidate.is_relative_to(item) or item.is_relative_to(candidate) for item in protected):
            fail('REWRITE_EVENT_OUTPUT_SCOPE', str(candidate), 'Command output must be a fresh independent sibling directory')
    native_out = stage / 'production-plan'
    try:
        native = _production_plan(rewrite['projectRoot'], spec, native_out)
    except BeaverError as error:
        for result in results:
            result.update(planned=False, failed=True, reason=error.message)
        base.update(status='blocked', sourcePins=source_pins)
        write_json(stage / 'rewrite-event-plan.json', base)
        return dict(status='blocked', report=str(stage / 'rewrite-event-plan.json'), native='not_run')
    base.update(status='planned', sourcePins=source_pins,
                production=dict(report=native['report'], planSha256=native['planSha256'],
                                originalSpecPreserved=True, fileEdits=len(spec.get('fileEdits', [])),
                                originalReport=str(original_native_path),
                                originalPlanSha256=rewrite['production']['planSha256']),
                commands=dict(
                    apply=['grea', 'develop', 'production', 'apply', '--plan', native['report'], '--expected-plan', native['planSha256'],
                           '--out', apply_directory, '--editor-path', editor_path],
                    recover=['grea', 'develop', 'production', 'recover', '--transaction', apply_directory,
                             '--out', apply_directory + '-recover', '--editor-path', editor_path],
                    verifyAppliedTemplate=['grea', 'develop', 'csharp', 'rewrite-event-verify', '--plan', str(stage / 'rewrite-event-plan.json'),
                                           '--expected-plan', '<event-plan-sha256 from this command result>', '--transaction', apply_directory,
                                           '--phase', 'applied', '--out', apply_directory + '-cold-verify', '--editor-path', editor_path],
                    verifyRecoveredTemplate=['grea', 'develop', 'csharp', 'rewrite-event-verify', '--plan', str(stage / 'rewrite-event-plan.json'),
                                             '--expected-plan', '<event-plan-sha256 from this command result>', '--transaction', apply_directory,
                                             '--phase', 'recovered', '--out', apply_directory + '-recovered-verify', '--editor-path', editor_path]),
                commandBundle=str(stage / 'commands.json'),
                perEvent=[dict(sourceRecordId=event['source']['recordId'], prefabPath=event['prefab']['path'],
                               prefabGuid=event['prefab']['guid'], buttonPath=event['button']['nodePath'],
                               buttonLocalId=event['button']['componentLocalId'], buttonNodeLocalId=event['button']['nodeLocalId'],
                               targetNode=event['target']['nodePath'], targetLocalId=event['target']['componentLocalId'],
                               targetNodeLocalId=event['target']['nodeLocalId'], targetAssembly=event['target']['assembly'],
                               scriptGuid=event['target']['scriptGuid'], targetComponent=event['target']['componentType'],
                               targetType=event['target']['fullType'], method=event['target']['method'],
                               inputPolicy=event['inputPolicy'],
                               expectedCount=0, planned=True, failed=False, reason=None)
                          for event in prepared])
    for result in base['events']:
        result['planned'] = True
    report_path = stage / 'rewrite-event-plan.json'
    write_json(report_path, base)
    event_plan_sha = sha(read(report_path))
    commands = dict(apply=base['commands']['apply'], recover=base['commands']['recover'],
                    verifyApplied=['grea', 'develop', 'csharp', 'rewrite-event-verify', '--plan', str(report_path),
                                   '--expected-plan', event_plan_sha, '--transaction', apply_directory,
                                   '--phase', 'applied', '--out', apply_directory + '-cold-verify', '--editor-path', editor_path],
                    verifyRecovered=['grea', 'develop', 'csharp', 'rewrite-event-verify', '--plan', str(report_path),
                                     '--expected-plan', event_plan_sha, '--transaction', apply_directory,
                                     '--phase', 'recovered', '--out', apply_directory + '-recovered-verify', '--editor-path', editor_path])
    write_json(stage / 'commands.json', dict(eventPlan=dict(path=str(report_path), sha256=event_plan_sha), argv=commands))
    return dict(status='planned', report=str(stage / 'rewrite-event-plan.json'),
                planSha256=event_plan_sha, production=native, commands=str(stage / 'commands.json'),
                argv=commands, native='not_run', behavior='not_verified')


def verify(event_plan_path, expected_event_plan, transaction_path, phase, output, editor_path):
    path = safe(event_plan_path)
    raw = read(path, max_bytes=64 * 1024**2)
    event_plan = load(raw)
    if (sha(raw) != expected_event_plan or event_plan.get('contract') != EVENT_PLAN
            or event_plan.get('implementationSha256') != csharp_rewrite.identity()
            or event_plan.get('status') != 'planned'):
        fail('REWRITE_EVENT_VERIFY_PLAN', str(path), 'Exact current planned rewrite-event-plan/1 required')
    if phase not in ('applied', 'recovered'):
        fail('REWRITE_EVENT_VERIFY_PHASE', str(phase), 'Expected applied or recovered phase')
    if not isinstance(editor_path, str) or not Path(editor_path).is_absolute():
        fail('REWRITE_EVENT_EDITOR', 'editorPath', 'Explicit absolute Unity Editor executable path required')
    for pin in event_plan.get('sourcePins', []):
        if sha(read(pin['path'])) != pin['sha256']:
            fail('REWRITE_EVENT_SOURCE_DRIFT', pin['path'], 'Source evidence changed after planning')
        record = _pointer(load(read(pin['path'])), pin['jsonPointer'])
        if sha(encoded(record)) != pin['recordSha256']:
            fail('REWRITE_EVENT_SOURCE_RECORD_DRIFT', pin['recordId'], 'Source record changed after planning')

    rewrite_ref = event_plan.get('rewritePlan')
    if not isinstance(rewrite_ref, dict):
        fail('REWRITE_EVENT_VERIFY_REWRITE', str(path), 'Pinned source rewrite plan is required')
    rewrite_path = safe(rewrite_ref.get('path', ''))
    rewrite_raw = read(rewrite_path, max_bytes=64 * 1024**2)
    if sha(rewrite_raw) != rewrite_ref.get('sha256'):
        fail('REWRITE_EVENT_VERIFY_REWRITE', str(rewrite_path), 'Source rewrite-plan bytes changed')
    rewrite = load(rewrite_raw)
    if rewrite.get('implementationSha256') != csharp_rewrite.identity():
        fail('REWRITE_EVENT_VERIFY_REWRITE', str(rewrite_path), 'Source rewrite-plan producer changed')
    original_ref = event_plan.get('production', {})
    original_path = safe(rewrite.get('production', {}).get('report', ''))
    original_native = load(read(original_path, max_bytes=64 * 1024**2))
    if (original_path != safe(original_ref.get('originalReport', ''))
            or rewrite.get('production', {}).get('planSha256') != original_ref.get('originalPlanSha256')
            or sha(encoded(original_native)) != original_ref.get('originalPlanSha256')):
        fail('REWRITE_EVENT_VERIFY_REWRITE', str(original_path), 'Original rewrite production plan is not hash-pinned')
    original_spec = original_native.get('spec')
    if event_plan.get('projectRoot') != rewrite.get('projectRoot') or event_plan.get('projectRoot') != original_native.get('projectRoot'):
        fail('REWRITE_EVENT_VERIFY_PROJECT', str(path), 'Project root does not match pinned rewrite and production plans')

    transaction = safe(transaction_path)
    commands = event_plan['commands']
    expected_transaction = Path(commands['apply'][commands['apply'].index('--out') + 1]).resolve()
    if transaction != expected_transaction:
        fail('REWRITE_EVENT_VERIFY_TRANSACTION', str(transaction), 'Transaction path must match the reviewed apply argv')
    journal_path = transaction / 'journal.json'
    journal = load(read(journal_path, max_bytes=64 * 1024**2))
    native_plan_sha = event_plan['production']['planSha256']
    native_plan_path = safe(event_plan['production']['report'])
    native_plan_raw = read(native_plan_path, max_bytes=128 * 1024**2)
    native_plan = load(native_plan_raw)
    if sha(native_plan_raw) != native_plan_sha:
        fail('REWRITE_EVENT_VERIFY_PLAN', str(native_plan_path), 'Derived production plan bytes changed')
    if native_plan.get('contract') != 'beaver-production/3' or native_plan.get('implementationSha256') != csharp_rewrite.identity():
        fail('REWRITE_EVENT_VERIFY_PLAN', str(native_plan_path), 'Current production plan/3 producer required')
    transaction_plan_raw = read(transaction / 'batch-plan.json', max_bytes=128 * 1024**2)
    if sha(transaction_plan_raw) != native_plan_sha:
        fail('REWRITE_EVENT_VERIFY_TRANSACTION', str(transaction), 'Transaction plan differs from the reviewed production plan')
    if native_plan.get('projectRoot') != event_plan['projectRoot']:
        fail('REWRITE_EVENT_VERIFY_PROJECT', str(native_plan_path), 'Derived production plan root differs from the pinned original project')
    spec_steps = native_plan.get('spec', {}).get('steps', [])
    cursor = len(original_spec.get('steps', []))
    if (native_plan.get('spec', {}).get('fileEdits') != original_spec.get('fileEdits')
            or spec_steps[:cursor] != original_spec.get('steps')):
        fail('REWRITE_EVENT_VERIFY_SPEC', str(native_plan_path), 'Original production steps/fileEdits were not preserved')
    expected_suffix = []
    for event in event_plan.get('perEvent', []):
        inspect = dict(kind='prefab.event.inspect', assetPath=event['prefabPath'], path=event['buttonPath'],
                       targetNode=event['targetNode'], targetComponent=event['targetComponent'], method=event['method'],
                       buttonLocalId=event['buttonLocalId'], targetLocalId=event['targetLocalId'],
                       prefabGuid=event['prefabGuid'], buttonNodeLocalId=event['buttonNodeLocalId'],
                       targetNodeLocalId=event['targetNodeLocalId'], targetAssembly=event['targetAssembly'],
                       scriptGuid=event['scriptGuid'])
        expected_suffix.extend([dict(inspect, expectedCount=0),
                                dict(kind='prefab.patch', assetPath=event['prefabPath'], actions=[dict(
                                    kind='binding.event.enable' if event.get('inputPolicy') == 'enable-source-button' else 'binding.event',
                                    path=event['buttonPath'], component='UnityEngine.UI.Button',
                                    property='onClick', value='empty', method=event['method'],
                                    targetNode=event['targetNode'], targetComponent=event['targetComponent'])]),
                                dict(inspect, expectedCount=1,
                                     **({'requireInteractable': True} if event.get('inputPolicy') == 'enable-source-button' else {}))])
    if spec_steps[cursor:] != expected_suffix:
        fail('REWRITE_EVENT_VERIFY_SPEC', str(native_plan_path), 'Event ordering or exact source/target identity differs from the event plan')
    planned_write_set = native_plan.get('writeSet')
    if not isinstance(planned_write_set, list) or planned_write_set != journal.get('writeSet'):
        fail('REWRITE_EVENT_VERIFY_WRITE_SET', str(transaction), 'Journal write set differs from the planned production write set')
    if (journal.get('contract') != 'beaver-production-transaction/3'
            or journal.get('planSha256') != native_plan_sha
            or journal.get('implementationSha256') != csharp_rewrite.identity()
            or safe(journal.get('projectRoot', '')) != safe(native_plan.get('projectRoot', ''))):
        fail('REWRITE_EVENT_VERIFY_TRANSACTION', str(transaction), 'Native production transaction does not match this event plan')
    project = safe(native_plan['projectRoot'])
    planned_before = native_plan.get('before')
    journal_before = journal.get('before')
    if not isinstance(planned_before, dict) or not isinstance(journal_before, dict):
        fail('REWRITE_EVENT_VERIFY_TRANSACTION', str(transaction), 'Plan and journal before-image maps are required')
    expected_before = {relative: planned_before[relative] for relative in planned_write_set if relative in planned_before}
    if len(expected_before) != len(planned_write_set) or journal_before != expected_before:
        fail('REWRITE_EVENT_VERIFY_TRANSACTION', str(transaction), 'Journal before-image must equal the planned write-set subset')

    write_set = set(planned_write_set)
    readonly_pins = []
    for pin in rewrite.get('pins', []):
        pin_path = safe(pin['path'])
        try:
            relative = pin_path.relative_to(project).as_posix()
        except ValueError:
            relative = None
        if relative not in write_set:
            readonly_pins.append(pin)
    csharp_rewrite._check_pins(readonly_pins)
    compile_pin = rewrite.get('compileReport')
    if not isinstance(compile_pin, dict) or sha(read(safe(compile_pin.get('path', '')))) != compile_pin.get('sha256'):
        fail('REWRITE_EVENT_VERIFY_COMPILE', str(rewrite_path), 'Pinned compile report changed')
    from .batch import state
    if phase == 'applied':
        if journal.get('status') != 'complete' or not isinstance(journal.get('native'), dict) or journal['native'].get('status') != 'verified':
            fail('REWRITE_EVENT_VERIFY_APPLIED', str(transaction), 'A complete verified apply journal is required')
        expected_state = journal.get('after')
        for edit in rewrite.get('fileEdits', []):
            observed = expected_state.get(edit['path']) if isinstance(expected_state, dict) else None
            if not isinstance(observed, dict) or observed.get('sha256') != edit['sha256']:
                fail('REWRITE_EVENT_VERIFY_APPLIED', edit['path'], 'Journal after-image differs from the reviewed compiled source patch')
        expected_count = 1
    else:
        receipt_path = journal.get('recoveryReport')
        if journal.get('status') != 'recovered' or not isinstance(receipt_path, str):
            fail('REWRITE_EVENT_VERIFY_RECOVERY', str(transaction), 'Verified recovery receipt is required')
        receipt = load(read(receipt_path, max_bytes=16 * 1024**2))
        if (receipt.get('status') != 'verified' or receipt.get('report') != receipt_path
                or receipt.get('nativeReadback') != 'restored_exact_bytes_and_imported'
                or receipt.get('restored') != len(journal.get('writeSet', []))):
            fail('REWRITE_EVENT_VERIFY_RECOVERY', str(receipt_path), 'Recovery receipt does not verify')
        expected_state = journal.get('before')
        expected_count = 0
    current = state(project, journal.get('writeSet', []))
    if not isinstance(expected_state, dict) or current != expected_state:
        fail('REWRITE_EVENT_VERIFY_DRIFT', str(project), 'Project write set differs from the native transaction phase checkpoint')

    steps = []
    for event in event_plan.get('perEvent', []):
        inspect = dict(kind='prefab.event.inspect', assetPath=event['prefabPath'],
                       path=event['buttonPath'], targetNode=event['targetNode'],
                       targetComponent=event['targetComponent'], method=event['method'],
                       buttonLocalId=event['buttonLocalId'], buttonNodeLocalId=event['buttonNodeLocalId'],
                       targetLocalId=event['targetLocalId'], targetNodeLocalId=event['targetNodeLocalId'],
                       prefabGuid=event['prefabGuid'], targetAssembly=event['targetAssembly'],
                       scriptGuid=event['scriptGuid'], expectedCount=expected_count)
        if phase == 'applied' and event.get('inputPolicy') == 'enable-source-button':
            inspect['requireInteractable'] = True
        steps.append(inspect)
    spec = dict(schemaVersion=3, operation='production', profile=original_spec['profile'], steps=steps,
                fileEdits=[], readPaths=[])
    stage = new_output(output, inputs=[path, transaction, project, *[safe(p['path']) for p in event_plan.get('sourcePins', [])]])
    native = _production_plan(project, spec, stage / 'inspection-plan')
    observation_out = str(stage.parent / (stage.name + '-native-observation'))
    report = dict(contract='beaver-csharp-rewrite-event-verification/1', status='planned',
                  implementationSha256=csharp_rewrite.identity(), eventPlan=dict(path=str(path), sha256=expected_event_plan),
                  transaction=str(transaction), phase=phase, expectedCount=expected_count,
                  writeSetStateSha256=sha(encoded(current)), inspection=dict(report=native['report'], planSha256=native['planSha256']),
                  argv=['grea', 'develop', 'production', 'apply', '--plan', native['report'], '--expected-plan', native['planSha256'],
                        '--out', observation_out, '--editor-path', editor_path],
                  native='not_run', eventReadback='not_run')
    write_json(stage / 'rewrite-event-verification.json', report)
    return dict(status='planned', report=str(stage / 'rewrite-event-verification.json'),
                inspection=native, argv=report['argv'], native='not_run', eventReadback='not_run')
