"""Compatible monkey_bridge CLI; implementation lives in integrations.monkey."""
import argparse
import json,os
from grea.host.paths import Path
from grea.common import digest,hash_file,write_new,GreaError
from grea.safe_paths import canonical_path,disjoint,relative_name
from grea import runner,artifacts
from grea.integrations.monkey.identity import read,pinned
from grea.integrations.monkey.package import collect
from grea.integrations.monkey.slice import collect_slice
from grea.integrations.monkey.handoff import collect_handoff,handoff

def run(config,output,source=None,target=None,workspace=None,modules=None,timeout=120,workflow="package",source_profile=None,asset_indices=None,all_assets=False,resume_native=False,handoff_contract=None):
    cfg=pinned(config);config_identity=hash_file(config);inputs=[config,*[row['path'] for row in cfg['identity_files']],*[x for x in (source,workspace,modules,handoff_contract) if x]]
    out=disjoint(output,*inputs)
    if out.exists() or not out.parent.is_dir():raise ValueError('Use a new output directory with existing parent')
    if bool(source)==bool(workspace):raise ValueError('Choose source conversion or existing workspace normalization')
    if workflow not in ('package','slice','handoff'):raise ValueError('Choose package or slice workflow')
    if (workflow=='handoff')!=bool(handoff_contract) or handoff_contract and (not workspace or source or modules or target or source_profile or asset_indices or all_assets or resume_native):raise ValueError('Handoff requires existing workspace and contract only')
    if resume_native and (workflow!='slice' or source):raise ValueError('Native resume requires an existing isolated slice workspace')
    if workflow=='slice' and source and (source_profile not in ('cocos-2.4.15-project','cocos-2.4.15-bundle') or bool(asset_indices)==bool(all_assets)):raise ValueError('Slice requires profile and explicit selection or all-assets')
    if workflow=='package' and (source_profile or asset_indices or all_assets):raise ValueError('Slice options do not apply to package mode')
    if source and target not in ('unity6','cocos38','both'):raise ValueError('Select supported package target explicitly')
    identity_source=canonical_path(source).parent if source and workflow=='slice' and canonical_path(source).is_file() else source
    if identity_source is not None:disjoint(output,identity_source)
    before=artifacts.inspect_target(identity_source,max_files=10000,max_bytes=512*1024**2) if source else None
    if before and before['coverage']!='complete':raise ValueError('Input identity exceeds explicit budget')
    if handoff_contract:
        declaration=read(handoff_contract,32*1024**2);inventory_path=canonical_path(handoff_contract).parent/relative_name(declaration['source_inventory']['path']);inventory=read(inventory_path);inventory=inventory.get('result',inventory)
        disjoint(output,inventory_path,inventory['target']['path'])
    out.mkdir()
    try:
        cap,_,error=runner.execute('monkey',[],out/'capabilities',probe=True,timeout_seconds=20,max_output_bytes=1024**2,max_inline_bytes=1024**2)
        if error or cap['inline_truncated'] or cap['parsed_stdout'] is None:raise ValueError('Capability probe failed')
        capabilities=cap['parsed_stdout']
        if capabilities.get('version')!=cfg['version'] or digest(capabilities)!=cfg['capabilities_sha256'] or capabilities.get('schemaVersion')!=1 or 'convert' not in capabilities.get('implemented',[]):raise ValueError('Provider capability/version mismatch')
        workspace=canonical_path(workspace) if workspace else out/'conversion'
        if source:
            argv=['convert','--source',str(canonical_path(source)),'--target',target,'--out',str(workspace)]
            if workflow=='package':argv.insert(1,'--package')
            else:
                if target=='both':raise ValueError('Slice accepts one target')
                argv[argv.index('--target')+1]={'unity6':'unity','cocos38':'cocos'}[target]
                if canonical_path(source).is_dir():argv[argv.index('--source')+1]=str(canonical_path(source)/('project.json' if source_profile.endswith('-project') else 'config.json'))
                argv+=['--source-profile',source_profile]
                if all_assets:argv+=['--all-assets']
                else:
                    for index in asset_indices:
                        if type(index) is not int or index<0:raise ValueError('Nonnegative asset index required')
                        argv+=['--asset-index',str(index)]
            receipt,_,error=runner.execute('monkey',argv,out/'convert-run',timeout_seconds=timeout,max_output_bytes=1024**2,max_inline_bytes=1024**2)
            if error or not receipt['capture_complete']:raise ValueError('Provider failed; inspect preserved process receipt')
            after=artifacts.inspect_target(identity_source,max_files=10000,max_bytes=512*1024**2)
            if after!=before:raise ValueError('Input changed during conversion')
        resume_report=None
        if resume_native:
            receipt,_,error=runner.execute('monkey',['convert','--resume',str(workspace)],out/'resume-run',timeout_seconds=timeout,max_output_bytes=1024**2,max_inline_bytes=1024**2)
            if error or not receipt['capture_complete'] or not receipt['parsed_stdout']:raise ValueError('Provider native verification failed')
            resume_report=receipt['parsed_stdout'].get('report')
            if not resume_report:raise ValueError('Provider did not return a native check report')
        pinned(config)
        if hash_file(config)!=config_identity:raise ValueError('Provider pin config changed')
        value=collect_handoff(workspace,cfg['version'],handoff_contract) if workflow=='handoff' else collect(workspace,cfg['version']) if workflow=='package' else collect_slice(workspace,cfg['version'],resume_report);value.update(input_identity=before,capabilities_sha256=cfg['capabilities_sha256'],workspace=str(workspace),workflow=workflow)
        write_new(out/'result.json',value);write_new(out/'ai-modules.json',handoff(value,modules))
        return value
    except Exception as e:
        write_new(out/'failure.json',dict(status='failed',message=str(e),partial_output_preserved=True));raise

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--output',required=True);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--source');g.add_argument('--workspace');p.add_argument('--target',choices=['unity6','cocos38','both']);p.add_argument('--workflow',choices=['package','slice','handoff'],default='package');p.add_argument('--source-profile');p.add_argument('--asset-index',action='append',type=int);p.add_argument('--all-assets',action='store_true');p.add_argument('--resume-native',action='store_true');p.add_argument('--handoff-contract');p.add_argument('--modules');p.add_argument('--timeout',type=int,default=120);a=p.parse_args()
    try:
        if not 1<=a.timeout<=600:raise ValueError('Timeout must be 1..600')
        value=run(a.config,a.output,a.source,a.target,a.workspace,a.modules,a.timeout,a.workflow,a.source_profile,a.asset_index,a.all_assets,a.resume_native,a.handoff_contract);print(json.dumps(dict(status=value['status'],result=str(Path(a.output)/'result.json'),modules=str(Path(a.output)/'ai-modules.json'))));return 1 if value['status']!='success' else 0
    except (OSError,ValueError,KeyError,TypeError,GreaError) as e:print(str(e));return 2
if __name__=="__main__":raise SystemExit(main())
