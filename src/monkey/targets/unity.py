"""Python plans and assembles a native Unity Editor import candidate."""
from importlib.resources import files
from pathlib import Path
import uuid
import re
from .. import __version__
from ..io import safe, inside, read, load, sha, encoded, new_output, finish, write_json, diagnostic, stage_document, stage_bytes, stage_manifest
from ..sources.compiled import fail
from ..layout import standard
from ..layout.standard import VERSION
from ..layout.standard import find_analysis

PROFILE = 'unity-6000.6.2f1-ugui'


def guid(namespace, identity):
    return uuid.uuid5(uuid.NAMESPACE_URL, 'monkey/'+namespace+'/'+identity).hex


def widget_geometry_matches(widget, node, parent):
    if parent is None:
        return False
    left,bottom,right,top=widget['margins']
    size=[parent['size'][0]-left-right,parent['size'][1]-bottom-top]
    position=[left+node['anchor'][0]*size[0]-parent['anchor'][0]*parent['size'][0],
              bottom+node['anchor'][1]*size[1]-parent['anchor'][1]*parent['size'][1]]
    return (all(abs(a-b)<.001 for a,b in zip(size,node['size'])) and
            all(abs(a-b)<.001 for a,b in zip(position,node['position'])))


def layout_issues(layout,children):
    issues=[]
    if layout['layoutType']not in(1,2,3)or layout['resize']not in(0,1,2)or any(v!=int(v)for v in layout['padding']):
        issues.append(('LAYOUT_SUBSET_UNSUPPORTED','Native linear/flow layout requires known modes and integer padding'))
    if layout['layoutType']in(1,2)and any(any(v<0 for v in n['scale'][:2])for n in children):
        issues.append(('LAYOUT_NEGATIVE_SCALE_PENDING','Negative-scale linear pivots need a separate native bounds contract'))
    if layout['layoutType']==3 and(layout['startAxis']not in(0,1)or layout.get('constraint',0)not in(0,1,2)or type(layout.get('constraintCount',2))is not int or layout.get('constraintCount',2)<1):
        issues.append(('GRID_SUBSET_UNSUPPORTED','Unknown flow axis or row/column constraint'))
    if layout['resize']==2 and layout.get('affectedByScale')and any(0 in n['scale'][:2]for n in children):
        issues.append(('LAYOUT_ZERO_SCALE_PENDING','Child resizing cannot divide by a zero effective scale'))
    return issues


def grid_native_extent(layout,parent,children):
    import math
    children=[n for n in children if n['active']]
    if not children:return None,'EMPTY_LAYOUT_HANDOFF'
    if any(n['scale'][:2]!=[1,1] for n in children):return None,'GRID_SCALED_CHILD_HANDOFF'
    width,height=children[0]['size'];spacing_x,spacing_y=layout['spacingXY']
    if width<=0 or height<=0 or width+spacing_x<=0:return None,'GRID_CELL_GEOMETRY_HANDOFF'
    left,bottom,right,top=layout['padding']
    columns=max(1,math.floor((parent['size'][0]-left-right+spacing_x+.001)/(width+spacing_x)))
    rows=math.ceil(len(children)/columns)
    extent=bottom+top+height*rows+spacing_y*(rows-1)
    if abs(extent-parent['size'][1])>.001:return None,'GRID_CACHED_CONTAINER_HANDOFF'
    return extent,None


def linear_container_matches(layout, parent, children):
    axis=0 if layout['layoutType']==1 else 1
    children=[child for child in children if child['active']]
    before,after=((layout['padding'][0],layout['padding'][2]) if axis==0 else (layout['padding'][1],layout['padding'][3]))
    extent=before+after+sum(child['size'][axis] for child in children)+max(0,len(children)-1)*layout['spacingXY'][axis]
    return abs(extent-parent['size'][axis])<.001


def cross_axis_mapping(layout, parent, children):
    # Creator linear layouts leave the other axis untouched. uGUI drives both axes;
    # only a shared, representable alignment is safe to emit as a standard group.
    axis = 1 if layout['layoutType'] == 1 else 0
    children = [child for child in children if child['active']]
    before, after = ((layout['padding'][1], layout['padding'][3]) if axis == 1
                     else (layout['padding'][0], layout['padding'][2]))
    extent = parent['size'][axis]
    for scaled in (False, True):
        if scaled and any(child['scale'][axis] <= 0 for child in children):
            continue
        for alignment in (.5, 0., 1.):
            def matches(child):
                size = child['size'][axis] * (child['scale'][axis] if scaled else 1.)
                position = (-parent['anchor'][axis] * extent + before
                            + (extent - before - after - size) * alignment
                            + child['anchor'][axis] * size)
                return abs(position - child['position'][axis]) < .001
            if all(matches(child) for child in children):
                return dict(crossAxisScale=scaled, crossAxisAlignment=alignment)
    return None


def untrimmed_frames(ir):
    if ir.get('previewResourceSelection'):
        return {f['sourceId']for f in ir['spriteFrames']}
    """Untrimmed sprite variants exist only for Sprites that reference them (PROJECT-SPEC 5.4)."""
    aliases=ir.get('aliases',{})
    def resolve(value):
        seen=set()
        while value in aliases and value not in seen:seen.add(value);value=aliases[value]
        return value
    return {resolve(c['spriteFrame']) for c in ir['components'] if c['type']=='cc.Sprite' and c.get('spriteFrame') and c.get('trim',True) is False}


def plan(ir_path, namespace, output, bindings_path=None,animation_selection=None,layout=None,system_font_resolution=None,expected_system_font_resolution=None,static_font_generation=None,expected_static_font_generation=None,static_source_bundle=None,expected_static_source_bundle=None):
    ir_path = safe(ir_path)
    ir = stage_document(ir_path)
    if ir.get('schemaVersion') != 1 or ir.get('sourceProfile') not in ('cocos-2.4.15-bundle','cocos-2.4.15-project','cocos-3.8.7-bundle','cocos-3.4.1-bundle','cocos-2.4.11-bundle','cocos-2.1.2-resource','generic-image-resources-v1','egret-custom-resource-plist-v1'):
        fail('UNSUPPORTED_IR', '$', 'Expected normalize schema 1')
    from ..prefab_static_pipeline import ensure_static_fields
    ensure_static_fields(ir)
    from ..prefab_richtext_pipeline import enrich as enrich_richtext
    enrich_richtext(ir)
    from ..prefab_static_button import enrich as enrich_buttons
    enrich_buttons(ir)
    from ..prefab_static_pipeline import enrich_declarations
    enrich_declarations(ir,static_source_bundle,expected_static_source_bundle)
    source_files = stage_manifest(ir_path.parent)['files']
    expected = {f['path']: f['sha256'] for f in source_files}
    diagnostics = list(ir['diagnostics'])
    for node in ir['nodes']:
        if node.get('sourceUITransformEnabled')is False:
            diagnostics.append(dict(code='SOURCE_UI_TRANSFORM_LIFECYCLE_UNSUPPORTED',sourceId=node['sourceId'],severity='warning',message='Source disabled UITransform geometry is retained; Unity RectTransform has no enabled state and source parent-change listener lifecycle needs manual review'))
    binding_receipt=None;label_bindings={}
    if bindings_path:
        raw=read(bindings_path);binding=load(raw)
        if binding.get('sourceManifestSha256')!=ir['sourceManifestSha256']:
            fail('BINDING_SOURCE_MISMATCH',str(bindings_path),'Binding targets a different source manifest')
        evidence={x['sha256']:x for x in ir.get('evidenceFiles',[])}
        if binding.get('evidenceSha256') not in evidence:
            fail('BINDING_EVIDENCE_MISSING',str(bindings_path),'Explicit inspect evidence hash is required')
        offset,length=binding.get('offset'),binding.get('bytes')
        if type(offset) is not int or type(length) is not int or offset<0 or length<=0 or offset+length>evidence[binding['evidenceSha256']]['bytes']:
            fail('BINDING_EVIDENCE_RANGE',str(bindings_path),'Evidence byte range is invalid')
        for item in binding.get('labelFonts',[]):
            if type(item.get('syntheticBold',False)) is not bool or not isinstance(item.get('font'),str):
                fail('INVALID_FONT_BINDING',str(bindings_path),'Font identity and syntheticBold must be typed')
            if item['component'] in label_bindings:fail('DUPLICATE_BINDING',item['component'],'Duplicate component binding')
            label_bindings[item['component']]=item
        known_ids={c['sourceId'] for c in ir['components'] if c['type']=='cc.Label'}
        if set(label_bindings)-known_ids:fail('UNKNOWN_BINDING_COMPONENT',str(bindings_path),'Binding references unknown Label')
        binding_receipt=dict(sha256=sha(raw),**binding)
        diagnostics=[d for d in diagnostics if not (d.get('sourceId') in label_bindings and d['message'].startswith('system font requires'))]
    from ..layout import LayoutPlanner
    overrides,overrides_sha=layout or ({},None)
    naming=LayoutPlanner('unity',ir.get('sourceNames'),overrides)
    untrimmed=untrimmed_frames(ir);suffix=lambda relative:Path(relative).suffix.lower()
    naming.reserve([(f['sourceId'],'sprite',suffix(f['image']),'',None,None) for f in ir['spriteFrames']]
        +[(f['sourceId']+'@original','sprite',suffix(f['originalImage']),'',None,None) for f in ir['spriteFrames'] if f['sourceId'] in untrimmed]
        +[(a['sourceId'],a['kind'],suffix(a['path']),'',None,None) for a in ir['assets']]
        +[(a['sourceId'],'font-asset','.asset','',None,None) for a in ir['assets'] if a['kind']=='cc.TTFFont']
        +[r for f in ir.get('bitmapFonts',[]) for r in ((f['sourceId']+'@atlas','bitmap-atlas',suffix(f['atlasImage']),'',None,None),(f['sourceId'],'font-asset','.asset','',None,None))])
    textures, copies = [], []
    def resource(relative, identity, role, kind):
        source = inside(ir_path.parent, relative)
        if relative not in expected or sha(read(source)) != expected[relative]:
            fail('SOURCE_CHANGED', relative, 'Normalized asset differs from output manifest')
        target = naming.path(identity,kind,source.suffix.lower())
        copies.append(dict(source=relative,target=target,sha256=expected[relative],sourceId=identity,role=role,
                           guid=guid(namespace,identity)))
        return target
    for frame in ir['spriteFrames']:
        sid = frame['sourceId']
        left,top,right,bottom = frame['capInsets']
        textures.append(dict(id=sid, path=resource(frame['image'],sid,'sprite','sprite'),
                             border=[left,bottom,right,top], size=frame['rect'][2:4],
                             originalSize=frame['originalSize'],offset=frame['offset']))
        if sid in untrimmed:
            textures.append(dict(id=sid+'@original',path=resource(frame['originalImage'],sid+'@original','sprite','sprite'),
                                 border=[left,bottom,right,top] if frame['rect'][2:4]==frame['originalSize'] and all(v==0 for v in frame['offset']) else [0,0,0,0],
                                 size=frame['originalSize'],originalSize=frame['originalSize'],offset=[0,0]))
    assets=[]
    for asset in ir['assets']:
        item=dict(id=asset['sourceId'],kind=asset['kind'],path=resource(asset['path'],asset['sourceId'],'native',asset['kind']),fontCoverage=asset.get('fontCoverage'))
        if asset['kind']=='cc.TTFFont':item['fontAssetPath']=naming.path(asset['sourceId'],'font-asset','.asset')
        assets.append(item)
    bitmap_fonts=[]
    for font in ir.get('bitmapFonts',[]):
        item={k:v for k,v in font.items() if k!='atlasImage'}
        item['id']=font['sourceId']
        item['atlasGuid']=guid(namespace,font['sourceId']+'@atlas')
        item['path']=resource(font['atlasImage'],font['sourceId']+'@atlas','bitmap-atlas','bitmap-atlas')
        item['fontPath']=naming.path(font['sourceId'],'font-asset','.asset')
        bitmap_fonts.append(item)
    resource_ids = {a['id'] for a in assets if a['kind']=='cc.TTFFont'}|{f['id'] for f in bitmap_fonts}
    system_font_binding=None;system_label_bindings={}
    if bool(system_font_resolution)!=bool(expected_system_font_resolution):
        fail('SYSTEM_FONT_RECEIPT_PIN_REQUIRED',str(ir_path),'Resolution receipt and expected SHA must be supplied together')
    if system_font_resolution:
        from ..prefab_system_fonts import prepare as prepare_system_fonts
        prepared=prepare_system_fonts(ir,sha(stage_bytes(ir_path)),system_font_resolution,expected_system_font_resolution)
        if prepared.status!='prepared':fail('SYSTEM_FONT_BINDING_NOT_READY',str(system_font_resolution),prepared.record.get('reason','Invalid font receipt'))
        system_font_binding=prepared.record
        system_label_bindings={b['sourceLabelId']:b for b in prepared.record['labelBindings']}
        if set(system_label_bindings)&set(label_bindings):fail('SYSTEM_FONT_BINDING_CONFLICT',str(ir_path),'Multiple font policies target the same Label')
        resource_ids.update(f['assetId']for f in prepared.record['systemFonts']['fonts'])
    sprite_ids = {s['id'] for s in textures}
    nodes = ir['nodes']
    node_ids = {n['sourceId'] for n in nodes}
    if len(node_ids) != len(nodes):
        fail('DUPLICATE_NODE','$','Duplicate node identities')
    by_node={n['sourceId']:n for n in nodes}
    for n in nodes:
        if len(n['children'])!=len(set(n['children'])):
            fail('INVALID_NODE_GRAPH',n['sourceId'],'Duplicate child reference')
        for child in n['children']:
            if child not in by_node or by_node[child]['parent']!=n['sourceId']:
                fail('INVALID_NODE_GRAPH',n['sourceId'],'Child missing or parent does not agree')
        if n['parent'] in by_node and n['sourceId'] not in by_node[n['parent']]['children']:
            fail('INVALID_NODE_GRAPH',n['sourceId'],'Parent does not list child')
        if n['parent'] and n['parent'] not in node_ids:
            diagnostics.append(diagnostic('MISSING_PARENT',n['sourceId'],'Parent not present in IR',n['sourceId']))
        if n['size'][0] <= 0 or n['size'][1] <= 0:
            diagnostics.append(diagnostic('ZERO_SIZE_NODE',n['sourceId'],'Node needs visibility/layout review',n['sourceId']))
        seen=set();cursor=n
        while cursor.get('parent') in node_ids:
            if cursor['sourceId'] in seen:
                fail('NODE_CYCLE',n['sourceId'],'Parent cycle')
            seen.add(cursor['sourceId']);cursor=next(v for v in nodes if v['sourceId']==cursor['parent'])
    native_types={'cc.Sprite','cc.Label','cc.Widget','cc.Mask','cc.ScrollView','cc.Layout','cc.Button','cc.BlockInputEvents','cc.LabelOutline','cc.ProgressBar'}
    native_materials={f['sourceId'] for f in ir.get('materials',[]) if f['nativeRole']=='standard-ugui'}
    from .. import prefab_material_pipeline as material_pipeline
    material_profile,material_gaps=material_pipeline.discover(ir,ir_path)
    diagnostics.extend(material_gaps)
    def resolve_id(value):
        seen=set()
        while value in ir.get('aliases',{}):
            if value in seen:fail('REDIRECT_CYCLE',value,'IR alias cycle')
            seen.add(value);value=ir['aliases'][value]
        return value
    components=[]
    for c in ir['components']:
        entry=dict(c)
        if c['sourceId'] in system_label_bindings:
            bind=system_label_bindings[c['sourceId']]
            entry.update(sourceFont=c.get('font'),font=bind['nativeFontAssetId'],nativeSystemFontBinding=bind)
            diagnostics.append(diagnostic('SYSTEM_FONT_PLATFORM_UNVERIFIED',c['sourceId'],'Explicit macOS font resolution; source OS and visual equivalence remain unverified',c['sourceId']))
        if c['sourceId'] in label_bindings:
            bind=label_bindings[c['sourceId']]
            if c.get('font') is not None:fail('BINDING_REPLACES_EXPLICIT_FONT',c['sourceId'],'Only absent system-font references may be source-bound')
            entry['font']=bind['font']
            entry['bold']=bind.get('syntheticBold',False)
        for field in ('spriteFrame','font'):
            value=entry.get(field);seen=set()
            while value in ir.get('aliases',{}):
                if value in seen:fail('REDIRECT_CYCLE',value,'IR alias cycle')
                seen.add(value);value=ir['aliases'][value]
            if field in entry:entry[field]=value
        c=entry
        entry['convertible']=c['type'] in native_types and c['node'] in node_ids
        entry['nativeId']=guid(namespace,c['sourceId'])
        from ..prefab_target_behaviors import binding as behavior_binding
        native_behavior=behavior_binding(c,'unity',namespace)
        if native_behavior is not None:
            entry.update(behaviorBinding=native_behavior,nativeType=native_behavior['typeName'],
                         convertible=c['node'] in node_ids and not c.get('materials'))
            diagnostics.append(diagnostic('BEHAVIOR_RUNTIME_UNVERIFIED',c['sourceId'],'Source-bound native script/fields; behavioral gaps and runtime checks remain',c['sourceId']))
            components.append(entry);continue
        if c.get('supported') is False:
            entry['convertible']=False
            diagnostics.append(diagnostic('SOURCE_COMPONENT_PROFILE_HANDOFF',c['sourceId'],'Source component semantics are not implemented for this profile',c['sourceId']))
            components.append(entry);continue

        if material_pipeline.supported_component(c,material_profile,resolve_id):
            entry['nativeMaterialSourceId']=material_profile['spec']['materialSourceId']
        elif material_pipeline.identity_text_component(c,material_profile,resolve_id):
            entry['nativeTextMaterialIdentitySourceId']=material_profile['spec']['materialSourceId']
            entry['nativeTextMaterialPolicy']='source-proven-identity-default-only'
        elif any(resolve_id(mat) not in native_materials for mat in c.get('materials',[])):
            entry['convertible']=False
            diagnostics.append(diagnostic('CUSTOM_MATERIAL_HANDOFF',c['sourceId'],'Material is not recognized standard UI texture',c['sourceId']))
        if c['type']=='cc.Sprite':
            if c.get('spriteFrame') is not None and c.get('spriteFrame') not in sprite_ids or c['mode'] not in (0,1,2):
                entry['convertible']=False
                diagnostics.append(diagnostic('SPRITE_NOT_CONVERTIBLE',c['sourceId'],'Missing frame or unsupported mode',c['sourceId']))
            if c.get('spriteFrame') is None:
                entry['needsSpriteBinding']=True
                diagnostics.append(diagnostic('SOURCE_SPRITE_UNBOUND',c['sourceId'],'Source Sprite has no frame; native Image is disabled until AI binds an actual Sprite and enables it',c['sourceId']))
            frame=next((t for t in textures if t['id']==c.get('spriteFrame')),None)
            untrimmed_identity=bool(frame and frame['size']==frame['originalSize'] and frame['offset']==[0,0])
            if not c.get('trim',True) and c['mode'] in (1,2) and untrimmed_identity:
                entry['untrimmedGeometryPolicy']='identity-full-frame-zero-offset'
            if not c.get('trim',True) and c['mode'] in (1,2) and not untrimmed_identity:
                entry['convertible']=False
                diagnostics.append(diagnostic('SLICED_UNTRIMMED_UNSUPPORTED',c['sourceId'],'Needs Cocos size-mode evidence',c['sourceId']))
        elif c['type']=='cc.Label':
            entry['nativeTextStylePolicy']='tmp-font-style-flags-v1'
            if c.get('font') not in resource_ids:
                entry['convertible']=False
                diagnostics.append(diagnostic('FONT_NOT_CONVERTIBLE',c['sourceId'],'No imported matching font; no fallback text',c['sourceId']))
            ttf=next((a for a in assets if a['id']==c.get('font') and a.get('fontCoverage')),None)
            if ttf:
                from ..assets.ttf import missing
                absent=missing(ttf['fontCoverage'],c['text'])
                if absent:
                    entry['convertible']=False
                    diagnostics.append(diagnostic('SOURCE_FONT_GLYPHS_MISSING',c['sourceId'],'Original TTF lacks codepoints: '+str(absent),c['sourceId']))
            font=next((f for f in bitmap_fonts if f['id']==c.get('font')),None)
            entry['bitmapLabel']=bool(font)
            if font:
                from ..assets.bitmap import single_line
                try:
                    entry['sourceBold']=entry.get('bold',False)
                    entry['bold']=False
                    entry['bitmapProbe']=single_line(font,c['text'],c['fontSize'],c.get('spacing',0))
                    codepoints=list(map(ord,c['text']))
                    actual_pairs={(codepoints[i],codepoints[i+1]) for i in range(len(codepoints)-1)}
                    if c['fontSize']!=font['pointSize'] and any((k['first'],k['second']) in actual_pairs and k['advance'] for k in font['kernings']):
                        fail('BITMAP_KERNING_SCALE_UNSUPPORTED',c['sourceId'],'Source pair offsets are unscaled, native TMP scales font features; this text needs a reviewed font variant')
                except ValueError as error:
                    entry['convertible']=False
                    diagnostics.append(diagnostic(getattr(error,'code','BITMAP_LAYOUT_UNSUPPORTED'),c['sourceId'],str(error),c['sourceId']))
            if c.get('overflow')not in(0,1,2,3):entry['convertible']=False
            entry['presentationPolicy']='native-tmp-sizing-v1'
            diagnostics.append(diagnostic('LABEL_METRICS_NOT_VERIFIED',c['sourceId'],'TMP line metrics need engine/reference comparison',c['sourceId']))
        elif c['type']=='cc.Widget':
            node=by_node.get(c['node'],{})
            entry.setdefault('center',[0,0]);entry.setdefault('centerAbsolute',[True,True])
            flags=c['flags'];horizontal=flags&56;vertical=flags&7
            invalid=(flags&~63 or horizontal in(24,48,56)or vertical in(3,6,7)or c.get('alignMode',1)not in(0,1,2))
            if invalid or c.get('target')not in(None,node.get('parent'))or node.get('scale',[1,1])[:2]!=[1,1]or node.get('rotation')!=[0,0,0,1]:
                entry['convertible']=False
                diagnostics.append(diagnostic('WIDGET_CONTEXT_UNSUPPORTED',c['sourceId'],'Requires parent-relative target, valid edge/center flags and unrotated unit-scale node',c['sourceId']))
            if flags and node.get('parent')not in by_node:
                entry['externalParentContext']='candidate-design-root'
                diagnostics.append(diagnostic('WIDGET_EXTERNAL_PARENT_CONTEXT',c['sourceId'],'Prefab root keeps native constraints for its future parent; the candidate Scene uses its declared design root, not a recovered original game viewport',c['sourceId']))
            entry['presentationPolicy']='native-rect-constraints-v1'
        elif c['type']=='cc.Mask':
            if c['maskType']!=0 or c['inverted']:
                entry['convertible']=False
                diagnostics.append(diagnostic('MASK_SUBSET_UNSUPPORTED',c['sourceId'],'Only non-inverted rectangular mask supported',c['sourceId']))
        elif c['type']=='cc.ScrollView':
            if c['content'] not in node_ids or by_node[c['content']].get('parent') not in node_ids:
                entry['convertible']=False
                diagnostics.append(diagnostic('SCROLL_SUBSET_UNSUPPORTED',c['sourceId'],'Native content and viewport must both resolve',c['sourceId']))
            entry['staticNativeBinding']=True;entry['dynamicScrollingVerified']=False
            diagnostics.append(diagnostic('SCROLL_PHYSICS_NOT_VERIFIED',c['sourceId'],'Native axes/content/viewport retained for static recovery; drag and inertia remain unverified',c['sourceId']))
        elif c['type']=='cc.Layout':
            children=[by_node[k]for k in by_node[c['node']]['children']]
            for code,message in layout_issues(c,children):
                entry['convertible']=False;diagnostics.append(diagnostic(code,c['sourceId'],message,c['sourceId']))
            entry.setdefault('alignCross',False);entry.setdefault('affectedByScale',False)
            entry['presentationPolicy']='unity-layout-components-v2'if c['layoutType']==3 else'native-linear-layout-v1'
            if c['layoutType']==3 and entry['convertible']:
                from ..native_layout_patch import classify
                try:
                    choice=classify(c,by_node[c['node']],children,c['cellSize']if c.get('cellSizeFromSource')else None)
                    entry['nativeLayoutMode']=choice['mode'];entry['nativeCellSize']=choice['cellSize']or[]
                except ValueError as error:
                    entry['convertible']=False
                    diagnostics.append(diagnostic('NATIVE_GRID_REVIEW_REQUIRED',c['sourceId'],'Authored rectangles retained; no source layout runtime emitted: '+str(error),c['sourceId']))
        elif c['type']=='cc.Button':
            static_color=c.get('staticButtonBinding',{}).get('renderReady') and c.get('target') in (node_ids|{None})
            if not static_color and (c['transition'] not in (0,3) or c['target'] not in (None,c['node'])):
                entry['convertible']=False
                diagnostics.append(diagnostic('BUTTON_SUBSET_UNSUPPORTED',c['sourceId'],'Only self-targeted none/scale transitions supported',c['sourceId']))
            if c['events']:
                diagnostics.append(diagnostic('BUTTON_BUSINESS_UNBOUND',c['sourceId'],'Native Button generated; original handlers remain AI work: '+','.join(e.get('handler') or '?' for e in c['events']),c['sourceId']))
        elif c['type']=='cc.LabelOutline':
            label=next((x for x in ir['components'] if x['node']==c['node'] and x['type']=='cc.Label'),None)
            if not label:entry['convertible']=False
            diagnostics.append(diagnostic('OUTLINE_METRICS_NOT_VERIFIED',c['sourceId'],'Bitmap outline is baked; TTF outline width needs actual pixel comparison',c['sourceId']))
        if not entry['convertible']:
            diagnostics.append(diagnostic('COMPONENT_HANDOFF',c['sourceId'],'Native mapping unavailable for '+str(c['type']),c['sourceId']))
        components.append(entry)
    for c in components:
        if c['type']=='cc.LabelOutline' and c['convertible'] and not any(x['type']=='cc.Label' and x['node']==c['node'] and x['convertible'] for x in components):
            c['convertible']=False
            diagnostics.append(diagnostic('MISSING_OUTLINE_LABEL',c['sourceId'],'Label dependency could not be converted',c['sourceId']))
    # Editor-created controllers/materials are named by owning prefab module and node, never by GUID (PROJECT-SPEC 5.5).
    def owned(component,tail):
        asset=component['node'].split('#',1)[0];meta=dict(ir.get('sourceNames',{}).get(asset,{}))
        logical=meta.get('logicalPath') or '';parent,_,owner=logical.rpartition('/')
        meta.update(sourceId=component['sourceId'],logicalPath=(parent+'/' if parent else '')+str(by_node.get(component['node'],{}).get('name') or 'node')+tail)
        return meta,owner or None
    native_assets=[(c,'controller','.controller','_button') if c['type']=='cc.Button' else (c,'material','.mat','_outline') for c in components
                   if c['convertible'] and (c['type']=='cc.Button' and c.get('transition')==3 or c['type']=='cc.LabelOutline')]
    naming.reserve([(c['sourceId'],kind,suffix,'',*owned(c,tail)) for c,kind,suffix,tail in native_assets])
    for c,kind,suffix,tail in native_assets:
        c['controllerPath' if kind=='controller' else 'materialPath']=naming.path(c['sourceId'],kind,suffix,metadata=owned(c,tail)[0])
        if kind=='controller':
            for state in ('normal','pressed'):
                c[state+'ClipPath']=naming.derived_path(c['sourceId']+'@'+state,c['controllerPath'],'_'+state,'.anim')
    from .common import reject_layout_conflicts
    diagnostics.extend(reject_layout_conflicts(components))
    from .progress import configure_progress
    diagnostics.extend(configure_progress(components,by_node))
    from ..assets.animation import plan_clips
    animations,animation_gaps=plan_clips(ir,namespace,PROFILE,animation_selection,naming)
    if animation_selection:
        unselected={c['sourceId'] for c in ir.get('animationClips',[]) if c['sourceId'] not in animation_selection}
        diagnostics=[d for d in diagnostics if d.get('sourceId') not in unselected]
    diagnostics.extend(animation_gaps)
    from .prefabs import plan_prefabs
    source_prefabs,prefab_gaps=plan_prefabs(ir,components)
    from .prefabs import native_relationships
    source_prefabs,prefab_instances=native_relationships(ir,source_prefabs,components)
    naming.reserve([(prefab['sourceId'],'prefab','.prefab','',None,None) for prefab in source_prefabs])
    for prefab in source_prefabs:prefab['path']=naming.path(prefab['sourceId'],'prefab','.prefab')
    diagnostics.extend(prefab_gaps)
    out = new_output(output,[ir_path.parent])
    static_font_inputs=None
    if bool(static_font_generation)!=bool(expected_static_font_generation):
        fail('STATIC_FONT_INPUTS_PAIR','fonts','Generation receipt and expected SHA are required together')
    if static_font_generation:
        if not system_font_binding:fail('STATIC_FONT_RESOLUTION_REQUIRED','fonts','Static inputs require an explicit resolved font binding')
        from ..prefab_system_fonts import prepare_static_inputs
        staged=prepare_static_inputs(static_font_generation,expected_static_font_generation,system_font_binding,out)
        if staged.status!='staged':fail('STATIC_FONT_INPUTS_INVALID','fonts',staged.record.get('reason','Staging failed'))
        static_font_inputs=staged.record
    elif system_font_binding and any(f.get('populationMode')=='StaticSDFRequired'for f in system_font_binding['systemFonts']['fonts']):
        fail('STATIC_FONT_INPUTS_REQUIRED','fonts','Resolved static face requires an explicit pinned generation receipt')
    (out/'resources').mkdir()
    for copy in copies:
        target = out/'resources'/(sha(copy['target'].encode())[:24]+Path(copy['target']).suffix)
        target.write_bytes(read(inside(ir_path.parent,copy['source'])))
        copy['source']='resources/'+target.name
    from .common import native_color_nodes
    nodes=native_color_nodes(nodes,components)
    for node in nodes:
        if node.get('sourceGeometryProfile'):
            diagnostics.append(diagnostic('COCOS3_UNITY_LAYER_HANDOFF',node['sourceId'],'Original layer bits retained as provenance; native uGUI uses target UI layer 5, source camera visibility is pending',node['sourceId']))
    from ..prefab_target_behaviors import prepare as prepare_behaviors
    behavior_scripts=prepare_behaviors(ir,ir_path.parent,'unity',namespace,out)
    from ..prefab_static_carriers import prepare as prepare_static
    static_fields=prepare_static([c for c in components if c.get('staticFieldSnapshot')], 'unity', 'Monkey.StaticFields.N'+sha(namespace.encode())[:12], out)
    for c in components:
        if c['sourceId'] in static_fields['bindings']:c['staticFieldBinding']=static_fields['bindings'][c['sourceId']]

    material_binding=material_pipeline.prepare(material_profile,'unity',out)
    if material_binding:
        material_binding['spec']['spriteBindings']=[dict(sourceId=c['sourceId'])for c in components if c.get('convertible')and c.get('nativeMaterialSourceId')]
    result=dict(schemaVersion=1,toolVersion=__version__,targetProfile=PROFILE,namespace=namespace,projectLayout=VERSION,layoutOverridesSha256=overrides_sha,
                staticFieldScripts=static_fields['scripts'],behaviorScripts=behavior_scripts,systemFontBinding=system_font_binding,staticFontInputs=static_font_inputs,materialBinding=material_binding,
                sourcePrefabs=source_prefabs,prefabInstances=prefab_instances,naming=naming.report(),
                scopeMode=ir.get('scopeMode','asset-selection'),
                sourceIrSha256=sha(stage_bytes(ir_path)),sourceManifestPath=ir.get('sourceManifestPath'),sourceManifestSha256=ir['sourceManifestSha256'],
                sourceRoots=ir.get('sourceRoots',{}),sourceLocations=ir.get('sourceLocations',{}),designSize=[750,1334],pixelsPerUnit=100,
                textures=textures,assets=assets,bitmapFonts=bitmap_fonts,animations=animations,bindings=binding_receipt,nodes=nodes,components=components,copies=copies,
                diagnostics=diagnostics,galleryOnly=not bool(nodes),editorValidation='not_run')
    if any(c['type']in('cc.Toggle','cc.ToggleContainer')for c in components):
        from ..prefab_static_toggle import prepare as prepare_toggle
        toggle=prepare_toggle(ir['sourceManifestPath'],result,'unity',out/'toggle-source')
        result['toggleBinding']={**toggle,'bindings':list(toggle['bindings'].values())}
        result['diagnostics'].extend(toggle['diagnostics'])
        for c in components:
            if c['sourceId']in toggle['bindings']:
                c['convertible']=toggle['bindings'][c['sourceId']]['staticComplete']
                c['nativeType']=c['type'];c['staticToggleBinding']=True
    if ir.get('sourceProfile') in ('cocos-2.4.15-bundle','cocos-2.4.15-project'):
        from ..prefab_sync_instances import load_verified_source_manifest, bind_sync_prefab_instances, needs_sync_prefab_binding, SyncPrefabError
        if needs_sync_prefab_binding(result):
            try:
                sync_manifest=load_verified_source_manifest(ir.get('sourceManifestPath'),ir.get('sourceManifestSha256'),ir.get('sourceProfile'))
                result=bind_sync_prefab_instances(result,sync_manifest,source_ir=ir,source_profile=ir.get('sourceProfile'))
            except SyncPrefabError as error:
                fail(error.code,error.where,error.detail)
    from ..prefab_static_asset_dependencies import plan_source_prefab_dependencies, PrefabDependencyError
    try:
        dependencies=plan_source_prefab_dependencies(result)
    except PrefabDependencyError as error:
        fail(error.code,'sourcePrefabs',str(error.details))
    result['staticPrefabAssetDependencies']=dependencies
    prefab_by_id={row['sourceId']:row for row in result.get('sourcePrefabs',[])}
    result['sourcePrefabs']=[prefab_by_id[sid] for sid in dependencies['order']]
    result['diagnostics'].extend(diagnostic('STATIC_PREFAB_DEPENDENCY_GAP',row.get('owner')or'sourcePrefabs',str(row)) for row in dependencies['gaps'])
    from ..prefab_static_button_targets import apply as apply_button_targets
    apply_button_targets(result)
    write_json(out/'plan.json',result)
    return finish(out,result)


def _native_source_evidence(plan):
    """Carry source pins for every consuming module, independently of peers."""
    if not any(plan.get(key)for key in ('spineNativeStage','spriteOutlineBinding',
                                      'staticSpineRendering','staticSpineContinuation')):
        return {}
    evidence={key:plan.get(key)for key in ('spineNativeStage','sourceManifestPath',
                                        'sourceManifestSha256','sourceIrSha256')}
    rendering=plan.get('staticSpineRendering')
    if isinstance(rendering,dict)and evidence['sourceManifestSha256']is None:
        evidence['sourceManifestSha256']=rendering.get('sourceManifestSha256')
    return evidence


def _requires_cocos_static_spine_adapter(plan):
    """Select the SDK bridge only for an explicit static Spine rendering module.

    The ordinary importer/sort helpers remain SDK-independent. The rendering
    module owns its real SDK/factory closure; an invalid declaration is refused
    instead of being interpreted as an absent optional feature.
    """
    fragment=plan.get('staticSpineRendering')
    if fragment is None:return False
    if (not isinstance(fragment,dict) or type(fragment.get('schemaVersion'))is not int or fragment.get('schemaVersion')!=1 or
            fragment.get('contract')!='monkey-static-spine-rendering/1' or
            not isinstance(fragment.get('components'),list) or not fragment['components'] or
            not isinstance(fragment.get('dataAssets'),list) or not fragment['dataAssets'] or
            not isinstance(fragment.get('sourceManifestSha256'),str) or
            re.fullmatch(r'[0-9a-f]{64}',fragment['sourceManifestSha256'])is None or
            (plan.get('sourceManifestSha256')is not None and
             fragment['sourceManifestSha256']!=plan['sourceManifestSha256']) or
            any(not isinstance(row,dict) for row in fragment['components']+fragment['dataAssets'])):
        fail('STATIC_SPINE_ADAPTER_CONTRACT_INVALID','staticSpineRendering',
             'Optional SDK adapter requires the complete declared static Spine rendering contract')
    return True


def export(plan_path, output):
    plan_path=safe(plan_path)
    from ..sources.compiled import ParseError
    try:p=stage_document(plan_path)
    except ParseError as error:
        if error.code=='STAGE_DOCUMENT_CHANGED':fail('PLAN_CHANGED',str(plan_path),'Plan differs from manifest')
        raise
    if p.get('targetProfile')!=PROFILE or p.get('schemaVersion')!=1:
        fail('UNSUPPORTED_PLAN','$','Expected Unity plan schema 1')
    if p.get('staticSpineContinuation') and p.get('spineNativeStage'):
        fail('STATIC_SPINE_CONTINUATION_STAGE_CONFLICT','spineNativeStage','Rendering and non-rendering Spine stages cannot share importer hooks')
    requires_static_spine_adapter=_requires_cocos_static_spine_adapter(p)
    from ..prefab_static_mask_continuation import validate_export_contract,StaticMaskContinuationError
    try:validate_export_contract(p)
    except StaticMaskContinuationError as error:
        prefix=str(error).partition(':')[0]
        code=prefix if re.fullmatch(r'STATIC_MASK_[A-Z_]+',prefix)else'STATIC_MASK_CONTRACT_INVALID'
        fail(code,'staticMasks',str(error))
    # Plan JSON itself must match its create-only manifest, not just copied images.
    pm=stage_manifest(plan_path.parent)
    expected={f['path']:f['sha256'] for f in pm['files']}
    if expected.get(plan_path.name)!=sha(stage_bytes(plan_path)):
        fail('PLAN_CHANGED',str(plan_path),'Plan differs from manifest')
    for c in p['copies']:
        if sha(read(inside(plan_path.parent,c['source'])))!=c['sha256']:
            fail('SOURCE_CHANGED',c['source'],'Plan resource differs')
        if not c['target'].startswith(standard.ROOTS['unity']['content']+'/'):
            fail('UNSAFE_TARGET',c['target'],'Unexpected target root')
    out=new_output(output,[plan_path.parent])
    if p.get('sourceResourceCompletion'):
        from ..prefab_static_asset_completion import emit as emit_source_assets
        emit_source_assets(p,plan_path.parent/p['sourceResourceCompletion']['stageRelativePath'],out,'unity')
    if p.get('staticRetainedAssets'):
        from ..prefab_static_retained_assets import emit as emit_retained
        emit_retained(p['staticRetainedAssets'],plan_path.parent,out,'unity')
    if p.get('staticControls'):
        from ..prefab_static_controls import emit_unity
        emit_unity(p['staticControls'],out)
    if any(x['maskType']==2 for x in (p.get('staticMasks')or{}).get('masks',[])):
        shader=out/'Assets/Game/Content/Materials/StaticMasks/NativeStaticImageMask.shader'
        shader.parent.mkdir(parents=True,exist_ok=True)
        shader.write_bytes(files('monkey.targets').joinpath('materials/static_mask/NativeStaticImageMask.shader').read_bytes())
        Path(str(shader)+'.meta').write_text('fileFormatVersion: 2\nguid: '+guid(p['namespace'],'static-mask-shader')+'\n')
    static_fonts=p.get('staticFontInputs')
    for item in (static_fonts or {}).get('copies',[]):
        raw=read(inside(plan_path.parent,item['relativePath']))
        if sha(raw)!=item['sha256'] or len(raw)!=item['sizeBytes']:fail('STATIC_FONT_INPUT_CHANGED',item['relativePath'],'Plan-owned font input differs')
        dest=inside(out,item['relativePath'])
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    for folder in [standard.ROOTS['unity']['conversion'],'Packages','ProjectSettings','Analysis']:
        (out/folder).mkdir(parents=True,exist_ok=True)
    ownership=[]
    for c in p['copies']:
        target=inside(out,c['target']);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(read(inside(plan_path.parent,c['source'])))
        metadata='fileFormatVersion: 2\nguid: '+c['guid']+'\n'
        if c['role'] in ('sprite','bitmap-atlas'):
            metadata+='TextureImporter:\n  serializedVersion: 13\n  externalObjects: {}\n  textureType: 0\n  textureShape: 1\n  alphaUsage: 1\n  alphaIsTransparency: 1\n'
        Path(str(target)+'.meta').write_text(metadata,encoding='utf-8')
        ownership.append(dict(path=c['target'],sourceId=c['sourceId'],guid=c['guid']))
    # Shipped sources keep their GUID keys across layouts; only their location follows monkey-project/2.0.0.
    for template,relative,key in [('ContentPreviewView.cs',standard.unity('previewView'),'native-view-script'),
            ('IntrinsicGridLayoutGroup.cs',standard.UNITY_LAYOUT_DIR+'/IntrinsicGridLayoutGroup.cs','intrinsic-grid-script'),
            ('UnityNumericCode.cs',standard.unity('numericCode'),'numeric-code-editor'),
            ('UnityBehaviorBindings.cs',str(Path(standard.unity('importer')).with_name('UnityBehaviorBindings.cs')),'behavior-bindings-editor'),
            ('UnityStaticRetainedAssets.cs',str(Path(standard.unity('importer')).with_name('UnityStaticRetainedAssets.cs')),'static-retained-assets-editor'),
            ('UnityStaticControls.cs',str(Path(standard.unity('importer')).with_name('UnityStaticControls.cs')),'static-controls-editor'),
            ('UnityStaticSortQueue.cs',str(Path(standard.unity('importer')).with_name('UnityStaticSortQueue.cs')),'static-sort-editor/UnityStaticSortQueue.cs'),
            ('UnityStaticSortQueueProxy.cs',str(Path(standard.unity('importer')).with_name('UnityStaticSortQueueProxy.cs')),'static-sort-editor/UnityStaticSortQueueProxy.cs'),
            ('UnityStaticSortQueueIntegration.cs',str(Path(standard.unity('importer')).with_name('UnityStaticSortQueueIntegration.cs')),'static-sort-editor/UnityStaticSortQueueIntegration.cs'),
            ('UnityStaticSortTextSource.cs',str(Path(standard.unity('importer')).with_name('UnityStaticSortTextSource.cs')),'static-sort-editor/UnityStaticSortTextSource.cs'),
            ('UnityStaticSortVertexPrecision.cs',str(Path(standard.unity('importer')).with_name('UnityStaticSortVertexPrecision.cs')),'static-sort-editor/UnityStaticSortVertexPrecision.cs'),
            ('NativeStaticSortTextSource.cs','Assets/Game/Scripts/Presentation/StaticSort/NativeStaticSortTextSource.cs','static-sort-runtime/NativeStaticSortTextSource.cs'),
            ('NativeStaticSortTextSlotEnumerationIdentity.cs','Assets/Game/Scripts/Presentation/StaticSort/NativeStaticSortTextSlotEnumerationIdentity.cs','static-sort-runtime/NativeStaticSortTextSlotEnumerationIdentity.cs'),
            ('NativeStaticSortQueueProxyGraphic.cs','Assets/Game/Scripts/Presentation/StaticSort/NativeStaticSortQueueProxyGraphic.cs','static-sort-runtime/NativeStaticSortQueueProxyGraphic.cs'),
            ('NativeStaticSortQueueProxyPresenter.cs','Assets/Game/Scripts/Presentation/StaticSort/NativeStaticSortQueueProxyPresenter.cs','static-sort-runtime/NativeStaticSortQueueProxyPresenter.cs'),
            ('NativeStaticSortQueueRuntime.cs','Assets/Game/Scripts/Presentation/StaticSort/NativeStaticSortQueueRuntime.cs','static-sort-runtime/NativeStaticSortQueueRuntime.cs'),
            ('NativeStaticSortQueueProxyRaycaster.cs','Assets/Game/Scripts/Presentation/StaticSort/NativeStaticSortQueueProxyRaycaster.cs','static-sort-runtime/NativeStaticSortQueueProxyRaycaster.cs'),
            ('NativeStaticSortInputSurface.cs','Assets/Game/Scripts/Presentation/StaticSort/NativeStaticSortInputSurface.cs','static-sort-runtime/NativeStaticSortInputSurface.cs'),
            ('NativeStaticSortQueueProxyMarker.cs','Assets/Game/Scripts/Presentation/StaticSort/NativeStaticSortQueueProxyMarker.cs','static-sort-runtime/NativeStaticSortQueueProxyMarker.cs'),
            ('NativeStaticSortOrderIdentity.cs','Assets/Game/Scripts/Presentation/StaticSort/NativeStaticSortOrderIdentity.cs','static-sort-runtime/NativeStaticSortOrderIdentity.cs'),
            ('NativeStaticSortRootIdentity.cs','Assets/Game/Scripts/Presentation/StaticSort/NativeStaticSortRootIdentity.cs','static-sort-runtime/NativeStaticSortRootIdentity.cs'),
            ('UnityStaticMaskSort.cs',str(Path(standard.unity('importer')).with_name('UnityStaticMaskSort.cs')),'static-mask-editor/UnityStaticMaskSort.cs'),
            ('UnityBitmapMissingGlyphsIntegration.cs',str(Path(standard.unity('importer')).with_name('UnityBitmapMissingGlyphsIntegration.cs')),'bitmap-missing-editor'),
            ('NativeBitmapMissingGlyphs.cs','Assets/Game/Scripts/Presentation/Bitmap/NativeBitmapMissingGlyphs.cs','bitmap-missing-runtime'),
            ('UnityStaticMaskIntegration.cs',str(Path(standard.unity('importer')).with_name('UnityStaticMaskIntegration.cs')),'static-mask-editor/UnityStaticMaskIntegration.cs'),
            ('UnityStaticMaskClipProbe.cs',str(Path(standard.unity('importer')).with_name('UnityStaticMaskClipProbe.cs')),'static-mask-editor/UnityStaticMaskClipProbe.cs'),
            ('NativeStaticEllipseMaskGraphic.cs','Assets/Game/Scripts/Presentation/StaticMasks/NativeStaticEllipseMaskGraphic.cs','static-mask-runtime/NativeStaticEllipseMaskGraphic.cs'),
            ('NativeStaticInvertedMaskGraphic.cs','Assets/Game/Scripts/Presentation/StaticMasks/NativeStaticInvertedMaskGraphic.cs','static-mask-runtime/NativeStaticInvertedMaskGraphic.cs'),
            ('NativeStaticMaskIdentity.cs','Assets/Game/Scripts/Presentation/StaticMasks/NativeStaticMaskIdentity.cs','static-mask-runtime/NativeStaticMaskIdentity.cs'),
            ('UnityStaticLayoutCompletionIntegration.cs',str(Path(standard.unity('importer')).with_name('UnityStaticLayoutCompletionIntegration.cs')),'static-layout-editor'),
            ('UnityStaticTextMetrics.cs',str(Path(standard.unity('importer')).with_name('UnityStaticTextMetrics.cs')),'static-text-metrics-editor'),
            ('UnityStaticSortSpineBinding.cs',str(Path(standard.unity('importer')).with_name('UnityStaticSortSpineBinding.cs')),'static-sort-spine-binding-editor'),
            ('NativeStaticLayoutCompletion.cs','Assets/Game/Scripts/Presentation/StaticLayout/NativeStaticLayoutCompletion.cs','static-layout-runtime'),
            ('UnityStaticAnimationIntegration.cs',str(Path(standard.unity('importer')).with_name('UnityStaticAnimationIntegration.cs')),'static-animation-integration'),
            ('UnityStaticAnimationBindings.cs',str(Path(standard.unity('importer')).with_name('UnityStaticAnimationBindings.cs')),'static-animation-editor'),
            ('UnityStaticProgressIntegration.cs',str(Path(standard.unity('importer')).with_name('UnityStaticProgressIntegration.cs')),'static-progress-editor'),
            ('UnityStaticFields.cs',str(Path(standard.unity('importer')).with_name('UnityStaticFields.cs')),'static-fields-editor'),
            ('UnitySourceComponentCoverage.cs',str(Path(standard.unity('importer')).with_name('UnitySourceComponentCoverage.cs')),'source-component-coverage-editor'),
            ('UnityStaticFieldIntegration.cs',str(Path(standard.unity('importer')).with_name('UnityStaticFieldIntegration.cs')),'static-field-integration-editor'),
            ('materials/ui_color/UnityMaterialBindings.cs',str(Path(standard.unity('importer')).with_name('UnityMaterialBindings.cs')),'material-bindings-editor'),
            ('UnityPreviewState.cs',str(Path(standard.unity('importer')).with_name('UnityPreviewState.cs')),'preview-state-editor'),
            ('UnityStaticSpriteFrames.cs',str(Path(standard.unity('importer')).with_name('UnityStaticSpriteFrames.cs')),'static-sprite-frames-editor'),
            ('UnityPreviewClones.cs',str(Path(standard.unity('importer')).with_name('UnityPreviewClones.cs')),'preview-clones-editor'),
            ('UnityStaticPreview.cs',str(Path(standard.unity('importer')).with_name('UnityStaticPreview.cs')),'static-preview-editor'),
            ('UnityStaticRichText.cs',str(Path(standard.unity('importer')).with_name('UnityStaticRichText.cs')),'static-richtext-editor'),
            ('UnityStaticToggle.cs',str(Path(standard.unity('importer')).with_name('UnityStaticToggle.cs')),'static-toggle-editor'),
            ('UnitySystemFonts.cs',str(Path(standard.unity('importer')).with_name('UnitySystemFonts.cs')),'system-fonts-editor'),
            ('UnityPrefabInstances.cs',standard.unity('prefabInstances'),'prefab-instances-editor'),
            *[(name,standard.UNITY_LAYOUT_DIR+'/'+name,'native-ui/'+name) for name in ('NativeLinearLayoutGroup.cs','NativeRectConstraints.cs','NativeTextLineBox.cs','NativeHorizontalProgressFill.cs','UnityStaticProgress.cs','NativeStaticAnimationBinding.cs','NativeStaticEditBox.cs','NativeStaticGraphics.cs','NativeRetainedMaterial.cs','NativeStaticLabelStyle.cs','NativeInputBlocker.cs','NativeInputBlockerSurface.cs','NativeStaticButtonTarget.cs','NativeStaticButtonTargetContract.cs','NativeStaticTextOutline.cs')],
            ('UnityDynamicUi.cs',standard.unity('dynamicUi'),'native-ui/UnityDynamicUi.cs'),
            ('UnityButtonAnimations.cs',Path(standard.unity('importer')).with_name('NativeButtonAnimations.cs').as_posix(),'button-animations-editor'),
            ('UnityImporter.cs',standard.unity('importer'),'editor-adapter')]:
        if template=='UnityStaticSortSpineBinding.cs' and not requires_static_spine_adapter:continue
        dest=out/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(files('monkey.targets').joinpath(template).read_bytes())
        Path(str(dest)+'.meta').write_text('fileFormatVersion: 2\nguid: '+guid(p['namespace'],key)+'\n')
    from ..prefab_target_behaviors import emit as emit_behaviors
    emit_behaviors(p,plan_path.parent,'unity',out)
    if p.get('spineNativeStage'):
        from ..prefab_spine_native_stage import emit_unity_stage
        emit_unity_stage(p['spineNativeStage'],plan_path.parent,out)
    if p.get('staticSpineContinuation'):
        from ..prefab_static_spine_continuation import emit as emit_static_spine
        emit_static_spine(p,plan_path.parent,out)
    if p.get('staticSpineRendering'):
        from ..prefab_static_spine_rendering import emit as emit_static_spine_rendering
        emit_static_spine_rendering(p,plan_path.parent,out)
    from ..prefab_static_carriers import emit as emit_static
    emit_static(p,plan_path.parent,'unity',out)
    if p.get('spriteOutlineBinding'):
        from ..prefab_sprite_outline_pipeline import emit_attached
        emit_attached(plan_path.parent,plan_path.parent,out)
    from ..prefab_material_pipeline import emit as emit_material
    emit_material(p.get('materialBinding'),plan_path.parent,out)
    if p.get('staticTimeMaterials'):
        from ..prefab_static_time_materials import emit as emit_static_time
        emit_static_time(p['staticTimeMaterials'],plan_path.parent,out)
        helper_root=out/'Assets/Game/Editor/Conversion/StaticTime'
        helper_root.mkdir(parents=True,exist_ok=True)
        for name in ('UnityStaticTimeMaterialBindings.cs','UnityStaticTimeMaterialsIntegration.cs'):
            dest=helper_root/name
            dest.write_bytes(files('monkey.targets').joinpath('materials/static_time/'+name).read_bytes())
            Path(str(dest)+'.meta').write_text('fileFormatVersion: 2\nguid: '+guid(p['namespace'],'static-time-helper/'+name)+'\n')

    # Only the typed, finite import instruction subset is sent to the Editor.
    instruction={key:p.get(key,[]) for key in ('designSize','pixelsPerUnit','textures','assets','bitmapFonts','nodes','components','galleryOnly','animations','sourcePrefabs','prefabInstances')}
    instruction.update(_native_source_evidence(p))
    instruction['staticCompletionEnabled']=bool(p.get('staticCompletion'))
    instruction['staticAnimationBindingsEnabled']=bool(p.get('staticAnimationBindingsEnabled'))
    instruction['staticSpineContinuationJson']=encoded(p['staticSpineContinuation']).decode('utf-8') if p.get('staticSpineContinuation') else None
    instruction['staticSpineRenderingJson']=encoded(p['staticSpineRendering']).decode('utf-8') if p.get('staticSpineRendering') else None
    instruction['staticRetainedAssets']=p.get('staticRetainedAssets')
    instruction['staticPresentation']=p.get('staticPresentation')
    instruction['layoutCompletion']=p.get('layoutCompletion')
    instruction['staticLayoutContinuation']=p.get('staticLayoutContinuation')
    instruction['staticMasks']=p.get('staticMasks')
    instruction['staticMasksPresent']=p.get('staticMasks') is not None
    if isinstance(instruction['staticMasks'],dict)and instruction['staticMasks'].get('contract')=='monkey-static-mask-continuation/1':
        mask_ids={row['sourceId']for row in instruction['staticMasks']['masks']}
        instruction['components']=[dict(row,nativeType='UnityEngine.UI.Mask')if row.get('sourceId')in mask_ids
            else row for row in instruction['components']]
    instruction['staticSortQueue']=p.get('staticSortQueue')
    instruction['staticSortContinuation']=p.get('staticSortContinuation')
    instruction['staticTextContinuationJson']=encoded(p['staticTextContinuation']).decode('utf-8') if p.get('staticTextContinuation') else None
    instruction['staticTextSlotCaptureLifecycleContract']=p.get('staticTextSlotCaptureLifecycleContract')
    instruction['staticTextSlotRoleRoutingContract']=p.get('staticTextSlotRoleRoutingContract')
    instruction['bitmapMissingGlyphs']=p.get('bitmapMissingGlyphs')
    instruction['staticParticleBoundary']=p.get('staticParticleBoundary')
    instruction['staticAnimationEvidence']=p.get('staticAnimationEvidence')
    instruction['staticAnimationComponentOrigins']=p.get('staticAnimationComponentOrigins')
    instruction['staticAnimationAssetReferences']=p.get('staticAnimationAssetReferences')
    instruction['staticControlBindings']=(p.get('staticControls')or{}).get('bindings')
    instruction['systemFontBinding']=p.get('systemFontBinding')
    instruction['staticFontReceiptPath']=(static_fonts or {}).get('portableReceiptRelativePath')
    instruction['staticFontReceiptSha256']=(static_fonts or {}).get('portableReceiptSha256')
    instruction['materialBinding']=(p.get('materialBinding')or {}).get('spec')
    instruction['sourceManifestSha256']=p.get('sourceManifestSha256')
    instruction['staticTimeMaterialsJson']=encoded(p['staticTimeMaterials']).decode('utf-8') if p.get('staticTimeMaterials') else None
    instruction['spriteOutlineBindingJson']=encoded(p['spriteOutlineBinding']).decode('utf-8') if p.get('spriteOutlineBinding') else None
    instruction['tmpResources']=dict(packageName='com.unity.ugui',packageVersion='2.6.0',resource='Package Resources/TMP Essential Resources.unitypackage',importMode='package-completion-callback')
    instruction['glyphReadback']='native-quad-padding-v1'
    instruction['sceneRoundtrip']=True
    instruction['sourcePrefabReadback']='native-layout-settled-v1'
    instruction['previewState']=p.get('previewState')
    instruction['previewStates']=p.get('previewStates')
    instruction['toggleBinding']=p.get('toggleBinding')
    # Unity JsonUtility can materialize a null nested serializable object with
    # null fields. Object non-nullness therefore cannot enable this feature.
    instruction['toggleBindingPresent']=p.get('toggleBinding') is not None
    instruction['behaviorBindingReadback']='persistent-source-fields-v1'
    instruction['transformReadback']='full-local-v1'
    instruction['sourceDiagnostics']=p.get('diagnostics',[])
    instruction['sourceDiagnosticCount']=len(p['diagnostics'])
    instruction['prefabGuid']=guid(p['namespace'],'native-prefab')
    instruction['prefabRelationshipReadback']='native-source-correspondence-v1'
    instruction['uiGeometryReadback']='native-ui-layout-roundtrip-v1'
    from .dynamic_ui import probe_sources
    instruction['uiStateProbeVersion']=2;instruction['uiProbeSources']=probe_sources(instruction)
    instruction['textLineBoxReadback']='native-cocos-ttf-line-box-v1'
    instruction['sceneGuid']=guid(p['namespace'],'native-scene')
    if p['galleryOnly']:
        instruction['galleryReadback']='exact-sprite-and-rect-v1'
        instruction['textures']=[dict(t,guid=guid(p['namespace'],t['id']))for t in instruction['textures']]
    write_json(out/standard.unity('importPlan'),instruction)
    write_json(out/standard.unity('outputPaths'),standard.unity_output_paths())
    write_json(out/'Packages/manifest.json',dict(dependencies={'com.unity.ugui':'2.6.0',
               'com.unity.modules.ui':'1.0.0','com.unity.modules.imgui':'1.0.0','com.unity.modules.animation':'1.0.0'}))
    (out/'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 6000.6.2f1\n')
    (out/'README.md').write_text('Unity 原生资源/UI候选，非可玩游戏。目录规范 '+VERSION+'（monkey docs/PROJECT-SPEC.md）。\n\n'
        '打开后执行 Tools > Monkey > Import Candidate。\n'
        '仅首次导入新候选；已生成 Prefab/Scene 存在时拒绝覆盖。\n'
        '或用独立 batchmode -projectPath 此目录 -executeMethod MonkeyImporter.ImportBatch。\n'
        '导入成功后删除 '+standard.ROOTS['unity']['conversion']+' 仍保留原生可编辑资产；Player 不读取转换 JSON。\n'
        '真实编辑器/画面对照/业务尚未验证，见 Analysis。\n',encoding='utf-8')
    from ..assets.animation import module_report
    write_json(find_analysis(out,'animation-module.json'),module_report(p.get('animations',[])))
    groups={}
    module_names={n['sourceId'].split('#')[0]:n['name'] for n in p['nodes'] if n['parent'] is None}
    component_types={c['sourceId']:c['type'] for c in p['components']}
    def cause(d):
        code=d['code'];message=d['message'].lower()
        if component_types.get(d.get('sourceId')) in ('cc.SortOrder','cc.SortRoot'):return 'render-order'
        if any(term in code for term in ('FONT','LABEL','BITMAP','OUTLINE')):return 'text-and-font-metrics'
        if any(term in code for term in ('SPRITE','TEXTURE','NATIVE','REFERENCE','REDIRECT')):return 'asset-binding'
        if any(term in code for term in ('NODE','WIDGET','LAYOUT','GRID','SCROLL','MASK')):return 'native-layout'
        if code=='BUTTON_BUSINESS_UNBOUND':return 'button-business-handlers'
        if any(term in code for term in ('IDENTITY','CONFIG')):return 'source-format'
        if any(term in message for term in ('cc.sortorder','cc.sortroot')):return 'render-order'
        return 'unknown-components-and-behavior'
    for d in p['diagnostics']:
        if d['code'].startswith('ANIMATION_'):continue
        sid=d.get('sourceId') or 'source-config';module=sid.split('#',1)[0] if '#' in sid else 'resources'
        key=(module,cause(d));groups.setdefault(key,[]).append(d)
    tasks=[]
    for (module,root_cause),gaps in sorted(groups.items()):
        task_id='module-'+sha((module+'/'+root_cause).encode())[:12]
        tasks.append(dict(taskId=task_id,module=module,moduleName=module_names.get(module,'Resources'),rootCause=root_cause,
            sourceRefs=sorted({str(d.get('sourceId') or d.get('location')) for d in gaps}),
            sourceManifest=dict(path=p.get('sourceManifestPath'),sha256=p.get('sourceManifestSha256')),
            sourceLocations=[dict(location=d.get('location'),sourceId=d.get('sourceId')) for d in gaps],
            gaps=gaps,generatedTargets=[standard.unity('previewPrefab')],
            allowedPaths=[standard.ROOTS['unity']['game']+'/'],dependencies=['matching original evidence'],
            verificationScope=['affected UI module in real Editor','source reference comparison']))
    if p.get('animations') or any(d['code'].startswith('ANIMATION_') for d in p['diagnostics']):
        from ..assets.animation import handoff_task
        tasks.append(handoff_task(p['animations'],p['diagnostics']))
    write_json(find_analysis(out,'handoff.json'),dict(schemaVersion=1,tasks=tasks,
               verification=dict(static='pending',editor='not_run',visual='not_run',business='not_run')))
    write_json(find_analysis(out,'source-map.json'),dict(assets=ownership,sourceRoots=p.get('sourceRoots',{}),sourceLocations=p.get('sourceLocations',{}),
        fonts=[dict(sourceId=f['id'],target=f['fontPath'],atlas=f['path']) for f in p.get('bitmapFonts',[])]+[dict(sourceId=a['id'],target=str(Path(a['path']).with_suffix('.asset'))) for a in p['assets'] if a['kind']=='cc.TTFFont'],
        nodes=[dict(sourceId=n['sourceId'],target=standard.unity('previewPrefab'),name=n['name']) for n in p['nodes']],
        components=[dict(sourceId=c['sourceId'],node=c['node'],type=c['type'],convertible=c['convertible'],
            target=standard.unity('previewPrefab'),viewField={'cc.Sprite':'Images','cc.Label':'Labels','cc.Button':'Buttons'}.get(c['type']),
            bindingEvidence='Actual indices and native fileIDs require Analysis/Readback/editor-readback.json') for c in p['components']]))
    if p.get('bindings'):write_json(find_analysis(out,'font-bindings.json'),p['bindings'])
    write_json(find_analysis(out,'name-map.json'),p.get('naming',{}))
    report=dict(schemaVersion=1,toolVersion=__version__,targetProfile=PROFILE,namespace=p['namespace'],projectLayout=VERSION,
                scopeMode=p.get('scopeMode','asset-selection'),
                planSha256=sha(stage_bytes(plan_path)),sourceRoots=p.get('sourceRoots',{}),sourceManifestSha256=p.get('sourceManifestSha256'),diagnostics=p['diagnostics'],editorValidation='not_run',
                visualValidation='not_run',businessValidation='not_run',galleryOnly=p['galleryOnly'])
    write_json(find_analysis(out,'candidate.json'),report)
    return finish(out,report)


def close(actual,expected,tolerance=.001):
    if isinstance(expected,list):
        return isinstance(actual,list) and len(actual)==len(expected) and all(close(a,b,tolerance) for a,b in zip(actual,expected))
    return type(actual) in (int,float) and abs(actual-expected)<=tolerance


def source_ttf_shrink_evidence(instruction):
    """Return only source-version-pinned system-TTF sizing facts, never mesh proof."""
    from ..prefab_static_text_continuation import SCHEMA, SOURCE_PROFILE, SOURCE_VERSION, _SOURCE_ENGINE_PINS, _RAW_BASE
    raw=instruction.get('staticTextContinuationJson')
    if not isinstance(raw,str):return {}
    try:fragment=load(raw.encode('utf-8'))
    except (ValueError,TypeError):return {}
    if (not isinstance(fragment,dict)or fragment.get('contract')!=SCHEMA or fragment.get('schemaVersion')!=1
        or fragment.get('sourceProfile')!=SOURCE_PROFILE or fragment.get('sourceVersion')!=SOURCE_VERSION
        or fragment.get('sourceManifestSha256')!=instruction.get('sourceManifestSha256')):return {}
    files=fragment.get('sourceEngineFiles')
    if not isinstance(files,list)or any(not isinstance(row,dict)or not isinstance(row.get('logicalPath'),str)for row in files):return {}
    by_path={row.get('logicalPath'):row for row in files}
    if len(by_path)!=len(files)or set(by_path)!=set(_SOURCE_ENGINE_PINS):return {}
    if any(by_path[path].get('sha256')!=digest or by_path[path].get('originUrl')!=_RAW_BASE+path
           or type(by_path[path].get('bytes'))is not int or by_path[path]['bytes']<=0
           for path,digest in _SOURCE_ENGINE_PINS.items()):return {}
    groups=fragment.get('components')
    if not isinstance(groups,list)or any(not isinstance(row,dict)or not isinstance(row.get('sourceLabelId'),str)for row in groups):return {}
    by_id={row.get('sourceLabelId'):row for row in groups}
    if len(by_id)!=len(groups)or any(not isinstance(key,str)or not key for key in by_id):return {}
    return by_id


def _source_ttf_zero_floor(spec,source_sizing):
    if not isinstance(source_sizing,dict):return False
    policy=source_sizing.get('layoutPolicy');native=source_sizing.get('nativeFontBinding')
    if not isinstance(native,dict):return False
    binding=native.get('binding')
    system=(spec.get('systemFont')is True and source_sizing.get('fontKind')=='system-font'
        and native.get('kind')=='system-font' and isinstance(binding,dict)and binding.get('sourceSystemFont')is True
        and binding==spec.get('nativeSystemFontBinding')and binding.get('sourceLabelId')==spec.get('sourceId'))
    explicit=(spec.get('systemFont')is False and source_sizing.get('fontKind')=='explicit-ttf'
        and native.get('kind')=='explicit-ttf'and native.get('assetIds')==[spec.get('font')])
    wrap=source_sizing.get('sourceWrap')
    shrink='wrapped-integer-binary-search-v2.4.15'if wrap is True else 'unwrapped-scale-floor-v2.4.15'
    return bool((system or explicit)and spec.get('nativeTextSizingPolicy')=='cocos24-ttf-shrink-v1'
        and source_sizing.get('sourceLabelId')==spec.get('sourceId')and type(wrap)is bool
        and source_sizing.get('sourceText')==spec.get('text')and close(source_sizing.get('sourceFontSize'),spec.get('fontSize'))
        and source_sizing.get('sourceOverflow')==2 and isinstance(policy,dict)
        and policy.get('profile')=='cocos-2.4.15-ttf-label-v1'and policy.get('shrinkPolicy')==shrink
        and type(policy.get('sourceShrinkLowerBound'))in(int,float)and policy['sourceShrinkLowerBound']==0
        and type(policy.get('targetAutoSizeMin'))in(int,float)and policy['targetAutoSizeMin']==0
        and policy.get('targetAutoSizing')is True and close(policy.get('sourceFontSizeMaximum'),spec.get('fontSize'))
        and close(policy.get('targetAutoSizeMax'),spec.get('fontSize')))


def label_font_matches(spec,actual,font,evidence=None,source_sizing=None):
    """SHRINK sizes may vary only with explicit native auto-size/bounds proof."""
    import math
    if not actual or not font or not font.get('guid') or actual.get('fontGuid')!=font['guid'] or actual.get('text')!=spec['text']:return False
    if spec.get('bitmapMissingGlyphPolicy')=='cocos24-bitmap-missing-glyph-skip-v1':
        if actual.get('bitmapMissingGlyphPolicy')!=spec['bitmapMissingGlyphPolicy'] or actual.get('bitmapMissingGlyphProofVerified')is not True or actual.get('bitmapDisplayText')!=spec['bitmapMissingGlyphDisplayText']:return False
        if not spec['bitmapMissingGlyphDisplayText'] and (actual.get('characterCount')!=0 or actual.get('glyphBounds')):return False
    elif actual.get('allCharactersPresent')is not True:return False
    if close(actual.get('fontSize'),spec['fontSize']) and not actual.get('autoSizeReadback'):return True
    if spec.get('overflow')!=2:return close(actual.get('fontSize'),spec['fontSize'])
    proof=evidence or actual
    config=proof.get('autoSizing')is True and (not evidence or proof.get('prefabUnchanged')is True)
    measured=proof.get('actualFontSize',proof.get('fontSize'));low=proof.get('fontSizeMin');high=proof.get('fontSizeMax')
    if not all(type(v)in(int,float)and math.isfinite(v)for v in (measured,low,high)):return False
    if evidence and (not close(measured,actual.get('fontSize'))or proof.get('fontGuid')!=font['guid'] or proof.get('text')!=spec['text']or proof.get('allCharactersPresent')is not True or not close(proof.get('requestedFontSize'),spec['fontSize'])):return False
    floor_valid=(0<=low<=high if _source_ttf_zero_floor(spec,source_sizing)else 0<low<=high)
    return bool(config and close(high,spec['fontSize'])and floor_valid and low-.001<=measured<=high+.001)


def bitmap_label_probe(spec,font,effective_size):
    """Native TMP keeps the emitted margin fixed while SHRINK scales glyph metrics."""
    original=spec['bitmapProbe']
    if spec.get('overflow')!=2 or close(effective_size,spec['fontSize']):return original,spec['fontSize'],original['inkRight']
    from ..assets.bitmap import single_line
    probe=single_line(font,spec['text'],effective_size,spec.get('spacing',0)*effective_size/spec['fontSize'])
    fixed_right_margin=original['inkRight']-original['advance']
    return probe,effective_size,probe['advance']+fixed_right_margin


def node_geometry_matches(actual,source,full=False):
    if not actual or actual.get('active')!=source['active']:
        return False
    if any(not close(actual.get(key),source[field]) for key,field in [('size','size'),('pivot','anchor'),('position','position')]):
        return False
    if source.get('sourceGeometryProfile'):
        if not close(actual.get('opacity'),source['opacity']):return False
        if source.get('verifyUiColor') and not close(actual.get('color'),source['color']):return False
    if full:
        rotation=actual.get('rotation');expected=source['rotation']
        # q and -q describe the same native rotation. No angular tolerance change.
        if not close(actual.get('scale'),source['scale']) or not (close(rotation,expected) or close(rotation,[-v for v in expected])):
            return False
    return True


def gallery_readback(instruction,readback):
    if instruction.get('galleryReadback')!='exact-sprite-and-rect-v1':return []
    expected={t['id']:t for t in instruction['textures']if not t['id'].endswith('@original')}
    rows=readback.get('gallery')
    actual={r.get('id'):r for r in rows}if isinstance(rows,list)and all(isinstance(r,dict)for r in rows)else{}
    valid=instruction.get('galleryOnly')is True and not instruction.get('nodes')and not instruction.get('components')and not instruction.get('sourcePrefabs')and readback.get('nativeScope')=='resources-and-gallery-only'and readback.get('sourceGraphVerification')=='not_run'
    valid=valid and isinstance(rows,list)and len(actual)==len(rows)and set(actual)==set(expected)
    if valid:valid=all(actual[key].get('spriteGuid')==spec['guid']and actual[key].get('geometryVerified')is True for key,spec in expected.items())
    return []if valid else[diagnostic('NATIVE_GALLERY_READBACK','Analysis/Readback/editor-readback.json','Resource-only preview must prove exact sprite identities/rects without claiming source graph restoration')]


def _static_sort_spine_bindings(plan, root):
    """Load measured-map input only from the frozen candidate binding-plan pin."""
    from ..prefab_spine_unity_readback import _relative_file, _sha
    stage = plan.get('spineNativeStage')
    if not isinstance(stage, dict):
        if plan.get('staticSpineRenderingJson'):
            path=inside(Path(root).resolve(),'Assets/Game/Editor/Conversion/spine-static-rendering.json')
            return read(path,max_bytes=32*1024*1024) if path.is_file() else None
        return None
    path = _relative_file(Path(root).resolve(), stage.get('nativeBindingPlanPath'))
    if path is None or _sha(path) != stage.get('nativeBindingPlanSha256'):
        return None
    return read(path, max_bytes=128 * 1024 * 1024)


def verify(candidate, output, level='static'):
    root=safe(candidate);m=stage_manifest(root);diagnostics=[]
    from ..sources.containers import fingerprint
    native={};editor='not_run';rb=None;coverage={};raw_native_diagnostics=[];spine_coverage=None;text_family_proofs={}
    rendering_fragment=None;rendering_receipt=None;saved_meta_observations=[]
    if level=='editor':
        readback_path=find_analysis(root,'editor-readback.json')
        if not readback_path.is_file():
            diagnostics.append(diagnostic('EDITOR_NOT_RUN','Analysis/Readback/editor-readback.json','Run native import in the declared Editor first'))
        else:
            rb=load(read(readback_path,max_bytes=128*1024*1024),max_nodes=8_000_000)
            from ..unity_verification_contract import native_diagnostics
            from ..native_readback_contract import saved_readback_admission
            raw_native_diagnostics=rb.get('diagnostics')
            instruction=load(read(root/standard.locate(m,'importPlan'),max_bytes=128*1024*1024),max_nodes=8_000_000)
            admission=saved_readback_admission(rb,gallery=instruction.get('galleryOnly')is True,
                expected_plan_sha256=fingerprint(root/standard.locate(m,'importPlan')),
                expected_source_manifest_sha256=instruction.get('sourceManifestSha256'))
            for issue in admission['issues']:
                diagnostics.append(diagnostic(issue['code'],str(readback_path)+'#'+issue['field'],issue['message']))
            native=admission['nativeFiles']
            for relative,expected in native.items():
                file=inside(root,relative)
                if not file.is_file() or fingerprint(file)!=expected:
                    diagnostics.append(diagnostic('NATIVE_FILE_CHANGED',relative,'Native file differs from saved readback'))
            diagnostics.extend(gallery_readback(instruction,rb))
            spine_receipts_bound=True;pending_rendering_receipt=None
            if instruction.get('staticSpineRenderingJson'):
                rendering_fragment=load(instruction['staticSpineRenderingJson'].encode('utf-8'))
                from ..unity_spine_rendering_coverage import load_bound_receipt
                try:pending_rendering_receipt=load_bound_receipt(root,rb)
                except (OSError,ValueError,KeyError,TypeError) as error:
                    spine_receipts_bound=False
                    diagnostics.append(diagnostic('STATIC_SPINE_READBACK_BINDING_INVALID',
                        'Analysis/Readback',str(error)))
            if instruction.get('staticSpineContinuationJson') and spine_receipts_bound:
                from ..prefab_static_spine_continuation import verify as verify_static_spine
                spine_diagnostics=verify_static_spine(load(instruction['staticSpineContinuationJson'].encode('utf-8')),root,rb,
                                                      meta_observations=saved_meta_observations)
                diagnostics.extend(spine_diagnostics)
                if not spine_diagnostics:
                    sidecar=load(read(root/'Analysis/Readback/spine-static-continuation.json'))
                    spine_coverage={'status':'verified','sourceComponentIds':[row['sourceComponentId']for row in sidecar['components']]}
            if rendering_fragment is not None and spine_receipts_bound:
                from ..prefab_static_spine_rendering import verify as verify_static_spine_rendering
                try:
                    rendering_gaps=verify_static_spine_rendering({'staticSpineRendering':rendering_fragment},root)
                    for gap in rendering_gaps:
                        normalized=diagnostic(gap['code'],gap.get('location','Analysis/Readback/SpineRendering'),
                                              gap.get('message')or encoded(gap).decode('utf-8'),gap.get('sourceId'))
                        normalized.update(gap);diagnostics.append(normalized)
                    if not rendering_gaps:rendering_receipt=pending_rendering_receipt
                except (OSError,ValueError,KeyError,TypeError) as error:
                    diagnostics.append(diagnostic('STATIC_SPINE_RENDERING_READBACK_INVALID','Analysis/Readback/SpineRendering',str(error)))
            from ..prefab_spine_unity_readback import verify as verify_spine_saved
            diagnostics.extend(verify_spine_saved(instruction,root,rb))
            from ..prefab_static_completion_readback import verify_assets as verify_retained
            diagnostics.extend(verify_retained(instruction,rb.get('staticRetainedAssetReadback'),'unity'))
            from ..prefab_static_sort_readback import verify as verify_static_sort
            sort_gaps=verify_static_sort(instruction,rb,
                spine_native_bindings=_static_sort_spine_bindings(instruction, root))
            diagnostics.extend(sort_gaps)
            if instruction.get('staticTextContinuationJson'):
                from ..prefab_static_text_continuation import verify as verify_static_text
                text_result=verify_static_text(instruction,root,rb)
                diagnostics.extend(text_result['diagnostics'])
                text_family_proofs=text_result['family_proofs']
            from ..prefab_sprite_outline_unity_readback import verify as verify_outline_saved
            diagnostics.extend(verify_outline_saved(instruction,root,rb))
            if instruction.get('staticTimeMaterialsJson'):
                from ..prefab_static_time_materials import verify as verify_static_time
                time_spec=load(instruction['staticTimeMaterialsJson'].encode('utf-8'))
                time_path=root/'Analysis/Readback/static-time-materials.json'
                time_read=load(read(time_path)) if time_path.is_file() else {}
                expected_owners={b['ownerPrefabId'] for mat in time_spec['materials'] for b in mat['spriteBindings']}
                owner_rows=time_read.get('prefabs',[])
                owner_map={row.get('sourcePrefabId'):row for row in owner_rows if isinstance(row,dict)}
                if len(owner_map)!=len(owner_rows) or set(owner_map)!=expected_owners:
                    diagnostics.append(diagnostic('STATIC_TIME_MATERIAL_OWNER_MISMATCH',str(time_path),'Saved per-Prefab material denominator differs'))
                for owner in expected_owners:
                    local_materials=[]
                    for mat in time_spec['materials']:
                        subset=[b for b in mat['spriteBindings'] if b['ownerPrefabId']==owner]
                        if subset:local_materials.append(dict(mat,spriteBindings=subset))
                    diagnostics.extend(verify_static_time(dict(time_spec,materials=local_materials),
                        dict(time_read,materials=owner_map.get(owner,{}).get('materials',[])),'unity'))

            from ..code_validation import numeric as verify_numeric
            from ..prefab_material_pipeline import verify as verify_material
            diagnostics.extend(verify_material(instruction.get('materialBinding'),rb.get('materialBinding'),'unity'))
            diagnostics.extend(verify_numeric(instruction['components'],rb.get('numericCodeBindings'),'unity','scene',rb.get('numericCodeExercise',[])))
            if instruction.get('bitmapFonts') or any(a['path'].lower().endswith('.ttf') for a in instruction['assets']):
                resources=rb.get('tmpResources') or {}
                expected_resources=instruction.get('tmpResources',{})
                if resources.get('status')!='ready' or resources.get('completionProof') not in ('package-completed-event','preexisting-files') or any(resources.get(k)!=expected_resources.get(k) for k in ('packageName','packageVersion','resource')) or not all(resources.get(k) for k in ('archiveSha256','bitmapGuid','distanceGuid','mobileGuid','settingsGuid')):
                    diagnostics.append(diagnostic('TMP_RESOURCES_NOT_VERIFIED','Analysis/Readback/tmp-resources.json','Exact installed package, essential resource import and native shader/settings identities are unverified'))
            if instruction.get('sceneRoundtrip') and rb.get('sceneReopened') is not True:
                diagnostics.append(diagnostic('SCENE_ROUNDTRIP_NOT_VERIFIED','Candidate.unity','Saved scene was not normally closed/reopened before native readback'))
            json_assets={a['id']:a for a in rb.get('jsonAssets',[])}
            actual_prefabs={a['sourceId']:a for a in rb.get('sourcePrefabs',[])}
            from .prefabs import verify_native_relationships
            template_guids={sid:row.get('guid')for sid,row in actual_prefabs.items()}
            diagnostics.extend(verify_native_relationships(instruction.get('prefabInstances',[]),instruction.get('sourcePrefabs',[]),rb.get('prefabInstances'),'scene',template_guids))
            if any(x.get('mountedChildren')or x.get('mountedComponents')for x in instruction.get('prefabInstances',[])):
                diagnostics.extend(verify_native_relationships(instruction['prefabInstances'],instruction.get('sourcePrefabs',[]),rb.get('candidatePrefabInstances'),'candidate-prefab',template_guids))
            from .dynamic_ui import expectations,verify_probes
            diagnostics.extend(verify_probes(instruction,rb.get('dynamicUiProbes')))
            scene_expected,ui_gaps=expectations(instruction,rb.get('nativeInitialNodes'),'UnityScene');diagnostics.extend(ui_gaps)
            expected_nodes={n['sourceId']:n for n in instruction['nodes']}
            for spec in instruction.get('sourcePrefabs',[]):
                actual=actual_prefabs.get(spec['sourceId'],{})
                diagnostics.extend(verify_native_relationships([x for x in instruction.get('prefabInstances',[])if x['owner']==spec['sourceId']],instruction.get('sourcePrefabs',[]),actual.get('prefabInstances'),spec['sourceId'],template_guids))
                target=spec['path']
                if not actual.get('guid') or actual.get('nodeCount')!=spec['nodeCount'] or actual.get('missingScripts')!=0 or actual.get('path')!=target or target not in native:
                    diagnostics.append(diagnostic('SOURCE_PREFAB_NOT_VERIFIED',spec['sourceId'],'Independent native prefab save/reopen evidence is absent or inconsistent'))
                if instruction.get('prefabRelationshipReadback')=='native-source-correspondence-v1':
                    root_variant=any(x['owner']==spec['sourceId']and x['root']==spec['root']for x in instruction.get('prefabInstances',[]))
                    if actual.get('nativePrefabType')!=('Variant'if root_variant else'Regular'):
                        diagnostics.append(diagnostic('NATIVE_PREFAB_ASSET_TYPE',spec['sourceId'],'Native Prefab/Variant asset type differs from the source relation'))
                if instruction.get('sourcePrefabReadback')=='native-layout-settled-v1':
                    saved_nodes={n['sourceId']:n for n in actual.get('nodes',[])}
                    if actual.get('savedReloaded') is not True or actual.get('geometryPhase')!='native-layout-settled-v1' or set(saved_nodes)!=set(spec['nodes']):
                        diagnostics.append(diagnostic('SOURCE_PREFAB_GEOMETRY_NOT_VERIFIED',spec['sourceId'],'Saved native hierarchy geometry evidence is absent'))
                    prefab_expected,ui_gaps=expectations(instruction,actual.get('nativeInitialNodes'),spec['sourceId'],[expected_nodes[sid]for sid in spec['nodes']]);diagnostics.extend(ui_gaps)
                    prefab_expected={n['sourceId']:n for n in prefab_expected}
                    for sid in spec['nodes']:
                        source=prefab_expected[sid];saved=saved_nodes.get(sid,{})
                        if not node_geometry_matches(saved,source,instruction.get('transformReadback')=='full-local-v1'):
                            diagnostics.append(diagnostic('SOURCE_PREFAB_GEOMETRY_MISMATCH',sid,'Independent saved prefab differs: '+target))
                    if actual.get('referencesVerified') is not True or actual.get('referenceFailures'):
                        diagnostics.append(diagnostic('SOURCE_PREFAB_REFERENCE_MISMATCH',spec['sourceId'],'Saved component references differ: '+str(actual.get('referenceFailures'))))
            for prefab in instruction.get('sourcePrefabs',[]):
                source_nodes=set(prefab['nodes']);specs=[c for c in instruction['components']if c.get('node')in source_nodes]
                diagnostics.extend(verify_numeric(specs,actual_prefabs.get(prefab['sourceId'],{}).get('numericCodeBindings'),'unity',prefab['sourceId']))
                from ..prefab_static_readback import verify as verify_static
                static_observed=actual_prefabs.get(prefab['sourceId'],{})
                from ..prefab_static_completion_readback import verify_prefab as verify_completion
                diagnostics.extend(verify_completion(instruction,specs,static_observed,'unity',prefab['sourceId']))
                from ..prefab_static_progress import verify as verify_progress
                diagnostics.extend(verify_progress(specs,static_observed.get('staticProgressFields'),'unity',prefab['sourceId']))
                diagnostics.extend(verify_static(specs,static_observed.get('staticFieldBindings'),static_observed.get('guid'),'unity',prefab['sourceId']))
                if instruction.get('behaviorBindingReadback')=='persistent-source-fields-v1':
                    from ..prefab_target_behaviors import verify_bindings
                    observed=actual_prefabs.get(prefab['sourceId'],{})
                    diagnostics.extend(verify_bindings(specs,observed.get('behaviorBindings'),observed.get('guid'),'unity',prefab['sourceId']))
            for spec in instruction['assets']:
                if spec['kind']=='cc.JsonAsset':
                    actual=json_assets.get(spec['id'],{})
                    if actual.get('textSha256')!=fingerprint(root/spec['path']) or not actual.get('guid'):
                        diagnostics.append(diagnostic('JSON_READBACK_MISMATCH',spec['path'],'Native TextAsset text/identity differs or is absent'))
            from ..unity_mask_clipping_readback import verify as verify_mask_clipping
            diagnostics.extend(verify_mask_clipping(instruction,rb,candidate=root,
                owned_files={row['path']:row for row in m['files']}))
            by_id={s['id']:s for s in rb.get('sprites',[])}
            for spec in instruction['textures']:
                actual=by_id.get(spec['id'])
                meta=(root/(spec['path']+'.meta')).read_text() if (root/(spec['path']+'.meta')).is_file() else ''
                if not actual or actual.get('size')!=spec['size'] or actual.get('border')!=spec['border'] or actual.get('guid','') not in meta or not actual.get('fileId'):
                    diagnostics.append(diagnostic('SPRITE_READBACK_MISMATCH',spec['path'],'Native sprite size/border/GUID/fileID mismatch'))
            by_node={n['sourceId']:n for n in rb.get('nodes',[])}
            for spec in scene_expected:
                actual=by_node.get(spec['sourceId'])
                if not node_geometry_matches(actual,spec,instruction.get('transformReadback')=='full-local-v1'):
                    diagnostics.append(diagnostic('NODE_READBACK_MISMATCH',spec['sourceId'],'Saved RectTransform differs from plan'))
            if rb.get('editableRoundtrip')is not True:
                diagnostics.append(diagnostic('EDITABLE_ROUNDTRIP_NOT_VERIFIED',standard.locate(m,'editableProbe'),'Native edit/save/reopen proof is absent or failed'))
            by_font={f['id']:f for f in rb.get('fonts',[])}
            for spec in instruction.get('bitmapFonts',[]):
                actual=by_font.get(spec['id'])
                if not actual or actual.get('glyphCount',0)<len(spec['glyphs']) or not close(actual.get('pointSize'),spec['pointSize']) or not close(actual.get('lineHeight'),spec['lineHeight']):
                    diagnostics.append(diagnostic('BITMAP_FONT_READBACK_MISMATCH',spec['id'],'Saved static font glyph count or metrics differ'))
                if spec.get('atlasGuid') and (not actual or actual.get('atlasGuid')!=spec['atlasGuid'] or actual.get('materialAtlasGuid')!=spec['atlasGuid']):
                    diagnostics.append(diagnostic('BITMAP_ATLAS_READBACK_MISMATCH',spec['id'],'Saved font and material must reference the original atlas GUID'))
            by_label={l['sourceId']:l for l in rb.get('labels',[])}
            source_sizing=source_ttf_shrink_evidence(instruction)
            from ..cocos_native_finish import font_evidence
            extra_fonts=font_evidence(root,instruction,readback_path)
            node_specs={n['sourceId']:n for n in instruction['nodes']}
            for spec in instruction['components']:
                if spec['type']!='cc.Label' or not spec['convertible']:continue
                actual=by_label.get(spec['sourceId']);font=by_font.get(spec.get('font'))
                if not label_font_matches(spec,actual,font,extra_fonts.get(spec['sourceId']),source_sizing.get(spec['sourceId'])):
                    diagnostics.append(diagnostic('LABEL_FONT_READBACK_MISMATCH',spec['sourceId'],'Saved text/font/GUID/glyph coverage differs; no fallback accepted'))
                    continue
                if spec.get('bitmapProbe'):
                    geometry=by_node.get(spec['node'],{});node=node_specs[spec['node']]
                    size=geometry.get('size',node['size']);pivot=geometry.get('pivot',node['anchor'])
                    source_font=next(f for f in instruction['bitmapFonts']if f['id']==spec['font'])
                    probe,line_size,aligned_width=bitmap_label_probe(spec,source_font,actual['fontSize']);glyphs=actual.get('glyphBounds',[])
                    if instruction.get('glyphReadback')=='native-quad-padding-v1':
                        from .common import native_ink_box
                        try:
                            if actual.get('geometryProbe') not in ('saved-node','isolated-active-clone'):raise ValueError('No native geometry probe')
                            glyphs=[native_ink_box(g) for g in glyphs]
                        except (ValueError,KeyError):
                            diagnostics.append(diagnostic('BITMAP_INK_PROOF_MISSING',spec['sourceId'],'Native quad padding/geometry proof absent or invalid'))
                            continue
                    expected=[b for b in probe['boxes'] if b['width']>0 and b['height']>0]
                    if len(glyphs)!=len(expected):
                        diagnostics.append(diagnostic('BITMAP_QUAD_READBACK_MISMATCH',spec['sourceId'],'Visible glyph count differs'))
                        continue
                    origin_x=-pivot[0]*size[0]+spec['horizontalAlign']*.5*(size[0]-aligned_width)
                    origin_top=(1-pivot[1])*size[1]-spec['verticalAlign']*.5*(size[1]-line_size)
                    for actual_glyph,box in zip(glyphs,expected):
                        intended=dict(left=origin_x+box['x'],top=origin_top-box['top'],width=box['width'],height=box['height'])
                        if actual_glyph.get('unicode')!=box['unicode'] or any(not close(actual_glyph.get(key),value,.03) for key,value in intended.items()):
                            diagnostics.append(diagnostic('BITMAP_QUAD_READBACK_MISMATCH',spec['sourceId'],'Glyph origin/size differs from source metric probe'))
                            break
            if instruction.get('textLineBoxReadback')=='native-cocos-ttf-line-box-v1':
                label_rows={r['sourceId']:r for r in rb.get('labels',[])};bitmap_ids={f['id']for f in instruction.get('bitmapFonts',[])}
                for c in instruction['components']:
                    if not(c.get('convertible')and c['type']=='cc.Label'and c['overflow']in(0,3)and c['font']not in bitmap_ids):continue
                    row=label_rows.get(c['sourceId'],{});node=by_node.get(c['node'],{});line_height=c['lineHeight']or c['fontSize']
                    if (row.get('lineBoxPresent')is not True or 'NativeTextLineBox'not in node.get('componentTypes',[])or
                        not close(row.get('lineBoxLineHeight'),line_height)or not close(row.get('lineBoxExtra'),.26)):
                        diagnostics.append(diagnostic('NATIVE_TTF_LINEBOX_MISSING',c['sourceId'],'Saved native TTF line box/leading differs'))
                    current=c['node'];active=c['enabled']
                    while current is not None:
                        n=expected_nodes[current];active=active and n['active'];current=n['parent']
                    if active and(row.get('lineBoxActive')is not True or not close((node.get('size')or[0,0])[1],row.get('lineBoxHeight'),.05)):
                        diagnostics.append(diagnostic('NATIVE_TTF_LINEBOX_HEIGHT',c['sourceId'],'Active native text height differs from its measured typographic line box'))
            view_refs={v['sourceId']:v for v in rb.get('viewReferences',[])}
            for spec in instruction['components']:
                if spec['convertible'] and spec['type'] in ('cc.Sprite','cc.Label','cc.Button'):
                    binding=view_refs.get(spec['sourceId'])
                    if not binding or not binding.get('bound') or binding.get('index',-1)<0 or not binding.get('prefabFileId'):
                        diagnostics.append(diagnostic('VIEW_REFERENCE_READBACK_MISMATCH',spec['sourceId'],'Serialized native View reference or fileID is missing'))
            for required in (standard.locate(m,'previewPrefab'),standard.locate(m,'previewScene')):
                if required not in native:
                    diagnostics.append(diagnostic('NATIVE_ARTIFACT_MISSING',required,'No saved native artifact hash'))
            from ..assets.animation import verify_native
            diagnostics.extend(verify_native(instruction.get('animations',[]),rb.get('animations',[]),native))
            editor='partial' if rb.get('diagnostics') else 'pass'
            # These diagnostics are emitted only after exact static native checks;
            # keep their unexecuted dynamic behavior separate from Editor failure.
            dynamic_boundaries={'SPINE_DYNAMIC_BEHAVIOR_INCOMPLETE','ANIMATION_DYNAMIC_CURVES_NOT_LOWERED'}
            if any(d['code']not in dynamic_boundaries|{'EDITOR_NOT_RUN'} for d in diagnostics):editor='fail'
    for item in m['files']:
        path=inside(root,item['path'])
        expected=native.get(item['path']) if level=='editor' and item['path'].endswith('.meta') else item['sha256']
        if expected is None: expected=item['sha256']
        changed=not path.is_file() or fingerprint(path)!=expected
        if changed and level=='editor' and item['path']=='ProjectSettings/ProjectVersion.txt' and path.is_file():
            from .common import normalized_unity_version
            changed=not normalized_unity_version(read(path),'6000.6.2f1')
        if changed:
            diagnostics.append(diagnostic('GENERATED_FILE_CHANGED',item['path'],'Missing or modified generated file'))
    from ..identities import verify as verify_assigned
    identity_gaps=verify_assigned(root,m);diagnostics.extend(identity_gaps)
    if identity_gaps and editor in ('pass','partial'):editor='fail'
    guids={}
    for path in (root/'Assets').rglob('*.meta'):
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.startswith('guid: '):
                value=line[6:]
                if value in guids:
                    diagnostics.append(diagnostic('DUPLICATE_TARGET_GUID',str(path.relative_to(root)),'GUID duplicates '+guids[value]))
                guids[value]=str(path.relative_to(root))
    instruction=load(read(root/standard.locate(m,'importPlan'),max_bytes=128*1024*1024),max_nodes=8_000_000)
    for item in instruction['textures']+instruction['assets']:
        if not inside(root,item['path']).is_file():
            diagnostics.append(diagnostic('TARGET_REFERENCE_MISSING',item['path'],'Import resource does not exist'))
    adapter=root/standard.locate(m,'importer')
    if not adapter.is_file() or list((root/'Assets').rglob('ir.json')):
        diagnostics.append(diagnostic('TARGET_LAYOUT_INVALID','Assets','Missing Editor adapter or runtime IR found'))
    if standard.current(m):
        from ..layout.verify import scan
        diagnostics.extend(scan([f['path'] for f in m['files']]))
    from ..unity_verification_contract import coverage_readback,statuses,deduplicate_diagnostics
    if level=='editor' and rb is not None:
        from ..prefab_component_coverage import assess
        source_diagnostics=instruction.get('sourceDiagnostics',m.get('diagnostics',[]))
        coverage_plan=dict(instruction,diagnostics=source_diagnostics)
        if instruction.get('staticSpineContinuationJson'):
            coverage_plan['staticSpineContinuation']=load(instruction['staticSpineContinuationJson'].encode('utf-8'))
        normalized_readback=coverage_readback(rb,spine_coverage)
        from ..unity_static_family_coverage import merge_sort,gate_layout
        try:normalized_readback=merge_sort(normalized_readback,instruction,rb,queue_verified=not sort_gaps)
        except ValueError as error:diagnostics.append(diagnostic('STATIC_SORT_COVERAGE_INVALID','staticSortQueue',str(error)))
        normalized_readback,family_proofs=gate_layout(normalized_readback,instruction,rb)
        family_proofs.update(text_family_proofs)
        if rendering_fragment is not None:
            coverage_plan['staticSpineRendering']=rendering_fragment
        if rendering_receipt is not None:
            from ..unity_spine_rendering_coverage import merge as merge_rendering
            try:normalized_readback=merge_rendering(normalized_readback,rendering_fragment,rendering_receipt)
            except ValueError as error:
                diagnostics.append(diagnostic('STATIC_SPINE_RENDERING_COVERAGE_INVALID','Analysis/Readback/SpineRendering',str(error)))
        coverage=assess(coverage_plan,normalized_readback,'unity')
        from ..unity_scroll_evidence import verify as verify_scroll_static
        scroll_static=verify_scroll_static(instruction,rb,coverage)
        diagnostics.extend(scroll_static['diagnostics'])
        family_proofs={**locals().get('family_proofs',{}),**scroll_static['familyProofs']}
        diagnostics.extend(native_diagnostics(raw_native_diagnostics))
        diagnostics.extend(coverage.get('diagnostics',[]))
    diagnostics=deduplicate_diagnostics(diagnostics)
    from ..unity_diagnostic_resolution import reconcile
    reconciliation=reconcile(diagnostics,coverage,family_proofs=locals().get('family_proofs',{}))
    diagnostics=reconciliation['diagnostics']
    dimensions=statuses(editor,diagnostics,coverage,level)
    out=new_output(output,[root])
    result=dict(schemaVersion=1,toolVersion=__version__,candidateManifestSha256=fingerprint(root/'manifest.json'),
                diagnostics=diagnostics,staticValidation='conflict' if any(d['code'] in ('GENERATED_FILE_CHANGED','DUPLICATE_TARGET_GUID','TARGET_REFERENCE_MISSING','TARGET_LAYOUT_INVALID','NATIVE_FILE_CHANGED','ASSIGNED_NATIVE_IDENTITY_CHANGED','LAYOUT_FORBIDDEN_NAME') for d in diagnostics) else 'pass',
                componentCoverage=coverage,nativeDiagnostics=raw_native_diagnostics,
                diagnosticResolution=reconciliation['summary'],
                savedGeneratedMetaReadback=saved_meta_observations,**dimensions,
                visualValidation='not_run',businessValidation='not_run')
    from ..unity_verification_contract import unresolved_diagnostics
    current_diagnostics=unresolved_diagnostics(diagnostics,coverage)
    result['currentDiagnosticCounts']={key:len(rows)for key,rows in current_diagnostics.items()}
    result['verificationScope']=('resource-gallery' if locals().get('instruction',{}).get('galleryOnly')is True else 'saved-source-node-subset')if level=='editor' else 'generated-files'
    write_json(out/'verification.json',result)
    completion_blockers=list(current_diagnostics['blocking'])
    required=('staticValidation','nativeStaticValidation','staticPresentationValidation')if level=='editor' else('staticValidation',)
    completion_blockers.extend(key for key in required if result.get(key)!='pass')
    return finish(out,result,blocking_diagnostics=completion_blockers)


def handoff(candidate, output):
    from ..sources.containers import fingerprint
    root=safe(candidate)
    package=load(read(find_analysis(root,'handoff.json')))
    out=new_output(output,[root])
    package['candidateManifestSha256']=fingerprint(root/'manifest.json')
    write_json(out/'handoff.json',package)
    lines=['# AI接续工作包','', '这是候选工程，Editor/原版画面对照/业务分别按验证记录处理。',
           '仅修改目标的 Manual/manual 区；生成区需要明确解除所有权后才可手改。','']
    for task in package['tasks']:
        lines.extend(['## '+task.get('moduleName',task.get('module','Module'))+' / '+task.get('rootCause',task['taskId']),'',
                      '任务：'+task['taskId'],
                      '来源：'+str(task['sourceRefs']),
                      '目标：'+', '.join(task['generatedTargets']),
                      '根因：'+task.get('rootCause','unknown')+'；详细诊断 '+str(len(task['gaps']))+' 条，见同目录 handoff.json。',
                      '摘要：'+'; '.join(dict.fromkeys(g['code'] for g in task['gaps'])),
                      '验证：'+', '.join(task['verificationScope']),''])
    (out/'HANDOFF.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return finish(out,dict(schemaVersion=1,diagnostics=[],tasks=len(package['tasks']),toolVersion=__version__))
