import unittest,copy
from monkey.prefab_material_pipeline import identity_text_component
class IdentityTextMaterialTests(unittest.TestCase):
 def test_only_proven_identity_transform_is_lowered(self):
  c={'type':'cc.Label','materials':['source:material']};p={'spec':{'materialSourceId':'source:material','properties':dict(brightness=1.,constrast=1.,gray=0.,saturation=1.,silhouette=[1.,1.,1.,1.])}}
  self.assertTrue(identity_text_component(c,p,lambda x:x))
  for key in ['brightness','constrast','gray','saturation']:
   bad=copy.deepcopy(p);bad['spec']['properties'][key]=.5;self.assertFalse(identity_text_component(c,bad,lambda x:x))
  bad=copy.deepcopy(p);bad['spec']['properties']['silhouette'][-1]=.5;self.assertFalse(identity_text_component(c,bad,lambda x:x))
  self.assertFalse(identity_text_component(dict(c,materials=['different']),p,lambda x:x))
