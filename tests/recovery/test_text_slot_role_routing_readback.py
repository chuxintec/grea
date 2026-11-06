import unittest

from .test_text_slot_capture_lifecycle_readback import fixture
from grea.recovery.text_slot_role_routing_readback import CONTRACT,verify_lifecycle


def role_fixture(role='primary-font',outline=False):
    _,life=fixture();life['slotRoleRoutingContract']=CONTRACT
    life['emptySlotRoutes']=[dict(slot=0,captureRole='empty-placeholder',captureRoleVerified=True,
        registrationDisposition='not-required',registrationOutcome='skipped',
        registrationSkipReason='empty-placeholder-has-no-drawable-binding')]
    cross=role.startswith('fallback-font-')and role!='fallback-font-same-asset-multi-atlas'
    required=cross and outline
    if not cross:
        life['ownerFontAssetGuid']='b'*32;life['ownerFontAssetLocalFileId']=42
    for phase in life['phases']:
        for s in phase['slots']:
            s.update(captureRole=role,observedRole=role,roleTransition='same',captureRoleVerified=True,
                observedRoleVerified=True,fontAtlasRenderMode=4169,fontAssetIsRasterBitmap=role=='primary-font',
                generatedSubmesh=role!='primary-font',outlineDriverPresent=outline,outlineTargetMatchesOwner=outline,
                fallbackAtlasIndex=1 if role=='fallback-font-same-asset-multi-atlas'else 0,registrationDisposition='required'if required else'not-required',
                registrationOutcome='pending'if required else'skipped',
                registrationSkipReason=''if required else'outline-driver-absent'if cross else {'primary-font':'primary-font-slot-does-not-use-fallback-variant','sprite':'sprite-slot-does-not-use-font-fallback-variant','fallback-font-same-asset-multi-atlas':'same-font-multi-atlas-route-does-not-register-fallback-variant'}[role],
                ownerFontAssetGuid=life['ownerFontAssetGuid'],ownerFontAssetLocalFileId=life['ownerFontAssetLocalFileId'],
                fallbackFontAssetGuid='b'*32 if cross or role=='fallback-font-same-asset-multi-atlas'else'',
                fallbackFontAssetLocalFileId=42 if cross or role=='fallback-font-same-asset-multi-atlas'else 0,
                requiresPersistentFallbackRegistration=required,persistentFallbackVariantRegistered=False,
                tmpFallbackMaterialBaked=role=='fallback-font-transient')
            if role=='sprite':s['sourceAssetKind']='sprite';s['fontAtlasRenderMode']=-1;s['fontAssetIsRasterBitmap']=False;s['fallbackAtlasIndex']=-1
            if role!='fallback-font-transient':
                s['sourceGraphicMaterialGuid']=s['bakedProxyMaterialGuid'];s['sourceGraphicMaterialLocalFileId']=s['bakedProxyMaterialLocalFileId']
                s['sourceMaterialFingerprint']=s['bakedProxyMaterialFingerprint']
            after=phase['phase']in ('register-fallback-variant-output','after-all-fallback-registrations-before-final-prepare',
                  'final-prepare-pass1','final-prepare-pass2','final-before-rebind','final-after-rebind')
            if required and after:
                s['registrationOutcome']='registered';s['requiresPersistentFallbackRegistration']=False;s['persistentFallbackVariantRegistered']=True
            if required and role=='fallback-font-transient'and phase['phase'].startswith(('final-prepare','final-before','final-after')):
                s['observedRole']='fallback-font-persistent';s['roleTransition']='transient-to-persistent-registered'
                s['sourceGraphicMaterialGuid']=s['bakedProxyMaterialGuid'];s['sourceGraphicMaterialLocalFileId']=s['bakedProxyMaterialLocalFileId']
    return life


class SlotRoleRoutingTests(unittest.TestCase):
    def test_primary_bitmap_material_is_verified_skip_without_fallback_asset(self):
        life=role_fixture();self.assertEqual([],verify_lifecycle(life,'persistent',True))

    def test_real_cross_font_registration_and_registered_material_transition(self):
        self.assertEqual([],verify_lifecycle(role_fixture('fallback-font-transient',True),'loaded',True))

    def test_persistent_fallback_registers_without_transient_bake(self):
        self.assertEqual([],verify_lifecycle(role_fixture('fallback-font-persistent',True),'loaded',True))

    def test_cross_font_without_outline_is_verified_skip(self):
        self.assertEqual([],verify_lifecycle(role_fixture('fallback-font-persistent'),'loaded',True))

    def test_sprite_and_same_font_atlas_are_explicit_nonregistration_roles(self):
        for role in ('sprite','fallback-font-same-asset-multi-atlas'):
            with self.subTest(role=role):self.assertEqual([],verify_lifecycle(role_fixture(role),'persistent',True))

    def test_false_required_marker_cannot_hide_cross_font_outline(self):
        life=role_fixture('fallback-font-transient',True)
        for phase in life['phases']:
            for row in phase['slots']:row['registrationDisposition']='not-required'
        self.assertTrue(verify_lifecycle(life,'persistent',True))

    def test_primary_cannot_be_renamed_fallback_to_enter_registration(self):
        life=role_fixture()
        for phase in life['phases']:
            for row in phase['slots']:row['captureRole']='fallback-font-persistent'
        self.assertTrue(verify_lifecycle(life,'loaded',True))

    def test_primary_cannot_request_or_report_variant_registration(self):
        for key in ('requiresPersistentFallbackRegistration','persistentFallbackVariantRegistered'):
            life=role_fixture();life['phases'][-1]['slots'][0][key]=True
            with self.subTest(key=key):self.assertTrue(verify_lifecycle(life,'loaded',True))

    def test_foreign_outline_target_never_qualifies_for_registration(self):
        life=role_fixture('fallback-font-transient',True)
        for phase in life['phases']:
            for row in phase['slots']:row['outlineTargetMatchesOwner']=False
        self.assertTrue(verify_lifecycle(life,'loaded',True))

    def test_equal_fingerprint_with_different_direct_asset_is_not_verified_skip(self):
        life=role_fixture();p=next(p for p in life['phases']if p['phase']=='capture-fallback-output')
        p['slots'][0]['bakedProxyMaterialGuid']='0'*32
        self.assertTrue(verify_lifecycle(life,'loaded',True))

    def test_registered_transition_must_use_exact_captured_bake(self):
        life=role_fixture('fallback-font-transient',True);life['phases'][-1]['slots'][0]['sourceGraphicMaterialGuid']='0'*32
        self.assertTrue(verify_lifecycle(life,'loaded',True))

    def test_empty_placeholder_has_exact_skip_denominator(self):
        life=role_fixture();life['emptySlotRoutes']=[]
        self.assertTrue(verify_lifecycle(life,'loaded',True))

    def test_skip_reason_and_generated_provenance_must_match_role(self):
        for key,value in (('registrationSkipReason','outline-driver-absent'),('generatedSubmesh',True),('fallbackAtlasIndex',1)):
            life=role_fixture()
            for phase in life['phases']:
                for row in phase['slots']:row[key]=value
            with self.subTest(key=key):self.assertTrue(verify_lifecycle(life,'loaded',True))

    def test_legacy_is_optional_new_flag_requires_role_contract(self):
        life=role_fixture();life.pop('slotRoleRoutingContract')
        self.assertEqual([],verify_lifecycle(life,'loaded',False));self.assertTrue(verify_lifecycle(life,'loaded',True))


if __name__=='__main__':unittest.main()
