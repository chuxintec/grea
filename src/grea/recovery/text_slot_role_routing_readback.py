"""Independently check captured TMP slot roles and registration dispositions."""
from __future__ import annotations

CONTRACT='monkey-static-sort-text-slot-role-routing/1'
_ROLES={'primary-font','fallback-font-transient','fallback-font-persistent',
        'fallback-font-same-asset-multi-atlas','sprite'}
_CROSS_FONT={'fallback-font-transient','fallback-font-persistent'}


def _identity(value,prefix):return value.get(prefix+'Guid')or'',value.get(prefix+'LocalFileId')or 0


def verify_lifecycle(life,mode,required=False):
    marker=life.get('slotRoleRoutingContract')
    if marker is None and not required:return []
    prefix=f'{mode} TMP slot role routing'
    sid=life.get('sourceComponentId');failures=[]
    def gap(message):failures.append(f'{prefix} {message}: {sid}')
    if marker!=CONTRACT:gap('contract is absent or unsupported');return failures
    initial=life['initialEnumeration'];final=life['finalEnumeration']
    drawable=[x['slot']for x in initial['rows']if x['disposition']=='drawable']
    empty=[x['slot']for x in initial['rows']if x['disposition']=='empty-placeholder']
    routes=life.get('emptySlotRoutes')
    if not isinstance(routes,list):gap('empty-placeholder routes are absent')
    else:
        ids=[r.get('slot')for r in routes if isinstance(r,dict)]
        if len(ids)!=len(routes)or sorted(ids)!=empty:gap('empty-placeholder route denominator differs')
        for route in routes:
            if (not isinstance(route,dict)or route.get('captureRole')!='empty-placeholder'or
                route.get('captureRoleVerified')is not True or route.get('registrationDisposition')!='not-required'or
                route.get('registrationOutcome')!='skipped'or
                route.get('registrationSkipReason')!='empty-placeholder-has-no-drawable-binding'):
                gap('empty-placeholder was not explicitly excluded from registration')
    phases=life['phases'];by_slot={}
    for phase in phases:
        for snapshot in phase['slots']:by_slot.setdefault(snapshot['slot'],[]).append((phase,snapshot))
    for slot in drawable:
        records=by_slot.get(slot,[])
        captures=[s for p,s in records if p['phase']=='capture-fallback-output'and p['slot']==slot]
        if len(captures)!=1:gap(f'slot {slot} has no unique captured role');continue
        captured=captures[0];role=captured.get('captureRole')
        if role not in _ROLES:gap(f'slot {slot} role is unsupported');continue
        font=_identity(captured,'sourceAsset');owner=_identity(life,'ownerFontAsset')
        fallback=_identity(captured,'fallbackFontAsset')
        source_persistent=bool(_identity(captured,'sourceGraphicMaterial')[0]and _identity(captured,'sourceGraphicMaterial')[1])
        if role=='sprite':
            if captured.get('sourceAssetKind')!='sprite':gap(f'slot {slot} sprite role has a font source')
            if fallback!=('',0)or not source_persistent:gap(f'slot {slot} sprite route has font fallback or transient material')
        else:
            if captured.get('sourceAssetKind')!='font':gap(f'slot {slot} font role has a sprite source')
            if type(captured.get('fallbackAtlasIndex'))is not int or captured['fallbackAtlasIndex']<0:
                gap(f'slot {slot} font atlas reference is unresolved')
            if role in _CROSS_FONT:
                if font==owner or fallback!=font:gap(f'slot {slot} fallback face is not a distinct bound source font')
            elif font!=owner:gap(f'slot {slot} primary/same-font role differs from owner font')
            if role=='primary-font'and (fallback!=('',0)or not source_persistent):
                gap(f'slot {slot} primary route has fallback descriptor or transient material')
            if role=='fallback-font-same-asset-multi-atlas'and fallback!=font:
                gap(f'slot {slot} same-font atlas route has a different fallback face')
            if role=='fallback-font-same-asset-multi-atlas'and captured.get('fallbackAtlasIndex',-1)<=0:
                gap(f'slot {slot} same-font atlas route uses the primary atlas')
            if role=='fallback-font-transient'and (source_persistent or captured.get('tmpFallbackMaterialBaked')is not True):
                gap(f'slot {slot} transient fallback origin has no transient/baked profile')
            if role=='fallback-font-persistent'and (not source_persistent or captured.get('tmpFallbackMaterialBaked')is not False):
                gap(f'slot {slot} persistent fallback origin has no direct persistent profile')
        driver=captured.get('outlineDriverPresent');target=captured.get('outlineTargetMatchesOwner')
        if type(driver)is not bool or type(target)is not bool:gap(f'slot {slot} outline ownership evidence is absent')
        if driver is True and target is not True:gap(f'slot {slot} outline driver targets another owner')
        expected_required=role in _CROSS_FONT and driver is True
        disposition='required'if expected_required else'not-required'
        if captured.get('registrationDisposition')!=disposition:gap(f'slot {slot} required/skip decision differs from source role')
        if captured.get('generatedSubmesh')is not (role!='primary-font'):
            gap(f'slot {slot} generated-slot evidence differs from source role')
        if role=='primary-font'and captured.get('fallbackAtlasIndex')!=0:
            gap(f'slot {slot} primary font does not use its primary atlas')
        if role=='sprite'and (captured.get('fontAtlasRenderMode')!=-1 or captured.get('fontAssetIsRasterBitmap')is not False or captured.get('fallbackAtlasIndex')!=-1):
            gap(f'slot {slot} sprite route contains font rendering evidence')
        if type(captured.get('fontAtlasRenderMode'))is not int or type(captured.get('fontAssetIsRasterBitmap'))is not bool:
            gap(f'slot {slot} font render-mode evidence is absent')
        reason=captured.get('registrationSkipReason')
        if expected_required:
            if reason not in (None,''):gap(f'slot {slot} required registration claims a skip reason')
        else:
            expected_reason={'primary-font':'primary-font-slot-does-not-use-fallback-variant',
                'sprite':'sprite-slot-does-not-use-font-fallback-variant',
                'fallback-font-same-asset-multi-atlas':'same-font-multi-atlas-route-does-not-register-fallback-variant'}.get(role,'outline-driver-absent')
            if reason!=expected_reason:gap(f'slot {slot} verified skip reason differs from source role')
        direct=not captured.get('tmpFallbackMaterialBaked')
        if direct:
            if (_identity(captured,'sourceGraphicMaterial')!=_identity(captured,'bakedProxyMaterial')or
                not _identity(captured,'sourceGraphicMaterial')[0]or
                captured.get('bakedProxyMaterialFingerprint')!=captured.get('sourceMaterialFingerprint')):
                gap(f'slot {slot} direct persistent profile is not the captured source material')
        stable=('captureRole','fontAtlasRenderMode','fontAssetIsRasterBitmap','generatedSubmesh',
                'outlineDriverPresent','outlineTargetMatchesOwner','fallbackAtlasIndex',
                'registrationDisposition','registrationSkipReason')
        for phase,snapshot in records:
            name=phase['phase'];observed=snapshot.get('observedRole')
            if (snapshot.get('captureRoleVerified')is not True or snapshot.get('observedRoleVerified')is not True or
                any(snapshot.get(k)!=captured.get(k)for k in stable)):
                gap(f'slot {slot} role/dispatch evidence differs across phases')
            if observed!=role:
                permitted=(role=='fallback-font-transient'and observed=='fallback-font-persistent'and
                    captured.get('tmpFallbackMaterialBaked')is True and
                    snapshot.get('persistentFallbackVariantRegistered')is True and
                    _identity(snapshot,'sourceGraphicMaterial')==_identity(captured,'bakedProxyMaterial')and
                    snapshot.get('sourceGraphicMaterialFingerprint')==captured.get('bakedProxyMaterialFingerprint'))
                if not permitted:gap(f'slot {slot} observed role changed without exact registered profile')
                if snapshot.get('roleTransition')!='transient-to-persistent-registered':gap(f'slot {slot} registered role transition has no exact receipt')
            elif snapshot.get('roleTransition')!='same':gap(f'slot {slot} unchanged role has a contradictory transition')
            if expected_required:
                if name in ('register-fallback-variant-output','after-all-fallback-registrations-before-final-prepare',
                            'final-prepare-pass1','final-prepare-pass2','final-before-rebind','final-after-rebind'):
                    if snapshot.get('registrationOutcome')!='registered'or snapshot.get('persistentFallbackVariantRegistered')is not True:
                        gap(f'slot {slot} required variant has no verified registration')
            elif (snapshot.get('registrationOutcome')!='skipped'or snapshot.get('requiresPersistentFallbackRegistration')is not False or
                  snapshot.get('persistentFallbackVariantRegistered')is not False):
                gap(f'slot {slot} not-required route performed or requested registration')
    return failures
