"""Inactive source evidence never pretends that an unreadable SDK list is empty."""
import copy
import unittest

from monkey.prefab_static_sort_readback import _check_spine_non_draw_children, _inactive_spine_source_flow_matches


def fixture():
    expected=dict(sourceComponentId='spine:source',node='child',sourceType='sp.Skeleton',sourceActive=False,sourceEnabled=True)
    plan=dict(sourceManifestSha256='a'*64,
              nodes=[dict(sourceId='child',parent='root',active=True),dict(sourceId='root',parent=None,active=False)],
              sourcePrefabs=[dict(sourceId='prefab',root='root',nodes=['child','root'])],
              components=[dict(sourceId='spine:source',node='child',type='sp.Skeleton',enabled=True)])
    proof=dict(contract='monkey-static-spine-inactive-source-flow/1',schemaVersion=1,
               sourceManifestSha256='a'*64,sourceComponentId='spine:source',node='child',
               sourcePrefabId='prefab',sourcePrefabRootNodeId='root',sourceActivityPath=['child','root'],
               sourceActivityValues=[True,False],inactiveSourceAncestorId='root',sourceEffectiveActive=False,
               sourceComponentEnabled=True,runtimeRendererListRequired=False,
               rendererListDisposition='not-required-source-inactive-subtree',
               persistentOwnerType='Spine.Unity.SkeletonGraphic',loadedOwnerType='Spine.Unity.SkeletonGraphic',
               persistentOwnerActiveSelf=True,loadedOwnerActiveSelf=True,loadedOwnerActiveInHierarchy=False)
    proof.update(dict.fromkeys(['applicable','verified','sourceActivityVerified','controlledHostVerified',
        'persistentIdentityVerified','loadedIdentityVerified','persistentEnabledVerified','loadedEnabledVerified'],True))
    row=dict(sourceComponentId='spine:source',sourceNode='child',noDrawReason='inactive-source-subtree-no-render-flow',
             sourceOwnerEnabled=True,sourceNodeActive=False,sourceIdentityComponentId='spine:source',
             sourceDataAssetId='spineAsset:data',sourceDataAssetPath='Assets/Spine.asset',sourceDataAssetGuid='b'*32,
             childPath='render-child',childGraphicType='UnityEngine.UI.RawImage',childMaterialGuid='c'*32,
             childTextureGuid='d'*32,sourceIdentityVerified=True,sourceDataReferenceVerified=True,
             registeredChildVerified=True,childReferencePersistent=True,verified=True,sourceChildEnabled=True,
             sourceChildActiveSelf=True,sourceChildActiveInHierarchy=False,targetChildEnabled=True,
             targetChildActiveInHierarchy=False,childNoDrawVerified=True,sourceChildMeshVertexCount=4,
             sourceChildMeshSubmeshCount=1,sourceChildMaterialCount=1,inactiveSourceFlowProof=proof,
             ownerRendererListReadable=False,currentOwnerRendererListReadable=False)
    row['registrationEvidenceDisposition']='captured-registered-child-and-persisted-owner-references;current-list-not-required'
    return expected,plan,proof,row


class SpineInactiveSourceFlowTests(unittest.TestCase):
    def test_full_source_path_can_prove_no_render_without_readable_sdk_list(self):
        expected,plan,proof,row=fixture()
        self.assertTrue(_inactive_spine_source_flow_matches(proof,expected,plan))
        for mode in ['persistent','loaded']:
            self.assertEqual([],_check_spine_non_draw_children(dict(nonDrawRenderers=[expected]),dict(spineNonDrawChildren=[row]),mode,plan))
        self.assertFalse(row['ownerRendererListReadable'])
        self.assertFalse(row['currentOwnerRendererListReadable'])

    def test_each_peer_identity_activity_host_and_provenance_gate_is_required(self):
        expected,plan,proof,row=fixture()
        changes={'sourceManifestSha256':'e'*64,'schemaVersion':True,'sourceComponentId':'other',
                 'sourcePrefabId':'other','sourcePrefabRootNodeId':'child','sourceActivityPath':['child'],
                 'sourceActivityValues':[True,True],'inactiveSourceAncestorId':'child',
                 'persistentIdentityVerified':False,'loadedIdentityVerified':False,'controlledHostVerified':False,
                 'loadedOwnerActiveInHierarchy':True,'runtimeRendererListRequired':True,
                 'persistentOwnerActiveSelf':False,'loadedEnabledVerified':False,'contract':'other'}
        for key,value in changes.items():
            with self.subTest(key=key):
                bad=copy.deepcopy(proof);bad[key]=value
                self.assertFalse(_inactive_spine_source_flow_matches(bad,expected,plan))

    def test_active_source_or_wrong_parent_path_cannot_use_inactive_evidence(self):
        expected,plan,proof,row=fixture();plan['nodes'][1]['active']=True
        self.assertFalse(_inactive_spine_source_flow_matches(proof,expected,plan))
        expected,plan,proof,row=fixture();plan['nodes'][0]['parent']='missing'
        self.assertFalse(_inactive_spine_source_flow_matches(proof,expected,plan))

    def test_child_resource_and_data_reference_checks_remain_strict(self):
        expected,plan,proof,row=fixture()
        for key in ['sourceDataReferenceVerified','childReferencePersistent','registeredChildVerified']:
            with self.subTest(key=key):
                bad=copy.deepcopy(row);bad[key]=False
                self.assertTrue(_check_spine_non_draw_children(dict(nonDrawRenderers=[expected]),dict(spineNonDrawChildren=[bad]),'persistent',plan))

    def test_inactive_owner_only_proof_does_not_claim_an_empty_list_or_mesh(self):
        expected,plan,proof,row=fixture()
        row.update(ownerOnlyNoRegisteredChildren=True,registeredChildVerified=False,
                   ownerRendererListEmpty=False,currentOwnerRendererListEmpty=False,
                   ownerRootMeshEmpty=False,currentOwnerRootMeshEmpty=False,
                   childPath=None,childGraphicType=None,childMaterialGuid=None,childTextureGuid=None,
                   sourceChildMeshVertexCount=-1,sourceChildMeshSubmeshCount=-1,sourceChildMaterialCount=-1)
        self.assertEqual([],_check_spine_non_draw_children(dict(nonDrawRenderers=[expected]),dict(spineNonDrawChildren=[row]),'loaded',plan))
        row['sourceDataReferenceVerified']=False
        self.assertTrue(_check_spine_non_draw_children(dict(nonDrawRenderers=[expected]),dict(spineNonDrawChildren=[row]),'loaded',plan))

    def test_new_reason_requires_new_proof(self):
        expected,plan,proof,row=fixture();del row['inactiveSourceFlowProof']
        self.assertTrue(_check_spine_non_draw_children(dict(nonDrawRenderers=[expected]),dict(spineNonDrawChildren=[row]),'persistent',plan))

    def test_inactive_child_registration_is_explicitly_captured_not_current_sdk_membership(self):
        expected,plan,proof,row=fixture();del row['registrationEvidenceDisposition']
        self.assertTrue(_check_spine_non_draw_children(dict(nonDrawRenderers=[expected]),dict(spineNonDrawChildren=[row]),'loaded',plan))

    def test_original_active_legacy_reason_is_not_reclassified(self):
        expected,plan,proof,row=fixture();expected['sourceActive']=True
        self.assertFalse(_inactive_spine_source_flow_matches(proof,expected,plan))


if __name__=='__main__':unittest.main()
