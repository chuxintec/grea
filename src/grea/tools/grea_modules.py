"""List, verify and explicitly install the monkey/beaver modules released with GREA."""
import argparse
import json
from grea import modules


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='action',required=True)
    commands.add_parser('status')
    sub=commands.add_parser('install');sub.add_argument('module',choices=modules.NAMES);sub.add_argument('--output',required=True)
    sub.add_argument('--wheel',help='Explicit wheel path; must match modules.lock.json exactly')
    args=parser.parse_args(argv)
    if args.action=='status':result=modules.status()
    else:
        try:result=modules.install(args.module,args.output,wheel=args.wheel)
        except (ValueError,OSError) as error:result=dict(status='needs_action',installed=False,diagnostic=str(error))
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result.get('status')=='ok' else 1

if __name__=='__main__':raise SystemExit(main())
