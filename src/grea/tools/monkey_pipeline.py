"""Plan, execute and audit the pinned monkey bulk pipeline; discover/bind locally or explicitly install a missing provider."""
import argparse,json,subprocess
from grea.common import GreaError,write_new
from grea.integrations.monkey import pipeline
from grea.integrations.monkey.identity import create_lock,pinned
from grea.integrations.monkey.audit import audit


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='action',required=True)
    commands.add_parser('discover')
    for action in ('check','ensure'):
        sub=commands.add_parser(action);sub.add_argument('--output',required=True)
        if action=='ensure':sub.add_argument('--install-if-missing',action='store_true')
    pin=commands.add_parser('pin');pin.add_argument('--package-root',required=True);pin.add_argument('--output',required=True)
    for action in ('plan','run','audit'):
        p=commands.add_parser(action);p.add_argument('--config',help='Omit to use the checked persistent local binding');p.add_argument('--output',required=True)
        p.add_argument({'plan':'--request','run':'--plan','audit':'--workspace'}[action],required=True)
        if action=='audit':
            p.add_argument('--level',choices=['generated','static','editor'],default='generated')
            p.add_argument('--expected-manifest')
            p.add_argument('--expected-readback')
    shader=commands.add_parser('classify-shaders',help='Bounded read-only classification with an explicit fixed local P0 lock')
    for name in ('config','project','manifest','expected-manifest','output'):shader.add_argument('--'+name,required=True)
    shader.add_argument('--source-mapping');shader.add_argument('--expected-source-mapping')
    shader.add_argument('--timeout-seconds',type=int,default=30)
    selection=commands.add_parser('freeze-native-selection')
    for name in ('config','candidate','expected-manifest','expected-readback','output'):selection.add_argument('--'+name,required=True)
    selection.add_argument('--prefab',action='append',required=True)
    native=commands.add_parser('native-step')
    for name in ('config','request','output'):native.add_argument('--'+name,required=True)
    args=parser.parse_args(argv)
    try:
        if args.action=='native-step':
            from grea.integrations.monkey.native_steps import run
            result=run(args.config,args.request,args.output)
            print(json.dumps(dict(status=result['status'],output=args.output,executed=result['executed'])));return 1
        if args.action=='freeze-native-selection':
            from grea.integrations.monkey.selection import freeze
            result=freeze(args.config,args.candidate,args.prefab,args.expected_manifest,args.expected_readback,args.output)
            print(json.dumps(result));return 1 if result['status']=='needs_action' else 0
        if args.action=='classify-shaders':
            from grea.integrations.monkey.shader import classify
            result=classify(args.config,args.project,args.manifest,args.expected_manifest,args.output,args.source_mapping,args.expected_source_mapping,args.timeout_seconds)
            print(json.dumps(result));return 0 if result['status']=='classified' else 1
        if args.action=='discover':
            from grea.integrations.monkey.local import discover
            print(json.dumps(discover()));return 0
        if args.action in ('check','ensure'):
            from grea.integrations.monkey.local import readiness
            result=readiness(args.output,ensure=args.action=='ensure',install_missing=getattr(args,'install_if_missing',False))
            print(json.dumps(result));return 0 if result.get('ready') else 1
        if args.action!='pin' and args.config is None:
            from grea.integrations.monkey.local import default_lock
            args.config=default_lock()
        if args.action=='pin':
            result=create_lock(args.package_root,args.output)
            print(json.dumps(dict(status='pinned',version=result['version'],output=args.output)));return 0
        if args.action=='plan':result=pipeline.plan(args.config,args.request,args.output)
        elif args.action=='run':result=pipeline.execute(args.config,args.plan,args.output)
        else:
            if args.level!='generated':
                from grea.integrations.monkey.saved import verify
                result=verify(args.config,args.workspace,args.output,args.level,args.expected_manifest,args.expected_readback)
                print(json.dumps(dict(status=result['status'],output=args.output,executed=result['executed'])))
                return 1 if result['status']=='needs_action' else 0
            if args.expected_manifest is not None or args.expected_readback is not None:
                raise ValueError('Expected hashes require an explicit static/editor audit level')
            from grea.safe_paths import disjoint
            from pathlib import Path
            cfg=pinned(args.config);out=disjoint(args.output,args.workspace,args.config,*[r['path'] for r in cfg['identity_files']])
            if cfg['version'] in (pipeline.DEV1_VERSION,pipeline.DEV2_VERSION,pipeline.DEV3_VERSION,pipeline.DEV4_VERSION):
                raise ValueError('Fixed dev1 audit requires explicit --level static/editor and expected hashes')
            if out.exists() or not out.parent.is_dir():raise ValueError('Use a fresh audit output')
            result=audit(args.workspace,cfg['version']);out.mkdir();write_new(out/'result.json',result)
        print(json.dumps(dict(status=result.get('status','planned'),output=args.output,executed=result.get('executed',False))))
        return 1 if result.get('status')=='needs_action' else 0
    except (OSError,ValueError,KeyError,TypeError,GreaError,subprocess.SubprocessError) as error:
        print(json.dumps(dict(status='failed',error=str(error))));return 2

if __name__=='__main__':raise SystemExit(main())
