import json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from monkey.io import write_json,sha
from monkey import cocos_native_finish as finish
from monkey.sources.compiled import ParseError
from monkey.targets.unity import label_font_matches
from monkey.native import stamp


class BulkFinishTests(unittest.TestCase):
    def fixture(self,root):
        project=root/'project';prepared=root/'prepared';prepared.mkdir();(project/'Analysis').mkdir(parents=True);(project/'Assets/Editor').mkdir(parents=True)
        (project/'Assets/Editor/import-plan.json').write_text('{}');(project/'Assets/Candidate.prefab').write_text('frozen prefab')
        (project/'Analysis/editor-readback.json').write_text('{}');write_json(project/'Analysis/output-paths.json',dict(plan='Assets/Editor/import-plan.json',prefab='Assets/Candidate.prefab'))
        (project/'manifest.json').write_text('{}');identity=sha((project/'manifest.json').read_bytes())
        plan=dict(inputPlanSha256=sha(b'{}'),candidatePrefabSha256=sha(b'frozen prefab'),priorReadbackSha256=sha(b'{}'),scenes=[],fontSourceIds=[])
        write_json(prepared/'bulk-finish-plan.json',plan);helper=(Path(finish.__file__).parent/'targets/UnityBulkFinish.cs').read_bytes();(prepared/'UnityBulkFinish.cs').write_bytes(helper)
        write_json(prepared/'preparation.json',dict(source=str(project),sourceManifestSha256=identity,planSha256=sha((prepared/'bulk-finish-plan.json').read_bytes()),helperSha256=sha(helper)))
        editor=root/'Unity';editor.write_text('#!/bin/sh\nexit 99\n');editor.chmod(0o700);now=datetime.now(timezone.utc)
        return dict(candidate=project,preparation=prepared,output=root/'execution',editor=editor,expected_manifest=identity,budget_seconds=600,deadline_utc=stamp(now+timedelta(minutes=15)),window_end_utc=stamp(now+timedelta(minutes=17)))

    def test_plan_cannot_launch_or_modify_existing_project(self):
        with tempfile.TemporaryDirectory()as temp:
            opts=self.fixture(Path(temp).resolve())
            with patch('subprocess.Popen',side_effect=AssertionError('planning must not launch')):result=finish.execute(**opts)
            self.assertEqual(result['status'],'planned');self.assertFalse((opts['candidate']/'Analysis/bulk-finish-plan.json').exists());self.assertFalse((opts['candidate']/'Assets/Editor/UnityBulkFinish.cs').exists())

    def test_changed_frozen_prefab_or_helper_is_refused_before_output(self):
        for kind in ['prefab','helper']:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory()as temp:
                opts=self.fixture(Path(temp).resolve())
                target=opts['candidate']/'Assets/Candidate.prefab'if kind=='prefab'else opts['preparation']/'UnityBulkFinish.cs'
                target.write_text('changed')
                with self.assertRaises(ParseError):finish.execute(**opts)
                self.assertFalse(opts['output'].exists())

    def test_previous_failed_layer_requires_exact_owned_evidence_before_any_replacement(self):
        with tempfile.TemporaryDirectory()as temp:
            opts=self.fixture(Path(temp).resolve());project=opts['candidate'];previous=Path(temp).resolve()/'previous';previous.mkdir()
            helper=(opts['preparation']/'UnityBulkFinish.cs').read_bytes();(project/'Assets/Editor/UnityBulkFinish.cs').write_bytes(helper)
            old_plan=json.loads((opts['preparation']/'bulk-finish-plan.json').read_text());old_plan.update(budgetSeconds=600,deadlineUtc=opts['deadline_utc']);write_json(project/'Analysis/bulk-finish-plan.json',old_plan)
            failed=dict(status='failed',scenes=[],fonts=[]);write_json(project/'Analysis/bulk-finish-readback.json',failed);write_json(previous/'bulk-finish-readback.json',failed)
            write_json(previous/'execution-result.json',dict(project=str(project),processExited=True,status='partial',historicalManifestUnchanged=True,nativeStatus='failed',sourceManifestSha256=opts['expected_manifest']))
            write_json(previous/'execution-plan.json',dict(preparation=str(opts['preparation']),budgetSeconds=600,deadlineUtc=opts['deadline_utc'],helperSha256=sha(helper)))
            with self.assertRaises(ParseError):finish.execute(**opts)
            with patch('subprocess.Popen',side_effect=AssertionError('planning must not launch')):result=finish.execute(**dict(opts,previous_execution=previous))
            self.assertEqual(result['status'],'planned');self.assertEqual(json.loads((project/'Analysis/bulk-finish-readback.json').read_text()),failed)
            (project/'Assets/Editor/UnityBulkFinish.cs').write_text('manual edit')
            with self.assertRaises(ParseError):finish.execute(**dict(opts,output=Path(temp).resolve()/'other',previous_execution=previous))
            self.assertFalse((Path(temp)/'other').exists())

    def test_long_expired_or_marginless_windows_are_rejected(self):
        with tempfile.TemporaryDirectory()as temp:
            opts=self.fixture(Path(temp).resolve());now=datetime.now(timezone.utc)
            for deadline,end in [(now+timedelta(minutes=39),now+timedelta(minutes=42)),(now-timedelta(seconds=1),now+timedelta(minutes=15)),(now+timedelta(minutes=17),now+timedelta(minutes=17))]:
                with self.assertRaises(ValueError):finish.execute(**dict(opts,deadline_utc=stamp(deadline),window_end_utc=stamp(end)))
                self.assertFalse(opts['output'].exists())

    def test_shrink_requires_actual_configuration_and_rejects_font_substitution(self):
        spec=dict(text='abc',fontSize=30,overflow=2);font=dict(guid='source-guid');actual=dict(text='abc',fontSize=21.4,fontGuid='source-guid',allCharactersPresent=True)
        proof=dict(text='abc',fontGuid='source-guid',requestedFontSize=30,actualFontSize=21.4,autoSizing=True,fontSizeMin=.1,fontSizeMax=30,prefabUnchanged=True,allCharactersPresent=True)
        self.assertFalse(label_font_matches(spec,actual,font));self.assertTrue(label_font_matches(spec,actual,font,proof))
        for changed in [dict(autoSizing=False),dict(fontSizeMax=31),dict(fontSizeMin=22),dict(actualFontSize=31),dict(actualFontSize=float('nan')),dict(fontGuid='fallback'),dict(text='other'),dict(prefabUnchanged=False),dict(allCharactersPresent=False)]:
            self.assertFalse(label_font_matches(spec,actual,font,dict(proof,**changed)),changed)
        self.assertFalse(label_font_matches(dict(spec,overflow=0),actual,font,proof))
        self.assertFalse(label_font_matches(spec,dict(actual,fontGuid='fallback'),font,proof))

    def test_shrink_geometry_keeps_native_fixed_margin_and_scales_metrics(self):
        from monkey.targets.unity import bitmap_label_probe
        font=dict(pointSize=20,ascent=20,kernings=[],glyphs=[dict(unicode=65,metrics=[8,12,1,16,12],sourceRect=[0,0,8,12])])
        from monkey.assets.bitmap import single_line
        spec=dict(text='AA',fontSize=40,overflow=2,spacing=4,bitmapProbe=single_line(font,'AA',40,4))
        probe,size,aligned=bitmap_label_probe(spec,font,20)
        self.assertEqual(size,20);self.assertEqual(probe['boxes'][0]['width'],8);self.assertEqual(probe['boxes'][1]['x'],15)
        fixed=spec['bitmapProbe']['inkRight']-spec['bitmapProbe']['advance']
        self.assertEqual(aligned,probe['advance']+fixed)
        self.assertNotEqual(aligned,probe['inkRight'])
        self.assertEqual(bitmap_label_probe(dict(spec,overflow=0),font,20)[0],spec['bitmapProbe'])

    def test_future_native_equal_size_shrink_still_requires_auto_size_configuration(self):
        spec=dict(text='short',fontSize=30,overflow=2);font=dict(guid='guid');row=dict(text='short',fontSize=30,fontGuid='guid',allCharactersPresent=True,autoSizeReadback=True,autoSizing=False,fontSizeMin=.1,fontSizeMax=30)
        self.assertFalse(label_font_matches(spec,row,font));self.assertTrue(label_font_matches(spec,dict(row,autoSizing=True),font))


if __name__=='__main__':unittest.main()
