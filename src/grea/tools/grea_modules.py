"""List, verify and explicitly install the monkey/beaver modules released with GREA."""
import argparse
import json
import zipfile
from grea import modules
from grea.common import GreaError


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='action',required=True)
    commands.add_parser('status')
    sub=commands.add_parser('install');sub.add_argument('module',choices=modules.NAMES);sub.add_argument('--output',required=True)
    sub.add_argument('--wheel',help='Explicit wheel path; must match modules.lock.json exactly')
    binary=commands.add_parser('install-binary');binary.add_argument('module',choices=modules.NAMES)
    for name in ('archive','expected-archive','expected-manifest','state-root','output'):
        binary.add_argument('--'+name,required=True)
    args=parser.parse_args(argv)
    if args.action=='status':result=modules.status()
    else:
        try:
            if args.action=='install-binary':
                from grea.binary_provider import install_archive
                result=install_archive(args.module,args.archive,args.expected_archive,args.expected_manifest,args.state_root,args.output)
            else:result=modules.install(args.module,args.output,wheel=args.wheel)
        except (ValueError,OSError,GreaError,zipfile.BadZipFile) as error:result=dict(status='needs_action',installed=False,diagnostic=str(error))
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result.get('status')=='ok' else 1

if __name__=='__main__':raise SystemExit(main())
