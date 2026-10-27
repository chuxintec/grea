"""Portable target identity/projection tests; native execution lives in Windows CI."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import plugin_targets,plugin_bundle,build_plugin,product_projection
import test_plugin_bundle as fixtures

class TargetTests(unittest.TestCase):
 def test_target_layout_and_locks_are_independent(self):
  for name,layout in plugin_targets.TARGETS.items():
   lock=json.loads((ROOT/layout['lock']).read_text(encoding='utf-8'))
   self.assertEqual(lock['target'],name);self.assertEqual(len(lock['sha256']),64)
   self.assertIn(layout['triple'],lock['url']);self.assertIn(layout['triple'],lock['licenseArchive']['url'])
  self.assertNotEqual(plugin_targets.TARGETS['macos-arm64']['python'],plugin_targets.TARGETS['windows-x64']['python'])
 def test_windows_manifest_uses_native_executable_without_shell(self):
  source=fixtures.PluginBundleTests().source_fixture()
  with tempfile.TemporaryDirectory(prefix='移 动 & ! () ') as tmp:
   root=Path(tmp)/'grea';build_plugin.write_product(source,root,'windows-x64')
   codex=json.loads((root/'.mcp.json').read_text())['mcpServers']['grea']
   claude=json.loads((root/'.claude-plugin/plugin.json').read_text())['mcpServers']['grea']
   for row in (codex,claude):
    self.assertTrue(row['command'].endswith('/runtime/python.exe'));self.assertEqual(row['args'][:3],['-I','-B','-c'])
    self.assertNotIn('cmd.exe',row['command']);self.assertEqual(row['args'][-1],'mcp')
 def test_projection_excludes_process_history_and_rewrites_external_links(self):
  source={'README.md':(b'[report](validation/releases/report.json) [guide](docs/usage.md)',0o100644),
          'validation/releases/report.json':(b'{}',0o100644),'docs/usage.md':(b'Guide',0o100644),
          'proposals/design/plan.md':(b'Old process',0o100644),'tests/unity/reference-project/keep':(b'x',0o100644),'tests/test_old.py':(b'x',0o100644)}
  files=product_projection.project(source,'a'*40)
  self.assertNotIn('validation/releases/report.json',files);self.assertNotIn('proposals/design/plan.md',files)
  self.assertIn('tests/unity/reference-project/keep',files);self.assertNotIn('tests/test_old.py',files)
  self.assertIn(b'https://github.com/chuxintec/grea/blob/'+b'a'*40,files['README.md'][0])
 def test_windows_unsafe_names_are_rejected(self):
  for name in ('grea/CON','grea/a./x','grea/Lpt1.json','grea/ok:stream','grea/a?/b','grea/trailing '):
   with self.subTest(name=name),self.assertRaises(ValueError):plugin_bundle.safe_name(name)

 def test_case_and_unicode_parent_collisions_are_refused(self):
  for names in (['grea/A/x','grea/a/y'],['grea/é/a','grea/e\u0301/b']):
   with self.assertRaises(ValueError):plugin_bundle.portable_names(names)

 def test_only_console_script_records_may_be_pruned(self):
  import csv
  with tempfile.TemporaryDirectory() as tmp:
   runtime=Path(tmp)/'runtime';site=runtime/'Lib/site-packages';info=site/'pip.dist-info';info.mkdir(parents=True)
   record=info/'RECORD'
   record.write_text('../../Scripts/pip.exe,,\n',encoding='utf-8')
   build_plugin.normalize_records(site,runtime)
   self.assertEqual(record.read_text(),'')
   record.write_text('missing_runtime_library.py,,\n',encoding='utf-8')
   with self.assertRaises(ValueError):build_plugin.normalize_records(site,runtime)

 def test_complete_product_keeps_current_skills_sync_and_document_closure(self):
  import check_docs
  source,_=plugin_bundle.read_source(ROOT,worktree=True)
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'grea';build_plugin.write_product(source,root,'macos-arm64','a'*40)
   self.assertEqual({p.parent.name for p in (root/'plugin/skills').glob('*/SKILL.md')},{p.parent.name for p in (ROOT/'plugin/skills').glob('*/SKILL.md')})
   self.assertTrue((root/'scripts/sync_skill.py').is_file())
   self.assertTrue((root/'LICENSE').is_file());self.assertTrue((root/'THIRD_PARTY.md').is_file())
   result=check_docs.check(root);self.assertTrue(result['ok'],result['errors'])
