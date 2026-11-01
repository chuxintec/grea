"""Forward a fixed producer's native selection; never infer dependencies here."""
import re
from grea import runner
from grea.common import hash_file, write_new
from grea.safe_paths import canonical_path, disjoint, relative_name, unique_paths
from .identity import pinned, read
from .pipeline import probe, DEV2_VERSION, DEV3_VERSION, DEV4_VERSION


def freeze(config, candidate, prefabs, expected_manifest, expected_readback, output):
    for value in (expected_manifest, expected_readback):
        if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{64}',value):raise ValueError('Expected SHA256')
    if not 1<=len(prefabs)<=128:raise ValueError('Select 1..128 Prefabs')
    unique_paths(prefabs)
    for p in prefabs:
        if relative_name(p).as_posix()!=p or not p.startswith('Assets/') or not p.endswith('.prefab'):raise ValueError('Expected canonical Assets Prefab')
    candidate=canonical_path(candidate);cfg=pinned(config)
    if cfg['schema_version']!=2 or cfg['version'] not in (DEV2_VERSION,DEV3_VERSION,DEV4_VERSION):raise ValueError('Fixed dev2/dev3/dev4 lock required')
    identities=[hash_file(config),hash_file(candidate/'manifest.json',128*1024**2),hash_file(candidate/'Analysis/Readback/editor-readback.json',128*1024**2)]
    if [x['sha256'] for x in identities[1:]]!=[expected_manifest,expected_readback]:raise ValueError('Candidate/readback identity drift')
    out=disjoint(output,candidate,config,*[x['path'] for x in cfg['identity_files']])
    if out.exists() or not out.parent.is_dir():raise ValueError('Fresh output required')
    out.mkdir();executed=False
    try:
        probe(config,out/'capabilities')
        argv=['freeze-native-selection','--candidate',str(candidate),'--expected-manifest',expected_manifest,'--expected-readback',expected_readback,'--out',str(out/'provider-output')]
        for p in prefabs:argv+=['--prefab',p]
        receipt,_,error=runner.execute('monkey',argv,out/'invocation',timeout_seconds=300,max_output_bytes=1024**2,max_inline_bytes=1024**2);executed=True
        pinned(config)
        if any(hash_file(x['path'],128*1024**2)!=x for x in identities):raise ValueError('Input identity changed')
        if error or receipt.get('exit_code')!=0 or not receipt.get('capture_complete'):raise ValueError('Selection failed; inspect original receipt')
        manifest=out/'provider-output/manifest.json';m=read(manifest,128*1024**2)
        if m.get('schemaVersion')!=1 or m.get('sourceCandidateManifestSha256')!=expected_manifest or m.get('sourceNativeReadbackSha256')!=expected_readback:raise ValueError('Selection parent identity mismatch')
        selected=m.get('selection',{}).get('prefabs',[])
        if not isinstance(selected,list) or len(selected)!=len(prefabs) or set(selected)!=set(prefabs):raise ValueError('Selection differs from request')
        files=m['files'];unique_paths(x['path'] for x in files)
        if len(files)>20000:raise ValueError('Selection file limit exceeded')
        remaining=256*1024**2
        for row in files:
            p=canonical_path(out/'provider-output'/relative_name(row['path']))
            if not p.is_relative_to(out/'provider-output'):raise ValueError('Selection path escapes output')
            h=hash_file(p,remaining);remaining-=h['bytes']
            if h['sha256']!=row['sha256'] or h['bytes']!=row['bytes']:raise ValueError('Selected file changed')
        result=dict(status='needs_action',executed=True,provider_version=cfg['version'],manifest=hash_file(manifest),files=len(files),bytes=256*1024**2-remaining,adoptionDependencies=m.get('adoptionDependencies'),shaderDependencies=m.get('shaderDependencies'),diagnostics=m.get('diagnostics',[]),nativeFontCoverageContract=m.get('nativeFontCoverageContract'),native_validation='existing_provider_evidence_reused',editor_started=False,business_validation='not_run',handoff_ready=False)
        write_new(out/'result.json',result);return result
    except Exception as error:
        write_new(out/'failure.json',dict(status='failed',executed=executed,message=str(error),partial_output_preserved=True));raise
