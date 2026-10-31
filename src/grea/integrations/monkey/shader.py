"""Bounded forwarding to the explicitly pinned local Shader evidence classifier."""
import re
from pathlib import Path
from jsonschema import Draft202012Validator
from grea import runner
from grea.common import digest, hash_file, write_new, GreaError
from grea.safe_paths import canonical_path, disjoint, unique_paths
from .identity import pinned, read
from .pipeline import probe

CAPABILITIES_SHA256 = '9a8d4849b93d7cd88ccc30d0c815d2c89f73d7419c3086205a0485f8b6cb181d'
PACKAGE_SHA256 = '86a1ee8ed4a85cc13f45dd76dce25c4b5ca1736cb876a83670288c25e917f1c3'


def validate_candidate(cfg, cap):
    files={Path(k).relative_to(cfg['identity_root']).as_posix():v for k,v in cfg['package_files'].items()}
    if (cfg['version']!='0.6.0' or digest(cap)!=CAPABILITIES_SHA256 or digest(files)!=PACKAGE_SHA256
            or cap.get('unitySourceProfile',{}).get('shaderHandoff')!='monkey-shader-handoff/1'
            or 'classify-unity-shaders' not in cap.get('implemented',[])):
        raise ValueError('Use the exact explicitly pinned local P0 Shader candidate; version alone is insufficient')


def classify(config, project, manifest, expected_manifest, output, source_mapping=None,
             expected_source_mapping=None, timeout_seconds=30):
    if type(timeout_seconds)is not int or not 1<=timeout_seconds<=1800:
        raise ValueError('Timeout must be 1..1800 seconds')
    if (source_mapping is None)!=(expected_source_mapping is None):
        raise ValueError('Source mapping and expected SHA256 must be supplied together')
    for value in (expected_manifest,expected_source_mapping):
        if value is not None and (not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value)):
            raise ValueError('Expected lowercase SHA256')
    project=canonical_path(project);manifest=canonical_path(manifest);config=canonical_path(config)
    if not project.is_dir():raise ValueError('Expected existing frozen candidate directory')
    inputs=[hash_file(manifest,128*1024**2)]
    if inputs[0]['sha256']!=expected_manifest:raise ValueError('Owner manifest differs from expected SHA256')
    if source_mapping is not None:
        source_mapping=canonical_path(source_mapping);inputs.append(hash_file(source_mapping,128*1024**2))
        if inputs[-1]['sha256']!=expected_source_mapping:raise ValueError('Source mapping differs from expected SHA256')
    cfg=pinned(config);lock_identity=hash_file(config)
    out=disjoint(output,project,manifest,config,*[x['path'] for x in inputs],*[x['path'] for x in cfg['identity_files']])
    if out.exists() or not out.parent.is_dir():raise ValueError('Use a fresh classification output')
    out.mkdir();result=dict(status='needs_action',executed=False,native_validation='not_run',business_validation='not_run')
    try:
        cfg,cap=probe(config,out/'capabilities');validate_candidate(cfg,cap)
        argv=['classify-unity-shaders','--project',str(project),'--manifest',str(manifest),
              '--expected-manifest',expected_manifest,'--out',str(out/'provider-output')]
        if source_mapping is not None:argv+=['--source-mapping',str(source_mapping),'--expected-source-mapping',expected_source_mapping]
        value,_,error=runner.execute('monkey',argv,out/'invocation',timeout_seconds=timeout_seconds,
                                    max_output_bytes=8*1024**2,max_inline_bytes=1024**2)
        result['executed']=True;result['provider_receipt']=str(out/'invocation/run.json')
        if isinstance(value.get('parsed_stdout'),dict):result['provider_result']=value['parsed_stdout']
        pinned(config)
        if hash_file(config)!=lock_identity:raise ValueError('Provider lock changed during classification')
        if any(hash_file(x['path'],128*1024**2)!=x for x in inputs):raise ValueError('Owner manifest or mapping changed')
        if error or value.get('exit_code')!=0 or not value.get('capture_complete'):
            raise ValueError('Classification did not complete; inspect preserved provider receipt')
        report=read(out/'provider-output/report.json',8*1024**2)
        handoff=read(out/'provider-output/handoff.json',8*1024**2)
        from grea.monkey_contracts import SHADER_HANDOFF_SCHEMA
        failure=next(Draft202012Validator(SHADER_HANDOFF_SCHEMA).iter_errors(handoff),None)
        if failure is not None:raise ValueError('Invalid Shader handoff: '+failure.json_path)
        if (report.get('status')!='classified' or report.get('contract')!='monkey-shader-handoff/1'
                or report.get('ownerManifestSha256')!=expected_manifest
                or report.get('sourceMappingSha256')!=expected_source_mapping
                or report.get('nativeCompilation')!='not_run' or report.get('nativeImport')!='not_run'
                or report.get('projectWritten')is not False or report.get('sourceCodeExecuted')is not False
                or report.get('scope',{}).get('shaderSubsetUnchanged')is not True
                or report.get('handoffSha256')!=hash_file(out/'provider-output/handoff.json',8*1024**2)['sha256']):
            raise ValueError('Shader report identity or evidence scope differs')
        unique_paths(x['path'] for x in handoff['items'])
        for item in handoff['items']:
            path=canonical_path(project/item['path'])
            if not path.is_relative_to(project):raise ValueError('Handoff path escapes project')
            actual=hash_file(path,16*1024**2)
            if actual['sha256']!=item['sha256'] or actual['bytes']!=item['bytes']:
                raise ValueError('Classified file differs from handoff')
        result.update(status='classified',provider_version=cfg['version'],report=hash_file(out/'provider-output/report.json'),
                      handoff=hash_file(out/'provider-output/handoff.json'),counts=report.get('counts',{}),
                      limitations=['Classification and serialized target declarations are not native compilation, build readiness or gameplay acceptance.'])
    except (OSError,ValueError,KeyError,TypeError,GreaError) as error:
        result['diagnostic']=str(error)
    write_new(out/'result.json',result)
    return result
