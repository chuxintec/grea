"""Check staged TMP capture evidence independently of its aggregate pass flags."""
from __future__ import annotations
import re

CONTRACT='monkey-static-sort-text-capture-lifecycle/1'
_SHA=re.compile(r'[0-9a-f]{64}\Z')
_GUID=re.compile(r'[0-9a-f]{32}\Z')
_FLAGS=('initialEnumerationVerified','allInitialBindingsCaptured','allFallbackProfilesCaptured',
        'allFallbackVariantsRegistered',
        'finalPrepareCompleted','finalSlotSetVerified','allSlotsRebound','sourceTextAndFontRechecked',
        'persistentReferencesRechecked','verified')
_STABLE=('slot','characterReferences','visibleCharacterReferences','disposition','sourceAssetKind',
         'sourceAssetGuid','sourceAssetLocalFileId','atlasGuid','atlasLocalFileId','characterAssetEvidenceSha256')
_AGGREGATE=('initial-after-prepare-source','after-all-fallback-profiles-before-registration',
            'after-all-fallback-registrations-before-final-prepare','final-prepare-pass1','final-prepare-pass2')
_SLOT_PHASES=('capture-fallback-input','capture-fallback-output','register-fallback-variant-input',
              'register-fallback-variant-output','final-before-rebind','final-after-rebind')
_V2_IDENTITIES=tuple(prefix+suffix for prefix in ('sourceGraphicMaterial','textInfoMaterial','sourceShader','sourceTexture')
                     for suffix in ('Guid','LocalFileId'))


def _hash(value):return isinstance(value,str) and _SHA.fullmatch(value) is not None


def _valid_enum(value,sid,text):
    from .prefab_static_sort_readback import _empty_text_slot_row_hash, _text_slot_enumeration_hash
    if (not isinstance(value,dict) or value.get('verified')is not True or value.get('sourceComponentId')!=sid or
        value.get('evidenceContract')!='monkey-static-sort-text-slot-enumeration/2' or
        value.get('sourceTextSha256')!=text or type(value.get('slotCount'))is not int or value['slotCount']<=0 or
        not isinstance(value.get('rows'),list) or len(value['rows'])!=value['slotCount']):return False
    for index,row in enumerate(value['rows']):
        if not isinstance(row,dict) or type(row.get('slot'))is not int or row['slot']!=index:return False
        if row.get('evidenceContract')!='monkey-static-sort-text-slot-evidence/2':return False
        if row.get('disposition')not in ('drawable','empty-placeholder')or row.get('sourceAssetKind')not in ('font','sprite'):return False
        for prefix in ('sourceAsset','atlas'):
            if (not _GUID.fullmatch(row.get(prefix+'Guid')or'')or type(row.get(prefix+'LocalFileId'))is not int or
                not row[prefix+'LocalFileId']):return False
        counts=('characterReferences','visibleCharacterReferences','textInfoNondegenerateTriangleCount','canvasNondegenerateTriangleCount')
        if any(type(row.get(k))is not int or row[k]<0 for k in counts):return False
        if row['disposition']=='drawable'and any(row[k]<=0 for k in counts):return False
        if row['disposition']=='empty-placeholder'and any(row[k]>0 for k in counts[1:]):return False
        if any(not _hash(row.get(k))for k in ('characterEvidenceSha256','characterAssetEvidenceSha256')):return False
        if row['disposition']=='drawable'and not _hash(row.get('sourceMeshSha256')):return False
        if row.get('evidenceSha256')!=_empty_text_slot_row_hash(row):return False
    return value.get('evidenceSha256')==_text_slot_enumeration_hash(value)


def verify_queue(queue,mode,required=False):
    try:return _verify_queue(queue,mode,required)
    except (TypeError,ValueError,KeyError,IndexError,AttributeError) as error:
        return [f'{mode} TMP capture lifecycle malformed evidence: {error}']


def _verify_queue(queue,mode,required=False):
    failures=[]
    actual=queue.get('textSources')
    if not isinstance(actual,list):return failures
    by_source={}
    for row in actual:
        if isinstance(row,dict):by_source.setdefault(row.get('sourceComponentId'),[]).append(row)
    for sid,rows in by_source.items():
        def gap(message):failures.append(f'{mode} TMP capture lifecycle {message}: {sid}')
        receipts=[row.get('captureLifecycle') for row in rows]
        if not required and all(x is None for x in receipts):continue
        if not isinstance(sid,str) or not sid or any(not isinstance(x,dict)for x in receipts):
            gap('receipt is missing');continue
        life=receipts[0]
        if any(x!=life for x in receipts):gap('receipts differ across drawable slots');continue
        text=life.get('sourceTextSha256')
        if (life.get('schemaVersion')!=1 or life.get('contract')!=CONTRACT or life.get('status')!='verified' or
            life.get('sourceComponentId')!=sid or not _hash(text) or not _hash(life.get('evidenceSha256')) or
            any(life.get(k)is not True for k in _FLAGS) or life.get('diagnostic')not in (None,'')):
            gap('contract, source or stage flags differ');continue
        initial=life.get('initialEnumeration');final=life.get('finalEnumeration')
        if not _valid_enum(initial,sid,text) or not _valid_enum(final,sid,text):gap('enumeration hash/denominator is invalid');continue
        initial_ids=[x['slot']for x in initial['rows']if x.get('disposition')=='drawable']
        final_ids=[x['slot']for x in final['rows']if x.get('disposition')=='drawable']
        if (life.get('initialSlotCount')!=initial['slotCount'] or life.get('finalSlotCount')!=final['slotCount'] or
            initial['slotCount']!=final['slotCount'] or life.get('initialDrawableSlotIds')!=initial_ids or
            life.get('finalDrawableSlotIds')!=final_ids or initial_ids!=final_ids):gap('raw/drawable slot sets differ')
        for before,after in zip(initial['rows'],final['rows']):
            if any(before.get(k)!=after.get(k)for k in _STABLE):gap('source text/font/atlas/character slot evidence drifted')
        font=(life.get('ownerFontAssetGuid'),life.get('ownerFontAssetLocalFileId'))
        owner_material=(life.get('ownerFontMaterialGuid'),life.get('ownerFontMaterialLocalFileId'),life.get('ownerFontMaterialFingerprint'))
        if (not _GUID.fullmatch(font[0] or '') or type(font[1])is not int or not font[1]):gap('primary font identity is absent')
        if (not _GUID.fullmatch(owner_material[0] or '') or type(owner_material[1])is not int or
            not owner_material[1] or not _hash(owner_material[2])):gap('primary material identity is absent')
        observed_slots=[]
        for row in rows:
            slot=row.get('materialSlot');observed_slots.append(slot);evidence=row.get('evidence')or{}
            if (evidence.get('textSlotEnumeration')!=final or
                evidence.get('captureLifecycle')not in (None,life)):
                gap('readback does not use the exact final snapshot')
            if mode=='loaded':
                current=evidence.get('currentTextSlotEnumeration')
                if not _valid_enum(current,sid,text):gap('loaded current enumeration hash/contract is invalid')
                elif (current['slotCount']!=final['slotCount']or
                      any(a.get(k)!=b.get(k)for a,b in zip(final['rows'],current['rows'])for k in _V2_IDENTITIES)):
                    gap('loaded current material/shader/texture identities differ from capture')
        if len(set(observed_slots))!=len(observed_slots) or set(observed_slots)!=set(final_ids):gap('drawable readback denominator differs')
        phases=life.get('phases')
        if not isinstance(phases,list) or not phases:gap('phase log is missing');continue
        indexes={};snapshots={};phase_enums={}
        for index,phase in enumerate(phases):
            if not isinstance(phase,dict):gap('phase row is malformed');continue
            name=phase.get('phase');slot=phase.get('slot');key=(name,slot)
            if phase.get('status')!='observed' or phase.get('diagnostic')not in (None,''):gap('phase was not successfully observed')
            if key in indexes:gap('phase/source slot repeats')
            indexes[key]=index
            enumeration=phase.get('enumeration');phase_enums[key]=enumeration
            if (phase.get('sourceComponentId')!=sid or phase.get('sourceTextSha256')!=text or
                (phase.get('ownerFontAssetGuid'),phase.get('ownerFontAssetLocalFileId'))!=font or
                (phase.get('ownerFontMaterialGuid'),phase.get('ownerFontMaterialLocalFileId'),phase.get('ownerFontMaterialFingerprint'))!=owner_material or
                not _valid_enum(enumeration,sid,text) or phase.get('enumerationSha256')!=(enumeration or{}).get('evidenceSha256')):
                gap('phase source/font/enumeration association differs')
            slots=phase.get('slots')
            if not isinstance(slots,list):gap('phase slot snapshots are absent');continue
            slot_rows={x.get('slot'):x for x in slots if isinstance(x,dict)}
            if len(slot_rows)!=len(slots):gap('phase slot snapshots repeat')
            for snapshot in slot_rows.values():
                if ((snapshot.get('ownerFontAssetGuid'),snapshot.get('ownerFontAssetLocalFileId'))!=font or
                    (snapshot.get('ownerFontMaterialGuid'),snapshot.get('ownerFontMaterialLocalFileId'),snapshot.get('ownerFontMaterialFingerprint'))!=owner_material):
                    gap('binding snapshot primary font/material differs')
                if not _hash(snapshot.get('textInfoCharacterMaterialFingerprint')):
                    gap('binding character material fingerprint is absent')
                number=snapshot.get('slot')
                if type(number)is not int or not 0<=number<len((enumeration or{}).get('rows',[])):
                    gap('binding snapshot slot is outside its phase enumeration')
                elif any(snapshot.get(k)!=enumeration['rows'][number].get(k)for k in _V2_IDENTITIES):
                    gap('binding snapshot material/shader/texture identity differs from phase enumeration')
            snapshots[key]=slot_rows
            if slot==-1:
                if set(slot_rows)!=set(initial_ids):gap('aggregate binding denominator differs')
            elif slot not in initial_ids or set(slot_rows)!={slot}:gap('per-slot binding denominator differs')
        aggregate=_AGGREGATE
        expected={(name,-1)for name in aggregate}|{(name,slot)for slot in initial_ids for name in _SLOT_PHASES}
        if set(indexes)!=expected:gap('phase set contains missing, unexpected or refused stages')
        if any((name,-1)not in indexes for name in aggregate):gap('aggregate capture stages are incomplete')
        for a,b in zip(aggregate,aggregate[1:]):
            if indexes.get((a,-1),-1)>=indexes.get((b,-1),-1):gap('aggregate phase order differs')
        if phase_enums.get((aggregate[0],-1))!=initial:gap('initial phase does not match its frozen snapshot')
        if phase_enums.get((aggregate[-1],-1))!=final:gap('final preparation does not match its frozen snapshot')
        if phase_enums.get(('final-prepare-pass1',-1))!=phase_enums.get(('final-prepare-pass2',-1)):
            gap('consecutive final preparations did not stabilize the full slot snapshot')
        for slot in initial_ids:
            keys=[(name,slot)for name in _SLOT_PHASES]
            if any(key not in indexes for key in keys):gap(f'slot {slot} capture/rebind stages are incomplete');continue
            if not (indexes[(aggregate[0],-1)]<indexes[keys[0]]<indexes[keys[1]]<indexes[(aggregate[1],-1)]<
                    indexes[keys[2]]<indexes[keys[3]]<indexes[(aggregate[2],-1)]<
                    indexes[(aggregate[-1],-1)]<indexes[keys[4]]<indexes[keys[5]]):gap(f'slot {slot} capture/rebind order differs')
            for key in keys[4:]:
                if phase_enums[key]!=final:gap(f'slot {slot} rebind uses a different final enumeration')
            capture=snapshots.get(keys[1],{}).get(slot,{})
            register_in=snapshots.get(keys[2],{}).get(slot,{})
            registered=snapshots.get(keys[3],{}).get(slot,{})
            before=snapshots.get(keys[0],{}).get(slot,{})
            current=snapshots.get(keys[4],{}).get(slot,{})
            rebound=snapshots.get(keys[5],{}).get(slot,{})
            evidence=next((row for row in rows if row['materialSlot']==slot),{}).get('evidence')or{}
            final_row=final['rows'][slot]
            for output_key,enum_prefix in (('shader','sourceShader'),('texture','sourceTexture')):
                if (evidence.get(output_key+'Guid'),evidence.get(output_key+'LocalFileId'))!=(final_row.get(enum_prefix+'Guid'),final_row.get(enum_prefix+'LocalFileId')):
                    gap(f'slot {slot} readback {output_key} identity differs from final enumeration')
            if (evidence.get('ownerFontMaterialGuid'),evidence.get('ownerFontMaterialLocalFileId'),evidence.get('ownerFontMaterialFingerprint'))!=owner_material:
                gap(f'slot {slot} readback primary material differs from capture')
            stable=(*_STABLE,'sourceGraphicEnabled','sourceGraphicActiveSelf','ownerFontAssetGuid',
                    'ownerFontAssetLocalFileId','ownerFontMaterialGuid','ownerFontMaterialLocalFileId',
                    'ownerFontMaterialFingerprint','fallbackFontAssetGuid','fallbackFontAssetLocalFileId',
                    'fallbackFontMaterialGuid','fallbackFontMaterialLocalFileId','fallbackFontMaterialFingerprint',
                    'sourceTextureGuid','sourceTextureLocalFileId')
            if any(before.get(k)!=current.get(k)for k in stable):gap(f'slot {slot} binding source identity drifted')
            layout_keys=('sourceComponentId','sourceTextSha256','materialSlot','textLayoutInputs','textLayoutEvidenceSha256',
                         'canvasRenderMode','canvasScaleFactor','worldCameraAssigned','ownerLossyScaleY','graphicLossyScaleY',
                         'ownerFontSize','ownerFontSizeMin','ownerFontSizeMax','ownerFontStyle','ownerAutoSizing',
                         'charWidthAdjustmentDelta','characterHorizontalScale')
            a=before.get('textScaleContext');b=current.get('textScaleContext')
            if not isinstance(a,dict) or not isinstance(b,dict) or any(a.get(k)!=b.get(k)for k in layout_keys):
                gap(f'slot {slot} layout/scale operands drifted')
            profile=('bakedProxyMaterialGuid','bakedProxyMaterialLocalFileId','bakedProxyMaterialFingerprint',
                     'transientFallbackFingerprint','tmpFallbackMaterialBaked','tmpFallbackAlgorithm')
            if any(capture.get(k)!=register_in.get(k)or capture.get(k)!=registered.get(k)for k in profile):
                gap(f'slot {slot} registered fallback profile differs from capture')
            if register_in.get('requiresPersistentFallbackRegistration')!=capture.get('requiresPersistentFallbackRegistration'):
                gap(f'slot {slot} registration requirement changed before registration')
            if type(capture.get('requiresPersistentFallbackRegistration'))is not bool:
                gap(f'slot {slot} registration requirement is absent')
            if registered.get('requiresPersistentFallbackRegistration')is not False:
                gap(f'slot {slot} fallback registration is incomplete')
            if capture.get('requiresPersistentFallbackRegistration')is True and registered.get('persistentFallbackVariantRegistered')is not True:
                gap(f'slot {slot} required fallback variant was not registered')
            if capture.get('tmpFallbackMaterialBaked')is True:
                if (not _GUID.fullmatch(capture.get('bakedProxyMaterialGuid')or'') or
                    type(capture.get('bakedProxyMaterialLocalFileId'))is not int or not capture['bakedProxyMaterialLocalFileId'] or
                    not _hash(capture.get('bakedProxyMaterialFingerprint')) or
                    capture.get('transientFallbackFingerprint')!=capture.get('bakedProxyMaterialFingerprint')):
                    gap(f'slot {slot} captured fallback profile is unbound')
                if (evidence.get('proxyMaterialGuid'),evidence.get('proxyMaterialLocalFileId'),evidence.get('bakedProxyMaterialFingerprint'))!=(capture.get('bakedProxyMaterialGuid'),capture.get('bakedProxyMaterialLocalFileId'),capture.get('bakedProxyMaterialFingerprint')):
                    gap(f'slot {slot} readback proxy material differs from captured profile')
                expected_fp=capture.get('bakedProxyMaterialFingerprint')
                final_row=final['rows'][slot];initial_row=initial['rows'][slot]
                if initial_row.get('sourceGraphicMaterialFingerprint')!=expected_fp or final_row.get('sourceGraphicMaterialFingerprint')!=expected_fp:
                    gap(f'slot {slot} fallback material fingerprint drifted')
                if registered.get('persistentFallbackVariantRegistered')is True:
                    if (final_row.get('sourceGraphicMaterialGuid'),final_row.get('sourceGraphicMaterialLocalFileId'))!=(capture.get('bakedProxyMaterialGuid'),capture.get('bakedProxyMaterialLocalFileId')):
                        gap(f'slot {slot} final material is not the registered profile')
                elif final_row.get('sourceGraphicMaterialGuid')or final_row.get('sourceGraphicMaterialLocalFileId'):
                    gap(f'slot {slot} transient fallback unexpectedly became persistent')
                if (initial_row.get('sourceMeshSha256')!=final_row.get('sourceMeshSha256')and
                    all(initial_row.get(k)==final_row.get(k)for k in
                        ('characterEvidenceSha256','textInfoMaterialFingerprint','sourceGraphicMaterialFingerprint'))and
                    before.get('textInfoCharacterMaterialFingerprint')==current.get('textInfoCharacterMaterialFingerprint')):
                    gap(f'slot {slot} mesh changed without an observed material transition')
            else:
                if (evidence.get('materialGuid'),evidence.get('materialLocalFileId'))!=(final_row.get('sourceGraphicMaterialGuid'),final_row.get('sourceGraphicMaterialLocalFileId')):
                    gap(f'slot {slot} readback source material identity differs from final enumeration')
                unchanged=('sourceGraphicMaterialGuid','sourceGraphicMaterialLocalFileId','sourceGraphicMaterialFingerprint',
                           'textInfoMaterialFingerprint','characterEvidenceSha256','sourceMeshSha256')
                if any(initial['rows'][slot].get(k)!=final['rows'][slot].get(k)for k in unchanged):
                    gap(f'slot {slot} non-fallback material/mesh changed')
            for snap in (current,rebound):
                for k in (*_STABLE,'sourceGraphicMaterialFingerprint','textInfoMaterialFingerprint','characterEvidenceSha256','sourceMeshSha256'):
                    if snap.get(k)!=final['rows'][slot].get(k):gap(f'slot {slot} final binding does not match enumeration: {k}')
            if current.get('textInfoCharacterMaterialFingerprint')!=rebound.get('textInfoCharacterMaterialFingerprint'):
                gap(f'slot {slot} rebind changed the final character material fingerprint')
    return failures
