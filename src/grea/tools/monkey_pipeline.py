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
    args=parser.parse_args(argv)
    try:
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
            from grea.safe_paths import disjoint
            from pathlib import Path
            cfg=pinned(args.config);out=disjoint(args.output,args.workspace,args.config,*[r['path'] for r in cfg['identity_files']])
            if out.exists() or not out.parent.is_dir():raise ValueError('Use a fresh audit output')
            result=audit(args.workspace,cfg['version']);out.mkdir();write_new(out/'result.json',result)
        print(json.dumps(dict(status=result.get('status','planned'),output=args.output,executed=result.get('executed',False))))
        return 1 if result.get('status')=='needs_action' else 0
    except (OSError,ValueError,KeyError,TypeError,GreaError,subprocess.SubprocessError) as error:
        print(json.dumps(dict(status='failed',error=str(error))));return 2

if __name__=='__main__':raise SystemExit(main())
