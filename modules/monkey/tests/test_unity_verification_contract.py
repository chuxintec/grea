import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from monkey import io
from monkey.native_selection import _native_verification
from monkey.unity_verification_contract import native_diagnostics,coverage_readback,statuses,deduplicate_diagnostics,unresolved_diagnostics


def _owned_component_fixture(component, native_row):
    owner='prefab:source#0';path='Assets/Prefabs/Source.prefab';node=component['node']
    planned={**component,'sourcePrefabId':owner}
    plan={'nodes':[{'sourceId':node,'active':True,'parent':None}],
        'sourcePrefabs':[{'sourceId':owner,'path':path,'nodes':[node]}],
        'components':[planned],'diagnostics':[]}
    row={**native_row,'sourceId':component['sourceId'],'node':node,'type':component['type']}
    row['sourceEnabled']=component['enabled']
    transform_guid='f'*32;transform_local=900
    transform_uuid=f'{transform_guid}:{transform_local}'
    target_guid=row.get('guid');target_local=row.get('localFileId')
    target_uuid=f'{target_guid}:{target_local}' if target_guid and target_local is not None else None
    target_type=row.get('nativeType')
    target_bases=([target_type,'UnityEngine.UI.MaskableGraphic','UnityEngine.UI.Graphic',
        'UnityEngine.EventSystems.UIBehaviour','UnityEngine.MonoBehaviour','UnityEngine.Behaviour',
        'UnityEngine.Component','UnityEngine.Object','System.Object']
        if target_type=='UnityEngine.UI.Image' else [target_type,'UnityEngine.Component','UnityEngine.Object','System.Object'])
    physical=[{'nativeType':'UnityEngine.RectTransform','componentUuid':transform_uuid,
        'guid':transform_guid,'localFileId':transform_local,'persistent':True,'enabledKnown':False,'enabled':True,
        'nativeBaseTypes':['UnityEngine.RectTransform','UnityEngine.Transform','UnityEngine.Component','UnityEngine.Object','System.Object'],
        'sourceComponentIds':[],'role':'unmapped','identityOrigin':'direct-observation',
        'identityPath':[transform_uuid]},
        {'nativeType':target_type,'componentUuid':target_uuid,'guid':target_guid,'localFileId':target_local,
        'persistent':True,'enabledKnown':True,'enabled':row.get('nativeEnabled') is True,
        'nativeBaseTypes':target_bases,'sourceComponentIds':[component['sourceId']],
        'role':'source-components','identityOrigin':'direct-observation','identityPath':[target_uuid]}]
    def node_record(scope):
        node_physical=copy.deepcopy(physical)
        if scope=='saved-scene-correspondence':
            for item in node_physical:
                item['identityOrigin']='corresponding-prefab-source'
                item['identityPath']=['d'*32+':900',item['componentUuid']]
        return {'sourceId':node,'active':True,
            'physicalInventoryContract':'monkey-unity-node-physical-components/1',
            'physicalInventoryPhase':'persistent-saved-reopened-node',
            'physicalObservationScope':scope,'physicalComponents':node_physical,
            'componentTypes':[item['nativeType'] for item in node_physical]}
    readback={'components':[copy.deepcopy(row)],'diagnostics':[],
        'nodes':[node_record('saved-scene-correspondence')],
        'sourcePrefabs':[{'sourceId':owner,'path':path,'nodes':[node_record('saved-source-prefab')],
            'components':[copy.deepcopy(row)]}]}
    readback.update(sceneComponentContract='monkey-unity-saved-scene-components/1',sceneComponentPhase='saved-scene-reopened',
        sceneComponents=[dict(copy.deepcopy(row),observationScope='saved-scene-correspondence',
                              identityOrigin='corresponding-prefab-source',identityPath=['d'*32+':900',target_uuid])])
    return plan,readback


class UnityVerificationContractTests(unittest.TestCase):
    def test_system_font_platform_gap_blocks_without_scoped_source_and_presentation_proof(self):
        coverage=dict(components=[],nativeStaticValidation='pass',retentionValidation='pass',
                      staticPresentationValidation=dict(status='pass'))
        historical=dict(code='SYSTEM_FONT_PLATFORM_UNVERIFIED',sourceId='label',message='original device unknown')
        result=statuses('pass',[historical],coverage,'editor')
        self.assertEqual(result['nativeStaticValidation'],'partial')
        metrics=dict(code='LABEL_METRICS_NOT_VERIFIED',sourceId='label',message='source comparison pending')
        result=statuses('pass',[historical,metrics],coverage,'editor')
        self.assertEqual(result['nativeStaticValidation'],'partial')
        self.assertEqual(historical['message'],'original device unknown')
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
        component={'sourceId':'s','node':'n','type':'cc.Sprite','nativeType':'cc.Sprite',
            'enabled':True,'spriteFrame':'sprite:a',
            'staticFieldBinding':{'fields':[{'sourceFieldName':'value'}]}}
        row={'sourceId':'s','status':'native','representation':'native-component',
             'nativeType':'UnityEngine.UI.Image',
             'guid':'0123456789abcdef0123456789abcdef','localFileId':1,
             'componentUuid':'0123456789abcdef0123456789abcdef:1',
             'sourceIdentityVerified':True,'persistent':True,'nativeEnabled':True,'sourceVisible':True}
        plan,rb=_owned_component_fixture(component,row)
        rb['sceneComponents'][0]['nativeStaticFieldsVerified']=True
        rb['sourcePrefabs'][0]['staticFieldBindings']=[{'binding':field}]
        rb['staticPresentationValidation']={'components':[{'sourceId':'s','sourceVisible':True,'verified':True,'rendered':True}]}
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
            from monkey.layout import standard
            plan_path=root/standard.unity('importPlan');plan_path.parent.mkdir(parents=True)
            io.write_json(plan_path,{'sourceManifestSha256':'b'*64})
            io.write_json(root/'manifest.json',{'projectLayout':standard.VERSION})
            manifest_sha=io.sha((root/'manifest.json').read_bytes())
            rb={'importPlanSha256':io.sha(plan_path.read_bytes()),'sourceManifestSha256':'b'*64,'unityVersion':'6000.6.2f1','missingScripts':0,'status':'imported',
                'nativeScope':'saved-source-node-subset','sourceGraphVerification':'saved-source-node-subset',
                'nativeFiles':[{'path':'Assets/a.prefab','sha256':io.sha((root/'Assets/a.prefab').read_bytes())}],
                'editableRoundtrip':True,'sceneReopened':True,'diagnostics':[]}
            path=root/'Analysis/Readback/editor-readback.json';io.write_json(path,rb)
            report={'candidateManifestSha256':manifest_sha,'staticValidation':'pass','nativeStaticValidation':'pass',
                    'editorValidation':'pass','staticPresentationValidation':'pass',
                    'componentCoverage':{'schema':'monkey-prefab-component-coverage/1','sourceComponentCount':0,
                                         'uniqueSourceComponentCount':0,'components':[]},'diagnostics':[]}
            def verify(candidate,out,level):
                out.mkdir();io.write_json(out/'verification.json',report)
            # Only the downstream verifier is substituted. The production enum,
            # pinned readback, native-file and freeze admission gates run intact.
            with patch('monkey.targets.unity.verify',side_effect=verify):
                actual,_,_=_native_verification(root,root/'out',manifest_sha,io.sha(path.read_bytes()))
                self.assertEqual(actual['status'],'imported')
                report['staticPresentationValidation']='partial'
                with self.assertRaisesRegex(ValueError,'NATIVE_SOURCE_COVERAGE_INCOMPLETE'):
                    _native_verification(root,root/'out',manifest_sha,io.sha(path.read_bytes()))
                report['staticPresentationValidation']='pass'
                report['componentCoverage']['sourceComponentCount']=1
                with self.assertRaisesRegex(ValueError,'NATIVE_SOURCE_COVERAGE_INCOMPLETE'):
                    _native_verification(root,root/'out',manifest_sha,io.sha(path.read_bytes()))
                report['componentCoverage']['sourceComponentCount']=0
                (root/'Assets/a.prefab').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'NATIVE_READBACK_DRIFT'):
                    _native_verification(root,root/'out',manifest_sha,io.sha(path.read_bytes()))

    def test_freeze_rejects_unexecuted_or_unknown_source_graph_before_full_verifier(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();path=root/'Analysis/Readback/editor-readback.json'
            path.parent.mkdir(parents=True)
            valid={'unityVersion':'6000.6.2f1','missingScripts':0,'status':'imported',
                   'nativeScope':'source-node-subset','sourceGraphVerification':'saved-source-node-subset'}
            for field,value in (('status','not_run'),('status','success'),('unityVersion','6000.6.1f1'),
                    ('missingScripts',1),('missingScripts',False),('nativeScope','resources-and-gallery-only'),
                    ('nativeScope','unknown'),('sourceGraphVerification','not_run'),
                    ('sourceGraphVerification','invented')):
                row={**valid,field:value};io.write_json(path,row)
                with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,'NATIVE_READBACK_INVALID'):
                    _native_verification(root,root/'out','a'*64,io.sha(path.read_bytes()))

    def test_initial_missing_component_diagnostic_resolves_only_with_exact_persistent_coverage(self):
        from monkey.prefab_component_coverage import assess
        source='source:asset#4';guid='0123456789abcdef0123456789abcdef'
        component={'sourceId':source,'node':'node:asset#1','type':'cc.Button','nativeType':'cc.Button',
            'enabled':True,'staticButtonBinding':{'behavior':'disabled','renderReady':True,'sourceEnabled':True}}
        native={'status':'disabled','representation':'native-component','nativeType':'UnityEngine.UI.Button',
                'nativeEnabled':False,
                'disabledReason':'static-button-business-safety','nativeStaticFieldsVerified':True,
                'sourceIdentityVerified':True,'persistent':True,'guid':guid,'localFileId':14,
                'componentUuid':guid+':14'}
        plan,readback=_owned_component_fixture(component,native)
        coverage=assess(plan,coverage_readback(readback),'unity')
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

    def test_shared_blocking_helper_revalidates_resolved_creation_and_preserves_raw_history(self):
        from monkey.unity_diagnostic_resolution import reconcile
        from monkey.prefab_component_coverage import assess
        sid='source:asset#9';guid='0123456789abcdef0123456789abcdef'
        native={'sourceId':sid,'status':'native','representation':'native-component',
            'nativeType':'UnityEngine.UI.Image','sourceIdentityVerified':True,'persistent':True,
            'nativeStaticFieldsVerified':True,'nativeEnabled':True,'sourceVisible':True,
            'guid':guid,'localFileId':70,'componentUuid':guid+':70'}
        component={'sourceId':sid,'node':'node:source#1','type':'cc.Sprite','nativeType':'cc.Sprite',
            'enabled':True,'spriteFrame':'frame:1'}
        plan,readback=_owned_component_fixture(component,native)
        readback['staticPresentationValidation']={'components':[{
            'sourceId':sid,'sourceVisible':True,'verified':True,'rendered':True}]}
        coverage=assess(plan,coverage_readback(readback),'unity')
        self.assertEqual(coverage['nativeStaticValidation'],'pass')
        self.assertEqual(coverage['staticPresentationValidation']['status'],'pass')
        original={'code':'COMPONENT_NOT_IMPORTED','sourceId':sid,'phase':'initial-component-creation',
            'rawDiagnostic':'COMPONENT_NOT_IMPORTED: original','history':[{'attempt':'initial'}]}
        annotated=reconcile([original],coverage)['diagnostics']
        state=unresolved_diagnostics(annotated,coverage)
        self.assertEqual(state['blocking'],[])
        self.assertEqual(state['resolved'][0]['history'],original['history'])
        result=statuses('pass',annotated,coverage,'editor')
        self.assertEqual(result['editorValidation'],'pass')
        mutated=copy.deepcopy(annotated)
        mutated[0]['currentResolutionEvidence']['guid']='f'*32
        state=unresolved_diagnostics(mutated,coverage)
        self.assertEqual(state['blocking'],mutated)
        self.assertEqual(state['resolved'],[])

    def test_system_font_code_is_not_globally_skipped_and_button_is_dynamic_only(self):
        coverage={'nativeStaticValidation':'pass','staticPresentationValidation':'pass','components':[
            {'sourceId':'label:1','sourceType':'cc.Label'}, {'sourceId':'button:1','sourceType':'cc.Button'}]}
        font={'code':'SYSTEM_FONT_PLATFORM_UNVERIFIED','sourceId':'label:1','message':'source OS unknown'}
        button={'code':'BUTTON_BUSINESS_UNBOUND','sourceId':'button:1',
                'message':'Native Button generated; original handlers remain AI work'}
        state=unresolved_diagnostics([font,button],coverage)
        self.assertEqual(state['blocking'],[font])
        self.assertEqual(state['remainingDynamic'],[button])

    def test_shared_blocking_helper_fails_closed_on_malformed_diagnostics(self):
        self.assertEqual(unresolved_diagnostics(None,{})['blocking'][0]['code'],
                         'NATIVE_DIAGNOSTICS_INVALID')
        self.assertEqual(unresolved_diagnostics(['not-a-row'],{})['blocking'][0]['code'],
                         'NATIVE_DIAGNOSTIC_INVALID')

    def test_layout_slot_component_resolution_requires_exact_source_slot_and_binding(self):
        source = 'layout:asset#0/components/0'
        guid = '0123456789abcdef0123456789abcdef'
        native = {'sourceId': source, 'guid': guid, 'localFileId': 14,
            'nativeType': 'NativeStaticLayoutCompletion', 'representation': 'native-component-slot',
            'nativeSlotId': source, 'sourceIdentityVerified': True, 'persistent': True,
            'nativeStaticFieldsVerified': True}
        coverage = {'nativeStaticValidation': 'pass', 'staticPresentationValidation': 'pass',
            'components': [{'sourceId': source, 'nativeStatus': 'pass', 'disposition': 'native',
                'nativeStaticFieldsVerified': True, 'nativeSlotId': source,
                'staticLayoutContinuationBinding': {'sourceComponentId': source,
                    'physicalNativeType': 'NativeStaticLayoutCompletion'},
                'nativeComponentReadback': native}]}
        row = {'code': 'COMPONENT_NOT_IMPORTED', 'sourceId': source,
            'phase': 'initial-component-creation', 'resolved': True,
            'resolution': 'native-counterpart-present',
            'resolutionEvidence': {'sourceId': source, 'guid': guid, 'localFileId': 14,
                'disposition': 'native', 'nativeStaticFieldsVerified': True,
                'representation': 'native-component-slot', 'nativeSlotId': source}}
        result = statuses('pass', [row], coverage, 'editor')
        self.assertEqual(result['nativeStaticValidation'], 'pass')
        mismatch = copy.deepcopy(row)
        mismatch['resolutionEvidence']['nativeSlotId'] = 'layout:other/slot'
        result = statuses('pass', [mismatch], coverage, 'editor')
        self.assertNotEqual(result['nativeStaticValidation'], 'pass')

    def test_reconciled_layout_family_proof_is_rechecked_against_exact_slot_identity(self):
        source = 'layout:asset#0/components/1'
        guid = '0123456789abcdef0123456789abcdef'
        native = {'sourceId': source, 'guid': guid, 'localFileId': 24,
            'nativeType': 'NativeStaticLayoutCompletion', 'representation': 'native-component-slot',
            'nativeSlotId': source, 'sourceIdentityVerified': True, 'persistent': True,
            'nativeStaticFieldsVerified': True}
        coverage = {'nativeStaticValidation': 'pass', 'staticPresentationValidation': 'pass',
            'components': [{'sourceId': source, 'nativeStatus': 'pass', 'disposition': 'native',
                'nativeStaticFieldsVerified': True, 'nativeSlotId': source,
                'staticLayoutContinuationBinding': {'sourceComponentId': source,
                    'physicalNativeType': 'NativeStaticLayoutCompletion'},
                'nativeComponentReadback': native}]}
        row = {'code': 'MULTIPLE_LAYOUT_HANDOFF', 'sourceId': source,
            'resolutionClassification': 'resolved', 'resolutionScope': 'saved-native-layout-proof',
            'currentResolutionEvidence': {'scope': 'saved-native-layout-proof',
                'resolvedCodes': ['MULTIPLE_LAYOUT_HANDOFF'],
                'evidence': {'sourceId': source, 'guid': guid, 'localFileId': 24,
                    'nativeType': 'NativeStaticLayoutCompletion', 'representation': 'native-component-slot',
                    'nativeSlotId': source, 'persistent': True, 'sourceIdentityVerified': True,
                    'requirements': {'layout': True, 'layout-context': True, 'layout-algorithm': True}},
                'nativeIdentity': {'guid': guid, 'localFileId': 24,
                    'nativeType': 'NativeStaticLayoutCompletion', 'representation': 'native-component-slot'}}}
        result = statuses('pass', [row], coverage, 'editor')
        self.assertEqual(result['nativeStaticValidation'], 'pass')
        self.assertEqual(result['resolvedNativeDiagnostics'], [row])
        changed = copy.deepcopy(row)
        changed['currentResolutionEvidence']['evidence']['nativeSlotId'] = 'other-slot'
        result = statuses('pass', [changed], coverage, 'editor')
        self.assertNotEqual(result['nativeStaticValidation'], 'pass')

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
        component={'sourceId':'s','node':'n','type':'cc.Sprite','nativeType':'cc.Sprite',
                   'enabled':True,'spriteFrame':'f'}
        first.update(node='n',type='cc.Sprite',sourceEnabled=True,nativeEnabled=True)
        second.update(node='n',type='cc.Sprite',sourceEnabled=True,nativeEnabled=True)
        plan,readback=_owned_component_fixture(component,first)
        readback['components'].append(second)
        normalized=coverage_readback(readback)
        result=assess(plan,normalized,'unity')
        self.assertEqual(result['components'][0]['disposition'],'missing')
        self.assertTrue(any(row['code']=='COMPONENT_OWNER_ROLE_AMBIGUOUS'
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

    def test_progress_projection_joins_one_carrier_and_requires_exact_saved_bar_identity(self):
        guid='a'*32
        carrier=dict(sourceId='progress',type='cc.ProgressBar',nativeType='UnityStaticProgress',
            status='retained',representation='disabled-source-data-carrier',guid=guid,localFileId=1,
            persistent=True,sourceIdentityVerified=True,sourceEnabled=True,nativeEnabled=False)
        bar=dict(sourceId='bar',type='cc.Sprite',nativeType='UnityEngine.UI.Image',status='native',
            representation='native-component',guid=guid,localFileId=2,persistent=True,sourceIdentityVerified=True)
        receipt=dict(sourceComponentId='progress',carrierGuid=guid,carrierLocalFileId=1,
            barSpriteSourceId='bar',barSpriteGuid=guid,barSpriteLocalFileId=2,barSpritePersistent=True,
            verified=True,carrierDisabled=True,sourceEnabled=True,mode=0,progress=.5,reverse=False)
        raw=dict(components=[carrier,bar],sourcePrefabs=[dict(components=[dict(carrier),dict(bar)],
            staticProgressFields=[receipt])])
        normalized=coverage_readback(raw)
        self.assertEqual(len(normalized['retainedComponents']),1)
        observed=normalized['retainedComponents'][0]
        self.assertTrue(observed['verified'])
        self.assertTrue(observed['barSpriteIdentityVerified'])
        self.assertEqual(observed['representation'],'disabled-source-data-carrier')
        receipt['barSpriteLocalFileId']=3
        changed=coverage_readback(raw)['retainedComponents'][0]
        self.assertFalse(changed['verified'])
        self.assertFalse(changed['barSpriteIdentityVerified'])

    def test_normalization_preserves_same_peer_duplicate_evidence(self):
        row=dict(sourceId='s',type='sp.Skeleton',nativeType='NativeStaticSpineReference',
            status='retained',representation='disabled-source-data-carrier',guid='a'*32,localFileId=1,
            sourceIdentityVerified=True,persistent=True)
        normalized=coverage_readback(dict(components=[row,dict(row)]))
        self.assertEqual(len(normalized['retainedComponents']),1)
        self.assertEqual(normalized['componentPeerDuplicates'][0]['duplicateCount'],2)
        self.assertEqual(normalized['componentPeerDuplicates'][0]['coverageRole'],'retained-carrier')
        self.assertEqual(normalized['componentPeerDuplicates'][0]['scope'],'root/components')
        repeated=coverage_readback(dict(components=[row],sourcePrefabs=[dict(components=[dict(row)])]))
        self.assertEqual(repeated['componentPeerDuplicates'],[])
