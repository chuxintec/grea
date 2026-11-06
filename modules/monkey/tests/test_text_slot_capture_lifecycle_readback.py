import copy
import hashlib
import json
from pathlib import Path
import unittest

from monkey.prefab_static_sort_readback import _empty_text_slot_row_hash, _text_slot_enumeration_hash
from monkey.text_slot_capture_lifecycle_readback import CONTRACT,verify_queue,_valid_scale_context


def enumeration():
    sid='label';text=hashlib.sha256('2日30分'.encode()).hexdigest();rows=[]
    for slot in range(3):
        row=dict(evidenceContract="monkey-static-sort-text-slot-evidence/2",slot=slot,characterReferences=0 if slot==0 else 2,visibleCharacterReferences=0 if slot==0 else 2,
            textInfoMaterialMissing=False,textInfoVertexCount=0 if slot==0 else 8,textInfoTriangleIndexCount=0 if slot==0 else 12,
            textInfoNondegenerateTriangleCount=0 if slot==0 else 4,canvasVertexCount=0 if slot==0 else 8,
            canvasTriangleIndexCount=0 if slot==0 else 12,canvasNondegenerateTriangleCount=0 if slot==0 else 4,
            disposition='empty-placeholder'if slot==0 else'drawable',sourceAssetKind='font',sourceAssetGuid='b'*32,
            sourceAssetLocalFileId=42,atlasGuid='c'*32,atlasLocalFileId=43,textInfoMaterialFingerprint='d'*64,
            sourceGraphicMaterialFingerprint='d'*64,characterEvidenceSha256='e'*64,characterAssetEvidenceSha256='f'*64,
            sourceMeshSha256='1'*64,sourceGraphicMaterialGuid='',sourceGraphicMaterialLocalFileId=0)
        row['evidenceSha256']=_empty_text_slot_row_hash(row);rows.append(row)
    value=dict(evidenceContract='monkey-static-sort-text-slot-enumeration/2',sourceComponentId=sid,sourceTextSha256=text,slotCount=3,verified=True,rows=rows)
    rehash(value);return value


def rehash(value):
    for row in value['rows']:row['evidenceSha256']=_empty_text_slot_row_hash(row)
    value['evidenceSha256']=_text_slot_enumeration_hash(value)


def scale_context(slot,text):
    layout=dict(rectSize=dict(x=100,y=30),pivot=dict(x=.5,y=.5),margin=dict(x=0,y=0,z=0,w=0),
                fontSize=28,fontSizeMin=1,fontSizeMax=72,fontStyle=0,autoSizing=False)
    for key in ('characterSpacing','wordSpacing','lineSpacing','lineSpacingAdjustment','paragraphSpacing',
                'textLineBoxLineHeight','textLineBoxExtraLineFraction','textLineBoxNativePreferredHeight'):layout[key]=0
    return dict(sourceComponentId='label',sourceTextSha256=text,materialSlot=slot,
                formula='TextMeshProUGUI.GenerateTextMesh.uv0.w-v1',canvasRenderMode=0,canvasScaleFactor=1,
                worldCameraAssigned=False,ownerLossyScaleY=1,graphicLossyScaleY=1,ownerFontSize=28,
                ownerFontSizeMin=1,ownerFontSizeMax=72,ownerFontStyle=0,ownerAutoSizing=False,
                charWidthAdjustmentDelta=0,characterHorizontalScale=1,textLayoutInputs=layout,
                operandEvidenceSha256='a'*64,textLayoutEvidenceSha256='b'*64,evidenceSha256='c'*64,
                characters=[dict(characterIndex=i,materialSlot=slot,vertexIndex=i*4,scale=1,visible=True)for i in range(2)],
                meshUv0W=[1]*8)


def fixture():
    initial=enumeration();final=copy.deepcopy(initial)
    life=dict(schemaVersion=1,contract=CONTRACT,status='verified',diagnostic='',sourceComponentId='label',
        sourceTextSha256=initial['sourceTextSha256'],evidenceSha256='a'*64,ownerFontAssetGuid='4'*32,ownerFontAssetLocalFileId=2,
        ownerFontMaterialGuid='7'*32,ownerFontMaterialLocalFileId=3,ownerFontMaterialFingerprint='8'*64,
        initialSlotCount=3,finalSlotCount=3,initialDrawableSlotIds=[1,2],finalDrawableSlotIds=[1,2],
        initialEnumeration=initial,finalEnumeration=final,phases=[])
    for key in ['initialEnumerationVerified','allInitialBindingsCaptured','allFallbackProfilesCaptured','allFallbackVariantsRegistered','finalPrepareCompleted',
                'finalSlotSetVerified','allSlotsRebound','sourceTextAndFontRechecked','persistentReferencesRechecked','verified']:life[key]=True
    def phase(name,slot=-1):
        snapshot=copy.deepcopy(final if name in ['final-prepare-pass2','final-before-rebind','final-after-rebind']else initial)
        life['phases'].append(dict(phase=name,status='observed',slot=slot,sourceComponentId='label',sourceTextSha256=life['sourceTextSha256'],
             ownerFontAssetGuid='4'*32,ownerFontAssetLocalFileId=2,
             ownerFontMaterialGuid='7'*32,ownerFontMaterialLocalFileId=3,ownerFontMaterialFingerprint='8'*64,enumeration=snapshot,enumerationSha256=snapshot['evidenceSha256'],
             slots=[dict(snapshot['rows'][i],tmpFallbackMaterialBaked=True,persistentFallbackVariantRegistered=False,
                         requiresPersistentFallbackRegistration=False,transientFallbackFingerprint='d'*64,
                         textInfoCharacterMaterialFingerprint='d'*64,
                         bakedProxyMaterialGuid='5'*32,bakedProxyMaterialLocalFileId=7,bakedProxyMaterialFingerprint='d'*64,
                         ownerFontAssetGuid='4'*32,ownerFontAssetLocalFileId=2,
                         ownerFontMaterialGuid='7'*32,ownerFontMaterialLocalFileId=3,ownerFontMaterialFingerprint='8'*64,
                         textScaleContext=scale_context(i,life['sourceTextSha256']))for i in ([1,2]if slot==-1 else[slot])]))
    phase('initial-after-prepare-source')
    for slot in [1,2]:phase('capture-fallback-input',slot);phase('capture-fallback-output',slot)
    phase('after-all-fallback-profiles-before-registration')
    for slot in [1,2]:phase('register-fallback-variant-input',slot);phase('register-fallback-variant-output',slot)
    for name in ['after-all-fallback-registrations-before-final-prepare','final-prepare-pass1','final-prepare-pass2']:phase(name)
    for slot in [1,2]:phase('final-before-rebind',slot);phase('final-after-rebind',slot)
    q=dict(textSources=[dict(sourceComponentId='label',materialSlot=i,captureLifecycle=life,
                           evidence=dict(textSlotEnumeration=final,currentTextSlotEnumeration=final,captureLifecycle=life,
                                         ownerFontMaterialGuid='7'*32,ownerFontMaterialLocalFileId=3,ownerFontMaterialFingerprint='8'*64,
                                         proxyMaterialGuid='5'*32,proxyMaterialLocalFileId=7,bakedProxyMaterialFingerprint='d'*64))for i in [1,2]])
    return q,life


class CaptureLifecycleReadbackTests(unittest.TestCase):
    def test_raw_three_slots_only_two_drawable_bindings(self):
        q,life=fixture();self.assertEqual([],verify_queue(q,'persistent',True))
    def test_legacy_absence_is_optional_but_new_required_contract_is_strict(self):
        q=dict(textSources=[dict(sourceComponentId='label',materialSlot=0)])
        self.assertEqual([],verify_queue(q,'loaded',False));self.assertTrue(verify_queue(q,'loaded',True))
    def test_each_stage_flag_is_independent(self):
        for key in ['allInitialBindingsCaptured','allFallbackProfilesCaptured','allFallbackVariantsRegistered','finalPrepareCompleted','persistentReferencesRechecked']:
            q,life=fixture();life[key]=False
            with self.subTest(key=key):self.assertTrue(verify_queue(q,'loaded',True))
    def test_source_text_or_font_drift_blocks(self):
        for key,value in [('sourceTextSha256','0'*64),('ownerFontAssetGuid','0'*32)]:
            q,life=fixture();life['phases'][-1][key]=value
            with self.subTest(key=key):self.assertTrue(verify_queue(q,'loaded',True))
    def test_character_asset_drift_cannot_hide_behind_rehashed_enumeration(self):
        q,life=fixture();life['finalEnumeration']['rows'][1]['sourceAssetGuid']='0'*32;rehash(life['finalEnumeration'])
        self.assertTrue(verify_queue(q,'persistent',True))
    def test_final_slot_graph_must_have_exact_same_receipt_for_all_slots(self):
        q,life=fixture();q['textSources'][1]['captureLifecycle']=copy.deepcopy(life);q['textSources'][1]['captureLifecycle']['evidenceSha256']='0'*64
        self.assertTrue(verify_queue(q,'persistent',True))
    def test_final_snapshot_is_bound_to_actual_readback(self):
        q,life=fixture();q['textSources'][0]['evidence']['textSlotEnumeration']=copy.deepcopy(enumeration());q['textSources'][0]['evidence']['textSlotEnumeration']['evidenceSha256']='0'*64
        self.assertTrue(verify_queue(q,'persistent',True))
    def test_capture_or_rebind_of_missing_slot_is_rejected(self):
        q,life=fixture();life['phases']=[x for x in life['phases']if not(x['phase']=='capture-fallback-output'and x['slot']==2)]
        self.assertTrue(verify_queue(q,'loaded',True))
    def test_reprepare_between_slot_captures_is_not_complete_staged_order(self):
        q,life=fixture();phases=life['phases'];moved=next(x for x in phases if x['phase']=='final-prepare-pass2');phases.remove(moved);phases.insert(2,moved)
        self.assertTrue(verify_queue(q,'loaded',True))
    def test_fallback_persistence_is_verified_per_captured_slot(self):
        q,life=fixture();p=next(x for x in life['phases']if x['phase']=='capture-fallback-output'and x['slot']==1);p['slots'][0]['bakedProxyMaterialLocalFileId']=0
        self.assertTrue(verify_queue(q,'persistent',True))
    def test_hash_tamper_blocks_even_with_success_flags(self):
        q,life=fixture();life['initialEnumeration']['rows'][1]['evidenceSha256']='0'*64
        self.assertTrue(verify_queue(q,'loaded',True))
    def test_drawable_source_denominator_cannot_drop_a_readback_slot(self):
        q,life=fixture();q['textSources'].pop();self.assertTrue(verify_queue(q,'loaded',True))

    def test_malformed_material_slot_is_a_gap_without_verifier_crash(self):
        q,life=fixture();q['textSources'][0]['materialSlot']=[]
        self.assertTrue(verify_queue(q,'loaded',True))

    def test_registration_cannot_start_before_all_profiles_are_captured(self):
        q,life=fixture();p=life['phases'];entry=next(x for x in p if x['phase']=='register-fallback-variant-input');p.remove(entry);p.insert(2,entry)
        self.assertTrue(verify_queue(q,'loaded',True))

    def test_required_variant_cannot_be_reported_as_unregistered_noop(self):
        q,life=fixture()
        for p in life['phases']:
            if p['slot']==1 and p['phase']in ('capture-fallback-output','register-fallback-variant-input'):
                p['slots'][0]['requiresPersistentFallbackRegistration']=True
        self.assertTrue(verify_queue(q,'loaded',True))

    def test_exact_registered_variant_and_transient_noop_can_coexist(self):
        q,life=fixture();final=life['finalEnumeration'];final['rows'][1]['sourceGraphicMaterialGuid']='5'*32;final['rows'][1]['sourceGraphicMaterialLocalFileId']=7;rehash(final)
        for p in life['phases']:
            if p['phase']in ('final-prepare-pass1','final-prepare-pass2','final-before-rebind','final-after-rebind'):
                p['enumeration']=copy.deepcopy(final);p['enumerationSha256']=final['evidenceSha256']
                for snap in p['slots']:
                    snap.update(final['rows'][snap['slot']])
            if p['slot']==1:
                if p['phase']in ('capture-fallback-output','register-fallback-variant-input'):
                    p['slots'][0]['requiresPersistentFallbackRegistration']=True
                if p['phase']=='register-fallback-variant-output':p['slots'][0]['persistentFallbackVariantRegistered']=True
        self.assertEqual([],verify_queue(q,'loaded',True))

    def test_fallback_final_material_cannot_use_another_profile(self):
        q,life=fixture();life['finalEnumeration']['rows'][1]['sourceGraphicMaterialFingerprint']='0'*64;rehash(life['finalEnumeration'])
        self.assertTrue(verify_queue(q,'loaded',True))

    def test_layout_and_source_activity_must_remain_frozen(self):
        for key in ('layout','activity'):
            q,life=fixture();p=next(x for x in life['phases']if x['phase']=='final-before-rebind')
            if key=='layout':p['slots'][0]['textScaleContext']['textLayoutInputs']['rectSize']=[200,30]
            else:p['slots'][0]['sourceGraphicActiveSelf']=False
            with self.subTest(key=key):self.assertTrue(verify_queue(q,'loaded',True))

    def test_final_binding_mesh_cannot_disagree_with_final_enumeration(self):
        q,life=fixture();p=next(x for x in life['phases']if x['phase']=='final-after-rebind');p['slots'][0]['sourceMeshSha256']='0'*64
        self.assertTrue(verify_queue(q,'loaded',True))

    def test_v2_material_identity_is_hash_bound(self):
        q,life=fixture();life['finalEnumeration']['rows'][1]['sourceGraphicMaterialGuid']='0'*32
        self.assertTrue(verify_queue(q,'loaded',True))

    def test_new_lifecycle_cannot_downgrade_to_legacy_slot_hashes(self):
        q,life=fixture()
        for enum in (life['initialEnumeration'],life['finalEnumeration']):
            enum.pop('evidenceContract')
            for row in enum['rows']:row.pop('evidenceContract')
            rehash(enum)
        self.assertTrue(verify_queue(q,'loaded',True))

    def test_fallback_mesh_change_requires_an_observed_material_change(self):
        q,life=fixture();life['finalEnumeration']['rows'][1]['sourceMeshSha256']='0'*64;rehash(life['finalEnumeration'])
        self.assertTrue(verify_queue(q,'loaded',True))

    def test_binding_character_material_transition_accounts_for_fallback_mesh_change(self):
        q,life=fixture();final=life['finalEnumeration'];final['rows'][1]['sourceMeshSha256']='0'*64;rehash(final)
        for p in life['phases']:
            if p['phase']in ('final-prepare-pass1','final-prepare-pass2','final-before-rebind','final-after-rebind'):
                p['enumeration']=copy.deepcopy(final);p['enumerationSha256']=final['evidenceSha256']
                for snap in p['slots']:
                    snap.update(final['rows'][snap['slot']])
                    if snap['slot']==1:snap['textInfoCharacterMaterialFingerprint']='9'*64
        self.assertEqual([],verify_queue(q,'loaded',True))

    def test_equal_fingerprints_do_not_allow_different_readback_shader_or_proxy_identity(self):
        for key in ('shaderGuid','proxyMaterialGuid'):
            q,life=fixture();q['textSources'][0]['evidence'][key]='0'*32
            with self.subTest(key=key):self.assertTrue(verify_queue(q,'loaded',True))

    def test_phase_snapshot_identity_must_match_the_hashed_enumeration(self):
        q,life=fixture();life['phases'][0]['slots'][0]['textInfoMaterialGuid']='0'*32
        self.assertTrue(verify_queue(q,'loaded',True))

    def test_loaded_equal_fingerprint_shader_swap_is_rejected_even_after_rehashing(self):
        q,life=fixture();current=copy.deepcopy(life['finalEnumeration']);current['rows'][1]['sourceShaderGuid']='0'*32;rehash(current)
        for row in q['textSources']:row['evidence']['currentTextSlotEnumeration']=current
        self.assertTrue(verify_queue(q,'loaded',True))

    def test_missing_default_or_nonfinite_context_never_counts_as_equal_valid_operands(self):
        for bad in (None,{},dict(canvasScaleFactor=0),dict(canvasScaleFactor=float('nan'))):
            q,life=fixture()
            for phase in life['phases']:
                for snapshot in phase['slots']:snapshot['textScaleContext']=copy.deepcopy(bad)
            with self.subTest(context=bad):self.assertTrue(verify_queue(q,'persistent',True))

    def test_valid_but_changed_character_scale_operands_are_not_frozen_inputs(self):
        q,life=fixture()
        for phase in life['phases']:
            if phase['phase']in ('final-before-rebind','final-after-rebind'):
                phase['slots'][0]['textScaleContext']['characters'][0]['scale']=2
                phase['slots'][0]['textScaleContext']['operandEvidenceSha256']='0'*64
        self.assertTrue(verify_queue(q,'persistent',True))

    def test_actual18_default_contexts_are_rejected_without_rewriting_the_failure(self):
        pins=Path(__file__).resolve().parents[1]/'.private/foodstreet-four-activity-20261104/dev24-text-context-capture/input-pins.json'
        if not pins.is_file():self.skipTest('actual18 private input pins unavailable')
        pin=next(x for x in json.loads(pins.read_text())if '/StaticSortTextCapture/'in x['path'])
        path=Path(pin['path']);raw=path.read_bytes();self.assertEqual(pin['sha256'],hashlib.sha256(raw).hexdigest())
        failure=json.loads(raw);life=failure['lifecycle'];observed=0
        for phase in life['phases']:
            for snapshot in phase['slots']:
                slot=snapshot['slot'];observed+=1
                self.assertFalse(_valid_scale_context(snapshot['textScaleContext'],life['sourceComponentId'],
                    life['sourceTextSha256'],slot,phase['enumeration']['rows'][slot]))
        self.assertGreater(observed,0);self.assertEqual(raw,path.read_bytes())


if __name__=='__main__':unittest.main()
