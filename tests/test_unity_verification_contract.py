import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from monkey import io
from monkey.native_selection import _native_verification
from monkey.unity_verification_contract import native_diagnostics,coverage_readback,statuses


class UnityVerificationContractTests(unittest.TestCase):
    def test_native_gap_cannot_be_promoted_by_editor_partial(self):
        raw=['COMPONENT_NOT_IMPORTED: source:missing sp.Skeleton']
        diagnostics=native_diagnostics(raw)
        result=statuses('partial',diagnostics,{'nativeStaticValidation':'pass','staticPresentationValidation':'pass'},'editor')
        self.assertEqual(diagnostics[0]['message'],raw[0])
        self.assertEqual(diagnostics[0]['code'],'COMPONENT_NOT_IMPORTED')
        self.assertNotEqual(result['nativeStaticValidation'],'pass')
        self.assertNotEqual(result['staticPresentationValidation'],'pass')
        self.assertEqual(result['runtimeCheck'],'not_run')

    def test_clean_editor_and_pure_dynamic_boundary_supply_no_player_proof(self):
        coverage={'nativeStaticValidation':'pass','staticPresentationValidation':'pass','retentionValidation':'pass'}
        for diagnostics in ([],[{'code':'ANIMATION_DYNAMIC_CURVES_NOT_LOWERED'}]):
            result=statuses('pass',diagnostics,coverage,'editor')
            self.assertEqual(result['nativeStaticValidation'],'pass')
            self.assertEqual(result['runtimeCheck'],'not_run')
            self.assertEqual(result['playerValidation'],'not_run')

    def test_verified_retention_is_distinct_from_source_presentation(self):
        result=statuses('partial',[],{'nativeStaticValidation':'partial','staticPresentationValidation':'partial',
                                      'retentionValidation':'pass'},'editor')
        self.assertEqual(result['retentionValidation'],'pass')
        self.assertEqual(result['nativeStaticValidation'],'partial')
        self.assertEqual(result['staticPresentationValidation'],'partial')

    def test_retained_identity_alone_does_not_verify_its_data(self):
        rb={'components':[{'sourceId':'s','status':'retained','sourceIdentityVerified':True}],
            'diagnostics':[],'sourcePrefabs':[]}
        before=copy.deepcopy(rb)
        self.assertFalse(coverage_readback(rb)['retainedComponents'][0]['verified'])
        self.assertTrue(coverage_readback(rb,{'status':'verified','sourceComponentIds':['s']})['retainedComponents'][0]['verified'])
        self.assertEqual(rb,before)

    def test_actual_unity_type_mapping_and_no_duplicate_field_evidence(self):
        from monkey.prefab_component_coverage import assess
        field={'sourceId':'s','nativeIdentityVerified':True,'fieldsVerified':True,
               'fields':[{'sourceFieldName':'value','kind':'number','storageType':'float',
                          'referenceVerified':False,'referencesVerified':False}]}
        plan={'nodes':[{'sourceId':'n','active':True,'parent':None}],
              'components':[{'sourceId':'s','node':'n','type':'cc.Sprite','nativeType':'cc.Sprite',
                             'staticFieldBinding':{'fields':[{'sourceFieldName':'value'}]}}]}
        row={'sourceId':'s','status':'native','nativeType':'UnityEngine.UI.Image',
             'componentUuid':'guid:1','sourceIdentityVerified':True,'persistent':True}
        rb={'components':[row],'diagnostics':[],
            'sourcePrefabs':[{'components':[row],'staticFieldBindings':[{'binding':field}]}],
            'staticPresentationValidation':{'components':[{'sourceId':'s','sourceVisible':True,'verified':True,'rendered':True}]}}
        normalized=coverage_readback(rb)
        result=assess(plan,normalized,'unity')
        self.assertEqual(result['nativeStaticValidation'],'pass')
        self.assertEqual(result['staticPresentationValidation']['status'],'pass')
        normalized['components'][0]['nativeType']='UnityEngine.Transform'
        self.assertNotEqual(assess(plan,normalized,'unity')['nativeStaticValidation'],'pass')

    def test_unmocked_imported_gate_keeps_file_and_presentation_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();(root/'Analysis/Readback').mkdir(parents=True)
            (root/'Assets').mkdir();(root/'Assets/a.prefab').write_bytes(b'neutral saved prefab fixture')
            rb={'unityVersion':'6000.6.2f1','missingScripts':0,'status':'imported',
                'nativeScope':'saved-source-node-subset','sourceGraphVerification':'saved-source-node-subset',
                'nativeFiles':[{'path':'Assets/a.prefab','sha256':io.sha((root/'Assets/a.prefab').read_bytes())}],
                'editableRoundtrip':True,'sceneReopened':True,'diagnostics':[]}
            path=root/'Analysis/Readback/editor-readback.json';io.write_json(path,rb)
            report={'candidateManifestSha256':'a'*64,'staticValidation':'pass','nativeStaticValidation':'pass',
                    'editorValidation':'pass','staticPresentationValidation':'pass',
                    'componentCoverage':{'schema':'monkey-prefab-component-coverage/1','sourceComponentCount':0,
                                         'uniqueSourceComponentCount':0,'components':[]},'diagnostics':[]}
            def verify(candidate,out,level):
                out.mkdir();io.write_json(out/'verification.json',report)
            # Only the downstream verifier is substituted. The production enum,
            # pinned readback, native-file and freeze admission gates run intact.
            with patch('monkey.targets.unity.verify',side_effect=verify):
                actual,_,_=_native_verification(root,root/'out','a'*64,io.sha(path.read_bytes()))
                self.assertEqual(actual['status'],'imported')
                report['staticPresentationValidation']='partial'
                with self.assertRaisesRegex(ValueError,'NATIVE_SOURCE_COVERAGE_INCOMPLETE'):
                    _native_verification(root,root/'out','a'*64,io.sha(path.read_bytes()))
                report['staticPresentationValidation']='pass'
                report['componentCoverage']['sourceComponentCount']=1
                with self.assertRaisesRegex(ValueError,'NATIVE_SOURCE_COVERAGE_INCOMPLETE'):
                    _native_verification(root,root/'out','a'*64,io.sha(path.read_bytes()))
                report['componentCoverage']['sourceComponentCount']=0
                (root/'Assets/a.prefab').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'NATIVE_READBACK_DRIFT'):
                    _native_verification(root,root/'out','a'*64,io.sha(path.read_bytes()))
