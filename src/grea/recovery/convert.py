"""Create-only CLI orchestration; never launches an editor or mutates a source."""
import json
import uuid
from . import __version__
from .io import safe, new_output, read, load, write_json, finish, sha, stage_document
from .sources import project, bundle
from .sources.compiled import fail
from .normalize import normalize
from .targets import unity, cocos

TARGETS = {'unity': unity, 'cocos': cocos, unity.PROFILE: unity, cocos.PROFILE: cocos}


def recipe(path):
    path = safe(path)
    data = load(read(path))
    types = dict(source=str,target=str,source_profile=str,namespace=str,selection=list,
                 all_assets=bool,dependencies=list,evidence=list,bindings=str,animations=list)
    if not isinstance(data,dict) or set(data)-set(types) or not {'source','target'} <= set(data):
        fail('INVALID_RECIPE',str(path),'Expected source/target and supported conversion options only')
    for key,value in data.items():
        if type(value) is not types[key]: fail('INVALID_RECIPE',key,'Unexpected option type')
        if isinstance(value,list):
            expected = int if key == 'selection' else str
            if any(type(v) is not expected for v in value): fail('INVALID_RECIPE',key,'Unexpected list value')
    if data['target'] not in TARGETS: fail('INVALID_RECIPE','target','Unsupported target profile')
    for key in ('source','bindings'):
        if key in data: data[key] = str(safe(path.parent/data[key]))
    for key in ('dependencies','evidence'):
        if key in data: data[key] = [str(safe(path.parent/p)) for p in data[key]]
    return data


def convert(source, target, output, namespace='monkey-project', source_profile=None,
            selection=None, all_assets=False, dependencies=(), evidence=(), bindings=None,
            animations=None, offline=False, system_fonts=False):
    source = safe(source)
    if source.is_dir():
        if (source/'project.json').is_file():
            source = source/'project.json'
            detected = project.PROFILE
        elif (source/'config.json').is_file():
            source = source/'config.json'
            detected = bundle.PROFILE
        else:
            fail('UNSUPPORTED_SOURCE', str(source), 'Expected project.json or bundle config.json')
    else:
        detected = project.PROFILE if source.name == 'project.json' else bundle.PROFILE
    profile = source_profile or detected
    if profile not in (project.PROFILE, bundle.PROFILE):
        fail('UNSUPPORTED_SOURCE', str(source), 'Unsupported source profile')
    if profile == bundle.PROFILE and source_profile is None:
        if load(read(source)).get('engineVersion') != '2.4.15':
            fail('VERSION_EVIDENCE_REQUIRED', str(source), 'Declare --source-profile when engineVersion is absent')
    adapter = TARGETS[target]
    if system_fonts and (adapter != unity or profile != bundle.PROFILE):
        fail('SOURCE_FONT_PROFILE_UNSUPPORTED', str(source), 'CoreText font conversion requires a Unity target and a Cocos 2.4.15 bundle')

    inputs = [source.parent, *[safe(p).parent for p in dependencies], *[safe(p).parent for p in evidence]]
    if bindings:
        inputs.append(safe(bindings))
    # Validate the input and selection before reserving an output directory.
    if selection and all_assets:
        fail('INVALID_SELECTION', '$', '--asset-index and --all-assets are mutually exclusive')
    if profile == project.PROFILE:
        if dependencies or evidence:
            fail('INVALID_SOURCE_OPTIONS', '$', 'Editable projects do not accept bundle dependencies/evidence')
        parsed = project.Project(source.parent)
        indices = list(selection) if selection else list(range(len(parsed.keys)))
    else:
        parsed = bundle.Bundle(source)
        if not selection and not all_assets:
            fail('SELECTION_REQUIRED', '$', 'Bundle input requires --asset-index or explicit --all-assets')
        indices = list(selection) if selection else list(range(len(parsed.keys)))
    if not indices:
        fail('EMPTY_SELECTION', str(source), 'No assets found')
    out = new_output(output, inputs)
    receipt = dict(schemaVersion=1, toolVersion=__version__, source=str(source),
                   sourceProfile=profile, targetProfile=adapter.PROFILE, selection=indices,
                   project=str(out/'project'), stages=[], diagnostics=[],
                   validation=dict(editor='not_run', visual='not_run', business='not_run'))
    stage = 'inspect'
    try:
        if profile == project.PROFILE:
            result = project.inspect(source.parent, indices, out/'inspect')
        else:
            result = bundle.inspect(source, indices, out/'inspect', dependencies, evidence)
        receipt['stages'].append(dict(stage=stage, status=result['status'], report='inspect/manifest.json'))
        def build_plan():
            args = {}
            if system_fonts:
                from .source_system_font_preparation import conversion_plan_inputs
                args = conversion_plan_inputs(out/'normalize/ir.json', out/'inspect/source-manifest.json', out/'SystemFonts')
            return adapter.plan(out/'normalize/ir.json', namespace, out/'plan', bindings, animations, **args)

        for stage, run in (
            ('normalize', lambda: normalize(out/'inspect/source-manifest.json', out/'normalize')),
            ('plan', build_plan),
            ('export', lambda: adapter.export(out/'plan/plan.json', out/'project')),
            ('verify', lambda: adapter.verify(out/'project', out/'verify', 'static')),
            ('handoff', lambda: unity.handoff(out/'project', out/'handoff')),
        ):
            result = run()
            directory = 'project' if stage == 'export' else stage
            receipt['stages'].append(dict(stage=stage, status=result['status'], report=directory+'/manifest.json'))
        # Stage diagnostics are cumulative in some adapters. Deduplicate exact records.
        seen = set()
        for directory in ('inspect', 'normalize', 'plan', 'project', 'verify', 'handoff'):
            for item in load(read(out/directory/'manifest.json')).get('diagnostics', []):
                key = json.dumps(item, sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    receipt['diagnostics'].append(item)
        # The adapter distinguishes file/schema verification from presentation gaps.
        verification = load(read(out/'verify/manifest.json'))
        receipt['validation']['static'] = verification['staticValidation']
        receipt['completed'] = True
        receipt['candidateManifestSha256'] = sha(read(out/'project/manifest.json'))
        receipt['sourceManifestSha256'] = sha(read(out/'inspect/source-manifest.json'))
        receipt['resultKind'] = 'candidate'
        receipt['workflowStatus'] = 'partial' if offline else 'needs_action'
        if receipt['validation']['static'] != 'pass':
            receipt['workflowStatus'] = 'failed'
        receipt['nextAction'] = dict(code='NATIVE_IMPORT_PENDING',
            message='Native editor import/save/readback is pending; automatic editor launch is not implemented by this command.',
            resume=['grea','recover','convert','--resume',str(out)])
        write_json(out/'conversion.json', receipt)
        return finish(out, receipt)
    except Exception as error:
        # Preserve completed stages and a machine-readable failure; never delete evidence.
        receipt.update(completed=False, failedStage=stage, status='error',
                       error=dict(code=getattr(error, 'code', 'CONVERSION_FAILED'), message=str(error)))
        write_json(out/'conversion.json', receipt)
        raise


def resume(output):
    """Recheck a completed candidate without re-extracting or overwriting it."""
    out = safe(output)
    receipt = stage_document(out/'conversion.json')
    if receipt.get('toolVersion') != __version__ or not receipt.get('completed'):
        fail('RESUME_MISMATCH', str(out), 'Only a completed candidate of the same tool version can resume')
    for path, field in ((out/'project/manifest.json','candidateManifestSha256'),
                        (out/'inspect/source-manifest.json','sourceManifestSha256')):
        if sha(read(path)) != receipt[field]:
            fail('RESUME_MISMATCH', str(path), 'Stage identity changed')
    source = load(read(out/'inspect/source-manifest.json'))
    for item in source['inputs']:
        from .io import inside
        root = safe(source['sourceRoots'][item['bundle']])
        if sha(read(inside(root,item['path']))) != item['sha256']:
            fail('SOURCE_CHANGED', item['path'], 'Source differs from conversion input')
    for item in source.get('evidenceFiles', []):
        if sha(read(item['path'])) != item['sha256']:
            fail('SOURCE_CHANGED', item['path'], 'Evidence differs from conversion input')
    adapter = TARGETS[receipt['targetProfile']]
    check = out/'checks'/str(uuid.uuid4())
    result = adapter.verify(out/'project', check, 'editor')
    receipt['validation']['editor'] = result['editorValidation']
    receipt['validation']['static'] = result['staticValidation']
    receipt['resultKind'] = 'native' if result['editorValidation'] == 'pass' else 'candidate'
    receipt['workflowStatus'] = 'partial' if result['editorValidation'] == 'pass' else 'needs_action'
    if result['staticValidation'] != 'pass' or result['editorValidation'] == 'fail':
        receipt['workflowStatus'] = 'failed'
    receipt['diagnostics'] += result['diagnostics']
    if result['editorValidation'] == 'pass':
        receipt['nextAction'] = dict(code='VISUAL_BUSINESS_PENDING',message='Native readback passed; visual and business validation remain pending.')
    write_json(check/'resume.json', receipt)
    receipt['report'] = str(check/'resume.json')
    return receipt
