"""Independent saved static module checks; dynamic curves remain a separate boundary."""
from .io import diagnostic


def verify_prefab(plan, components, saved, target, owner):
    result=[]
    def gap(message):result.append(diagnostic('STATIC_COMPLETION_NATIVE_MISMATCH',owner,message,owner))
    if plan.get('staticPresentation'):
        for c in components:
            if c['type'] in ('cc.SortOrder','cc.SortRoot') and plan.get('staticSortQueue'):
                # Native queue/field evidence is verified independently by both target verifiers.
                continue
            if c['type'] in ('cc.Sprite','cc.Label','cc.LabelOutline','cc.SortOrder','cc.SortRoot') and not c.get('convertible'):
                gap('Static native presentation is not restored: '+c['sourceId']+' ('+c['type']+')')
    masks=(plan.get('staticMasks')or{}).get('masks',[])
    scope={c['sourceId'] for c in components}
    bitmap=plan.get('bitmapMissingGlyphs')
    if bitmap:
        from .prefab_bitmap_missing_glyphs import verify_readback as verify_bitmap
        local=dict(bitmap,components=[s for s in bitmap.get('components',[])if s['sourceComponentId']in scope])
        for error in verify_bitmap(local,saved.get('bitmapMissingGlyphFields',[]))['errors']:gap(error)
    expected_masks={s['sourceId']:s for s in masks if s['sourceId']in scope}
    if expected_masks:
        rows=saved.get('staticMaskFields')
        observed={r.get('sourceId'):r for r in rows or []}
        if not isinstance(rows,list)or len(observed)!=len(rows)or set(observed)!=set(expected_masks):gap('Saved native Mask identity set differs')
        for sid,spec in expected_masks.items():
            row=observed.get(sid,{})
            if row.get('verified')is not True or row.get('node')!=spec['node'] or row.get('maskType')!=spec['maskType'] or row.get('inverted')!=spec['inverted'] or row.get('enabled')!=spec['enabled'] or abs(row.get('alphaThreshold',-2)-spec['alphaThreshold'])>1e-6:gap('Saved native Mask fields differ: '+sid)
            if row.get('sourceFieldsJson')!=spec.get('sourceFieldsJson'):gap('Saved native Mask source document differs: '+sid)
    if expected_masks and target=='creator':
        initialized=saved.get('staticMaskInitializedFields')
        observed={r.get('sourceId'):r for r in initialized or []}
        if not isinstance(initialized,list)or len(observed)!=len(initialized)or set(observed)!=set(expected_masks):gap('Initialized native Mask identity set differs')
        for sid,spec in expected_masks.items():
            row=observed.get(sid,{})
            if row.get('verified')is not True or row.get('initialized')is not True or row.get('initializedBackingVerified')is not True:gap('Initialized native Mask backing differs: '+sid)
            if spec['maskType']==2 and (not row.get('nativeSpriteFrameUuid')or row.get('maskSpriteFrameUuid')!=row.get('nativeSpriteFrameUuid')):gap('Initialized image Mask SpriteFrame differs: '+sid)
    layout=plan.get('layoutCompletion')
    if layout:
        from .prefab_static_layout_completion import verify_readback,verify_native_probe
        nodes={c['node']for c in components}
        subset=dict(layout,nodes=[n for n in layout.get('nodes',[])if n['sourceNodeId']in nodes])
        checked=verify_readback(subset,saved.get('staticLayoutFields',[]))
        for error in checked['errors']:gap(error)
        if subset['nodes']:
            probe=verify_native_probe(subset,saved.get('staticLayoutProbe'))
            for error in probe['errors']:gap(error)
    controls=[c['staticControlBinding'] for c in components if c.get('staticControlBinding')]
    if controls or saved.get('staticControlFields'):
        from .prefab_static_controls import verify
        import copy
        expected=copy.deepcopy(controls)
        if target=='unity':
            for spec in expected:spec['nativeCreatorType']='NativeStaticGraphics' if spec['sourceType']=='cc.Graphics' else 'NativeStaticEditBox'
        for error in verify(expected,saved.get('staticControlFields'),target):gap(error)
        if target=='unity':
            for row in saved.get('staticControlFields')or[]:
                for ref in (row.get('references')or[])+(row.get('materials')or[]):
                    if ref.get('persistent') is not True or not ref.get('assetGuid') or not ref.get('localFileId'):gap('Control persistent reference absent: '+str(row.get('sourceId')))
    if not plan.get('staticAnimationEvidence'):return result
    expected={c['sourceId']:c for c in components if c['type']=='cc.Animation'}
    rows=saved.get('staticAnimationFields')
    if not isinstance(rows,list):gap('Animation fields absent');return result
    actual={row.get('sourceComponentId'):row for row in rows}
    if len(actual)!=len(rows) or set(actual)!=set(expected):gap('Animation component identity set differs');return result
    motions={m['id']:m for m in plan.get('animations',[])if m.get('convertible')}
    origins={r['instanceSourceId']:r['templateSourceId'] for r in plan.get('staticAnimationComponentOrigins',[])}
    evidence={r['sourceClipId']:r for r in plan['staticAnimationEvidence']}
    for sid,spec in expected.items():
        row=actual[sid];binding=row.get('binding')or{}
        if binding.get('status')!='reference_fields_verified' or binding.get('markerDisabled')is not True or binding.get('animatorDisabled' if target=='unity' else 'animationDisabled')is not True:gap(sid+': native static policy or comparison failed')
        if row.get('playbackExecuted')is not False or binding.get('playbackExecuted')is not False:gap(sid+': unexpected playback')
        for key,expected_value in [('sourceEnabled',spec['enabled']),('sourcePlayOnLoad',spec['playOnLoad']),('sourceClipOrder',spec['clips'])]:
            if binding.get(key)!=expected_value:gap(sid+': '+key+' differs')
        if (binding.get('sourceDefaultClipId')or None)!=(spec.get('defaultClip')or None):gap(sid+': default Clip identity differs')
        slots=binding.get('clips' if target=='unity' else 'clipBindings')
        if not isinstance(slots,list) or len(slots)!=len(spec['clips']):gap(sid+': Clip slot count differs');continue
        retained=[]
        for index,(clip,slot) in enumerate(zip(spec['clips'],slots)):
            if slot.get('sourceClipId')!=clip or slot.get('order')!=index:gap(sid+': Clip slot identity/order differs');continue
            motion=motions.get(clip+'@'+sid)or motions.get(clip+'@'+origins.get(sid,sid))
            if motion:
                if slot.get('status')!='native_clip_reference_resolved' or slot.get('nativeClipPath')!=motion['path'] or not slot.get('nativeClipGuid'):gap(sid+': native Clip reference differs '+clip)
                if target=='unity' and (slot.get('referenceMatches')is not True or slot.get('assetHashStatus')!='verified' or slot.get('metaHashStatus')!='verified'):gap(sid+': native Clip persistent content differs '+clip)
            else:
                retained.append(clip)
                if slot.get('status')!='source_evidence_retained':gap(sid+': unavailable source curves disposition differs '+clip)
            ev=evidence.get(clip,{})
            if slot.get('sourceEvidencePath')!=ev.get('path') or not slot.get('sourceEvidenceGuid'):gap(sid+': source Clip evidence asset absent '+clip)
            if target=='unity':
                if slot.get('sourceEvidenceHashStatus')!='verified' or slot.get('referenceMatches')is not True:gap(sid+': retained source Clip hash/reference differs '+clip)
            elif slot.get('sourceEvidenceSha256')!=ev.get('sha256'):gap(sid+': source Clip evidence hash differs '+clip)
        if retained:result.append(diagnostic('ANIMATION_DYNAMIC_CURVES_NOT_LOWERED',owner,'Native static component and source assets retained; timeline not run: '+str(retained),sid))
    return result


def verify_assets(plan, rows, target):
    contract=plan.get('staticRetainedAssets')
    if not contract:return []
    def gap(message):return diagnostic('STATIC_RETAINED_ASSET_NATIVE_MISMATCH','staticRetainedAssets',message)
    if not isinstance(rows,list):return [gap('Retained asset readback absent')]
    actual={r.get('sourceId'):r for r in rows};expected={a['sourceId']:a for a in contract['assets']}
    if len(actual)!=len(rows)or set(actual)!=set(expected):return [gap('Retained asset identity set differs')]
    result=[]
    for sid,spec in expected.items():
        r=actual[sid];native=spec['unity' if target=='unity' else 'creator']
        if r.get('verified')is not True or r.get('persistent')is not True or r.get('retentionKind')!=spec['retentionKind']:result.append(gap(sid+': native type/reference check failed'))
        if r.get('guid' if target=='unity' else 'uuid')!=native['guid' if target=='unity' else 'uuid']:result.append(gap(sid+': native asset identity differs'))
        if target=='unity' and not r.get('localFileId'):result.append(gap(sid+': persistent local ID absent'))
        if spec['retentionKind']=='buffer-asset' and r.get('sourceSha256')!=spec['contentSha256']:result.append(gap(sid+': retained binary differs'))
        if spec['retentionKind']=='texture-asset':
            if target=='unity':
                valid=r.get('pixelSha256')==spec['rgbaSha256']
            else:
                valid=(r.get('sourceRgbaSha256')==spec['rgbaSha256'] and r.get('pngSha256')==spec['creatorPngSha256']
                       and r.get('imageUuid')==spec['creator']['imageUuid']
                       and [r.get('width'),r.get('height')]==spec['dimensions'])
                if r.get('nativePixelAccess')=='image-canvas':
                    valid=valid and r.get('pixelComparison')=='browser-decoded-png-to-native-image-canvas-exact-v1' and r.get('nativePixelsEqualPng')is True and bool(r.get('pngPixelSha256')) and r.get('pngPixelSha256')==r.get('nativeImagePixelSha256')
                elif r.get('nativePixelAccess')=='typed-array':
                    valid=valid and r.get('pixelComparison')=='native-typed-array-source-rgba-exact-v1' and r.get('nativeImagePixelSha256')==spec['rgbaSha256']
                else:valid=False
            if not valid:result.append(gap(sid+': decoded texture pixels differ'))
    return result
