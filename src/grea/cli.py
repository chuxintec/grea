"""Thin CLI over the same application contracts advertised to MCP."""
import argparse,json,os,sys,subprocess
from grea.host.paths import Path
from . import __version__
from .common import GreaError,package_root,digest
from .contracts import CONTRACTS,catalog

def legacy_main(tool_id,arguments):
    from .registry import legacy_command
    try:
        argv=legacy_command(tool_id)+arguments
        if os.name=='nt':return subprocess.call(argv)
        os.execv(argv[0],argv)
    except GreaError as e:print(e.code+': '+str(e),file=sys.stderr);return 2

def main():
    if os.name=='nt':
        for stream in (sys.stdin,sys.stdout,sys.stderr):
            if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    from .commands.interface import route
    if not sys.argv[1:] or sys.argv[1:] in (["--help"], ["-h"]):
        from .commands.groups import MODULES
        print("GREA — game research, recovery and development")
        print("usage: grea [--request FILE|-] MODULE ACTION [parameters]")
        print("       grea commands [MODULE [ACTION]] [--json]")
        print("       grea --version | grea mcp")
        print()
        for name, description in MODULES.items():
            print(f"  {name:10} {description}")
        return 0
    routed = route(sys.argv[1:])
    if routed is not None:
        return routed
    if sys.argv[1:2] == ['recover']:
        from .recovery.cli import main as recover
        return recover(sys.argv[2:])
    if sys.argv[1:2] == ['develop']:
        from .development.cli import main as develop
        return develop(sys.argv[2:])
    p=argparse.ArgumentParser(prog='grea',description='Game Reverse Engineering and Assembly: game research, explicit Unity/Cocos targets, Go templates and MCP.')
    p.add_argument('--version',action='version',version=__version__)
    sub=p.add_subparsers(dest='operation',required=True)
    from .commands.groups import MODULES
    sub.add_parser('commands', help='List functional modules and command parameters')
    for module, label in MODULES.items():
        sub.add_parser(module, help=label)
    sub.add_parser('recover', help='Recover source packages, assets, Prefabs and code.')
    sub.add_parser('develop', help='Adopt, edit, verify and build development projects.')
    sub.add_parser('mcp',help='Serve stdio MCP using the official SDK; stdout is protocol-only.')
    sub.add_parser('catalog',help='Print generated operation/provider contracts as JSON.')
    legacy=sub.add_parser('legacy',help='Compatibility passthrough: retain existing helper argv, stdout and exit codes.')
    legacy.add_argument('tool_id');legacy.add_argument('arguments',nargs=argparse.REMAINDER)
    for name,(description,_,_) in CONTRACTS.items():
        q=sub.add_parser(name.replace('_','-'),help=description,description=description)
        group=q.add_mutually_exclusive_group()
        group.add_argument('request',nargs='?',default=None,help='JSON object; omitted for empty requests.')
        group.add_argument('--input',type=Path,help='Read a JSON request file.')
        q.add_argument('--json',action='store_true',help='Compatibility flag; output is always a structured JSON envelope.')
    args=p.parse_args()
    if args.operation=='mcp':
        from .mcp_server import main as serve
        serve();return 0
    if args.operation=='legacy':
        return legacy_main(args.tool_id,args.arguments)
    if args.operation=='catalog':
        from .registry import load
        value={'schema_version':1,'product':'grea','version':__version__,'operations':catalog(),'providers':load()}
        value['catalog_sha256']=digest(value);print(json.dumps(value,ensure_ascii=False,indent=2));return 0
    from .application import dispatch
    try:request=json.loads(args.input.read_text(encoding='utf-8') if args.input else args.request or '{}',parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-JSON constant '+value)))
    except (OSError,ValueError) as e:
        from .common import envelope
        result=envelope(args.operation.replace('-','_'),status='error',error=GreaError('INVALID_JSON',str(e)))
    else:result=dispatch(args.operation.replace('-','_'),request)
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    return {'ok':0,'partial':1,'error':2}[result['status']]

if __name__=='__main__':raise SystemExit(main())
