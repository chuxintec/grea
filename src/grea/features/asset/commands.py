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
    from .bundle_models import build_parser, prepare
    def prepare_models(args):
        return development_result(args, operation=lambda a: prepare(a.inspections, a.output, a.occupied))
    commands.append(Command('asset', 'prepare-bundle-models', 'structured',
                            ('asset', 'prepare-bundle-models'), build_parser(),
                            {'command': 'asset', 'action': 'prepare-bundle-models'},
                            'Prepare pinned static models for native Unity recovery.', prepare_models))
    from .verify_visual import verify as verify_visual
    def verify_native(args):
        return development_result(args, operation=verify_visual)
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--paths', required=True, help='UTF-8 file, one existing Unity asset path per line')
    parser.add_argument('--unity-editor', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--budget-seconds', type=int, default=1800)
    commands.append(Command('asset', 'verify-visual-assets', 'structured',
                            ('asset', 'verify-visual-assets'), parser,
                            {'command': 'asset', 'action': 'verify-visual-assets'},
                            'Read native visual objects and their persistent references.', verify_native))
    from .prepare_visual import prepare as prepare_visual
    def prepare_native(args):
        return development_result(args, operation=prepare_visual)
    parser = argparse.ArgumentParser()
    parser.add_argument('--texture-plan', required=True)
    parser.add_argument('--atlas-plan', required=True)
    parser.add_argument('--font-plan')
    parser.add_argument('--binding-plan', help='Source-proven material texture slots and permitted current pixel identities')
    parser.add_argument('--packable-sprites', action='store_true', help='Include native Sprite Editor atlas authoring helper; requires com.unity.2d.sprite')
    parser.add_argument('--output', required=True)
    commands.append(Command('asset', 'prepare-visual-assets', 'structured',
                            ('asset', 'prepare-visual-assets'), parser,
                            {'command': 'asset', 'action': 'prepare-visual-assets'},
                            'Pin source-derived texture, atlas and dynamic font plans for Unity.', prepare_native))
    from .reconstruct_shader import reconstruct
    def shader_source(args):
        return development_result(args, operation=reconstruct)
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, help='Pinned form.json and numbered GLSL subprogram directory')
    parser.add_argument('--output', required=True)
    commands.append(Command('asset', 'reconstruct-gles-shader', 'structured',
                            ('asset', 'reconstruct-gles-shader'), parser,
                            {'command': 'asset', 'action': 'reconstruct-gles-shader'},
                            'Reconstruct editable ShaderLab from serialized GLES source.', shader_source))
    return tuple(commands)
