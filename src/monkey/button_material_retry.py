"""Prepare an Editor adapter for strictly source-proven tiled Button target Images."""
import json
import re
import shutil
import tempfile
from collections import defaultdict
from importlib.resources import files
from pathlib import Path

from . import native
from .export_plan import open_plan, read_import_instruction
from .io import encoded, fail, inside, safe, sha, write_json
from .layout import standard
from .prefab_static_mask_continuation import _component_origins
from .sources.containers import fingerprint

SIDECAR = 'Analysis/Mappings/button-material-projection.json'
PREVIOUS_IMPORTER = 'f634083f43cb061f6ca045b8be2dc5cfceb9287ee432f6d2282dee443aff97fc'


def _unique(rows, key):
    index = {row[key]:row for row in rows}
    if len(index) != len(rows):
        fail('BUTTON_MATERIAL_DUPLICATE', key, 'Repeated source identity')
    return index


def _targets(instruction, plan, root):
    components = _unique(plan['components'], 'sourceId')
    _unique(instruction['components'], 'sourceId')
    nodes = defaultdict(list)
    for c in instruction['components']:
        if c['type'] in ('cc.Sprite','cc.Label','cc.RichText'):
            nodes[c['node']].append(c)
    textures = _unique(instruction['textures'], 'id')
    origins = _component_origins(plan)
    reasons = defaultdict(set)
    for issue in plan.get('diagnostics', []):
        reasons[issue.get('sourceId')].add(issue.get('code'))
    selected = []
    for b in instruction['components']:
        if (b['type'] != 'cc.Button' or not b.get('convertible') or b.get('transition') != 1 or
                not (b.get('staticButtonBinding') or {}).get('renderReady')):
            continue
        target = b.get('target') or b['node']
        graphics = nodes[target]
        if not graphics or any(g.get('convertible') for g in graphics):
            continue
        if len(graphics) != 1:
            fail('BUTTON_MATERIAL_AMBIGUOUS_TARGET', b['sourceId'], 'Expected exactly one source Graphic')
        s = graphics[0]
        if (s['type'] != 'cc.Sprite' or s.get('convertible') is not False or type(s.get('enabled')) is not bool or s.get('mode') != 2 or s.get('trim') is not False or
                s.get('untrimmedGeometryPolicy') != 'identity-full-frame-zero-offset' or len(s.get('materials', [])) != 1):
            fail('BUTTON_MATERIAL_UNSUPPORTED_TARGET', s['sourceId'], 'Expected exact full-frame tiled Sprite and one material')
        for c, fields in ((b,('type','target','node','nativeId','transition','staticButtonBinding')),
                          (s,('type','node','nativeId','mode','trim','enabled','spriteFrame','materials'))):
            if any(c.get(k) != components[c['sourceId']].get(k) for k in fields):
                fail('BUTTON_MATERIAL_PLAN_MISMATCH', c['sourceId'], 'Saved instruction differs from its owning plan')
        origin = s['sourceId']
        while origin in origins:
            origin = origins[origin]
        if ('CUSTOM_MATERIAL_HANDOFF' not in reasons[origin] or
                (reasons[origin] | reasons[s['sourceId']]) - {'CUSTOM_MATERIAL_HANDOFF', 'COMPONENT_HANDOFF'}):
            fail('BUTTON_MATERIAL_OTHER_SOURCE_GAPS', origin, 'Renderer has unproven causes beyond the material handoff')
        base = textures[s['spriteFrame']]
        texture = textures[s['spriteFrame']+'@original']
        if (not all(base[k]==texture[k] for k in ('size','border','offset','originalSize')) or
                base['size'] != base['originalSize'] or base['offset'] != [0,0]):
            fail('BUTTON_MATERIAL_FRAME_GEOMETRY', s['sourceId'], 'Untrimmed Sprite geometry differs')
        meta = inside(root,texture['path']+'.meta').read_text()
        guids = re.findall(r'(?m)^guid: ([a-f0-9]{32})$',meta)
        if len(guids) != 1:
            fail('BUTTON_MATERIAL_TEXTURE_GUID', texture['path'], 'Expected one exact owned texture identity')
        selected.append(dict(buttonId=b['sourceId'],buttonNativeId=b['nativeId'],nodeId=target,
                             spriteId=s['sourceId'],spriteNativeId=s['nativeId'],sourceOriginId=origin,
                             frameId=s['spriteFrame'],texturePath=texture['path'],textureGuid=guids[0],
                             enabled=s['enabled'],materialId=s['materials'][0]))
    if not selected:
        fail('BUTTON_MATERIAL_NO_TARGETS', str(root), 'No unresolved source-backed ColorTint targets')
    return selected


def prepare(candidate, expected_manifest, plan_path, ir_path, output):
    from .prefab_materials import plan_ui_color_for_origins
    from .prefab_material_pipeline import prepare as prepare_material, emit
    root, parent, import_hash = native.source(candidate, expected_manifest)
    plan_path = safe(plan_path)
    ir_path = safe(ir_path)
    out = safe(output)
    for p in (root,plan_path.parent,ir_path.parent):
        if out.exists() or out.is_relative_to(p) or p.is_relative_to(out):
            fail('OUTPUT_OVERLAP',str(out),'Expected a fresh independent retry directory')
    plan, entries, _ = open_plan(plan_path)
    if parent['planSha256'] != entries[plan_path.name]['sha256'] or fingerprint(ir_path) != plan['sourceIrSha256']:
        fail('BUTTON_MATERIAL_PARENT_PIN',str(root),'Source plan or IR does not match original inputs')
    ip = standard.locate(parent,'importPlan')
    instruction, pin = read_import_instruction(root,parent,ip)
    if (pin != import_hash or instruction.get('materialBinding') or
            instruction['sourceManifestSha256'] != plan['sourceManifestSha256']):
        fail('BUTTON_MATERIAL_PARENT_PIN',ip,'Expected a pinned instruction with no installed material profile')
    rows = _targets(instruction,plan,root)
    origin_ids = {r['sourceOriginId'] for r in rows}
    profile = plan_ui_color_for_origins(plan['sourceManifestPath'],ir_path,plan['sourceManifestSha256'],
                                        plan['sourceIrSha256'],sorted(origin_ids))
    spec = profile['spec']
    bindings = _unique(spec['sourceComponentMaterialBindings'],'sourceId')
    if set(bindings) != origin_ids:
        fail('BUTTON_MATERIAL_ORIGINS',str(ir_path),'Source profile did not cover exactly the target origins')
    for row in rows:
        proof = bindings[row['sourceOriginId']]
        if (row['materialId'] != proof['sourceMaterialId'] or
                row['frameId'] != proof['resolvedSpriteFrameSourceId']):
            fail('BUTTON_MATERIAL_SOURCE_ID',row['spriteId'],'Component does not own this material')
    by_sprite = {r['spriteId']:r for r in rows}
    material = dict(spec, sourcePlanSha256=parent['planSha256'], sourceComponentIds=sorted(by_sprite),
                    spriteBindings=[dict(sourceId=sid) for sid in sorted(by_sprite)],
                    sourceComponentMaterialBindings=[dict(bindings[r['sourceOriginId']], sourceId=sid)
                        for sid,r in sorted(by_sprite.items())])
    from .prefab_materials import _validate_binding_spec
    _validate_binding_spec(material)
    projection = dict(schema='monkey-button-material-projection/1',parentManifestSha256=expected_manifest,
                      importPlanSha256=import_hash,sourceManifestSha256=plan['sourceManifestSha256'],
                      sourceIrSha256=plan['sourceIrSha256'],rows=rows,material=material)
    raw = encoded(projection)
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as temporary:
        temp = Path(temporary)
        derived = temp/'candidate'
        shutil.copytree(root,derived)
        native.source(derived,expected_manifest)
        owned = _unique(parent['files'],'path')
        importer = standard.locate(parent,'importer')
        templates = files('monkey.targets')
        importer_raw = templates.joinpath('UnityImporter.cs').read_bytes()
        if owned[importer]['sha256'] not in {PREVIOUS_IMPORTER,sha(importer_raw)}:
            fail('BUTTON_MATERIAL_IMPORTER_VERSION',importer,'Unrecognized base adapter')
        adapter_path = str(Path(importer).with_name('UnityButtonMaterialProjection.cs'))
        adapter = templates.joinpath('UnityButtonMaterialProjection.cs').read_text()
        if adapter.count('__MONKEY_PROJECTION_SHA256__') != 1:
            raise ValueError('Invalid material adapter template')
        owned_payloads = prepare_material(profile,'unity',temp)
        additions = [r['target'] for r in owned_payloads['payloads']]+[SIDECAR,adapter_path]
        if any(inside(derived,p).exists() for p in additions) or inside(derived,spec['materialPath']).exists():
            fail('BUTTON_MATERIAL_OUTPUT_COLLISION',str(derived),'Original candidate already owns projected output')
        emit(owned_payloads,temp,derived)
        inside(derived,importer).write_bytes(importer_raw)
        inside(derived,adapter_path).write_text(adapter.replace('__MONKEY_PROJECTION_SHA256__',sha(raw)))
        inside(derived,SIDECAR).write_bytes(raw)
        for name in [importer,*additions]:
            p=inside(derived,name)
            owned[name]=dict(path=name,owner='generated',bytes=p.stat().st_size,sha256=fingerprint(p))
        updated=dict(parent,files=[owned[k] for k in sorted(owned)],buttonMaterialProjection=dict(
            parentManifestSha256=expected_manifest,path=SIDECAR,sha256=sha(raw)))
        write_json(derived/'manifest.json',updated)
        new_pin=fingerprint(derived/'manifest.json')
        _,_,new_plan=native.source(derived,new_pin)
        if new_plan!=import_hash or out.exists():
            fail('BUTTON_MATERIAL_PUBLICATION',str(out),'Instruction changed or destination exists')
        derived.rename(out)
    return dict(status='prepared',candidate=str(out),manifestSha256=new_pin,importPlanSha256=import_hash,
                sourceOrigins=len(origin_ids),buttons=len(rows),editor='not_run')


def projected_instruction(root, manifest, instruction, instruction_sha):
    """Reconcile the expected Renderer set with the same manifest-owned adapter input."""
    from .io import load, read
    from .prefab_materials import _validate_binding_spec
    meta = manifest.get('buttonMaterialProjection')
    if meta is None:
        return instruction
    if meta.get('path') != SIDECAR:
        fail('BUTTON_MATERIAL_PROJECTION_PATH', str(root), 'Unexpected adapter input')
    entries = [r for r in manifest['files'] if r['path'] == SIDECAR]
    raw = read(inside(root,SIDECAR))
    if len(entries) != 1 or entries[0]['sha256'] != sha(raw) or meta.get('sha256') != sha(raw):
        fail('BUTTON_MATERIAL_PROJECTION_PIN', SIDECAR, 'Adapter input fingerprint differs')
    sidecar = load(raw)
    if (sidecar.get('schema') != 'monkey-button-material-projection/1' or
            sidecar.get('importPlanSha256') != instruction_sha or
            sidecar.get('sourceManifestSha256') != instruction['sourceManifestSha256'] or
            sidecar.get('parentManifestSha256') != meta.get('parentManifestSha256') or instruction.get('materialBinding')):
        fail('BUTTON_MATERIAL_PROJECTION_INPUT',SIDECAR,'Adapter is not bound to the original instruction')
    spec = sidecar['material']
    _validate_binding_spec(spec)
    components = _unique(instruction['components'],'sourceId')
    targets = _unique(sidecar['rows'],'buttonId')
    sprites = {r['spriteId']:r for r in targets.values()}
    bindings = _unique(spec['sourceComponentMaterialBindings'],'sourceId')
    if not sprites or set(sprites)!=set(bindings):
        fail('BUTTON_MATERIAL_PROJECTION_BINDINGS',SIDECAR,'Adapter binding denominator differs')
    for row in targets.values():
        sprite = components[row['spriteId']]
        button = components[row['buttonId']]
        proof = bindings[row['spriteId']]
        if (sprite['type']!='cc.Sprite' or sprite['convertible'] or sprite['node']!=row['nodeId'] or
                sprite['nativeId']!=row['spriteNativeId'] or sprite['materials']!=[row['materialId']] or
                sprite['spriteFrame']!=row['frameId'] or proof['sourceMaterialId']!=row['materialId'] or
                proof['sourceOriginId']!=row['sourceOriginId'] or proof['resolvedSpriteFrameSourceId']!=row['frameId'] or
                button['type']!='cc.Button' or (button.get('target') or button['node'])!=row['nodeId'] or button['nativeId']!=row['buttonNativeId']):
            fail('BUTTON_MATERIAL_PROJECTION_RELATION',row['buttonId'],'Saved source and adapter relation differs')
    return dict(instruction, materialBinding=spec, components=[
        dict(c,convertible=True,nativeMaterialSourceId=sprites[c['sourceId']]['materialId'])
        if c['sourceId'] in sprites else c for c in instruction['components']])
