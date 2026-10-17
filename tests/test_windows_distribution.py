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
          'docs/design/plan.md':(b'Old process',0o100644),'tests/unity/reference-project/keep':(b'x',0o100644),'tests/test_old.py':(b'x',0o100644)}
  files=product_projection.project(source,'a'*40)
  self.assertNotIn('validation/releases/report.json',files);self.assertNotIn('docs/design/plan.md',files)
  self.assertIn('tests/unity/reference-project/keep',files);self.assertNotIn('tests/test_old.py',files)
  self.assertIn(b'https://github.com/chuxintec/grea/blob/'+b'a'*40,files['README.md'][0])
 def test_windows_unsafe_names_are_rejected(self):
  for name in ('grea/CON','grea/a./x','grea/Lpt1.json','grea/ok:stream','grea/a?/b','grea/trailing '):
   with self.subTest(name=name),self.assertRaises(ValueError):plugin_bundle.safe_name(name)

 def test_case_and_unicode_parent_collisions_are_refused(self):
  for names in (['grea/A/x','grea/a/y'],['grea/é/a','grea/e\u0301/b']):
   with self.assertRaises(ValueError):plugin_bundle.portable_names(names)
