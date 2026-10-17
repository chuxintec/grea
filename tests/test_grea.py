import json,os,sys,tempfile,threading,time,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
from jsonschema import Draft202012Validator
from grea.application import dispatch
from grea.contracts import catalog,ENVELOPE_SCHEMA
from grea.common import package_root

ROOT=package_root();CLI=ROOT/'bin/grea'

class GreaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
    def tearDown(self):self.temp.cleanup()
    def call(self,name,args=None):
        value=dispatch(name,{} if args is None else args);Draft202012Validator(ENVELOPE_SCHEMA).validate(value);return value
    def artifact(self,name='source.bin',content=b'original'):
        p=self.root/name;p.write_bytes(content);return p
    def init(self,mode='fix',dims=None):
        source=self.artifact();args={'project_dir':str(self.root),'source':str(source),'mode':mode}
        if dims:args['required_dimensions']=dims
        r=self.call('init_case',args);self.assertEqual(r['status'],'ok',r)
        candidate=self.artifact('candidate.cs',b'candidate-v1')
        revision=self.call('start_case_revision',{'case_dir':str(self.root),'candidate_root':str(self.root),'candidate_files':[candidate.name],'platform':'editor','qa_profile':'synthetic'})
        self.assertEqual(revision['status'],'ok',revision)
        return self.root/'.grea'
    def evidence(self,case,kind,name):
        p=self.artifact(name,('data-'+name).encode());r=self.call('add_evidence',{'case_dir':str(case),'kind':kind,'path':str(p),'description':'fixture observation','run_instance':'synthetic-test-run'})
        self.assertEqual(r['status'],'ok',r);return r['result']['evidence']['id']
    def fake_registry(self,body):
        p=self.root/'provider.py';p.write_text(body)
        (self.root/'registry.json').write_text(json.dumps({'tools':[{'id':'fixture','execution':{'command':[sys.executable,str(p)],'finding_exit_codes':[]}}]}))
        return patch.dict(os.environ,{'GREA_HOME':str(self.root)})
    def test_catalog_and_strict_input(self):
        for c in catalog():Draft202012Validator.check_schema(c['inputSchema']);Draft202012Validator.check_schema(c['outputSchema'])
        self.assertEqual(self.call('session')['status'],'ok')
        self.assertEqual(self.call('session',{'unexpected':1})['error']['code'],'INVALID_ARGUMENTS')
        self.assertEqual(self.call('missing')['error']['code'],'UNKNOWN_OPERATION')
        self.assertEqual(dispatch('session',None)['error']['code'],'INVALID_ARGUMENTS')
        self.assertEqual(self.call('describe_tool',{'tool_id':'not-registered'})['error']['code'],'UNKNOWN_TOOL')
    def test_inventory_digest_and_explicit_partial(self):
        p=self.artifact();r=self.call('inspect_target',{'path':str(p)})
        self.assertEqual(r['result']['coverage'],'complete')
        self.artifact('second.bin');r=self.call('inspect_target',{'path':str(self.root),'max_files':1})
        self.assertEqual(r['status'],'partial');self.assertIsNone(r['result']['target']['sha256'])
        link=self.root/'link';link.symlink_to(p);self.assertEqual(self.call('inspect_target',{'path':str(link)})['status'],'error')
    def test_workflows_and_provider_not_ready(self):
        r=self.call('plan_workflow',{'mode':'recover','source_engine':'laya'})
        self.assertEqual(r['status'],'ok',r);self.assertFalse(r['result']['executed']);self.assertTrue(Path(r['result']['steps'][0]['reference']).is_file());self.assertIn('Unity-原生转换规范',r['result']['steps'][0]['reference']);self.assertTrue(any('Unity-跨引擎' in s['reference'] for s in r['result']['steps']));self.assertFalse(any('Unity-工程重建' in s['reference'] for s in r['result']['steps']))
        self.assertEqual(self.call('describe_tool',{'tool_id':'unity_pipeline'})['result']['availability']['runtime'],'not_checked')
        self.assertEqual(self.call('doctor',{'probe':True})['error']['code'],'EXPLICIT_SELECTION_REQUIRED')
    def test_existing_case_and_unknown_not_complete(self):
        case=self.init();r=self.call('case_status',{'case_dir':str(case)})
        self.assertEqual(r['status'],'partial');self.assertEqual(r['result']['declared_acceptance'],'incomplete')
        self.assertEqual(self.call('init_case',{'project_dir':str(self.root),'source':str(self.root/'source.bin'),'mode':'fix'})['error']['code'],'OUTPUT_EXISTS')
    def test_roles_required_and_reviewed_closure(self):
        case=self.init('recover',['visual']);static=self.evidence(case,'test_report','static.json')
        request={'case_dir':str(case),'dimension':'visual','status':'passed','evidence_ids':[static],'note':'cannot use static alone'}
        self.assertEqual(self.call('record_verification',request)['error']['code'],'INSUFFICIENT_EVIDENCE')
        request['status']='not_applicable';self.assertEqual(self.call('record_verification',request)['error']['code'],'REQUIRED_DIMENSION')
        original=self.evidence(case,'original_runtime','original.mp4');candidate=self.evidence(case,'candidate_runtime','candidate.mp4')
        request.update(status='passed',evidence_ids=[original,candidate]);self.assertEqual(self.call('record_verification',request)['status'],'ok')
        r=self.call('case_status',{'case_dir':str(case)})
        self.assertEqual(r['result']['declared_acceptance'],'ready_for_review');self.assertFalse(r['result']['verified_game_equivalence'])
    def test_evidence_and_source_staleness(self):
        case=self.init();self.evidence(case,'test_report','test.json');(self.root/'test.json').write_text('changed')
        self.assertEqual(self.call('case_status',{'case_dir':str(case)})['error']['code'],'STALE_EVIDENCE')
        (self.root/'source.bin').write_bytes(b'new version')
        self.assertEqual(self.call('case_status',{'case_dir':str(case)})['error']['code'],'STALE_SOURCE')
    def test_tamper_detection(self):
        case=self.init();eid=self.evidence(case,'test_report','test.json');p=case/'evidence'/f'{eid}.json';v=json.loads(p.read_text());v['kind']='original_runtime';p.write_text(json.dumps(v))
        self.assertEqual(self.call('case_status',{'case_dir':str(case)})['error']['code'],'TAMPERED_EVIDENCE')
    def test_real_helper_and_nonzero_parity(self):
        a=self.artifact('a.jsonl',b'{"value":1}\n');b=self.artifact('b.jsonl',b'{"value":2}\n')
        args={'tool_id':'compare_traces','arguments':[str(a),str(b),'--field','/value'],'run_dir':str(self.root/'run')}
        r=self.call('run_tool',args)
        self.assertEqual(r['result']['exit_code'],1,r);self.assertEqual(r['status'],'partial');self.assertTrue((self.root/'run/run.json').exists())
        receipt=json.loads((self.root/'run/run.json').read_text())
        self.assertEqual(receipt['limits']['timeout_seconds'],120)
        self.assertEqual(receipt['identity_observed_at'],'before_launch')
        self.assertEqual(self.call('run_tool',args)['error']['code'],'OUTPUT_EXISTS')
    def test_typed_unity_adapters(self):
        assets=self.root/'Assets';assets.mkdir()
        (assets/'Panel.prefab').write_text('%YAML 1.1\n--- !u!1 &1\nGameObject: {m_Name: Panel}\n')
        (assets/'Panel.prefab.meta').write_text('fileFormatVersion: 2\nguid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n')
        r=self.call('audit_unity_dependencies',{'assets':str(assets),'roots':['Panel.prefab'],'output':str(self.root/'closure.json'),'run_dir':str(self.root/'audit')})
        self.assertEqual(r['status'],'ok',r);self.assertEqual(r['operation'],'audit_unity_dependencies')
        r=self.call('snapshot_unity_assets',{'assets':str(assets),'output':str(self.root/'ledger.json'),'run_dir':str(self.root/'snapshot')})
        self.assertEqual(r['status'],'ok',r)
        import struct
        texture=self.artifact('float.bin',struct.pack('<4f',1,2,3,4))
        r=self.call('inspect_numeric_texture',{'source':str(texture),'width':1,'height':1,'channels':4,'dtype':'f32','run_dir':str(self.root/'texture')})
        self.assertEqual(r['status'],'ok',r)
        a=self.artifact('same-a.jsonl',b'{"value":1}\n');b=self.artifact('same-b.jsonl',b'{"value":1}\n')
        r=self.call('compare_gameplay_traces',{'before':str(a),'after':str(b),'fields':['/value'],'run_dir':str(self.root/'traces')})
        self.assertEqual(r['status'],'ok',r)
    def test_timeout_and_cancel_preserve_receipt(self):
        with self.fake_registry('import time\nprint("started",flush=True)\ntime.sleep(20)\n'):
            args={'tool_id':'fixture','arguments':[],'run_dir':str(self.root/'timeout'),'timeout_seconds':1}
            r=self.call('run_tool',args);self.assertEqual(r['error']['code'],'TIMEOUT',r)
            self.assertIn('started',(self.root/'timeout/stdout.log').read_text())
            event=threading.Event();timer=threading.Timer(.2,event.set);timer.start()
            args['run_dir']=str(self.root/'cancel');args['timeout_seconds']=10
            r=dispatch('run_tool',args,event);timer.join();self.assertEqual(r['error']['code'],'CANCELLED',r)
            self.assertTrue((self.root/'cancel/run.json').exists())
    def test_doctor_inventory_only_probe(self):
        script=self.root/'version.py';script.write_text('print("fixture 1.0")')
        (self.root/'registry.json').write_text(json.dumps({'tools':[{'id':'fixture','execution':None,'probe':[sys.executable,str(script)]}]}))
        with patch.dict(os.environ,{'GREA_HOME':str(self.root)}):
            result=self.call('doctor',{'tool_ids':['fixture'],'probe':True})
            self.assertEqual(result['status'],'ok',result)
            self.assertEqual(result['result']['checks'][0]['state'],'probe_passed')

    def test_owned_descendant_stops_on_timeout(self):
        beacon=self.root/'beacon'
        child='import time;from pathlib import Path;p=Path('+repr(str(beacon))+');\nwhile True:p.write_text(str(time.time()));time.sleep(.03)'
        parent='import subprocess,sys,time\nsubprocess.Popen([sys.executable,"-c",'+repr(child)+'])\nprint("parent started",flush=True)\ntime.sleep(20)\n'
        with self.fake_registry(parent):
            r=self.call('run_tool',{'tool_id':'fixture','arguments':[],'run_dir':str(self.root/'descendant'),'timeout_seconds':1})
            self.assertEqual(r['error']['code'],'TIMEOUT',r)
            self.assertTrue(beacon.exists())
            value=beacon.read_text();time.sleep(.15);self.assertEqual(beacon.read_text(),value)
    def test_output_limit(self):
        with self.fake_registry('import sys\nsys.stdout.write("x"*2000000)\n'):
            r=self.call('run_tool',{'tool_id':'fixture','arguments':[],'run_dir':str(self.root/'large'),'max_output_bytes':1024})
            self.assertEqual(r['error']['code'],'OUTPUT_LIMIT',r);self.assertLessEqual((self.root/'large/stdout.log').stat().st_size,1024)
    def test_cli_json_failure(self):
        p=subprocess.run([sys.executable,str(ROOT/'launch.py'),'session','{"extra":1}'],capture_output=True,text=True,cwd=tempfile.gettempdir())
        self.assertEqual(p.returncode,2);self.assertEqual(json.loads(p.stdout)['error']['code'],'INVALID_ARGUMENTS')

    def test_typed_cli_paths_resolve_from_caller(self):
        self.artifact('a.jsonl',b'{"value":1}\n');self.artifact('b.jsonl',b'{"value":1}\n')
        request={'before':'a.jsonl','after':'b.jsonl','fields':['/value'],'run_dir':'run'}
        p=subprocess.run([sys.executable,str(ROOT/'launch.py'),'compare-gameplay-traces',json.dumps(request)],capture_output=True,text=True,cwd=self.root)
        result=json.loads(p.stdout)
        self.assertEqual(p.returncode,0,result)
        self.assertEqual(result['status'],'ok')
        self.assertTrue((self.root/'run/run.json').is_file())

if __name__=='__main__':unittest.main()
