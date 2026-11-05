"""Creator 3.8.8 candidate asset emitter; native objects are saved only by its Editor."""
from importlib.resources import files
from pathlib import Path
import uuid,re
from .. import __version__
from ..io import safe, inside, read, load, sha, write_json, new_output, finish, diagnostic, stage_document, stage_bytes,stage_manifest
from ..sources.compiled import fail
from .common import input_ir, tasks,native_color_nodes
from ..layout import standard
from ..layout.standard import VERSION
from ..layout.standard import find_analysis

PROFILE='cocos-3.8.8'


def _validate_extension_dependencies(extension, static_time_materials=False, sprite_outline=False):
    """Check emitted relative module names before starting the native Editor."""
    extension=Path(extension).resolve()
    for script in extension.glob('*.js'):
        for name in re.findall(r'''\brequire\(\s*['"](\.[^'"]+)['"]\s*\)''',script.read_text(encoding='utf-8')):
            dependency=(script.parent/name).resolve()
            if not dependency.is_relative_to(extension):
                fail('CREATOR_EXTENSION_DEPENDENCY_ESCAPE',str(script),name)
            if dependency.is_file() or (not dependency.suffix and any(
                    candidate.is_file() for candidate in (dependency.with_suffix('.js'),dependency.with_suffix('.json'),dependency/'index.js'))):
                continue
            # The broker has a source-tree-only fallback for direct Node tests.
            if (script.name=='owned-import-undo.js' and name=='./CreatorEditorUndoDiagnostics.js' and
                    (extension/'editor-undo-diagnostics.js').is_file()):
                continue
            if (script.name=='owned-build-scene-teardown.js' and name=='./CreatorSavedSceneScope.js' and
                    (extension/'creator-saved-scene-scope.js').is_file()):
                continue  # source-tree Node-test fallback; emitted canonical module is required
            if (script.name=='owned-build-scene-teardown.js' and name=='./CreatorOwnedImportUndo.js' and
                    (extension/'owned-import-undo.js').is_file()):
                continue
            # These imports are invoked only for a declared static-time material plan.
            if (not static_time_materials and script.name in ('main.js','scene.js','prefab.js') and name=='./static-time-materials.js'):
                continue
            if (not sprite_outline and script.name in ('scene.js','prefab.js') and
                    name in ('./sprite-outline-material-bindings.js','./sprite-outline-importer.js')):
                continue
            fail('CREATOR_EXTENSION_DEPENDENCY_MISSING',str(script),name)


def identity(namespace,sid):
    return str(uuid.uuid5(uuid.NAMESPACE_URL,'monkey/'+namespace+'/creator-3.8.8/'+sid))


def meta(uid,importer,version,user=None):
    return dict(ver=version,uuid=uid,importer=importer,imported=False,files=[],subMetas={},userData=user or {})


def bitmap_text(font,atlas_name,face="MonkeySourceBitmap"):
    # Normalized sourceRect is top-origin; metrics stores the logical point-size bearing.
    lines=[f'info face="{face}" size={font["pointSize"]} bold=0 italic=0 unicode=1',
           f'common lineHeight={font["lineHeight"]} base={font["pointSize"]} scaleW={font["atlasSize"][0]} scaleH={font["atlasSize"][1]} pages=1 packed=0',
           f'page id=0 file="{atlas_name}"',f'chars count={len(font["glyphs"])}']
    for g in font['glyphs']:
        x,y,w,h=g['sourceRect'];_,_,bearing_x,bearing_y,advance=g['metrics']
        lines.append(f'char id={g["unicode"]} x={x} y={y} width={w} height={h} xoffset={bearing_x} yoffset={font["pointSize"]-bearing_y} xadvance={advance} page=0 chnl=15')
    lines.append(f'kernings count={len(font["kernings"])}')
    lines += [f'kerning first={k["first"]} second={k["second"]} amount={k["advance"]}' for k in font['kernings']]
    return ('\n'.join(lines)+'\n').encode()


def plan(ir_path,namespace,output,bindings_path=None,animation_selection=None,layout=None,spine_bindings=None,expected_spine_bindings=None,spine_resources=None,static_source_bundle=None,expected_static_source_bundle=None):
    path,ir,bindings,receipt,resource,resolve=input_ir(ir_path,bindings_path)
    from ..prefab_static_pipeline import ensure_static_fields
    ensure_static_fields(ir)
    from ..prefab_richtext_pipeline import enrich as enrich_richtext
    enrich_richtext(ir)
    from ..prefab_static_button import enrich as enrich_buttons
    enrich_buttons(ir)
    from ..prefab_static_pipeline import enrich_declarations
    enrich_declarations(ir,static_source_bundle,expected_static_source_bundle)
    from .. import prefab_spine_pipeline as spine_pipeline
    spine_profile=spine_pipeline.load_binding(ir,path,spine_bindings,expected_spine_bindings,spine_resources)
    spine_components={c['sourceComponentId']:c for c in spine_profile['record']['components']}if spine_profile else {}
    if ir.get('sourceProfile')in ('generic-image-resources-v1','egret-custom-resource-plist-v1'):fail('SOURCE_TARGET_UNSUPPORTED',str(ir_path),'Non-Cocos sources target Unity 6 only')
    from ..layout import LayoutPlanner
    overrides,overrides_sha=layout or ({},None)
    naming=LayoutPlanner('creator',ir.get('sourceNames'),overrides)
    planned={'sprite':'sprite','ttf':'cc.TTFFont','json':'cc.JsonAsset','audio':'cc.AudioClip'}
    # Creator trims natively from the original image, so no untrimmed duplicate is emitted (PROJECT-SPEC 5.4).
    naming.reserve([(f['sourceId'],'sprite','.png','',None,None) for f in ir['spriteFrames']]
        +[(a['sourceId'],a['kind'],Path(a['path']).suffix if a['kind']=='cc.AudioClip' else {'cc.TTFFont':'.ttf','cc.JsonAsset':'.json'}[a['kind']],'',None,None) for a in ir['assets'] if a['kind'] in ('cc.TTFFont','cc.JsonAsset','cc.AudioClip')]
        +[r for f in ir.get('bitmapFonts',[]) for r in ((f['sourceId']+'@atlas','bitmap-atlas','.png','',None,None),(f['sourceId'],'bitmap','.fnt','',None,None))])
    diagnostics=list(ir['diagnostics']);assets=[];copies=[]
    diagnostics.extend(spine_pipeline.material_origin_diagnostics(spine_profile))
    def add(sid,relative,kind,suffix,**fields):
        raw=resource(relative);uid=identity(namespace,sid);target=naming.path(sid,fields.get('role')=='bitmap-atlas-page' and 'bitmap-atlas' or planned[kind],suffix)
        item=dict(sourceId=sid,uuid=uid,path=target,kind=kind,sha256=sha(raw),**fields)
        assets.append(item);copies.append(dict(source=relative,target=target,sha256=sha(raw)))
        return item
    for f in ir['spriteFrames']:
        # Already physically unrotated pixels; no raw atlas rotation is guessed in target metadata.
        add(f['sourceId'],f['originalImage'],'sprite','.png',size=f['rect'][2:4],trimOrigin=f['trimOrigin'],originalSize=f['originalSize'],
            offset=f['offset'],border=f['capInsets'],subresource='spriteFrame')
    for a in ir['assets']:
        if a['kind']=='cc.TTFFont':add(a['sourceId'],a['path'],'ttf','.ttf',fontCoverage=a.get('fontCoverage'))
        elif a['kind']=='cc.JsonAsset':add(a['sourceId'],a['path'],'json','.json')
        elif a['kind']=='cc.AudioClip':add(a['sourceId'],a['path'],'audio',Path(a['path']).suffix)
        else:diagnostics.append(diagnostic('ASSET_HANDOFF',a['sourceId'],'Creator native subset has no mapping for '+a['kind'],a['sourceId']))
    font_by_id={}
    for f in ir.get('bitmapFonts',[]):
        atlas=add(f['sourceId']+'@atlas',f['atlasImage'],'sprite','.png',size=f['atlasSize'],originalSize=f['atlasSize'],
                  offset=[0,0],border=[0,0,0,0],subresource='spriteFrame',role='bitmap-atlas-page')
        uid=identity(namespace,f['sourceId']);target=naming.path(f['sourceId'],'bitmap','.fnt')
        raw=bitmap_text(f,Path(atlas['path']).name,Path(target).stem)
        assets.append(dict(sourceId=f['sourceId'],uuid=uid,path=target,kind='bitmap',sha256=sha(raw),
                           atlas=atlas['sourceId'],pointSize=f['pointSize'],glyphCount=len(f['glyphs']),kerningCount=len(f['kernings'])))
        copies.append(dict(source=None,target=target,sha256=sha(raw),text=raw.decode()))
        font_by_id[f['sourceId']]=f
    asset_by_id={a['sourceId']:a for a in assets};components=[]
    supported={'cc.Sprite','cc.Label','cc.Widget','cc.Mask','cc.ScrollView','cc.Layout','cc.Button','cc.BlockInputEvents','cc.LabelOutline','cc.ProgressBar'}
    materials={m['sourceId'] for m in ir.get('materials',[]) if m['nativeRole']=='standard-ugui'}
    from .. import prefab_material_pipeline as material_pipeline
    material_profile,material_gaps=material_pipeline.discover(ir,path)
    diagnostics.extend(material_gaps)
    node_ids={n['sourceId'] for n in ir['nodes']};source_nodes={n['sourceId']:n for n in ir['nodes']}
    for src in ir['components']:
        c=dict(src);sid=c['sourceId'];c['convertible']=c['type'] in supported and c.get('node') in node_ids
        if sid in spine_components:
            spine_row=spine_components[sid];material_proof=spine_row.get('creatorMaterialBinding')or{}
            exact_builtin=(material_proof.get('contract')=='cocos24-builtin-spine-material-v1' and material_proof.get('targetMaterialUuid')=='default-spine-material'
                           and c.get('materials') in ([material_proof.get('sourceMaterialReferenceSourceId')],[material_proof.get('sourceMaterialSourceId')]))
            c.update(spineBinding=spine_row,nativeType='sp.Skeleton',convertible=c.get('node')in node_ids and (not c.get('materials')or exact_builtin))
            if c.get('materials')and not exact_builtin:
                diagnostics.append(diagnostic('SPINE_MATERIAL_HANDOFF',sid,'Exact source Spine material requires its own verified native profile',sid))
            diagnostics.append(diagnostic('SPINE_RUNTIME_UNVERIFIED',sid,'Native component binding; exact animation, dynamic resource assignment and visual checks remain',sid))
            components.append(c);continue
        from ..prefab_target_behaviors import binding as behavior_binding
        native_behavior=behavior_binding(c,'creator',namespace)
        if native_behavior is not None:
            c.update(behaviorBinding=native_behavior,nativeType=native_behavior['typeName'],
                     convertible=c.get('node') in node_ids and not c.get('materials'))
            diagnostics.append(diagnostic('BEHAVIOR_RUNTIME_UNVERIFIED',sid,'Source-bound native script/fields; behavioral gaps and runtime checks remain',sid))
            components.append(c);continue
        if c.get('supported') is False:
            c['convertible']=False;c['nativeType']=None
            diagnostics.append(diagnostic('SOURCE_COMPONENT_PROFILE_HANDOFF',c['sourceId'],'Source component semantics are not implemented for this profile',c['sourceId']))
            components.append(c);continue
        if sid in bindings:c.update(font=bindings[sid]['font'],bold=bindings[sid].get('syntheticBold',False))
        for field in ['font','spriteFrame']:
            if field in c:c[field]=resolve(c[field])
        def gap(code,message):
            c['convertible']=False;diagnostics.append(diagnostic(code,sid,message,sid))
        if material_pipeline.supported_component(c,material_profile,resolve):
            c['nativeMaterialSourceId']=material_profile['spec']['materialSourceId']
        elif material_pipeline.identity_text_component(c,material_profile,resolve):
            c['nativeTextMaterialIdentitySourceId']=material_profile['spec']['materialSourceId'];c['nativeTextMaterialPolicy']='source-proven-identity-default-only'
        elif any(resolve(m) not in materials for m in c.get('materials',[])):gap('CUSTOM_MATERIAL_HANDOFF','Unrecognized source material')
        if c['type']=='cc.Sprite':
            if c['mode'] not in (0,1,2) or c['sizeMode'] not in (0,1,2):gap('SPRITE_SUBSET_UNSUPPORTED','Unknown mode')
            if c.get('spriteFrame') is not None and c['spriteFrame'] not in asset_by_id:gap('MISSING_SPRITE','SpriteFrame absent')
            if c.get('spriteFrame') is None:
                c['needsSpriteBinding']=True;diagnostics.append(diagnostic('SOURCE_SPRITE_UNBOUND',sid,'Keep native Sprite disabled pending real binding',sid))
            frame=asset_by_id.get(c.get('spriteFrame'))
            if c['convertible']:c.update(nativeSizeMode=c['sizeMode'],sizingPolicy='native-sprite-sizing-v1')
        elif c['type']=='cc.Label':
            font=asset_by_id.get(c.get('font'))
            source_system = c.get('systemFont') is True and c.get('font') is None and bool(c.get('fontFamily'))
            if source_system:
                c['nativeSystemFont']=True
                diagnostics.append(diagnostic('SYSTEM_FONT_PLATFORM_UNVERIFIED',sid,'Preserved source font family; actual platform fallback and visual equivalence require native evidence',sid))
            elif not font or font['kind'] not in ('ttf','bitmap'):gap('FONT_NOT_CONVERTIBLE','No matching original font; no system fallback')
            elif font['kind']=='ttf':
                from ..assets.ttf import missing
                if missing(font['fontCoverage'],c['text']):gap('SOURCE_FONT_GLYPHS_MISSING','Missing original font glyphs')
            else:
                available={g['unicode'] for g in font_by_id[c['font']]['glyphs']}
                if any(ord(ch) not in available for ch in c['text'] if ch not in '\r\n'):gap('SOURCE_FONT_GLYPHS_MISSING','Bitmap lacks glyphs')
                c['bold']=False
            if c['overflow']not in(0,1,2,3):gap('LABEL_SUBSET_UNSUPPORTED','Unknown overflow mode')
            if c['convertible']:c.update(nativeOverflow=c['overflow'],sizingPolicy='native-label-sizing-v1')
            diagnostics.append(diagnostic('CREATOR_TEXT_METRICS_NOT_VERIFIED',sid,'Original font selected; cross-version glyph layout needs real source comparison',sid))
        elif c['type']=='cc.Widget':
            if c['flags']&~63 or c.get('alignMode',1)not in(0,1,2):gap('WIDGET_SUBSET_UNSUPPORTED','Unknown flags or align policy')
            c.setdefault('center',[0,0]);c.setdefault('centerAbsolute',[True,True])
        elif c['type']=='cc.Mask':
            if c['maskType']!=0 or c['inverted']:gap('MASK_SUBSET_UNSUPPORTED','Only plain rectangle')
        elif c['type']=='cc.ScrollView':
            if c.get('content') not in {n['sourceId'] for n in ir['nodes']}:gap('MISSING_SCROLL_CONTENT','Scroll content absent')
            c['staticNativeBinding']=True;c['dynamicScrollingVerified']=False
            diagnostics.append(diagnostic('SCROLL_PHYSICS_NOT_VERIFIED',sid,'Native axes and content retained for static recovery; dynamic scrolling remains unverified',sid))
        elif c['type']=='cc.Button':
            static_color=c.get('staticButtonBinding',{}).get('renderReady') and c.get('target') in (node_ids|{None})
            if not static_color and (c['transition'] not in (0,3) or c['target'] not in (None,c['node'])):gap('BUTTON_SUBSET_UNSUPPORTED','Unsupported button transition/target')
            if c['events']:diagnostics.append(diagnostic('BUTTON_BUSINESS_UNBOUND',sid,'Original click handlers remain native AI work',sid))
        elif c['type']=='cc.LabelOutline':
            if not any(x['type']=='cc.Label' and x['node']==c['node'] for x in ir['components']):gap('MISSING_OUTLINE_LABEL','Outline has no Label')
        elif c['type']=='cc.Layout':
            if c['layoutType']not in(0,1,2,3)or c['resize']not in(0,1,2)or c.get('constraint',0)not in(0,1,2):gap('LAYOUT_SUBSET_UNSUPPORTED','Unknown native Layout mode')
        if not c['convertible']:diagnostics.append(diagnostic('COMPONENT_HANDOFF',sid,'Unsupported native mapping: '+c['type'],sid))
        c['nativeType']=('cc.Label' if c['type']=='cc.LabelOutline' else c['type']) if c['convertible'] else None;components.append(c)
    for c in components:
        if c['type']=='cc.LabelOutline' and c['convertible'] and not any(x['type']=='cc.Label' and x['node']==c['node'] and x['convertible'] for x in components):
            c['convertible']=False;c['nativeType']=None
            diagnostics.append(diagnostic('MISSING_OUTLINE_LABEL',c['sourceId'],'Label dependency could not be converted',c['sourceId']))
    from .progress import configure_progress
    diagnostics.extend(configure_progress(components,source_nodes))
    for c in components:
        if c['type']=='cc.ProgressBar' and not c['convertible']:c['nativeType']=None
    from .prefabs import plan_prefabs,native_relationships
    prefabs,prefab_gaps=plan_prefabs(ir,components)
    diagnostics.extend(prefab_gaps)
    prefabs,instances=native_relationships(ir,prefabs,components)
    roots={p['sourceId']:p['root']for p in prefabs}
    for link in instances:
        if roots.get(link['owner'])==link['root']:
            fail('CREATOR_ROOT_PREFAB_INHERITANCE_PENDING',link['root'],'Root inheritance needs a dedicated Creator asset contract; nested instances are supported, Unity emits a native Variant')
    by_node={n['sourceId']:n for n in ir['nodes']}
    naming.reserve([(prefab['sourceId'],'prefab','.prefab','',None,None) for prefab in prefabs])
    for prefab in prefabs:
        prefab['path']=naming.path(prefab['sourceId'],'prefab','.prefab')
        prefab['rootNamePolicy']='creator-asset-basename-v1'
        prefab['sourceRootName']=by_node[prefab['root']]['name']
        prefab['nativeRootName']=Path(prefab['path']).stem
    from .common import reject_layout_conflicts
    diagnostics.extend(reject_layout_conflicts(components))
    from ..assets.animation import plan_clips
    animations,animation_gaps=plan_clips(ir,namespace,PROFILE,animation_selection,naming)
    if animation_selection:
        unselected={c['sourceId'] for c in ir.get('animationClips',[]) if c['sourceId'] not in animation_selection}
        diagnostics=[d for d in diagnostics if d.get('sourceId') not in unselected]
    diagnostics.extend(animation_gaps)
    out=new_output(output,[path.parent]);(out/'resources').mkdir()
    for i,c in enumerate(copies):
        raw=c.pop('text',None)
        raw=raw.encode() if raw is not None else resource(c['source'])
        dest=f'resources/{i:04d}'+Path(c['target']).suffix;(out/dest).write_bytes(raw);c['source']=dest
    from ..creator_geometry import renderer_budget
    render_budget,tile_gaps=renderer_budget(ir['nodes'],components,assets)
    diagnostics.extend(diagnostic('TILED_GEOMETRY_UNSUPPORTED',sid,message,sid) for sid,message in tile_gaps)
    from ..prefab_target_behaviors import prepare as prepare_behaviors
    behavior_scripts=prepare_behaviors(ir,path.parent,'creator',namespace,out)
    from ..prefab_static_carriers import prepare as prepare_static
    static_fields=prepare_static([c for c in components if c.get('staticFieldSnapshot')], 'creator', 'Monkey.StaticFields.N'+sha(namespace.encode())[:12], out)
    for c in components:
        if c['sourceId'] in static_fields['bindings']:c['staticFieldBinding']=static_fields['bindings'][c['sourceId']]

    material_binding=material_pipeline.prepare(material_profile,'creator',out)
    spine_binding=spine_pipeline.prepare(spine_profile,out)
    if material_binding:
        material_binding['spec']['spriteBindings']=[dict(sourceId=c['sourceId'])for c in components if c.get('convertible')and c.get('nativeMaterialSourceId')]
    result=dict(schemaVersion=1,toolVersion=__version__,targetProfile=PROFILE,namespace=namespace,projectLayout=VERSION,layoutOverridesSha256=overrides_sha,
        staticFieldScripts=static_fields['scripts'],behaviorScripts=behavior_scripts,materialBinding=material_binding,spineBinding=spine_binding,
        scopeMode=ir.get('scopeMode','asset-selection'),
        sourceIrSha256=sha(stage_bytes(path)),sourceManifestSha256=ir['sourceManifestSha256'],sourceManifestPath=ir.get('sourceManifestPath'),
        sourceRoots=ir.get('sourceRoots',{}),sourceLocations=ir.get('sourceLocations',{}),bindings=receipt,
        designSize=[750,1334],rendererBudget=render_budget,assets=assets,copies=copies,animations=animations,sourcePrefabs=prefabs,prefabInstances=instances,naming=naming.report(),nodes=native_color_nodes(ir['nodes'],components),components=components,
        diagnostics=diagnostics,editorValidation='not_run',subresourceValidation='pending-native-import')
    if any(c['type']in('cc.Toggle','cc.ToggleContainer')for c in components):
        from ..prefab_static_toggle import prepare as prepare_toggle
        toggle=prepare_toggle(ir['sourceManifestPath'],result,'creator',out/'toggle-source')
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
    write_json(out/'plan.json',result);return finish(out,result)


def export(plan_path,output):
    path=safe(plan_path);p=stage_document(path)
    if p.get('targetProfile')!=PROFILE or p.get('schemaVersion')!=1:fail('UNSUPPORTED_PLAN',str(path),'Expected Creator schema 1')
    # Preflight everything before output creation.
    for c in p['copies']:
        if not c['target'].startswith(standard.ROOTS['creator']['content']+'/') or sha(read(inside(path.parent,c['source'])))!=c['sha256']:
            fail('SOURCE_CHANGED',c['target'],'Invalid plan resource')
    out=new_output(output,[path.parent,*p.get('sourceRoots',{}).values()])
    if p.get('sourceResourceCompletion'):
        from ..prefab_static_asset_completion import emit as emit_source_assets
        emit_source_assets(p,path.parent/p['sourceResourceCompletion']['stageRelativePath'],out,'creator')
    if p.get('staticRetainedAssets'):
        from ..prefab_static_retained_assets import emit as emit_retained
        emit_retained(p['staticRetainedAssets'],path.parent,out,'creator')
    for folder in ['assets',standard.ROOTS['creator']['conversion'],'Analysis']:
        (out/folder).mkdir(parents=True,exist_ok=True)
    by_path={a['path']:a for a in p['assets']};by_id={a['sourceId']:a for a in p['assets']}
    for c in p['copies']:
        target=inside(out,c['target']);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(read(inside(path.parent,c['source'])))
        a=by_path[c['target']]
        if a['kind']=='sprite':m=meta(a['uuid'],'image','1.0.27',dict(type='sprite-frame',fixAlphaTransparencyArtifacts=False,hasAlpha=True))
        elif a['kind']=='ttf':m=meta(a['uuid'],'ttf-font','1.0.1')
        elif a['kind']=='json':m=meta(a['uuid'],'json','2.0.1')
        elif a['kind']=='audio':m=meta(a['uuid'],'audio-clip','1.0.0',dict(downloadMode=0))
        else:m=meta(a['uuid'],'bitmap-font','1.0.6',dict(fontSize=a['pointSize'],textureUuid=by_id[a['atlas']]['uuid']))
        write_json(Path(str(target)+'.meta'),m)
    from ..prefab_target_behaviors import emit as emit_behaviors
    emit_behaviors(p,path.parent,'creator',out)
    from ..prefab_static_carriers import emit as emit_static
    emit_static(p,path.parent,'creator',out)
    if p.get('spriteOutlineBinding'):
        from ..prefab_sprite_outline_pipeline import emit_attached
        emit_attached(path.parent,path.parent,out)
    from ..prefab_material_pipeline import emit as emit_material
    emit_material(p.get('materialBinding'),path.parent,out)
    from ..prefab_static_time_materials import emit as emit_static_time
    emit_static_time(p.get('staticTimeMaterials'),path.parent,out)
    from ..prefab_spine_pipeline import emit as emit_spine
    emit_spine(p.get('spineBinding'),path.parent,out)
    if p.get('spineBinding'):
        runtime_dir=out/'assets/Game/Scripts/Presentation/Recovered/Spine'
        runtime_dir.mkdir(parents=True,exist_ok=True)
        for name in ('CreatorSpineUITransformPreserver.ts','CreatorSpineUITransformPreserver.ts.meta'):
            (runtime_dir/name).write_bytes(files('monkey.targets').joinpath('spine/'+name).read_bytes())
    if p.get('staticAnimationEvidence'):
        runtime_dir=out/'assets/Game/Scripts/Presentation/Recovered/Animation'
        runtime_dir.mkdir(parents=True,exist_ok=True)
        for name in ('CreatorStaticAnimation.ts','CreatorStaticAnimation.ts.meta'):
            (runtime_dir/name).write_bytes(files('monkey.targets').joinpath(name).read_bytes())
    if any(b.get('sourceType')=='cc.EditBox' for b in (p.get('staticControls')or{}).get('bindings',[])):
        runtime_dir=out/'assets/Game/Scripts/Presentation/StaticControls'
        runtime_dir.mkdir(parents=True,exist_ok=True)
        for name in ('CreatorStaticEditBox.ts','CreatorStaticEditBox.ts.meta'):
            (runtime_dir/name).write_bytes(files('monkey.targets').joinpath(name).read_bytes())
    if (p.get('bitmapMissingGlyphs')or{}).get('components'):
        runtime_dir=out/'assets/Game/Scripts/Presentation/Bitmap'
        runtime_dir.mkdir(parents=True,exist_ok=True)
        for name in ('CreatorStaticBitmapMissingGlyphs.ts','CreatorStaticBitmapMissingGlyphs.ts.meta'):
            (runtime_dir/name).write_bytes(files('monkey.targets').joinpath(name).read_bytes())
    if p.get('staticSortQueue'):
        runtime_dir=out/'assets/Game/Scripts/Presentation/StaticSort'
        runtime_dir.mkdir(parents=True,exist_ok=True)
        for stem in ('CreatorStaticSortQueue','CreatorStaticSortQueueProxy','CreatorStaticSortQueueProxyMarker','CreatorStaticSortQueueProxyPresenter','CreatorStaticSortRootField'):
            for suffix in ('.ts','.ts.meta'):
                (runtime_dir/(stem+suffix)).write_bytes(files('monkey.targets').joinpath(stem+suffix).read_bytes())
    if p.get('staticMasks'):
        runtime_dir=out/'assets/Game/Scripts/Presentation/StaticMasks'
        runtime_dir.mkdir(parents=True,exist_ok=True)
        for name in ('CreatorStaticMaskIdentity.ts','CreatorStaticMaskIdentity.ts.meta'):
            (runtime_dir/name).write_bytes(files('monkey.targets').joinpath(name).read_bytes())
    if p.get('layoutCompletion'):
        runtime_dir=out/'assets/Game/Scripts/Presentation/StaticLayout'
        runtime_dir.mkdir(parents=True,exist_ok=True)
        for name in ('CreatorStaticLayoutCompletion.ts','CreatorStaticLayoutCompletion.ts.meta'):
            (runtime_dir/name).write_bytes(files('monkey.targets').joinpath(name).read_bytes())
    project_id=identity(p['namespace'],'project')
    write_json(out/'package.json',dict(name='monkey-native-candidate',version='3.8.8',uuid=project_id,creator=dict(version='3.8.8')))
    write_json(out/'settings/v2/packages/project.json',dict(__version__='1.0.6',general=dict(designResolution=dict(width=p['designSize'][0],height=p['designSize'][1]))))
    if p.get('rendererBudget',{}).get('macroConfig',{}).get('BATCHER2D_MEM_INCREMENT',144)>144:
        write_json(out/'settings/v2/packages/engine.json',dict(__version__='1.0.12',macroConfig=p['rendererBudget']['macroConfig']))
        (out/'Docs').mkdir(exist_ok=True)
        kib=p['rendererBudget']['macroConfig']['BATCHER2D_MEM_INCREMENT']
        (out/'Docs/RENDERER-REQUIREMENTS.md').write_text(
            '# Creator renderer requirements\n\nThis isolated 3.8.8 candidate requires '
            f'BATCHER2D_MEM_INCREMENT={kib} KiB for its original Tiled Sprite geometry. '
            'The candidate-local settings/v2/packages/engine.json records the requirement; '
            'the Editor importer also applies it in this owned Editor process.\n\n'
            'Copying assets alone does not transfer project settings. A development-project consumer must '
            'review and explicitly merge this requirement, preserving its other engine settings. '
            'Do not overwrite a development project settings file or assume asset adoption applies the macro. '
            'Preview/build/Player validation is separate from the Editor allocation proof.\n',encoding='utf-8')
    ext=out/'extensions/monkey-import'
    for name in ['main.js','scene.js']:(ext/name).write_bytes(files('monkey.targets').joinpath('Creator'+('Main.js' if name=='main.js' else 'Scene.js')).read_bytes())
    (ext/'execution.js').write_bytes(files('monkey.targets').joinpath('CreatorExecution.js').read_bytes())
    (ext/'static-toggle.js').write_bytes(files('monkey.targets').joinpath('CreatorStaticToggle.js').read_bytes())
    (ext/'static-richtext.js').write_bytes(files('monkey.targets').joinpath('CreatorStaticRichText.js').read_bytes())
    (ext/'numeric-code.js').write_bytes(files('monkey.targets').joinpath('CreatorNumericCode.js').read_bytes())
    (ext/'behavior-bindings.js').write_bytes(files('monkey.targets').joinpath('CreatorBehaviorBindings.js').read_bytes())
    (ext/'preview-state.js').write_bytes(files('monkey.targets').joinpath('CreatorPreviewState.js').read_bytes())
    (ext/'static-sprite-frames.js').write_bytes(files('monkey.targets').joinpath('CreatorStaticSpriteFrames.js').read_bytes())
    (ext/'preview-clones.js').write_bytes(files('monkey.targets').joinpath('CreatorPreviewClones.js').read_bytes())
    (ext/'static-preview.js').write_bytes(files('monkey.targets').joinpath('CreatorStaticPreview.js').read_bytes())
    for source,dest in [('CreatorStaticAnimationBindings.js','static-animation-bindings.js'),('CreatorStaticAnimationIntegration.js','static-animation-integration.js'),('CreatorStaticAnimationContext.js','static-animation-context.js')]:
        (ext/dest).write_bytes(files('monkey.targets').joinpath(source).read_bytes())
    (ext/'static-retained-assets.js').write_bytes(files('monkey.targets').joinpath('CreatorStaticRetainedAssets.js').read_bytes())
    (ext/'bitmap-missing-glyphs.js').write_bytes(files('monkey.targets').joinpath('CreatorStaticBitmapMissingGlyphs.js').read_bytes())
    (ext/'static-masks.js').write_bytes(files('monkey.targets').joinpath('CreatorStaticMaskSort.js').read_bytes())
    (ext/'CreatorStaticSortQueueIntegration.js').write_bytes(files('monkey.targets').joinpath('CreatorStaticSortQueueIntegration.js').read_bytes())
    (ext/'static-sort-serialization.js').write_bytes(files('monkey.targets').joinpath('CreatorStaticSortSerialization.js').read_bytes())
    (ext/'editor-undo-diagnostics.js').write_bytes(files('monkey.targets').joinpath('CreatorEditorUndoDiagnostics.js').read_bytes())
    (ext/'owned-import-undo.js').write_bytes(files('monkey.targets').joinpath('CreatorOwnedImportUndo.js').read_bytes())
    (ext/'reopen-verification.js').write_bytes(files('monkey.targets').joinpath('CreatorReopenVerification.js').read_bytes())
    (ext/'creator-saved-scene-scope.js').write_bytes(files('monkey.targets').joinpath('CreatorSavedSceneScope.js').read_bytes())
    (ext/'owned-build-scene-teardown.js').write_bytes(files('monkey.targets').joinpath('CreatorOwnedBuildSceneTeardown.js').read_bytes())
    (ext/'static-layout-completion.js').write_bytes(files('monkey.targets').joinpath('CreatorStaticLayoutCompletion.js').read_bytes())
    (ext/'static-controls.js').write_bytes(files('monkey.targets').joinpath('CreatorStaticControls.js').read_bytes())
    (ext/'static-progress.js').write_bytes(files('monkey.targets').joinpath('CreatorStaticProgress.js').read_bytes())
    (ext/'static-fields.js').write_bytes(files('monkey.targets').joinpath('CreatorStaticFields.js').read_bytes())
    (ext/'static-field-integration.js').write_bytes(files('monkey.targets').joinpath('CreatorStaticFieldIntegration.js').read_bytes())
    (ext/'prefab.js').write_bytes(files('monkey.targets').joinpath('CreatorPrefab.js').read_bytes())
    (ext/'prefab-instances.js').write_bytes(files('monkey.targets').joinpath('CreatorPrefabInstances.js').read_bytes())
    (ext/'dynamic-ui.js').write_bytes(files('monkey.targets').joinpath('CreatorDynamicUi.js').read_bytes())
    (ext/'sprite-metadata.js').write_bytes(files('monkey.targets').joinpath('CreatorSpriteMetadata.js').read_bytes())
    (ext/'batch.js').write_bytes(files('monkey.targets').joinpath('CreatorBatch.js').read_bytes())
    (ext/'jobs.js').write_bytes(files('monkey.targets').joinpath('CreatorJobs.js').read_bytes())
    (ext/'animation.js').write_bytes(files('monkey.targets').joinpath('CreatorAnimation.js').read_bytes())
    (ext/'resources.js').write_bytes(files('monkey.targets').joinpath('CreatorResources.js').read_bytes())
    (ext/'progress.js').write_bytes(files('monkey.targets').joinpath('CreatorProgress.js').read_bytes())
    if p.get('staticTimeMaterials'):
        (ext/'static-time-materials.js').write_bytes(files('monkey.targets').joinpath('materials/static_time/CreatorStaticTimeMaterials.js').read_bytes())
    (ext/'material-bindings.js').write_bytes(files('monkey.targets').joinpath('materials/ui_color/CreatorMaterialBindings.js').read_bytes())
    (ext/'spine-bindings.js').write_bytes(files('monkey.targets').joinpath('spine/creator_spine_binding.js').read_bytes())
    (ext/'spine-ui-transform.js').write_bytes(files('monkey.targets').joinpath('spine/CreatorSpineUITransformBindings.js').read_bytes())
    write_json(ext/'package.json',dict(package_version=2,version='0.2.0',name='monkey-import',main='./main.js',
        contributions=dict(scene=dict(script='./scene.js'),menu=[dict(path='Monkey',label='Import isolated candidate',message='import-candidate'),
                           dict(path='Monkey',label='Inspect ordinary save',message='inspect-ordinary-save'),
                           dict(path='Monkey',label='Revalidate saved candidate',message='revalidate-saved-candidate'),
                           dict(path='Monkey',label='Stop save diagnostics',message='stop-save-diagnostics')],
                           messages={'import-candidate':dict(methods=['importCandidate']),
                                     'inspect-ordinary-save':dict(methods=['inspectOrdinarySaveApi']),
                                     'revalidate-saved-candidate':dict(methods=['revalidateSavedCandidate']),
                                     'stop-save-diagnostics':dict(methods=['stopOrdinarySaveProbe'])})))
    write_json(ext/'import-plan.json',{k:p[k] for k in ['schemaVersion','targetProfile','designSize','assets','nodes','components'] }|dict(sourceDiagnostics=p.get('diagnostics',[]),resourceProbes=p.get('resourceProbes'),rendererBudget=p.get('rendererBudget'),projectUuid=project_id,animations=p.get('animations',[]),sourcePrefabs=p.get('sourcePrefabs',[]),prefabInstances=p.get('prefabInstances',[]),prefabRelationshipReadback='creator-native-fileid-v1',uiGeometryReadback='native-ui-layout-roundtrip-v1',sceneGeometryReadback='full-local-v1',bitmapPageReadback='sprite-frame-v1',spriteMeshReadback='native-rect-mesh-v1',outputPaths=standard.creator_output_paths()))
    from .dynamic_ui import driven_fields
    instruction_path=ext/'import-plan.json';instruction=load(instruction_path.read_bytes())
    instruction['sourceManifestSha256']=p.get('sourceManifestSha256')
    instruction['staticCompletion']=p.get('staticCompletion')
    for key in ('staticAnimationEvidence','staticAnimationComponentOrigins','staticAnimationAssetReferences','staticControls','staticRetainedAssets','staticParticleBoundary','staticPresentation','layoutCompletion','staticMasks','bitmapMissingGlyphs','staticSortQueue'):
        if key in p:instruction[key]=p[key]
    instruction['syncPrefabBindings']=p.get('syncPrefabBindings',[])
    instruction['staticPrefabAssetDependencies']=p.get('staticPrefabAssetDependencies')
    instruction['staticTimeMaterials']=p.get('staticTimeMaterials')
    instruction['previewState']=p.get('previewState')
    instruction['previewStates']=p.get('previewStates')
    instruction['toggleBinding']=p.get('toggleBinding')
    instruction['behaviorBindingReadback']='persistent-source-fields-v1'
    instruction['materialBinding']=(p.get('materialBinding')or {}).get('spec')
    instruction['spriteOutlineBinding']=p.get('spriteOutlineBinding')
    instruction['spineBinding']={k:v for k,v in (p.get('spineBinding')or {}).items()if k!='copies'}or None
    instruction['uiStateProbeVersion']=2
    from .dynamic_ui import probe_sources
    instruction['uiProbeSources']=probe_sources(instruction)
    instruction['uiDrivenFields']={sid:{key:sorted(axes)for key,axes in fields.items()}for sid,fields in driven_fields(instruction).items()}
    write_json(instruction_path,instruction)
    _validate_extension_dependencies(ext,bool(p.get('staticTimeMaterials')),bool(p.get('spriteOutlineBinding')))
    from ..assets.animation import module_report
    write_json(find_analysis(out,'animation-module.json'),module_report(p.get('animations',[])))
    write_json(find_analysis(out,'source-map.json'),dict(assets=p['assets'],sourcePrefabs=p.get('sourcePrefabs',[]),nodes=[dict(sourceId=n['sourceId'],target=standard.creator('previewScene')) for n in p['nodes']],
        components=[dict(sourceId=c['sourceId'],node=c['node'],nativeType=c['nativeType']) for c in p['components']],
        sourceRoots=p['sourceRoots'],sourceLocations=p['sourceLocations'],subresources='actual UUIDs require native importer readback'))
    handoff_tasks=tasks(p['components'],[d for d in p['diagnostics'] if not d['code'].startswith('ANIMATION_')],standard.creator('previewScene'),'assets/')
    normalized=[dict(sourceId=s['sourceId'],path=s['path'],sourceRootName=s['sourceRootName'],nativeRootName=s['nativeRootName'])
                for s in p.get('sourcePrefabs',[]) if s.get('rootNamePolicy')=='creator-asset-basename-v1' and s['sourceRootName']!=s['nativeRootName']]
    if normalized:
        handoff_tasks.append(dict(taskId='creator-prefab-root-names',module='creator-prefabs',rootCause='native-prefab-root-name-compatibility',
            sourceRefs=[s['sourceId'] for s in normalized],gaps=[dict(code='CREATOR_PREFAB_ROOT_NAME_POLICY',
                message='Creator normalizes root names to asset basenames. Source names remain in Scene/source-map; review name-dependent business code.')],
            generatedTargets=['Analysis/Mappings/source-map.json'],allowedPaths=['assets/'],verificationScope=['native root-name policy','name-dependent business code'],rootNames=normalized))
    if p.get('animations') or any(d['code'].startswith('ANIMATION_') for d in p['diagnostics']):
        from ..assets.animation import handoff_task
        handoff_tasks.append(handoff_task(p['animations'],p['diagnostics']))
    write_json(find_analysis(out,'handoff.json'),dict(schemaVersion=1,tasks=handoff_tasks,
        verification=dict(static='pending',editor='not_run',visual='not_run',business='not_run')))
    if p['bindings']:write_json(find_analysis(out,'font-bindings.json'),p['bindings'])
    (out/'README.md').write_text('Creator 3.8.8 isolated candidate. Layout '+VERSION+' (monkey docs/PROJECT-SPEC.md).\nOpen only in an authorized resource window.\nRun Monkey/Import isolated candidate once after assets import. Existing outputs are refused.\nNative scene and child UUIDs require Editor; no source engine interpreter ships.\n')
    write_json(find_analysis(out,'name-map.json'),p.get('naming',{}))
    report=dict(schemaVersion=1,toolVersion=__version__,targetProfile=PROFILE,namespace=p['namespace'],projectUuid=project_id,projectLayout=VERSION,
        scopeMode=p.get('scopeMode','asset-selection'),rendererBudget=p.get('rendererBudget'),
        sourceManifestSha256=p['sourceManifestSha256'],sourceRoots=p['sourceRoots'],planSha256=sha(stage_bytes(path)),diagnostics=p['diagnostics'],
        editorValidation='not_run',visualValidation='not_run',businessValidation='not_run',subresourceValidation='pending-native-import')
    write_json(find_analysis(out,'candidate.json'),report);return finish(out,report)


def _verify_creator_native_identity_contract(plan, readback, project_uuid, manifest_sha256):
    """Check the readback's top-level Creator version, ownership and identity coverage."""
    gaps=[]
    def mismatch(code,location,expected,actual):
        gaps.append(diagnostic(code,location,'Expected '+str(expected)+'; observed '+str(actual),location))

    if readback.get('creatorVersion')!='3.8.8':
        mismatch('CREATOR_VERSION_IDENTITY_MISMATCH','CreatorVersion','3.8.8',readback.get('creatorVersion'))
    if readback.get('projectUuid')!=project_uuid or plan.get('projectUuid')!=project_uuid:
        mismatch('CREATOR_PROJECT_IDENTITY_MISMATCH','CreatorProjectUuid',project_uuid,
                 dict(plan=plan.get('projectUuid'),readback=readback.get('projectUuid')))
    if readback.get('manifestSha256')!=manifest_sha256:
        mismatch('CREATOR_MANIFEST_IDENTITY_MISMATCH','CreatorManifestSha256',manifest_sha256,readback.get('manifestSha256'))

    scopes=(('assets','assets','uuid'),('nodes','nodes','nodeUuid'),
            ('components','components','componentUuid'),('sourcePrefabs','sourcePrefabs','uuid'))
    for readback_key,plan_key,native_key in scopes:
        expected_rows=plan.get(plan_key,[])
        if plan_key=='components':
            expected_rows=[row for row in expected_rows if row.get('convertible')]
        actual_rows=readback.get(readback_key)
        if not isinstance(expected_rows,list): expected_rows=[]
        if not isinstance(actual_rows,list): actual_rows=[]
        expected_ids=[row.get('sourceId') for row in expected_rows if isinstance(row,dict)]
        actual_ids=[row.get('sourceId') for row in actual_rows if isinstance(row,dict)]
        expected_set=set(x for x in expected_ids if isinstance(x,str))
        actual_set=set(x for x in actual_ids if isinstance(x,str))
        duplicates=sorted({x for x in actual_ids if isinstance(x,str) and actual_ids.count(x)>1})
        if (len(expected_set)!=len(expected_ids) or len(actual_set)!=len(actual_ids) or
                duplicates or expected_set!=actual_set):
            mismatch('CREATOR_NATIVE_SOURCE_COUNT_MISMATCH',readback_key,
                     dict(rows=len(expected_rows),uniqueSourceIds=len(expected_set)),
                     dict(rows=len(actual_rows),uniqueSourceIds=len(actual_set),
                          missing=sorted(expected_set-actual_set)[:8],extra=sorted(actual_set-expected_set)[:8],duplicates=duplicates[:8]))
        expected_by_id={row.get('sourceId'):row for row in expected_rows if isinstance(row,dict)}
        actual_by_id={row.get('sourceId'):row for row in actual_rows if isinstance(row,dict)}
        for source_id in sorted(expected_set & actual_set):
            actual=actual_by_id[source_id]
            identity=actual.get(native_key)
            if not isinstance(identity,str) or not identity:
                mismatch('CREATOR_NATIVE_IDENTITY_MISSING',source_id,native_key,identity)
                continue
            if readback_key in ('assets','sourcePrefabs'):
                expected=expected_by_id[source_id].get('uuid')
                if isinstance(expected,str) and expected and identity!=expected:
                    mismatch('CREATOR_NATIVE_IDENTITY_MISMATCH',source_id,expected,identity)
    if readback.get('nodeCount')!=len(plan.get('nodes',[])):
        mismatch('CREATOR_NATIVE_NODE_COUNT_MISMATCH','nodeCount',len(plan.get('nodes',[])),readback.get('nodeCount'))
    return gaps


_CREATOR_STATIC_DYNAMIC_BOUNDARIES = frozenset({
    'SPINE_SOURCE_UNBOUND_DYNAMIC_NOT_RUN',
    'SPINE_DYNAMIC_BEHAVIOR_INCOMPLETE',
    'ANIMATION_DYNAMIC_CURVES_NOT_LOWERED',
})
_CREATOR_NATIVE_DYNAMIC_BOUNDARIES = _CREATOR_STATIC_DYNAMIC_BOUNDARIES | frozenset({
    # Runtime animation/resource assignment and visual comparison are outside
    # native static field identity; they still block static presentation.
    'SPINE_RUNTIME_UNVERIFIED',
})


def _creator_validation_summary(component_coverage, diagnostics, editor_validation, plan=None):
    """Join whole-source coverage with execution/readback diagnostics.

    Only the named dynamic-only gaps are excluded. Unknown/raw diagnostics,
    missing references, field discrepancies, failed native execution and
    changed files cannot leave a passing native-static/presentation summary.
    """
    native_status = component_coverage.get('nativeStaticValidation', 'not_run')
    presentation = component_coverage.get('staticPresentationValidation')
    presentation_status = presentation.get('status', 'not_run') if isinstance(presentation, dict) else 'not_run'
    rows = diagnostics if isinstance(diagnostics, list) else []

    native_blockers = [row for row in rows if not _creator_dynamic_boundary(row, component_coverage, 'native', plan)]
    presentation_blockers = [row for row in rows if not _creator_dynamic_boundary(row, component_coverage, 'presentation', plan)]

    if editor_validation == 'not_run':
        return {'nativeStaticValidation': 'not_run', 'staticPresentationStatus': 'not_run'}
    if editor_validation not in ('pass','partial'):
        return {'nativeStaticValidation': 'fail',
                'staticPresentationStatus': 'partial' if presentation_status != 'not_run' else 'not_run'}

    if native_status == 'pass' and native_blockers:
        native_status = 'fail' if any(isinstance(row, dict) and row.get('severity') == 'error'
                                      for row in native_blockers) else 'partial'
    if presentation_status == 'pass' and presentation_blockers:
        presentation_status = 'partial'
    return {'nativeStaticValidation': native_status, 'staticPresentationStatus': presentation_status}


def _creator_dynamic_boundary(row, component_coverage, scope='presentation', plan=None):
    """Recognize only source-typed dynamic gaps after static native evidence passes."""
    if not isinstance(row, dict):
        return False
    code = row.get('code')
    source_id = row.get('sourceId') or row.get('sourceComponentId')
    rows = component_coverage.get('components', []) if isinstance(component_coverage, dict) else []
    matches = [item for item in rows if isinstance(item, dict) and item.get('sourceId') == source_id]
    covered = matches[0] if len(matches) == 1 else None
    if code == 'SCROLL_PHYSICS_NOT_VERIFIED':
        if not isinstance(covered, dict) or covered.get('sourceType') != 'cc.ScrollView':
            return False
        native = covered.get('nativeComponentReadback')
        spec = next((item for item in (plan or {}).get('components', [])
                     if isinstance(item, dict) and item.get('sourceId') == source_id), None)
        evidence = native.get('staticScrollFields') if isinstance(native, dict) else None
        return bool(spec and isinstance(evidence, dict) and evidence.get('verified') is True and
                    evidence.get('sourceId') == source_id and
                    evidence.get('horizontal') is spec.get('horizontal') and
                    evidence.get('vertical') is spec.get('vertical') and
                    evidence.get('contentNodeId') == spec.get('content') and
                    isinstance(spec.get('viewport'), str) and evidence.get('viewportNodeId') == spec.get('viewport') and
                    covered.get('nativeStatus') == 'pass' and covered.get('nativeStaticFieldsVerified') is True)
    if code == 'BUTTON_BUSINESS_UNBOUND':
        from ..unity_diagnostic_resolution import is_dynamic_boundary
        return bool(covered and is_dynamic_boundary(row, covered) and
                    covered.get('sourceType') == 'cc.Button' and covered.get('nativeStatus') == 'pass' and
                    covered.get('disposition') == 'native' and covered.get('nativeStaticFieldsVerified') is True and
                    isinstance(covered.get('nativeComponentReadback'), dict))
    spine_codes = {'SPINE_SOURCE_UNBOUND_DYNAMIC_NOT_RUN', 'SPINE_DYNAMIC_BEHAVIOR_INCOMPLETE',
                   'SPINE_RUNTIME_UNVERIFIED'}
    if code in spine_codes:
        return bool(covered and covered.get('sourceType') == 'sp.Skeleton' and
                    covered.get('nativeStatus') == 'pass' and covered.get('disposition') == 'native' and
                    covered.get('nativeStaticFieldsVerified') is True and
                    isinstance(covered.get('nativeComponentReadback'), dict) and
                    (scope == 'native' or code != 'SPINE_RUNTIME_UNVERIFIED'))
    if code == 'ANIMATION_DYNAMIC_CURVES_NOT_LOWERED':
        animations = (plan or {}).get('animations', []) if isinstance(plan, dict) else []
        matches = [item for item in animations if isinstance(item, dict) and
                   (item.get('sourceId') or item.get('id')) == source_id]
        return (len(matches) == 1 and isinstance(matches[0].get('curves'), list) and
                scope in ('native', 'presentation'))
    return False


def _creator_blocking_diagnostics(report, component_coverage, diagnostics, plan=None):
    """Keep full diagnostic history while honoring verified dynamic boundaries.

    A pure dynamic warning may remain in the report without changing the
    candidate exit status only when the actual saved native coverage and
    presentation gates pass. Unknown or static failures always remain blockers.
    """
    rows = diagnostics if isinstance(diagnostics, list) else []
    editor = report.get('editorValidation')
    native = report.get('nativeStaticValidation')
    presentation = report.get('staticPresentationValidation')
    presentation_status = presentation.get('status') if isinstance(presentation, dict) else None
    expected_visible = presentation.get('expectedSourceVisibleCount') if isinstance(presentation, dict) else None
    presentation_ok = presentation_status in ('pass', 'not_applicable') or (
        presentation_status == 'not_run' and expected_visible == 0)
    accepted = (report.get('staticValidation') == 'pass' and editor in ('pass', 'partial') and
                native in ('pass', 'not_applicable') and presentation_ok)
    if not accepted:
        blockers = [row for row in rows if not _creator_dynamic_boundary(row, component_coverage, 'presentation', plan)]
        if not blockers:
            blockers = [diagnostic('CREATOR_VERIFICATION_INCOMPLETE', 'verification',
                                   'Editor/static component/presentation gates are not all satisfied')]
        return blockers
    return [row for row in rows if not _creator_dynamic_boundary(row, component_coverage, 'presentation', plan)]


def verify(candidate,output,level='static'):
    root=safe(candidate);m=stage_manifest(root);diagnostics=[];component_coverage=None
    from ..sources.containers import fingerprint
    if m.get('targetProfile')!=PROFILE:fail('UNSUPPORTED_CANDIDATE',str(root),'Expected Creator profile')
    plan=load(read(root/'extensions/monkey-import/import-plan.json',max_bytes=128*1024*1024),max_nodes=8_000_000)
    native={};editor='not_run'
    if level=='editor':
        rb_path=find_analysis(root,'editor-readback.json')
        if not rb_path.exists():diagnostics.append(diagnostic('EDITOR_NOT_RUN',str(rb_path),'Run native importer in declared Creator first'))
        else:
            from ..creator_readback_revision import select_current_revision, RevisionError
            try:
                revision=select_current_revision(root,fingerprint(root/'manifest.json'),m['projectUuid'],
                    fingerprint(root/'extensions/monkey-import/import-plan.json'),rb_path.relative_to(root).as_posix())
            except RevisionError as error:
                fail('CREATOR_READBACK_REVISION_INVALID',str(root/'Analysis/Readback/current-revision.json'),str(error))
            if revision is not None:rb_path=revision['path']
            rb=load(read(rb_path,max_bytes=128*1024*1024),max_nodes=8_000_000);native={f['path']:f['sha256'] for f in rb.get('nativeFiles',[])}
            from ..prefab_component_coverage import assess as assess_component_coverage
            component_coverage=assess_component_coverage(plan,rb,'creator')
            diagnostics.extend(component_coverage['diagnostics'])
            expected_assets={a['sourceId']:a for a in plan['assets']}
            actual_assets={a['sourceId']:a for a in rb.get('assets',[])}
            json_assets={a['sourceId']:a for a in rb.get('jsonAssets',[])}
            audio_assets={a['sourceId']:a for a in rb.get('audioAssets',[])}
            identity_gaps=_verify_creator_native_identity_contract(plan,rb,m['projectUuid'],fingerprint(root/'manifest.json'))
            good=not identity_gaps
            if identity_gaps:diagnostics.extend(identity_gaps)
            good=good and set(expected_assets)==set(actual_assets) and rb.get('nodeCount')==len(plan['nodes'])
            from ..prefab_material_pipeline import verify as verify_material
            material_gaps=verify_material(plan.get('materialBinding'),rb.get('materialBinding'),'creator')
            if material_gaps:good=False;diagnostics.extend(material_gaps)
            from ..prefab_spine_pipeline import verify as verify_spines
            spine_gaps=verify_spines(plan['components'],rb.get('spineBindings'),'scene')
            if spine_gaps:
                good=good and all(g['code']=='SPINE_SOURCE_UNBOUND_DYNAMIC_NOT_RUN' for g in spine_gaps);diagnostics.extend(spine_gaps)
            from ..creator_geometry import verify_tiled_readback
            if not verify_tiled_readback(plan,rb):
                good=False;diagnostics.append(diagnostic('TILED_NATIVE_READBACK_MISMATCH','CreatorScene','Tiled mesh allocation/budget/topology/identity readback differs'))
            from ..resource_probe import verify as verify_resources
            if not verify_resources(plan,rb):
                good=False;diagnostics.append(diagnostic('RESOURCE_NATIVE_READBACK_MISMATCH','CreatorResources','Resource identities or native animation state differ'))
            for sid,a in expected_assets.items():
                actual=actual_assets.get(sid,{})
                good=good and actual.get('uuid')==a['uuid'] and (a['kind']!='sprite' or bool(actual.get('spriteFrameUuid')))
                if a['kind']=='json':
                    actual_json=json_assets.get(sid,{})
                    good=good and actual_json.get('uuid')==a['uuid'] and 'value' in actual_json and actual_json['value']==load(read(root/a['path']))
                if a['kind']=='audio':
                    audio=audio_assets.get(sid,{})
                    if audio.get('uuid')!=a['uuid'] or not isinstance(audio.get('duration'),(int,float)):
                        good=False;diagnostics.append(diagnostic('AUDIO_READBACK_MISMATCH',sid,'Expected a native AudioClip readback'))
            labels={v['sourceId']:v for v in rb.get('labels',[])}
            if plan.get('bitmapPageReadback')=='sprite-frame-v1':
                font_pages={f['sourceId']:f for f in rb.get('fontPages',[])}
                for font in (a for a in plan['assets'] if a['kind']=='bitmap'):
                    page=font_pages.get(font['sourceId'],{});atlas=expected_assets[font['atlas']];native_atlas=actual_assets.get(font['atlas'],{})
                    if (page.get('fontUuid')!=font['uuid'] or page.get('spriteFrameUuid')!=native_atlas.get('spriteFrameUuid') or
                            page.get('textureUuid')!=native_atlas.get('textureUuid') or page.get('rect')!=[0,0,*atlas['size']]):
                        good=False;diagnostics.append(diagnostic('BITMAP_PAGE_READBACK_MISMATCH',font['sourceId'],'Native BitmapFont page identity/texture/rect differs'))
            for c in plan['components']:
                if c['convertible'] and c['type']=='cc.Label':
                    actual=labels.get(c['sourceId'],{})
                    font_good = (actual.get('useSystemFont') is True and actual.get('fontUuid') is None and actual.get('fontFamily')==c['fontFamily']) if c.get('nativeSystemFont') else actual.get('fontUuid')==expected_assets[c['font']]['uuid']
                    good=good and actual.get('text')==c['text'] and font_good
            expected_components={c['sourceId'] for c in plan['components'] if c['convertible']}
            good=good and {c['sourceId'] for c in rb.get('components',[])}==expected_components
            good=good and {n['sourceId'] for n in rb.get('nodes',[])}=={n['sourceId'] for n in plan['nodes']}
            if plan.get('sceneGeometryReadback')=='full-local-v1':
                from .unity import node_geometry_matches
                saved_nodes={n['sourceId']:n for n in rb.get('nodes',[])}
                from .dynamic_ui import expectations,verify_probes
                probe_gaps=verify_probes(plan,rb.get('dynamicUiProbes'));diagnostics.extend(probe_gaps)
                if probe_gaps:good=False
                scene_expected,ui_gaps=expectations(plan,rb.get('nativeInitialNodes'),'CreatorScene');diagnostics.extend(ui_gaps)
                if ui_gaps:good=False
                for spec in scene_expected:
                    actual_node=saved_nodes.get(spec['sourceId'])
                    if not node_geometry_matches(actual_node,spec,True) or ('sourceLayer'in spec and actual_node.get('sourceLayer')!=spec['sourceLayer']):
                        good=False;diagnostics.append(diagnostic('SCENE_GEOMETRY_MISMATCH',spec['sourceId'],'Saved native Scene transform differs from the frozen source plan'))
            def near(actual,expected):
                return isinstance(actual,list) and len(actual)==len(expected) and all(type(x) in (int,float) and abs(x-y)<.001 for x,y in zip(actual,expected))
            frames={f['sourceId']:f for f in rb.get('frames',[])}
            for sid,a in expected_assets.items():
                if a['kind']=='sprite':
                    f=frames.get(sid,{})
                    expected=dict(uuid=actual_assets.get(sid,{}).get('spriteFrameUuid'),textureUuid=actual_assets.get(sid,{}).get('textureUuid'),
                                  rect=a.get('trimOrigin',[0,0])+a['size'],originalSize=a['originalSize'],offset=a['offset'],border=a['border'])
                    mismatches=[key for key,value in expected.items() if (f.get(key)!=value if key in ('uuid','textureUuid') else not near(f.get(key),value))]
                    if plan.get('spriteMeshReadback')=='native-rect-mesh-v1':
                        w,h=a['size'];tw,th=a['originalSize'];x,y=a.get('trimOrigin',[0,0]);mesh=f.get('mesh')or{}
                        expected_mesh=dict(rawPosition=[-w/2,-h/2,0,w/2,-h/2,0,-w/2,h/2,0,w/2,h/2,0],indexes=[0,1,2,2,1,3],
                            uv=[x,th-y,x+w,th-y,x,th-y-h,x+w,th-y-h],nuv=[x/tw,(th-y-h)/th,(x+w)/tw,(th-y-h)/th,x/tw,(th-y)/th,(x+w)/tw,(th-y)/th])
                        for key,value in expected_mesh.items():
                            actual=mesh.get(key)
                            if not isinstance(actual,list)or len(actual)!=len(value)or any(type(v)not in(int,float)or abs(v-e)>1e-6 for v,e in zip(actual,value)):
                                good=False;diagnostics.append(diagnostic('SPRITE_NATIVE_MESH_MISMATCH',sid,'Saved native RECT mesh '+key+' differs'))
                    if mismatches:
                        good=False;diagnostics.append(diagnostic('SPRITE_READBACK_MISMATCH',sid,
                            'Saved native sprite differs: '+str({key:dict(expected=expected[key],actual=f.get(key)) for key in mismatches})))
            good=good and all(isinstance(n.get('nodeUuid'),str) and n['nodeUuid'] for n in rb.get('nodes',[]))
            good=good and all(isinstance(c.get('componentUuid'),str) and c['componentUuid'] for c in rb.get('components',[]))
            from ..code_validation import numeric as verify_numeric
            code_gaps=verify_numeric(plan['components'],rb.get('numericCodeBindings'),'cocos','scene',rb.get('numericCodeExercise',[]))
            if code_gaps:good=False;diagnostics.extend(code_gaps)
            good=good and standard.locate(m,'previewScene','creator') in native and bool(rb.get('sceneUuid'))
            if plan.get('staticTimeMaterials'):
                from ..prefab_static_time_materials import verify as verify_static_time
                static_time_gaps=verify_static_time(plan['staticTimeMaterials'],rb.get('staticTimeMaterials'),'creator')
                diagnostics.extend(static_time_gaps);good=good and not static_time_gaps
            from ..prefab_static_completion_readback import verify_assets as verify_retained
            retained_gaps=verify_retained(plan,rb.get('staticRetainedAssetReadback'),'creator')
            diagnostics.extend(retained_gaps);good=good and not retained_gaps
            from ..prefab_static_sort_readback import verify_creator as verify_static_sort
            sort_gaps=verify_static_sort(plan,rb)
            diagnostics.extend(sort_gaps);good=good and not sort_gaps
            actual_prefabs={v['sourceId']:v for v in rb.get('sourcePrefabs',[])}
            expected_prefabs={v['sourceId']:v for v in plan.get('sourcePrefabs',[])}
            if set(actual_prefabs)!=set(expected_prefabs):good=False
            for sid,spec in expected_prefabs.items():
                actual=actual_prefabs.get(sid,{})
                source_nodes=set(spec['nodes']);code_specs=[c for c in plan['components']if c.get('node')in source_nodes]
                from ..prefab_static_readback import verify as verify_static
                from ..prefab_static_completion_readback import verify_prefab as verify_completion
                completion_gaps=verify_completion(plan,code_specs,actual,'creator',sid)
                diagnostics.extend(completion_gaps)
                good=good and not any(g['code']=='STATIC_COMPLETION_NATIVE_MISMATCH' for g in completion_gaps)
                from ..prefab_static_progress import verify as verify_progress
                progress_gaps=verify_progress(code_specs,actual.get('staticProgressFields'),'creator',sid)
                if progress_gaps:good=False;diagnostics.extend(progress_gaps)
                static_gaps=verify_static(code_specs,actual.get('staticFieldBindings'),actual.get('uuid'),'creator',sid)
                if static_gaps:good=False;diagnostics.extend(static_gaps)
                code_gaps=verify_numeric(code_specs,actual.get('numericCodeBindings'),'cocos',sid)
                if code_gaps:good=False;diagnostics.extend(code_gaps)
                spine_gaps=verify_spines(code_specs,actual.get('spineBindings'),sid)
                if spine_gaps:
                    good=good and all(g['code']=='SPINE_SOURCE_UNBOUND_DYNAMIC_NOT_RUN' for g in spine_gaps);diagnostics.extend(spine_gaps)
                if plan.get('behaviorBindingReadback')=='persistent-source-fields-v1':
                    from ..prefab_target_behaviors import verify_bindings
                    behavior_gaps=verify_bindings(code_specs,actual.get('behaviorBindings'),actual.get('uuid'),'creator',sid)
                    if behavior_gaps:good=False;diagnostics.extend(behavior_gaps)
                if plan.get('uiGeometryReadback')=='native-ui-layout-roundtrip-v1':
                    from .dynamic_ui import expectations
                    _,ui_gaps=expectations(plan,actual.get('nativeInitialNodes'),sid,[n for n in plan['nodes']if n['sourceId']in source_nodes])
                    if ui_gaps:good=False;diagnostics.extend(ui_gaps)
                for mismatch in actual.get('geometryMismatches',[]):
                    good=False
                    diagnostics.append(diagnostic('PREFAB_GEOMETRY_MISMATCH',mismatch.get('sourceId',sid),
                        'Saved native geometry differs: '+str(mismatch)))
                expected_components={c['sourceId'] for c in plan['components'] if c['convertible'] and c['node'] in set(spec['nodes'])}
                valid=(set(actual.get('components',[]))==expected_components and actual.get('path')==spec['path'] and bool(actual.get('uuid')) and
                       actual.get('nodeCount')==spec['nodeCount'] and actual.get('savedReloaded') is True and
                       actual.get('geometryVerified') is True and actual.get('referencesVerified') is True and spec['path'] in native)
                if spec.get('rootNamePolicy')=='creator-asset-basename-v1':
                    valid=valid and all(actual.get(key)==spec[key] for key in ['rootNamePolicy','sourceRootName','nativeRootName'])
                if not valid:
                    good=False;diagnostics.append(diagnostic('SOURCE_PREFAB_NOT_VERIFIED',sid,'Independent Creator prefab save/reload evidence absent or inconsistent'))
            from .prefabs import verify_native_relationships
            native_ids={sid:a.get('uuid')for sid,a in actual_prefabs.items()}
            relation_gaps=verify_native_relationships(plan.get('prefabInstances',[]),plan.get('sourcePrefabs',[]),rb.get('prefabInstances',[]),'CreatorScene',native_ids,'uuid')
            for sid,a in actual_prefabs.items():
                relation_gaps.extend(verify_native_relationships([x for x in plan.get('prefabInstances',[])if x['owner']==sid],plan.get('sourcePrefabs',[]),a.get('prefabInstances',[]),sid,native_ids,'uuid'))
            if relation_gaps:good=False;diagnostics.extend(relation_gaps)
            from ..assets.animation import verify_native
            motion_gaps=verify_native(plan.get('animations',[]),rb.get('animations',[]),native);diagnostics.extend(motion_gaps);good=good and not motion_gaps
            editor='pass' if good else 'fail'
    for f in m['files']:
        if f.get('owner')=='manual':continue
        target=inside(root,f['path']);expected=native.get(f['path'],f['sha256'])
        if not target.is_file() or fingerprint(target)!=expected:diagnostics.append(diagnostic('GENERATED_FILE_CHANGED',f['path'],'Generated file differs'))
    for relative,h in native.items():
        prefixes=('assets/','Analysis/')
        if not relative.startswith(prefixes):fail('UNSAFE_NATIVE_FILE',relative,'Unexpected native output')
        p=inside(root,relative)
        if not p.is_file() or fingerprint(p)!=h:diagnostics.append(diagnostic('NATIVE_FILE_CHANGED',relative,'Saved native hash differs'))
    from ..identities import verify as verify_assigned
    identity_gaps=verify_assigned(root,m);diagnostics.extend(identity_gaps)
    if identity_gaps and editor=='pass':editor='fail'
    # Static asset references are logical, not asserted native subresource UUIDs.
    ids={a['sourceId'] for a in plan['assets']}
    for a in plan['assets']:
        if a.get('atlas') and a['atlas'] not in ids:diagnostics.append(diagnostic('MISSING_ATLAS',a['path'],'Bitmap atlas absent'))
    for c in plan['components']:
        if c['convertible']:
            for field in ['font','spriteFrame']:
                if c.get(field) is not None and c[field] not in ids:diagnostics.append(diagnostic('MISSING_REFERENCE',c['sourceId'],'Missing '+field))
    if standard.current(m):
        from ..layout.verify import scan
        diagnostics.extend(scan([f['path'] for f in m['files']]))
    if any(d['code'] in ('GENERATED_FILE_CHANGED','NATIVE_FILE_CHANGED') for d in diagnostics) and editor=='pass':editor='fail'
    if component_coverage is None:
        from ..prefab_component_coverage import assess as assess_component_coverage
        component_coverage=assess_component_coverage(plan,{},'creator')
        diagnostics.extend(component_coverage['diagnostics'])
    from ..unity_verification_contract import deduplicate_diagnostics
    diagnostics=deduplicate_diagnostics(diagnostics)
    creator_summary=_creator_validation_summary(component_coverage,diagnostics,editor,plan)
    integrity_codes={'GENERATED_FILE_CHANGED','NATIVE_FILE_CHANGED','DUPLICATE_TARGET_GUID','TARGET_REFERENCE_MISSING','TARGET_LAYOUT_INVALID','ASSIGNED_NATIVE_IDENTITY_CHANGED','LAYOUT_FORBIDDEN_NAME'}
    static_integrity='conflict' if any(d.get('code') in integrity_codes for d in diagnostics) else 'pass'
    out=new_output(output,[root]);report=dict(schemaVersion=1,toolVersion=__version__,diagnostics=diagnostics,
        staticValidation=static_integrity,editorValidation=editor,
        nativeStaticValidation=creator_summary['nativeStaticValidation'],
        componentCoverage=component_coverage['components'] if component_coverage else [],
        componentCoverageCounts=component_coverage['dispositionCounts'] if component_coverage else {},
        componentCoverageSourceCount=component_coverage['sourceComponentCount'] if component_coverage else None,
        retentionValidation=component_coverage['retentionValidation'] if component_coverage else 'not_run',
        staticPresentationValidation=({**component_coverage['staticPresentationValidation'],
                                      'status':creator_summary['staticPresentationStatus']}
                                     if component_coverage and isinstance(component_coverage.get('staticPresentationValidation'),dict)
                                     else {'status':creator_summary['staticPresentationStatus']}),
        runtimeCheck='not_run',playerValidation='not_run',
        counts=dict(scope='candidate-import-plan',assets=len(plan['assets']),spriteFrames=sum(a['kind']=='sprite'for a in plan['assets']),nodes=len(plan['nodes']),plannedPrefabs=len(plan.get('sourcePrefabs',[]))))
    write_json(out/'verification.json',report)
    return finish(out,report,blocking_diagnostics=_creator_blocking_diagnostics(report,component_coverage,diagnostics,plan))
