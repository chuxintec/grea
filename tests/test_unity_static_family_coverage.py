import copy
import unittest
from monkey.unity_static_family_coverage import merge_sort,gate_layout


class SavedFamilyCoverageTests(unittest.TestCase):
    def fixture(self):
        source=dict(sourceId='source:sort',sourceNodeId='source:node',sourceType='cc.SortOrder',
                    sourceEnabled=True,expectedMarkerType='NativeSortIdentity')
        marker=dict(sourceId=source['sourceId'],actualSourceId=source['sourceId'],markerPersistent=True,
            markerGuid='a'*32,markerLocalFileId=41,verified=True,identityComponentEnabled=False)
        queue=dict(driverPersistent=True,driverGuid='b'*32,driverLocalFileId=42,
                   sourceFields=[marker],sourceSortRoots=[])
        plan=dict(staticSortContinuation=dict(sourceComponents=[source]))
        saved=dict(sourcePrefabs=[dict(staticSortFields=dict(persistentAsset=[queue]))])
        return plan,saved,marker,queue

    def test_queue_fail_does_not_promote_a_valid_marker(self):
        plan,saved,_,_=self.fixture()
        self.assertEqual(merge_sort({},plan,saved,queue_verified=False),{})

    def test_marker_and_driver_are_both_required_and_inputs_immutable(self):
        plan,saved,marker,queue=self.fixture();before=copy.deepcopy(saved)
        result=merge_sort({},plan,saved,queue_verified=True)
        row=result['disabledComponents'][0]
        self.assertEqual(row['localFileId'],41)
        self.assertEqual(row['queueDriverLocalFileId'],42)
        self.assertEqual(row['sourceBehaviorStatus'],'dynamic_not_run')
        self.assertEqual(saved,before)
        for target,key,value in ((marker,'markerPersistent',False),(queue,'driverLocalFileId',0)):
            previous=target[key];target[key]=value
            with self.assertRaisesRegex(ValueError,'SAVED_IDENTITY_INVALID'):
                merge_sort({},plan,saved,queue_verified=True)
            target[key]=previous

    def test_multiple_actual_markers_are_ambiguous(self):
        plan,saved,marker,queue=self.fixture();queue['sourceFields'].append(copy.deepcopy(marker))
        with self.assertRaisesRegex(ValueError,'IDENTITY_AMBIGUOUS'):
            merge_sort({},plan,saved,queue_verified=True)

    def test_slot_field_flag_cannot_replace_actual_algorithm_probe(self):
        readback=dict(components=[dict(sourceId='layout',representation='native-component-slot',nativeStaticFieldsVerified=True)])
        plan=dict(layoutCompletion=dict(nodes=[]),sourcePrefabs=[])
        result,proofs=gate_layout(readback,plan,dict(sourcePrefabs=[]))
        self.assertFalse(result['components'][0]['nativeStaticFieldsVerified'])
        self.assertEqual(proofs,{})
        self.assertTrue(readback['components'][0]['nativeStaticFieldsVerified'])
