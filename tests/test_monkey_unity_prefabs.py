import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from grea.common import hash_file
from grea.integrations.monkey import unity_prefabs as p


class UnityPrefabPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        pin = {'path': str(self.root/'not-read'), 'sha256': 'a'*64, 'bytes': 1}
        self.q = dict(schemaVersion=1, contract=p.CONTRACT, targetUnityVersion='6000.6.2f1',
                      roots=[dict(sourceSha256='b'*64, file='0', pathId='-9223372036854775808')],
                      inputIndex=pin, providerExport=dict(root=str(self.root), **{k:pin for k in ('inventory','receipt','binding','prepared','prepareJob')}))

    def prepare(self, q):
        path=self.root/'request.json';path.write_text(json.dumps(q))
        return p.prepare(path, hash_file(path)['sha256'])

    def test_named_abi_reads_only_request_and_never_invokes_provider(self):
        with patch('grea.runner.execute') as execute:
            result=self.prepare(self.q)
            execute.assert_not_called()
        self.assertEqual(result['command'][0], 'recover-unity-prefabs')
        self.assertEqual(result['dependency_identity'], 'not_verified')
        self.assertFalse(result['executed'])
        self.assertEqual(result['public_dispatch'], 'not_adapted')
        self.assertFalse((self.root/'not-read').exists())

    def test_request_drift_refused(self):
        self.prepare(self.q)
        with self.assertRaisesRegex(ValueError, 'identity differs'):
            p.prepare(self.root/'request.json', '0'*64)

    def test_extra_argv_and_unsafe_execution_fields_refused(self):
        for field,value in [('argv',['--executeMethod','X']),('out',str(self.root)),('sourceMethodsExecuted',True),('schemaVersion',True),('allowDisabledUnavailableCarriers',1)]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.prepare(dict(self.q, **{field:value}))

    def test_source_identity_preserves_64_bit_ids_and_rejects_duplicates(self):
        for value in [9223372036854775807, '9223372036854775808', '0', '+1', '01']:
            q=copy.deepcopy(self.q);q['roots'][0]['pathId']=value
            with self.subTest(value=value),self.assertRaises(ValueError):self.prepare(q)
        q=copy.deepcopy(self.q);q['roots']*=2
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.prepare(q)

    def test_pins_and_target_contract_are_finite(self):
        q=copy.deepcopy(self.q);q['inputIndex']['sha256']='A'*64
        with self.assertRaises(ValueError):self.prepare(q)
        with self.assertRaises(ValueError):self.prepare(dict(self.q,targetUnityVersion='latest'))
        q=copy.deepcopy(self.q);q['providerExport']['extra']='ignored'
        with self.assertRaises(ValueError):self.prepare(q)


class UnityPrefabFreezeTests(unittest.TestCase):
    def test_fixed_package_and_capabilities_cannot_drift(self):
        from grea.integrations.monkey import pipeline
        from grea.common import digest
        cfg=dict(version=pipeline.UNITY_PREFAB_VERSION,identity_root='/fixed',package_files={'/fixed/cli.py':'a'*64})
        cap=dict(implemented=['verify','freeze-unity-prefabs'])
        with patch.object(pipeline,'UNITY_PREFAB_PACKAGE_SHA256',digest({'cli.py':'a'*64})),patch.object(pipeline,'UNITY_PREFAB_CAPABILITIES_SHA256',digest(cap)):
            pipeline.validate_fixed_candidate(cfg,cap)
            with self.assertRaises(ValueError):pipeline.validate_fixed_candidate(dict(cfg,package_files={'/fixed/cli.py':'b'*64}),cap)
            with self.assertRaises(ValueError):pipeline.validate_fixed_candidate(cfg,dict(cap,extra=True))

    def test_dev4_package_gate_and_legacy_plan_refusal(self):
        from grea.integrations.monkey import pipeline
        from grea.common import digest
        cfg=dict(version=pipeline.UNITY_PREFAB_DEV4_VERSION,identity_root='/fixed',package_files={'/fixed/cli.py':'a'*64})
        cap=dict(implemented=['verify','freeze-unity-prefabs'])
        with patch.object(pipeline,'UNITY_PREFAB_DEV4_PACKAGE_SHA256',digest({'cli.py':'a'*64})),patch.object(pipeline,'UNITY_PREFAB_DEV4_CAPABILITIES_SHA256',digest(cap)):
            pipeline.validate_fixed_candidate(cfg,cap)
            with self.assertRaises(ValueError):pipeline.validate_fixed_candidate(dict(cfg,package_files={'/fixed/cli.py':'b'*64}),cap)
            with self.assertRaises(ValueError):pipeline.validate_fixed_candidate(cfg,dict(cap,extra=True))
        request=self.root/'request.json';layout=self.work/'layout.json';layout.write_text('{}')
        self.write(request,dict(schema_version=1,operation='layout-preview',options={'conversion':str(self.work),'layout':str(layout)},input_roots=[str(self.work)],timeout_seconds=30))
        for version in (pipeline.UNITY_PREFAB_DEV4_VERSION,pipeline.UNITY_PREFAB_DEV5_VERSION,pipeline.UNITY_PREFAB_DEV6_VERSION,pipeline.UNITY_PREFAB_DEV7_VERSION):
            lock=dict(schema_version=2,version=version,identity_files=[])
            with patch.object(pipeline,'pinned',return_value=lock),patch.object(pipeline,'probe',return_value=(lock,cap)),patch('grea.runner.execute') as execute:
                with self.assertRaisesRegex(ValueError,'not adapted'):pipeline.plan('lock',request,self.root/('legacy-plan-'+version))
                execute.assert_not_called()

    def test_dev5_package_and_capabilities_cannot_drift(self):
        from grea.integrations.monkey import pipeline
        from grea.common import digest
        cfg=dict(version=pipeline.UNITY_PREFAB_DEV5_VERSION,identity_root='/fixed',package_files={'/fixed/cli.py':'a'*64})
        cap=dict(implemented=['verify','freeze-unity-prefabs'])
        with patch.object(pipeline,'UNITY_PREFAB_DEV5_PACKAGE_SHA256',digest({'cli.py':'a'*64})),patch.object(pipeline,'UNITY_PREFAB_DEV5_CAPABILITIES_SHA256',digest(cap)):
            pipeline.validate_fixed_candidate(cfg,cap)
            with self.assertRaises(ValueError):pipeline.validate_fixed_candidate(dict(cfg,package_files={'/fixed/cli.py':'b'*64}),cap)
            with self.assertRaises(ValueError):pipeline.validate_fixed_candidate(cfg,dict(cap,extra=True))

    def test_dev6_package_and_capabilities_cannot_drift(self):
        from grea.integrations.monkey import pipeline
        from grea.common import digest
        cfg=dict(version=pipeline.UNITY_PREFAB_DEV6_VERSION,identity_root='/fixed',package_files={'/fixed/cli.py':'a'*64})
        cap=dict(implemented=['verify','freeze-unity-prefabs'])
        with patch.object(pipeline,'UNITY_PREFAB_DEV6_PACKAGE_SHA256',digest({'cli.py':'a'*64})),patch.object(pipeline,'UNITY_PREFAB_DEV6_CAPABILITIES_SHA256',digest(cap)):
            pipeline.validate_fixed_candidate(cfg,cap)
            with self.assertRaises(ValueError):pipeline.validate_fixed_candidate(dict(cfg,package_files={'/fixed/cli.py':'b'*64}),cap)
            with self.assertRaises(ValueError):pipeline.validate_fixed_candidate(cfg,dict(cap,extra=True))

    def test_dev7_package_and_capabilities_cannot_drift(self):
        from grea.integrations.monkey import pipeline
        from grea.common import digest
        cfg=dict(version=pipeline.UNITY_PREFAB_DEV7_VERSION,identity_root='/fixed',package_files={'/fixed/cli.py':'a'*64})
        cap=dict(implemented=['verify','freeze-unity-prefabs'])
        with patch.object(pipeline,'UNITY_PREFAB_DEV7_PACKAGE_SHA256',digest({'cli.py':'a'*64})),patch.object(pipeline,'UNITY_PREFAB_DEV7_CAPABILITIES_SHA256',digest(cap)):
            pipeline.validate_fixed_candidate(cfg,cap)
            with self.assertRaises(ValueError):pipeline.validate_fixed_candidate(dict(cfg,package_files={'/fixed/cli.py':'b'*64}),cap)
            with self.assertRaises(ValueError):pipeline.validate_fixed_candidate(cfg,dict(cap,extra=True))

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.native=self.root/'native';self.work=self.native/'UnityProject'
        self.work.mkdir(parents=True)
        self.manifest={'contract':'monkey-unity-prefab-recovery/1','diagnostics':[{'status':'unsupported'}], 'selectedSourceRoots':[{'pathId':'-1'}]}
        self.write(self.work/'manifest.json',self.manifest)
        saved=[]
        for name in ('Assets/retained.cs','Analysis/readback.json','Analysis/cold.json'):
            path=self.work/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{}')
            saved.append(dict(path=name,**{k:v for k,v in hash_file(path).items() if k!='path'}))
        self.receipt=dict(status='native-partial',processExited=True,sourceCodeExecuted=False,savedFiles=saved,
                          sourceCandidateManifestSha256=hash_file(self.work/'manifest.json')['sha256'],
                          readbackPath=str(self.work/'Analysis/readback.json'),readbackSha256=saved[1]['sha256'],
                          independentReopen=dict(status='cold-reopen-verified-subset',processExited=True,
                          readbackPath=str(self.work/'Analysis/cold.json'),readbackSha256=saved[2]['sha256']))
        self.write(self.native/'execution-result.json',self.receipt)
        self.sha=hash_file(self.native/'execution-result.json')['sha256']

    def write(self,path,value):
        path.write_text(json.dumps(value,indent=2)+'\n')

    def test_native_snapshot_excludes_library_and_requires_saved_bytes(self):
        library=self.work/'Library';library.mkdir();(library/'unowned').write_text('not an input')
        _,identities=p.native_inputs(self.native,self.sha)
        self.assertEqual(len(identities),5)
        self.assertFalse(any('/Library/' in path for path in identities))
        (self.work/'Assets/retained.cs').write_text('changed')
        with self.assertRaisesRegex(ValueError,'Saved input identity'):p.native_inputs(self.native,self.sha)

    def test_external_readback_and_pending_reopen_are_refused(self):
        for changes in [dict(readbackPath=str(self.root/'external')),dict(processExited=False),dict(independentReopen={'status':'pending'})]:
            self.write(self.native/'execution-result.json',dict(self.receipt,**changes))
            with self.assertRaises(ValueError):p.native_inputs(self.native,hash_file(self.native/'execution-result.json')['sha256'])

    def test_old_version_cannot_invoke_new_command(self):
        with patch('grea.integrations.monkey.identity.pinned',return_value={'schema_version':2,'version':'0.7.0.dev9'}),patch('grea.runner.execute') as execute:
            with self.assertRaisesRegex(ValueError,'launcher lock required'):p.freeze('lock',self.native,self.sha,self.root/'out')
            execute.assert_not_called()

    def test_partial_freeze_retains_diagnostics_and_rejects_changed_parent(self):
        from grea.integrations.monkey.pipeline import UNITY_PREFAB_VERSION
        lock=self.root/'lock';lock.write_text('{}');cfg=dict(schema_version=2,version=UNITY_PREFAB_VERSION,identity_files=[])
        def execute(tool,argv,out,**kwargs):
            target=Path(argv[-1]);target.mkdir()
            rows=copy.deepcopy(self.receipt['savedFiles'])
            for row in rows:
                dest=target/row['path'];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((self.work/row['path']).read_bytes())
            dest=target/'Analysis/Native/execution-result.json';dest.parent.mkdir(parents=True);dest.write_bytes((self.native/'execution-result.json').read_bytes())
            rows.append(dict(path='Analysis/Native/execution-result.json',**{k:v for k,v in hash_file(dest).items() if k!='path'}))
            m=dict(self.manifest,files=rows,executionReceiptSha256=self.sha,sourceCandidateManifestSha256=self.receipt['sourceCandidateManifestSha256'],native='native-partial',independentReopen='cold-reopen-verified-subset',namespace='unity-source/test',player='not_run',business='not_run',staticPresentation='not_run_headless')
            if self.corrupt:m['diagnostics']=[]
            self.write(target/'manifest.json',m)
            return dict(exit_code=1,capture_complete=True,parsed_stdout=dict(status='needs_action',manifestSha256=hash_file(target/'manifest.json')['sha256'])),None,None
        with patch('grea.integrations.monkey.identity.pinned',return_value=cfg),patch('grea.integrations.monkey.pipeline.probe',return_value=(cfg,{'implemented':['freeze-unity-prefabs']})),patch('grea.runner.execute',side_effect=execute):
            self.corrupt=False;result=p.freeze(lock,self.native,self.sha,self.root/'positive')
            self.assertEqual(result['diagnostics'],self.manifest['diagnostics']);self.assertFalse(result['editor_started']);self.assertFalse(result['handoff_ready'])
            self.corrupt=True
            with self.assertRaisesRegex(ValueError,'lineage differs'):p.freeze(lock,self.native,self.sha,self.root/'negative')
            self.assertTrue((self.root/'negative/failure.json').exists())
