import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from grea.common import hash_file,GreaError
from grea.integrations.monkey import pipeline
from grea.integrations.monkey.audit import audit
from grea.integrations.monkey.identity import package_files

class PipelineTests(unittest.TestCase):
    def request(self,root):
        return dict(schema_version=1,operation='convert',options={'source':str(root),'source-family':'cocos','target':'unity6'},input_roots=[str(root)],timeout_seconds=120)

    def test_argv_is_named_no_shell_or_unknown_side_effect_flags(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t).resolve();q=self.request(r);argv,_=pipeline.validate_request(q)
            self.assertIn(str(r),argv)
            for key in ('native','remote-manifest','out','resume','apply-owned'):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    pipeline.validate_request(dict(q,options=dict(q['options'],**{key:'injected'})))

    def test_unity_bulk_requires_declared_full_pool(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t).resolve();q=self.request(r);q['options']['source-family']='unity'
            with self.assertRaises(ValueError):pipeline.validate_request(q)
            (r/'bundle').write_bytes(b'UnityFS-owned');h=hash_file(r/'bundle')
            (r/'pool.json').write_text(json.dumps(dict(schemaVersion=1,files=[dict(h,path='bundle')])))
            q['options'].update({'unity-export-scope':'all','unity-dependency-manifest':str(r/'pool.json'),'provider-python':str(r/'bundle'),'asset-ripper':str(r/'bundle')})
            argv,_=pipeline.validate_request(q);self.assertIn('--unity-export-scope',argv)
            (r/'bundle').write_bytes(b'changed')
            with self.assertRaises(ValueError):pipeline.validate_request(q)

    def test_input_set_external_roots_must_be_frozen(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t).resolve();source=r/'source';source.mkdir();manifest=r/'inputs.json';manifest.write_text(json.dumps(dict(inputs=[dict(path='source')])));
            q=self.request(source);q['options'].pop('source');q['options']['input-set']=str(manifest);q['input_roots']=[str(manifest)]
            with self.assertRaises(ValueError):pipeline.validate_request(q)
            q['input_roots'].append(str(source));pipeline.validate_request(q)

    def test_snapshot_handles_file_and_directory_and_mutation(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t).resolve();f=r/'input';f.write_bytes(b'owned');before=pipeline.snapshot([f]);self.assertEqual(len(before),1)
            with self.assertRaises(ValueError):pipeline.snapshot([r],max_files=0)
            f.write_bytes(b'new');self.assertNotEqual(before,pipeline.snapshot([f]))

    def test_budget_bool_overlap_and_unsupported_operation_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t).resolve();q=self.request(r)
            for change in ({'timeout_seconds':True},{'timeout_seconds':1801},{'operation':'apply'},{'input_roots':[str(r),str(r)]}):
                with self.subTest(change=change),self.assertRaises(ValueError):pipeline.validate_request(dict(q,**change))

    def test_new_package_file_invalidates_identity(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t).resolve();(r/'cli.py').write_text('old');a=package_files(r);(r/'new.py').write_text('new');self.assertNotEqual(a,package_files(r))

    def fixture(self,r,unity=True):
        project=r/'Project';project.mkdir();files=[]
        content={'Docs/START-HERE.md':'Owned entry','Assets/Game/content.txt' if unity else 'assets/content.txt':'Owned asset','ProjectSettings/ProjectVersion.txt' if unity else 'package.json':'{}'}
        for name,text in content.items():
            p=project/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);files.append(dict(hash_file(p),path=name))
        name='recovery-manifest.json' if unity else 'manifest.json'
        m=project/name;m.write_text(json.dumps(dict(schemaVersion=1,toolVersion='0.4.0',files=files,validation={'editor':'pass'})))
        row=dict(path='Project',**({'targetVersion':'6000.6.2f1'} if unity else {'targetProfile':'cocos-3.8.8','manifestSha256':hash_file(m)['sha256']}))
        (r/'conversion-result.json').write_text(json.dumps(dict(schemaVersion=1,toolVersion='0.4.0',workflowStatus='success',completed=True,projects=[row])))
        return project,m

    def test_both_manifests_do_not_promote_native_or_gameplay(self):
        for unity in (True,False):
            with self.subTest(unity=unity),tempfile.TemporaryDirectory() as t:
                r=Path(t).resolve();self.fixture(r,unity);a=audit(r,'0.4.0');self.assertEqual(a['native_validation'],'not_run');self.assertFalse(a['handoff_ready']);self.assertEqual(a['status'],'needs_action');self.assertEqual(a['verified_files'],3)

    def test_changed_added_missing_and_traversal_outputs_refused(self):
        for mode in ('changed','added','missing','traversal'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as t:
                r=Path(t).resolve();p,m=self.fixture(r)
                if mode=='changed':(p/'Assets/Game/content.txt').write_text('tampered')
                if mode=='added':(p/'Assets/Game/new.cs').write_text('unlisted')
                if mode=='missing':(p/'Docs/START-HERE.md').unlink()
                if mode=='traversal':
                    d=json.loads(m.read_text());d['files'][0]['path']='../escape';m.write_text(json.dumps(d))
                with self.assertRaises((ValueError,GreaError)):audit(r,'0.4.0')

    def test_linked_files_and_directories_refused_even_with_matching_bytes(self):
        for directory in (False, True):
            with self.subTest(directory=directory), tempfile.TemporaryDirectory() as t:
                r=Path(t).resolve();p,_=self.fixture(r)
                linked=p/'Assets/Game' if directory else p/'Assets/Game/content.txt'
                outside=r/'outside'
                linked.rename(outside)
                try:linked.symlink_to(outside,target_is_directory=directory)
                except (OSError,NotImplementedError):self.skipTest('Symbolic links unavailable on this host')
                with self.assertRaisesRegex(ValueError,'Linked candidate output'):
                    audit(r,'0.4.0')

    def test_stale_plan_prevents_provider_execution(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t).resolve();s=r/'source';s.mkdir();(s/'a').write_text('old');q=r/'request.json';q.write_text(json.dumps(self.request(s)));lock=r/'lock.json';lock.write_text('{}')
            argv,roots=pipeline.validate_request(json.loads(q.read_text()));p=dict(schema_version=1,kind='monkey-execution-plan',executed=False,lock=hash_file(lock),request=hash_file(q),argv=argv,input_snapshot=pipeline.snapshot(roots),timeout_seconds=120,command_identity={})
            f=r/'plan.json';f.write_text(json.dumps(p));(s/'a').write_text('new')
            with patch.object(pipeline,'command_identity',return_value={}),patch.object(pipeline.runner,'execute') as execute:
                with self.assertRaisesRegex(ValueError,'Input set changed'):pipeline.execute(lock,f,r/'out')
                execute.assert_not_called();self.assertFalse((r/'out').exists())

if __name__=='__main__':unittest.main()
