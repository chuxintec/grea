"""Copy semantics, preflight boundaries and the unified tool entry."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from grea.common import package_root
from grea.tools.static_asset_copy import copy_assets

ROOT = package_root()


class StaticAssetCopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve(); self.source = self.root/'source'; self.source.mkdir()
        (self.source/'index.html').write_bytes(b'<p>unchanged</p>\n')
        (self.source/'assets/empty').mkdir(parents=True)
        (self.source/'assets/中文.bin').write_bytes(bytes(range(256)))
        (self.source/'run.sh').write_text('#!/bin/sh\nexit 0\n'); (self.source/'run.sh').chmod(0o755)
        self.output = self.root/'new output'

    def test_nested_unicode_binary_empty_directories_and_independent_bytes(self):
        result = copy_assets(self.source,self.output,['index.html=home.html','assets=data','run.sh=bin/run.sh'])
        self.assertEqual(result['output'],str(self.output))
        self.assertEqual(result['mappings'][1],{'from':'assets','to':'data'})
        self.assertEqual((self.output/'data/中文.bin').read_bytes(),bytes(range(256)))
        self.assertTrue((self.output/'data/empty').is_dir())
        if os.name!='nt':self.assertTrue((self.output/'bin/run.sh').stat().st_mode & 0o111)
        (self.output/'home.html').write_text('changed')
        self.assertEqual((self.source/'index.html').read_bytes(),b'<p>unchanged</p>\n')

    def test_empty_output_reuse_and_nonempty_output_preservation(self):
        self.output.mkdir();copy_assets(self.source,self.output,['index.html=index.html'])
        before=(self.output/'index.html').read_bytes()
        with self.assertRaises(ValueError):copy_assets(self.source,self.output,['assets=assets'])
        self.assertEqual((self.output/'index.html').read_bytes(),before)

    def test_all_mappings_checked_before_output_creation(self):
        for bad in ['missing=late','index.html','index.html=','../index.html=x','index.html=../x',
                    'index.html=/absolute','index.html=C:\\outside','index.html=\\absolute','assets/../index.html=x','index.html=..\\x']:
            with self.subTest(mapping=bad):
                with self.assertRaises((ValueError,OSError)):copy_assets(self.source,self.output,['index.html=good',bad])
                self.assertFalse(self.output.exists())

    def test_source_output_and_target_overlap_rejected(self):
        for output in [self.source,self.source/'child',self.root]:
            with self.assertRaises(ValueError):copy_assets(self.source,output,['index.html=a'])
        for maps in [['index.html=x','run.sh=x'],['assets=x','index.html=x/nested'],['index.html=x/nested','assets=x']]:
            with self.assertRaises(ValueError):copy_assets(self.source,self.output,maps)
            self.assertFalse(self.output.exists())

    def test_source_symlinks_and_output_alias_cannot_bypass_boundaries(self):
        link=self.source/'linked'
        try:link.symlink_to(self.source/'assets',target_is_directory=True)
        except OSError:self.skipTest('Symlinks unavailable')
        with self.assertRaises(ValueError):copy_assets(self.source,self.output,['linked/中文.bin=copy'])
        (self.source/'assets/link').symlink_to(self.source/'index.html')
        with self.assertRaises(ValueError):copy_assets(self.source,self.output,['assets=data'])
        alias=self.root/'alias';alias.symlink_to(self.source,target_is_directory=True)
        with self.assertRaises(ValueError):copy_assets(self.source,alias/'inside',['index.html=x'])
        self.assertFalse((self.source/'inside').exists());self.assertFalse(self.output.exists())

    def test_special_file_rejected_without_opening_it(self):
        if not hasattr(os,'mkfifo'):self.skipTest('FIFO unavailable')
        os.mkfifo(self.source/'pipe')
        with self.assertRaises(ValueError):copy_assets(self.source,self.output,['index.html=first','pipe=second'])
        self.assertFalse(self.output.exists())

    def test_native_exit_codes_and_controlled_receipt(self):
        launch=[sys.executable,str(ROOT/'launch.py')]
        bad=subprocess.run(launch+['legacy','static_asset_copy','--unknown'],cwd=self.root,capture_output=True,text=True)
        self.assertEqual(bad.returncode,1);self.assertEqual(bad.stdout,'')
        args={'tool_id':'static_asset_copy','arguments':['--source',str(self.source),'--output',str(self.output),'--map','assets=payload'],
              'run_dir':str(self.root/'receipt')}
        run=subprocess.run(launch+['run-tool',json.dumps(args)],cwd=self.root,capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr+run.stdout)
        receipt=json.loads(run.stdout);self.assertEqual(receipt['status'],'ok')
        self.assertTrue((self.root/'receipt/run.json').is_file());self.assertTrue((self.output/'payload/中文.bin').is_file())


class ReferenceRoutesTests(unittest.TestCase):
    def test_category_grouping_and_all_workflow_and_scenario_paths_resolve(self):
        from grea.workflows import WORKFLOWS, plan
        categories={'流程':'01','工具':'02','恢复':'03','资源':'04','Unity':'05','玩法':'06','美术':'07','验收':'08','交付':'09','维护':'10'}
        for path in [*(ROOT/'plugin/shared').glob('*.md'),*(ROOT/'plugin/skills').glob('*/references/*.md')]:
            number,category,module=path.stem.split('-',2)
            self.assertEqual(number,categories[category]);self.assertTrue(module)
        for mode in WORKFLOWS:
            for engine in ['unity','cocos','laya']:
                for step in plan(mode,engine)['steps']:self.assertTrue(Path(step['reference']).is_file(),step)
        cases=json.loads((ROOT/'tests/scenarios/scenarios.json').read_text())['cases']
        for case in cases:
            self.assertNotIn('primary_reference_numbers',case)
            for name in case['primary_references']:self.assertTrue((ROOT/name).is_file(),(case['id'],name))

if __name__=='__main__':unittest.main()
