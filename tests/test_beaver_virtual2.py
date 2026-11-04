import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from jsonschema import Draft202012Validator
from grea.integrations import beaver, beaver_operations as ops
from grea.beaver_contracts import documents

class Virtual2Tests(unittest.TestCase):
    version = beaver.VIRTUAL2_VERSION
    def request(self,action):
        options={'spec':'/fixture/spec','expected-spec':'a'*64} if action=='prepare' else ({'project':'demo','build':'build-a','profile':'qa-a','run':'run-a','expected-owner':'a'*64,'channel':'/fixture/channel','expected-channel':'b'*64} if action=='bind' else {'session':'/fixture/session','expected-session':'a'*64})
        if action=='input':options.update(spec='/fixture/input',**{'expected-spec':'b'*64})
        return dict(schema_version=1,operation='qa.virtual-'+action,options=options,timeout_seconds=90)

    def test_exact_producer_and_five_capabilities(self):
        cap=dict(version=self.version,**beaver.V03_CONTRACTS,producer_implementation_sha256=beaver.V03_CANDIDATES[self.version]['implementation_sha256'],capabilities=[dict(id=n,state='implemented') for n in sorted(beaver.V02_OPERATIONS|beaver.V03_GROUPS|beaver.VIRTUAL_OPERATIONS|beaver.VIRTUAL_BOOTSTRAP_OPERATIONS)])
        beaver.validate_capabilities(cap)
        for change in [dict(version='0.6.0.dev20261102+virtual1'),dict(producer_implementation_sha256='0'*64),dict(capabilities=[r for r in cap['capabilities'] if r['id']!='qa.virtual-stop'])]:
            with self.assertRaises(ValueError):beaver.validate_capabilities(dict(cap,**change))

    def test_only_virtual_surface_schema_and_no_legacy_inheritance(self):
        version=self.version
        wanted=beaver.VIRTUAL_OPERATIONS|beaver.VIRTUAL_BOOTSTRAP_OPERATIONS
        self.assertEqual({n for n in ops.OPERATIONS if version in ops.operation_versions(n)},wanted)
        variants=documents()['beaver-operation.schema.json']['oneOf']
        self.assertEqual({v['properties']['operation']['const'] for v in variants if version in v['x-beaver-versions']},wanted)
        for action in ('prepare','bind','input','status','stop'):
            q=self.request(action);ops.validate_provider_version(q,version)
            Draft202012Validator(documents()['beaver-operation.schema.json']).validate(q)
            argv=ops.argv_for(q,'/fixture/new');self.assertEqual(argv[:2],['qa','virtual-'+action]);self.assertIn('--out',argv)
            for old in (beaver.P0_FIX21_VERSION,beaver.P0_FIX26_VERSION,'0.6.0.dev20261102+virtual1'):
                with self.assertRaises(ValueError):ops.validate_provider_version(q,old)
        self.assertFalse(beaver.operation_allowed(version,'qa.input'))
        self.assertFalse(beaver.operation_allowed(version,'intake.apply'))

    def test_bootstrap_preserves_exact_owner_profile_and_no_raw_input(self):
        for name in ('qa.prepare','qa.launch','qa.collect'):
            options=({'spec':'/fixture/prepare','expected-spec':'a'*64} if name=='qa.prepare' else dict(project='demo',build='build-a',profile='qa-a',run='run-a',**{'expected-owner':'a'*64}))
            q=dict(schema_version=1,operation=name,options=options,timeout_seconds=90)
            ops.validate_provider_version(q,self.version)
            with self.assertRaises(ValueError):ops.validate(dict(q,options=dict(options,pid=42)))

    def test_strict_hashes_ids_and_no_dispatch_override(self):
        for action in ('prepare','bind','input','status','stop'):
            q=self.request(action)
            for change in ({'pid':42},{'backend':'macos-native-ax-pid/1'},{'fallback':True}):
                with self.assertRaises(ValueError):ops.validate(dict(q,options=dict(q['options'],**change)))
            key=next(k for k in q['options'] if k.startswith('expected-'))
            with self.assertRaises(ValueError):ops.validate(dict(q,options=dict(q['options'],**{key:'bad'})))
        q=self.request('bind')
        with self.assertRaises(ValueError):ops.validate(dict(q,options=dict(q['options'],project='../other')))
        for name in ('qa.bind','qa.input'):
            self.assertNotIn(self.version,ops.operation_versions(name))

    def test_partial_virtual_receipt_is_not_replayed_or_promoted(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp).resolve();q=self.request('input');q['options'].update(session=str(r/'session'),spec=str(r/'input'));f=r/'request.json';f.write_text(json.dumps(q))
            version=self.version;producer=dict(name='beaver',version=version,implementationSha256=beaver.V03_CANDIDATES[version]['implementation_sha256'])
            actual=dict(schemaVersion=1,contract='beaver-result/1',operationId='fixture',producer=producer,status='partial',actualChanges=[dict(inputMode='virtual-pointer',sequence=2,delivery='possibly-consumed')],artifacts=[],diagnostics=[],limitations=[],verification=dict(native='not_run',virtualInput='not_verified',player='not_run',visual='not_run',business='not_run'),data=dict(inputMode='virtual-pointer',backend='unity-inputsystem-virtual-pointer/1',cleanupPerformed=False,endpointRemoved=False,status='partial'))
            cfg=dict(version=version,identity_root=str(r/'package'),package_files={},command=[str(r/'beaver')],command_files={});lock=r/'lock';lock.write_text(json.dumps(cfg))
            def checked(output,**kw):
                p=Path(output)/'probe';p.mkdir(parents=True);(p/'run.json').write_text(json.dumps(dict(parsed_stdout=dict(producer=producer,data=dict(capabilities=[dict(id='qa.virtual-input',state='requires_provider')])))));return {'ready':True}
            with patch('grea.integrations.monkey.local.readiness',return_value={'ready':True}),patch.object(beaver,'check',side_effect=checked),patch.object(beaver,'package_identity',return_value={}),patch.object(beaver,'command_identity',return_value={}),patch('grea.runner.execute',return_value=({'parsed_stdout':actual,'capture_complete':True,'exit_code':1},[],None)) as run:
                result=ops.invoke(lock,f,r/'out')
            self.assertEqual(run.call_count,1)
            self.assertEqual(result['provider_result'],actual)
            self.assertEqual(result['status'],'partial')
            self.assertEqual(result['native'],'not_run')


class Virtual4Tests(Virtual2Tests):
    version = beaver.VIRTUAL4_VERSION


class Fix30Tests(Virtual2Tests):
    version = beaver.P0_FIX30_VERSION


class Fix31Tests(Virtual2Tests):
    version = beaver.P0_FIX31_VERSION
