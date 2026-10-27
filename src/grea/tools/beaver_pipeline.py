"""Discover and verify the external beaver provider; never substitutes engineering logic."""
import argparse
import json
from grea.integrations.beaver import discover, check, inspect_project


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='action',required=True)
    commands.add_parser('discover')
    for action in ('check','pin'):
        sub=commands.add_parser(action);sub.add_argument('--output',required=True)
        if action=='check': sub.add_argument('--config')
        else: sub.add_argument('--identity-root',required=True)
    sub=commands.add_parser('inspect');sub.add_argument('--config',required=True);sub.add_argument('--project',required=True);sub.add_argument('--output',required=True)
    sub=commands.add_parser('invoke');sub.add_argument('--config',required=True);sub.add_argument('--request',required=True);sub.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    if args.action=='discover': result=discover()
    elif args.action=='invoke':
        from grea.integrations.beaver_operations import invoke
        result=invoke(args.config,args.request,args.output)
    elif args.action=='inspect':result=inspect_project(args.config,args.project,args.output)
    else: result=check(args.output,lock=getattr(args,'config',None),identity_root=getattr(args,'identity_root',None),pin=args.action=='pin')
    print(json.dumps(result,ensure_ascii=False))
    return 0 if args.action=='discover' or result.get('ready') or result.get('status')=='ok' else (2 if result.get('status')=='failed' else 1)

if __name__=='__main__':raise SystemExit(main())
