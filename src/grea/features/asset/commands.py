"""Public operations for standardizing a recovered Unity asset set."""
import argparse

from grea.commands.catalog import Command
from grea.development.result import development_result


def run(args):
    from .recovered_layout import stage
    from .verify_recovered import verify
    from .collect_recovered import collect
    operation = {'stage-recovered-layout': stage, 'verify-recovered-layout': verify, 'collect-recovered-layout': collect}[args.action]
    return development_result(args, operation=operation)


def declared_commands():
    commands = []
    for action in ('collect-recovered-layout', 'stage-recovered-layout', 'verify-recovered-layout'):
        parser = argparse.ArgumentParser()
        parser.add_argument('--project', required=True, help='Closed Unity project to read')
        if action != 'collect-recovered-layout':
            parser.add_argument('--inventory', required=True, help='Native inventory TSV collected from this project')
        parser.add_argument('--output', required=True, help='Fresh independent output directory')
        if action == 'collect-recovered-layout':
            parser.add_argument('--unity-editor', required=True, help='Matching installed Unity Editor executable')
            parser.add_argument('--budget-seconds', type=int, default=1800, help='Native Editor timeout (30..7200 seconds)')
            description = 'Collect native asset types and direct references in Unity.'
        elif action == 'stage-recovered-layout':
            parser.add_argument('--addresses', help='Optional JSON object mapping asset GUIDs to source logical paths')
            description = 'Stage recovered assets under GREA paths.'
        else:
            parser.add_argument('--before', required=True, help='Original native inventory TSV')
            parser.add_argument('--ledger', required=True, help='Staged layout.jsonl')
            description = 'Verify asset identities, bytes, types and dependencies after Unity import.'
        commands.append(Command('asset', action, 'structured', ('asset', action), parser,
                                {'command':'asset', 'action':action}, description, run))
    return tuple(commands)
