import tempfile,unittest,json
from pathlib import Path
from grea.tools.server_go_project import generate
from grea.application import dispatch
class ServerGoTemplate(unittest.TestCase):
 def test_generator_is_create_only_no_credentials_no_deployment(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'new';r=generate(root)
   self.assertEqual(r['options']['payment'],'Unavailable')
   self.assertEqual(len(r['options']['roles']),6)
   for role in r['options']['roles']:self.assertTrue((root/'cmd'/role/'main.go').is_file())
   self.assertTrue((root/'api/game.pb.go').is_file());self.assertTrue((root/'go.sum').is_file());self.assertTrue((root/'.dockerignore').is_file());self.assertIn('.local/',(root/'.gitignore').read_text())
   self.assertFalse((root/'.local').exists());self.assertFalse((root/'compose.json').exists())
   with self.assertRaises(ValueError):generate(root)
 def test_backend_plan_cannot_use_only_identity_for_execution(self):
  r=dispatch('plan_workflow',dict(mode='recover',target_engine='none',backend='go'))
  self.assertEqual(r['status'],'ok',r);self.assertTrue({'rules','runtime','identity'}<=set(r['result']['required_dimensions']))
