import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from monkey.spine_owner_lifecycle_readback import CONTRACT, EVIDENCE_PATH, SOURCE_PATH, CONFIG_PATH, IMPORT_PATH, verify_lifecycle_evidence


class OwnerLifecycleReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.data='Assets/Shared/SkeletonData.asset';self.guids={self.data:'d'*32,'Assets/One.prefab':'a'*32,'Assets/Two.prefab':'b'*32}
        self.specs=[dict(sourceComponentId='instance-'+str(i),sourceDataAssetId='spineAsset:shared',sourceNodeId='node-'+str(i),
                         sourcePrefabId='prefab-'+str(i),templateComponentId='template:spine',eligible=True)for i in range(2)]
        self.rendering=dict(ownerContextLifecycleEvidenceContract=CONTRACT,sourceManifestSha256='f'*64,components=self.specs,
                            dataAssets=[dict(sourceDataAssetId='spineAsset:shared',eligible=True,factorySpec=dict(skeletonDataAssetPath=self.data))])
        self.put(CONFIG_PATH,self.rendering);self.config_sha=self.digest(CONFIG_PATH)
        self.source=dict(evidenceSha256='e'*64,renderingPlanSha256=self.config_sha,
            components=[dict(sourceComponentId=x['sourceComponentId'],sourceCanvasContextIndex=0)for x in self.specs],
            contexts=[dict(contextIndex=0,sourceCanvasReferencePixelsPerUnit=100)])
        self.source['contexts'][0]['sourceCanvasRenderMode']='ScreenSpaceOverlay'
        self.plan=dict(prefabInstances=[],sourcePrefabs=[],staticSortQueue=[dict(renderers=[])])
        self.plan['components']=[dict(sourceId='template:spine',type='sp.Skeleton',node='template-node')]
        self.envelope=dict(schemaVersion=1,contract=CONTRACT,phase='native-import',sourceManifestSha256='f'*64,
            renderingPlanSha256=self.config_sha,sourceCanvasEvidenceSha256='e'*64,
            sourceCanvasEvidenceContract='monkey-static-spine-source-canvas-context/1',components=[],transitions=[])
        self.saved=[]
        for i,spec in enumerate(self.specs):
            self.plan['sourcePrefabs'].append(dict(sourceId=spec['sourcePrefabId'],path=['Assets/One.prefab','Assets/Two.prefab'][i]))
            self.plan['prefabInstances'].append(dict(owner=spec['sourcePrefabId'],root=spec['sourceNodeId'],template='same-template',
                nodes=[dict(instanceObject=spec['sourceNodeId'],templateObject='template-node')]))
            self.plan['staticSortQueue'][0]['renderers'].append(dict(sourceComponentId=spec['sourceComponentId'],sourceType='sp.Skeleton'))
            item=dict(spec,sourceConstructionOwnerRegistered=True,sourceConstructionOwnerType='Spine.Unity.SkeletonGraphic',
                sourceConstructionOwnerPath='constructed/'+spec['sourceNodeId'],sourceConstructionDataAssetPath=self.data,
                sourceConstructionDataAssetGuid='d'*32,sourceCanvasEvidenceSha256='e'*64,sourceCanvasPpu=100,
                sourceCanvasRenderMode='ScreenSpaceOverlay')
            rows=[]
            for phase in ['native-instance-clone','static-sort-create-capture','saved-prefab-owner-pair','controlled-host-release']:
                row=dict(spec,phase=phase,sourceManifestSha256='f'*64,renderingPlanSha256=self.config_sha,
                    sourceCanvasEvidenceSha256='e'*64,dataAssetType='Spine.Unity.SkeletonDataAsset',dataAssetPath=self.data,
                    dataAssetGuid='d'*32,dataAssetLocalFileId=11400000,registrationStatus='registered-verified',verified=True,
                    ownerPairRegistered=True,actualOwnerType='Spine.Unity.SkeletonGraphic',actualOwnerPath='controlled/'+spec['sourceNodeId'],
                    actualCanvasRenderMode='WorldSpace',actualCanvasPpu=100,sourceCanvasPpu=100,priorOwnerType='Spine.Unity.SkeletonGraphic',
                    priorOwnerPath='old/'+spec['sourceNodeId'],priorOwnerRegistryRevoked=True,priorOwnerRetired=True,
                    instanceOwnerPrefabId=spec['sourcePrefabId'],instanceRootNodeId=spec['sourceNodeId'],instanceNodeId=spec['sourceNodeId'],
                    templatePrefabId='same-template',templateNodeId='template-node')
                row.update(priorOwnerPersistent=False,actualOwnerPersistent=False)
                if phase=='static-sort-create-capture':row['ownerPairRegistered']=False
                if phase in ('saved-prefab-owner-pair','controlled-host-release'):
                    row.update(priorOwnerPersistent=True,actualOwnerPersistent=False,priorOwnerGuid=['a','b'][i]*32,
                        priorOwnerLocalFileId=100+i,priorOwnerAssetPath=['Assets/One.prefab','Assets/Two.prefab'][i])
                if phase=='controlled-host-release':row.update(registrationStatus='released',ownerPairRegistered=False,priorOwnerRetired=False)
                rows.append(row)
            item['transitions']=rows;self.envelope['components'].append(item);self.envelope['transitions'].extend(rows)
            self.saved.append(dict(sourceComponentId=spec['sourceComponentId'],rendererGuid=['a','b'][i]*32,rendererLocalId=100+i,
                                   dataAssetGuid='d'*32,dataAssetLocalId=11400000))
        self.main=dict(nativeFiles=[],staticSpineReadbackFiles=[])
        for path,guid in self.guids.items():
            p=self.root/(path+'.meta');p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fileFormatVersion: 2\nguid: '+guid+'\n')
            self.main['nativeFiles'].append(dict(path=path+'.meta',sha256=self.digest(path+'.meta')))
        self.sync()

    def put(self,path,value):
        p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,sort_keys=True))
    def digest(self,path):return hashlib.sha256((self.root/path).read_bytes()).hexdigest()
    def sync(self):
        self.put(SOURCE_PATH,self.source);self.put(EVIDENCE_PATH,self.envelope);self.put(IMPORT_PATH,self.plan)
        saved_path='Analysis/Readback/SpineRendering/saved.json';self.put(saved_path,dict(contract='monkey-static-spine-rendering-readback/1',components=self.saved))
        self.main['staticSpineReadbackFiles']=[dict(path=p,sha256=self.digest(p))for p in (SOURCE_PATH,EVIDENCE_PATH,saved_path)]
        self.put('Analysis/Readback/editor-readback.json',self.main)
    def check(self):return verify_lifecycle_evidence(self.rendering,self.root)
    def rows(self,phase):return [r for r in self.envelope['transitions']if r['phase']==phase]

    def test_all_instances_of_same_template_keep_distinct_lifetime_identity(self):
        self.assertEqual([],self.check())
    def test_legacy_plan_without_flag_or_trace_remains_legacy(self):
        self.assertEqual([],verify_lifecycle_evidence({},self.root/'legacy'))
    def test_required_missing_trace_fails(self):
        (self.root/EVIDENCE_PATH).unlink();self.assertTrue(self.check())
    def test_stale_raw_hash_is_not_accepted(self):
        (self.root/EVIDENCE_PATH).write_bytes((self.root/EVIDENCE_PATH).read_bytes()+b' ');self.assertTrue(self.check())
    def test_replaced_or_released_owner_must_have_explicit_revocation(self):
        for phase,key in [('native-instance-clone','priorOwnerRetired'),('native-instance-clone','priorOwnerRegistryRevoked'),('controlled-host-release','priorOwnerRegistryRevoked')]:
            with self.subTest(phase=phase,key=key):
                row=self.rows(phase)[0];old=row[key];row[key]=False;self.sync();self.assertTrue(self.check());row[key]=old
    def test_wrong_template_same_asset_cannot_borrow_another_instance(self):
        self.rows('native-instance-clone')[1]['instanceRootNodeId']='node-0';self.sync();self.assertTrue(self.check())

    def test_component_id_is_resolved_through_component_table_to_its_node(self):
        self.plan['components'][0]['node']='different-node';self.sync();self.assertTrue(self.check())
    def test_persistent_owner_cannot_borrow_same_template_peer_file_id(self):
        self.rows('saved-prefab-owner-pair')[1]['priorOwnerLocalFileId']=100;self.sync();self.assertTrue(self.check())
    def test_data_identity_and_ppu_cannot_be_self_reported(self):
        for key,value in [('dataAssetGuid','0'*32),('actualCanvasPpu',99),('sourceCanvasEvidenceSha256','0'*64)]:
            with self.subTest(key=key):
                row=self.rows('static-sort-create-capture')[0];old=row[key];row[key]=value;self.sync();self.assertTrue(self.check());row[key]=old
    def test_phase_coverage_cannot_drop_an_instance(self):
        self.envelope['transitions']=[r for r in self.envelope['transitions']if not(r['phase']=='native-instance-clone'and r['sourceComponentId']=='instance-1')]
        self.envelope['components'][1]['transitions']=[r for r in self.envelope['components'][1]['transitions']if r['phase']!='native-instance-clone']
        self.sync();self.assertTrue(self.check())
    def test_canonical_denominator_and_event_table_cannot_disagree(self):
        self.envelope['components'][0]['transitions']=[];self.sync();self.assertTrue(self.check())
    def test_construction_registration_is_not_recreated_from_saved_scale(self):
        self.envelope['components'][0]['sourceConstructionOwnerRegistered']=False;self.sync();self.assertTrue(self.check())
    def test_cleanup_cannot_claim_registered_owner_pair(self):
        self.rows('controlled-host-release')[0]['ownerPairRegistered']=True;self.sync();self.assertTrue(self.check())

    def test_release_or_capture_in_wrong_lifecycle_order_is_rejected(self):
        for phases in [('native-instance-clone','static-sort-create-capture','controlled-host-release','saved-prefab-owner-pair'),
                       ('static-sort-create-capture','native-instance-clone','saved-prefab-owner-pair','controlled-host-release')]:
            with self.subTest(phases=phases):
                events=self.envelope['components'][0]['transitions'];order={phase:i for i,phase in enumerate(phases)}
                events.sort(key=lambda x:order[x['phase']])
                other=[r for r in self.envelope['transitions']if r['sourceComponentId']!='instance-0']
                self.envelope['transitions']=events+other;self.sync();self.assertTrue(self.check())


if __name__=='__main__':unittest.main()
