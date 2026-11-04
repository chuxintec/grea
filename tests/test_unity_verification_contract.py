import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from monkey import io
from monkey.native_selection import _native_verification
from monkey.unity_verification_contract import native_diagnostics,coverage_readback,statuses,deduplicate_diagnostics


class UnityVerificationContractTests(unittest.TestCase):
    def test_final_merge_preserves_source_provenance_and_distinct_messages(self):
        original={'code':'FIELD_UNPROVEN','sourceId':'source:component','location':'field/path',
                  'message':'first field','severity':'warning','origin':'source',
                  'sourceEvidence':[{'origin':'source','index':2,'raw':'source observation'}]}
        native={**original,'origin':'native-readback','severity':'error','nativeDiagnosticIndex':7,
                'sourceEvidence':[{'origin':'native-readback','index':7,'raw':'native observation'}]}
        rows=[original,native,{**original,'message':'different field'}]
        before=copy.deepcopy(rows);merged=deduplicate_diagnostics(rows)
        self.assertEqual(rows,before)
        self.assertEqual(len(merged),2)
        self.assertEqual(merged[0]['severity'],'error')
        self.assertEqual(merged[0]['origins'],['source','native-readback'])
        self.assertEqual(len(merged[0]['sourceEvidence']),2)
        self.assertEqual(merged[0]['nativeDiagnosticIndexes'],[7])

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
                             'spriteFrame':'sprite:a',
                             'staticFieldBinding':{'fields':[{'sourceFieldName':'value'}]}}]}
        row={'sourceId':'s','status':'native','nativeType':'UnityEngine.UI.Image',
             'guid':'0123456789abcdef0123456789abcdef','localFileId':1,
             'componentUuid':'0123456789abcdef0123456789abcdef:1',
             'sourceIdentityVerified':True,'persistent':True}
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

    def test_initial_missing_component_diagnostic_resolves_only_with_exact_persistent_coverage(self):
        from monkey.prefab_component_coverage import assess
        source='source:asset#4';guid='0123456789abcdef0123456789abcdef'
        plan={'nodes':[{'sourceId':'node:asset#1','active':True}],
              'components':[{'sourceId':source,'node':'node:asset#1','type':'cc.Button','enabled':True,
                  'staticButtonBinding':{'behavior':'disabled','renderReady':True,'sourceEnabled':True}}],
              'diagnostics':[]}
        native={'sourceId':source,'status':'disabled','representation':'native-component',
                'nativeType':'UnityEngine.UI.Button','sourceEnabled':True,'nativeEnabled':False,
                'disabledReason':'static-button-business-safety','nativeStaticFieldsVerified':True,
                'sourceIdentityVerified':True,'persistent':True,'guid':guid,'localFileId':14}
        coverage=assess(plan,{'components':[native]},'unity')
        diagnostic_row={'code':'COMPONENT_NOT_IMPORTED','sourceId':source,
            'phase':'initial-component-creation','resolved':True,'resolution':'native-counterpart-present',
            'resolutionEvidence':{'sourceId':source,'guid':guid,'localFileId':14,'disposition':'disabled',
                                  'nativeStaticFieldsVerified':True}}
        result=statuses('pass',[diagnostic_row],coverage,'editor')
        self.assertEqual(result['editorValidation'],'partial')
        self.assertEqual(result['resolvedNativeDiagnostics'],[diagnostic_row])
        changed=copy.deepcopy(diagnostic_row);changed['resolutionEvidence']['localFileId']=15
        result=statuses('pass',[changed],coverage,'editor')
        self.assertEqual(result['editorValidation'],'partial')
        self.assertEqual(result['resolvedNativeDiagnostics'],[])

    def test_diagnostic_exact_dedupe_keeps_distinct_messages_and_origins(self):
        raw='COMPONENT_NOT_IMPORTED: gameAsset:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa#2 missing'
        rows=native_diagnostics([raw,raw,{'code':'COMPONENT_NOT_IMPORTED',
            'sourceId':'gameAsset:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa#2',
            'location':'other-phase','message':'late mismatch'}])
        self.assertEqual(len(rows),2)
        self.assertEqual(len(rows[0]['sourceEvidence']),2)
        self.assertEqual(rows[0]['nativeDiagnosticIndexes'],[0,1])
        self.assertNotEqual(rows[0]['message'],rows[1]['message'])

    def test_nested_prefab_instances_fill_component_rows_without_double_count(self):
        guid='0123456789abcdef0123456789abcdef'
        component={'sourceId':'s','status':'native','representation':'native-component',
                   'nativeType':'UnityEngine.Transform','sourceIdentityVerified':True,'persistent':True,
                   'guid':guid,'localFileId':2}
        readback={'components':[component],
                  'sourcePrefabs':[{'components':[copy.deepcopy(component)]}],
                  'prefabInstances':[{'instances':[{'components':[copy.deepcopy(component)]}]}],
                  'diagnostics':[]}
        normalized=coverage_readback(readback)
        self.assertEqual(len(normalized['components']),1)

    def test_conflicting_nested_component_rows_are_not_collapsed_by_source_id(self):
        from monkey.prefab_component_coverage import assess
        guid='0123456789abcdef0123456789abcdef'
        first={'sourceId':'s','status':'native','representation':'native-component',
               'nativeType':'UnityEngine.UI.Image','sourceIdentityVerified':True,'persistent':True,
               'guid':guid,'localFileId':2}
        second={**first,'localFileId':3,'componentUuid':guid+':3'}
        plan={'nodes':[{'sourceId':'n','active':True}],
              'components':[{'sourceId':'s','node':'n','type':'cc.Sprite','spriteFrame':'f'}]}
        normalized=coverage_readback({'components':[first],
            'prefabInstances':[{'components':[second]}],'diagnostics':[]})
        result=assess(plan,normalized,'unity')
        self.assertEqual(result['components'][0]['disposition'],'missing')
        self.assertTrue(any(row['code']=='NATIVE_COMPONENT_READBACK_AMBIGUOUS'
                            for row in result['diagnostics']))

    def test_static_progress_normalization_rejects_bad_carrier_identity(self):
        row={'sourceComponentId':'progress','verified':True,'carrierDisabled':True,
             'carrierGuid':'bad-guid','carrierLocalFileId':4,'sourceEnabled':True,
             'mode':0,'progress':1.0,'reverse':False,'barSpriteSourceId':'bar','barSpritePersistent':True}
        normalized=coverage_readback({'staticProgressFields':[row]})
        retained=normalized['retainedComponents'][0]
        self.assertFalse(retained['sourceIdentityVerified'])
        self.assertFalse(retained['persistent'])
        self.assertFalse(retained['verified'])
