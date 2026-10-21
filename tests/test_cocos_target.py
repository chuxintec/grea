import json,tempfile,unittest
from pathlib import Path
from grea.tools.cocos_project import generate,audit_layers
from grea.tools.cocos_convert import convert
from grea.application import dispatch
class CocosTarget(unittest.TestCase):
 def test_create_layers_identity_configuration_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'new';r=generate(p,width=540,height=960)
   self.assertEqual(r['options']['width'],540)
   for layer in ['domain','gameplay','presentation','services','bootstrap']:self.assertTrue(any((p/'assets/scripts'/layer).glob('*.ts')))
   pure=''.join(x.read_text() for layer in ['domain','gameplay'] for x in (p/'assets/scripts'/layer).glob('*.ts'));self.assertNotIn("from 'cc'",pure)
   self.assertEqual(json.loads((p/'settings/v2/packages/project.json').read_text())['general']['designResolution']['height'],960)
   self.assertEqual(audit_layers(p)['status'],'static_layer_screen_pass')
   f=p/'assets/scripts/domain/Counter.ts';f.write_text(f.read_text()+"\nimport { Node } from 'cc';\n")
   self.assertEqual(audit_layers(p)['status'],'findings')
   with self.assertRaises(ValueError):generate(p)
 def test_transform_reference_and_unsupported_never_drop_component(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);source=p/'owned.prefab'
   graph=[dict(__type__='cc.Prefab',data={'__id__':1}),dict(__type__='cc.Node',_name='Sample',_parent=None,_children=[],_components=[{'__id__':2}],_contentSize=dict(width=80,height=20),_anchorPoint=dict(x=.25,y=.5),_trs={'array':[4,5,0,0,0,0,1,2,2,1]},_opacity=128),dict(__type__='cc.Label',node={'__id__':1},_string='OWN')]
   source.write_text(json.dumps(graph));before=source.read_bytes();r=convert(source,p/'good','2.4.15')
   self.assertEqual(r['status'],'serialized_candidate_not_imported');out=json.loads((p/'good/Converted.prefab').read_text());self.assertEqual(out[1]['_lpos']['x'],4);self.assertEqual(out[3]['_contentSize']['width'],80);self.assertEqual(out[4]['_opacity'],128)
   graph.append(dict(__type__='UnknownScript'));source.write_text(json.dumps(graph));r=convert(source,p/'blocked','2.4.15');self.assertEqual(r['status'],'blocked_unsupported');self.assertFalse((p/'blocked/Converted.prefab').exists())
 def test_explicit_cocos_plan_and_legacy_unity_route(self):
  c=dispatch('plan_workflow',dict(mode='recover',source_engine='cocos',target_engine='cocos'))
  self.assertEqual(c['status'],'ok',c);self.assertNotIn('native',c['result']['required_dimensions']);self.assertTrue(any('05-Cocos' in x['reference'] for x in c['result']['steps']))
  u=dispatch('plan_workflow',dict(mode='recover',source_engine='cocos'));self.assertEqual(u['result']['target_engine'],'unity');self.assertIn('native',u['result']['required_dimensions'])
