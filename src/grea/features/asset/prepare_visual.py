"""Pin source-derived visual plans and native helper code for independent Unity staging."""
import json
import re
from pathlib import Path, PurePosixPath

from grea.common import hash_file
from grea.development.io import safe, new_output


def prepare(args):
    files = {'texture-import-plan.json': safe(args.texture_plan), 'atlas-plan.json': safe(args.atlas_plan)}
    if args.font_plan:
        files['dynamic-font-plan.json'] = safe(args.font_plan)
    if args.binding_plan:
        files['sampler-source-materials.json'] = safe(args.binding_plan)
    plans = {name: json.loads(path.read_text()) for name, path in files.items()}
    targets = set()

    def asset_path(path):
        if not isinstance(path, str) or not path.startswith('Assets/') or any(c in path for c in ('\\', '\x00', '\n', '\r', '\t')) or any(part in ('', '.', '..') for part in path.split('/')):
            raise ValueError('Invalid canonical Unity asset path')
        return path

    def guid(value):
        if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{32}', value):
            raise ValueError('Expected exact Unity GUID')

    def target(path):
        asset_path(path)
        value = PurePosixPath(path)
        if not path.startswith('Assets/Game/Content/') or '..' in value.parts or '\\' in path:
            raise ValueError('Native visual target must use canonical GREA content paths')
        if path.casefold() in targets:
            raise ValueError('Duplicate native visual target')
        targets.add(path.casefold())

    for row in plans['texture-import-plan.json']['textures']:
        target(row['path'])
        if not all(isinstance(row[k], int) for k in ('w', 'h', 'filter', 'wrapU', 'wrapV', 'wrapW', 'colorSpace', 'mips', 'aniso')):
            raise ValueError('Native texture settings must be source integers')
        if not 0 < row['w'] <= 8192 or not 0 < row['h'] <= 8192:
            raise ValueError('Unsupported native texture dimensions')
    for row in plans['atlas-plan.json']['atlases']:
        target(row['target'])
        for member in row['members']:
            asset_path(member['path'])
            guid(member['guid'])
            if not isinstance(member['local'], int) or not member['local']:
                raise ValueError('Exact source sprite local ID required')
    for row in plans.get('dynamic-font-plan.json', {}).get('fonts', []):
        target(row['target'])
        asset_path(row['fontPath'])
        asset_path(row['shaderPath'])
        if not 0 < row['point'] <= 512 or not 0 < row['width'] <= 8192 or not 0 < row['height'] <= 8192:
            raise ValueError('Unsupported source dynamic font dimensions')
    slots = {}
    bindings = plans.get('sampler-source-materials.json', {})
    for sprite in bindings.get('sprites', []):
        asset_path(sprite['sprite'])
        guid(sprite['guid'])
        if type(sprite['local']) is not int or not sprite['local'] or sprite['property'] != 'm_RD.texture':
            raise ValueError('Exact source Sprite identity and texture slot required')
    for row in bindings.get('materials', []) + [dict(r, material=r['sprite']) for r in bindings.get('sprites', [])]:
        asset_path(row['material'])
        asset_path(row['texture'])
        guid(row['textureGuid'])
        if not isinstance(row['allowed'], list) or not row['allowed']:
            raise ValueError('Source-proven current texture identities required')
        for value in row['allowed']:
            guid(value)
        if not isinstance(row['property'], str) or not row['property'] or any(ord(c) < 32 for c in row['property']):
            raise ValueError('Exact source material property required')
        slot = (row['material'], row['property'])
        if slot in slots:
            raise ValueError('Duplicate or conflicting source material texture slot')
        slots[slot] = row['textureGuid']
    out = new_output(args.output, list(files.values()))
    for name, path in files.items():
        (out / name).write_bytes(path.read_bytes())
    helpers = ['VisualAssetReadback', 'SourceTextureBindings'] + (['DynamicFontRecovery'] if args.font_plan else [])
    if getattr(args, 'packable_sprites', False):
        helpers.append('SpriteAtlasRecovery')
    for name in helpers:
        (out / (name + '.cs')).write_bytes(Path(__file__).with_name(name + '.cs.txt').read_bytes())
    result = dict(plans={name: hash_file(path) for name, path in files.items()},
                  nativeScripts=[str(out / (name + '.cs')) for name in helpers],
                  output=str(out), targets=len(targets), nativeReadback='not_run')
    (out / 'handoff.json').write_text(json.dumps(result, indent=2))
    return result
