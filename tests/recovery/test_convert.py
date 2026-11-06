import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from .fixtures import fixture
from grea.recovery.cli import main
from grea.recovery.convert import convert, resume, recipe
from grea.recovery.io import read, load, write_json
from grea.recovery.sources.compiled import ParseError


class ConvertTests(unittest.TestCase):
    def test_one_command_both_targets_preserves_source_and_reports_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = fixture(root/'source')
            before = {p: p.read_bytes() for p in source.parent.rglob('*') if p.is_file()}
            for target in ('unity', 'cocos'):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    code = main(['convert', '--source', str(source), '--target', target,
                                 '--asset-index', '2', '--out', str(root/target)])
                summary = json.loads(stdout.getvalue())
                self.assertEqual(code, 1)  # Missing original font remains a real gap.
                self.assertTrue(summary['completed'])
                self.assertEqual(summary['validation']['static'], 'pass')
                self.assertEqual(summary['validation']['editor'], 'not_run')
                self.assertTrue((root/target/'project/manifest.json').is_file())
                self.assertTrue((root/target/'handoff/HANDOFF.md').is_file())
                receipt = load(read(root/target/'conversion.json'))
                self.assertEqual(len(receipt['stages']), 6)
                check = resume(root/target)
                self.assertEqual(check['resultKind'], 'candidate')
                self.assertEqual(check['workflowStatus'], 'needs_action')
                if target == 'cocos':
                    self.assertIn('STATIC_PRESENTATION_NATIVE_INCOMPLETE',{d['code'] for d in receipt['diagnostics']})
                self.assertIn('EDITOR_NOT_RUN', [d['code'] for d in check['diagnostics']])
            source.write_text('{}', encoding='utf-8')
            with self.assertRaises(ParseError): resume(root/'cocos')
            source.write_bytes(before[source])
            self.assertEqual(before, {p: p.read_bytes() for p in source.parent.rglob('*') if p.is_file()})

    def test_requested_coretext_policy_reaches_unity_plan_with_digested_sources(self):
        from grea.recovery.sources.containers import fingerprint
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            source=fixture(root/'bundle')
            out=root/'native-fonts'
            seen=[]
            def observe(ir, manifest, destination):
                self.assertEqual(load(read(ir))['sourceManifestSha256'],fingerprint(manifest))
                self.assertEqual(destination,out/'SystemFonts')
                seen.append(manifest)
                raise ValueError("font preparation unavailable in this fixture")
            with patch("grea.recovery.source_system_font_preparation.conversion_plan_inputs",side_effect=observe):
                with contextlib.redirect_stderr(io.StringIO()):
                    code=main(['convert','--source',str(source),'--all-assets','--target','unity',
                               '--unity-system-fonts','coretext','--offline','--out',str(out)])
            self.assertEqual(code,2)
            self.assertEqual(len(seen),1)
            self.assertEqual(load(read(out/'conversion.json'))['failedStage'],'plan')
            self.assertFalse((out/'project').exists())

    def test_project_default_selects_all_and_refuses_existing_or_source_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); source = root/'source'; (source/'assets').mkdir(parents=True)
            write_json(source/'project.json', dict(version='2.4.15', id='cli-project'))
            write_json(source/'assets/view.prefab.meta', dict(uuid='00000000-0000-0000-0000-000000000003'))
            write_json(source/'assets/view.prefab', [
                {'__type__':'cc.Prefab','data':{'__id__':1}},
                {'__type__':'cc.Node','_name':'Root','_parent':None,'_children':[],'_components':[]}])
            result = convert(source, 'cocos', root/'out')
            self.assertTrue(result['completed'])
            self.assertEqual(result['selection'], [0])
            self.assertEqual(load(read(root/'out/project/package.json'))['version'], '3.8.8')
            with self.assertRaises(ParseError): convert(source, 'unity', root/'out')
            with self.assertRaises(ParseError): convert(source, 'unity', source/'output')

    def test_bundle_requires_explicit_scope_and_failed_stage_keeps_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); source = fixture(root/'source')
            with self.assertRaises(ParseError): convert(source, 'unity', root/'out')
            self.assertFalse((root/'out').exists())
            with patch('grea.recovery.convert.normalize', side_effect=ValueError('normalizer failure')):
                with self.assertRaises(ValueError):
                    convert(source, 'unity', root/'out', all_assets=True)
            receipt = load(read(root/'out/conversion.json'))
            self.assertFalse(receipt['completed'])
            self.assertEqual(receipt['failedStage'], 'normalize')
            self.assertTrue((root/'out/inspect/source-manifest.json').is_file())

    def test_recipe_relative_paths_and_missing_version_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); source = fixture(root/'source')
            config = load(read(source)); del config['engineVersion']; write_json(source, config)
            with self.assertRaises(ParseError): convert(source, 'cocos', root/'absent', selection=[2])
            self.assertFalse((root/'absent').exists())
            write_json(root/'recipe.json', dict(source='source/config.json',target='cocos',
                                               source_profile='cocos-2.4.15-bundle',selection=[2]))
            args = recipe(root/'recipe.json')
            self.assertEqual(args['source'], str(source))
            convert(output=root/'out', **args)
            manifest = root/'out/project/manifest.json'
            manifest.write_text('{}', encoding='utf-8')
            with self.assertRaises(ParseError): resume(root/'out')


if __name__ == '__main__': unittest.main()
