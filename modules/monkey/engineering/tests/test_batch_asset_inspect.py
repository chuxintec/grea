"""Asset identity evidence plans have an empty product write set."""
import tempfile,unittest,json
from pathlib import Path
from beaver.batch import plan, validate
from beaver.io import write_json
from beaver.errors import BeaverError
from test_intake import _project,_write_asset

class AssetInspectPlanTests(unittest.TestCase):
 def test_real_selected_asset_and_meta_are_pinned_without_product_write(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp).resolve();p=_project(root/'project');_write_asset(p,'Assets/Shared.shader',b'Shader "Fixture" {}','2'*32)
   spec=dict(schemaVersion=2,operation='batch',steps=[dict(kind='asset.inspect',assetPath='Assets/Shared.shader')])
   sp=root/'spec.json';write_json(sp,spec);r=plan(p,sp,root/'out');doc=json.loads(Path(r['report']).read_text())
   self.assertEqual(doc['writeSet'],[]);self.assertIn('Assets/Shared.shader',doc['before']);self.assertIn('Assets/Shared.shader.meta',doc['before'])
   self.assertEqual(r['metrics']['editorStarts'],0)
 def test_bad_inspection_path_and_mutation_fields_are_rejected(self):
  for row in (dict(kind='asset.inspect',assetPath='Assets/../Outside.shader'),dict(kind='asset.inspect',assetPath='Assets/Shared.shader',after='replace'),dict(kind='asset.inspect',assetPath='Assets/Script.cs')):
   with self.subTest(row=row):
    with self.assertRaises(BeaverError):validate(dict(schemaVersion=2,operation='batch',steps=[row]))
