"""Check both required providers explicitly; discovery/session never installs or probes."""
import argparse
import json
from pathlib import Path
from grea.common import write_new
from grea.safe_paths import disjoint


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True);parser.add_argument('--beaver-config')
    args=parser.parse_args(argv)
    from grea.integrations.monkey.local import readiness, state_root as monkey_state
    from grea.integrations.beaver import check, state_root as beaver_state
    roots=[monkey_state(),beaver_state()]+([args.beaver_config] if args.beaver_config else [])
    out=disjoint(args.output,*roots)
    if out.exists() or not out.parent.is_dir():raise ValueError('Use a fresh toolchain receipt directory')
    out.mkdir()
    providers={'monkey':readiness(out/'monkey'),'beaver':check(out/'beaver',lock=args.beaver_config)}
    ready=all(p.get('ready') is True for p in providers.values())
    result=dict(status='ok' if ready else 'needs_action',ready=ready,required_providers=['monkey','beaver'],providers=providers,
                executed=False,native='not_run',gameplay='not_run',
                next_action='Select and invoke the provider for the task stage.' if ready else 'Resolve provider diagnostics; documentation/planning and explicitly pinned in-flight legacy work may continue.')
    write_new(out/'result.json',result);print(json.dumps(result,ensure_ascii=False));return 0 if ready else 1

if __name__=='__main__':raise SystemExit(main())
