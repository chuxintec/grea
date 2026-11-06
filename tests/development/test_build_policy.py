"""Build mode is explicit, frozen, and cannot be coerced from truthy input."""
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from grea.development.unity import validate_spec, plan, recover, source_files
from grea.development.io import write_json, load, read, sha
from grea.development.errors import BeaverError
from grea.development.build_policy import validate, validate_readback, check_sources
from .test_adoption import candidate


class BuildPolicyTests(unittest.TestCase):
    def spec(self, **extra):
        return dict(schemaVersion=1,operation='build.macos',scenes=['Assets/Main.unity'],productName='Example',**extra)

    def test_default_and_explicit_boolean_modes(self):
        for extra in ({},{'development':False},{'development':True}):
            validate_spec(self.spec(**extra))
        for value in [0,1,'false','true',None,[],{}]:
            with self.subTest(value=value),self.assertRaises(BeaverError):
                validate_spec(self.spec(development=value))

    def test_mode_is_frozen_in_plan_and_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project=candidate(root/'project');(project/'Assets/Main.unity').write_text('synthetic plan input')
            identities=[]
            for index,mode in enumerate([False,True]):
                spec=root/f'spec{index}.json';write_json(spec,self.spec(development=mode));result=plan(project,spec,root/f'plan{index}')
                saved=load(read(Path(result['report'])))
                self.assertIs(saved['spec']['development'],mode);identities.append(result['planSha256'])
            self.assertNotEqual(*identities)

    def test_arbitrary_hook_and_malformed_font_policy_rejected(self):
        for extra in [{'executeMethod':'Project.Build'},{'tmpFontPolicy':{}},{'buildOptions':123}]:
            with self.subTest(extra=extra),self.assertRaises(BeaverError):validate_spec(self.spec(**extra))


class FontPolicyTests(unittest.TestCase):
    def policy(self):
        return dict(schemaVersion=1,fonts=[dict(path='Assets/Font.asset',guid='1'*32,sourceSha256='2'*64,metaSha256='3'*64,normalizeDynamicAtlas=True)])

    def test_strict_policy_and_duplicate_paths(self):
        validate(self.policy())
        for key,value in [('path','Assets/../Font.asset'),('normalizeDynamicAtlas',1),('guid','bad')]:
            p=self.policy();p['fonts'][0][key]=value
            with self.subTest(key=key),self.assertRaises(BeaverError):validate(p)
        p=self.policy();p['fonts']*=2
        with self.assertRaises(BeaverError):validate(p)

    def test_missing_native_restoration_or_wrong_build_identity_rejected(self):
        p=self.policy();row=dict(p['fonts'][0],buildSha256='4'*64,restoredSha256='2'*64)
        validate_readback(p,dict(fontSourcesRestoredInProcess=True,fontInputs=[row]))
        for report in [dict(fontSourcesRestoredInProcess=False,fontInputs=[row]),dict(fontSourcesRestoredInProcess=True,fontInputs=[dict(row,restoredSha256='5'*64)]),dict(fontSourcesRestoredInProcess=True,fontInputs=[])]:
            with self.assertRaises(BeaverError):validate_readback(p,report)

    def test_stale_font_rejected_before_plan_output(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(BeaverError):check_sources(Path(temp),self.policy(),{})


class BuildRecoveryGuardTests(unittest.TestCase):
    def transaction(self, root):
        project=candidate(root/'project')
        (project/'Assets/Main.unity').write_bytes(b'synthetic scene')
        font='Assets/Font.asset';meta=font+'.meta'
        original=b'original font bytes';normalized=b'normalized build font bytes'
        (project/font).write_bytes(original)
        (project/meta).write_bytes(b'fileFormatVersion: 2\nguid: '+b'1'*32+b'\n')
        declaration=dict(path=font,guid='1'*32,sourceSha256=sha(original),metaSha256=sha((project/meta).read_bytes()),normalizeDynamicAtlas=True)
        spec=root/'spec.json';write_json(spec,dict(schemaVersion=1,operation='build.macos',scenes=['Assets/Main.unity'],productName='Example',development=True,tmpFontPolicy=dict(schemaVersion=1,fonts=[declaration])))
        planned=plan(project,spec,root/'preview')
        stage=root/'transaction';stage.mkdir()
        data=load(read(Path(planned['report'])));write_json(stage/'unity-plan.json',data)
        expected=planned['planSha256']
        write_json(stage/'journal.json',dict(status='recovery-required',operation='build.macos',planSha256=expected))
        write_json(stage/'process.json',dict(owned=True,exited=True,exitCode=1))
        for path in (font,meta):
            backup=stage/'before'/path;backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes((project/path).read_bytes())
        (project/font).write_bytes(normalized)
        write_json(stage/'font-checkpoint.json',dict(planSha256=expected,mutationInProgress='',fonts=[dict(path=font,sourceSha256=declaration['sourceSha256'],metaSha256=declaration['metaSha256'],observedSha256=sha(normalized),observedMetaSha256=declaration['metaSha256'])]))
        return project,stage,expected,font

    def assert_prelaunch_refusal(self, fault, message):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,stage,expected,font=self.transaction(root)
            if fault=='font-edit':(project/font).write_bytes(b'later human font edit')
            elif fault=='backup':(stage/'before'/font).write_bytes(b'damaged before-image')
            elif fault=='checkpoint':
                p=stage/'font-checkpoint.json';d=load(read(p));d['mutationInProgress']=font;write_json(p,d)
            elif fault=='unrelated':(project/'Assets/Main.unity').write_bytes(b'later human scene edit')
            observed=source_files(project);journal=(stage/'journal.json').read_bytes()
            with patch('grea.development.unity.editor_path',return_value=root/'Unity'),patch('grea.development.unity.native_lock'),patch('grea.development.unity._install_native_helper') as helper,patch('grea.development.unity.run') as native:
                with self.assertRaises(BeaverError) as caught:recover(stage,root/'Unity',expected,30)
                self.assertEqual(caught.exception.code,'BUILD_FONT_RECOVERY')
                self.assertIn(message,str(caught.exception))
                helper.assert_not_called();native.assert_not_called()
            self.assertEqual(source_files(project),observed)
            self.assertEqual((stage/'journal.json').read_bytes(),journal)
            self.assertFalse((project/'.beaver/operation.lock').exists())

    def test_later_font_edit_refused_before_editor(self):
        self.assert_prelaunch_refusal('font-edit','Later source edit')

    def test_corrupt_backup_refused_before_editor(self):
        self.assert_prelaunch_refusal('backup','Before-image differs')

    def test_inconclusive_mutation_refused_before_editor(self):
        self.assert_prelaunch_refusal('checkpoint','Missing conclusive mutation checkpoint')

    def test_unrelated_source_drift_refused_before_editor(self):
        self.assert_prelaunch_refusal('unrelated','Unrelated source changed')

    def test_valid_checkpoint_reaches_native_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,stage,expected,font=self.transaction(root)
            def restore(*args):
                (project/font).write_bytes((stage/'before'/font).read_bytes())
                write_json(stage/'process.json',dict(owned=True,exited=True,exitCode=0))
                return dict(status='verified',fontSourcesRestoredInProcess=True,fontInputs=[])
            with patch('grea.development.unity.editor_path',return_value=root/'Unity'),patch('grea.development.unity.native_lock'),patch('grea.development.unity._install_native_helper',return_value=(root/'helper','fingerprint')) as helper,patch('grea.development.unity._remove_native_helper'),patch('grea.development.unity.run',side_effect=restore) as native:
                result=recover(stage,root/'Unity',expected,30)
                self.assertEqual(result['status'],'recovered')
                helper.assert_called_once();native.assert_called_once()
            self.assertEqual(load(read(stage/'journal.json'))['status'],'recovered')
