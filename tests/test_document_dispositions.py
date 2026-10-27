"""Validate the executed inventory and historical byte preservation, not prose count alone."""
import hashlib,json
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import check_docs

class DocumentationTests(unittest.TestCase):
 def test_inventory_is_complete_and_immutable_reports_match(self):
  inventory=json.loads((ROOT/'proposals/design/windows-docs-inventory-20261017.json').read_text(encoding='utf-8'))
  self.assertEqual(len(inventory['entries']),77)
  for row in inventory['entries']:
   self.assertIn(row['status'],('executed','retained_with_reason'))
   if row['action']=='move_immutable':
    self.assertEqual(hashlib.sha256((ROOT/row['resolved_target']).read_bytes()).hexdigest(),row['sha256'])
   if row['status']=='retained_with_reason':self.assertTrue(row['execution_note'])
 def test_core_navigation_and_current_links(self):
  expected={'README.md','安装与平台.md','使用指南.md','接口与证据说明.md','Unity指南.md','维护与发布.md','故障排查.md'}
  # Product guides live in the skill environment (grea's shared references); docs/ is gone.
  expected=(expected-{'README.md'})|{'产品文档索引.md'}
  self.assertTrue(expected<={p.name for p in (ROOT/'plugin/skills/grea/references').glob('*.md')})
  self.assertFalse((ROOT/'docs').exists())
  self.assertTrue(check_docs.check(ROOT)['ok'])
  self.assertEqual(list((ROOT/'docs/history').glob('*.md')),[])
