import unittest
from grea.integrations import beaver,beaver_operations as o
class QARuntimeTests(unittest.TestCase):
    def request(self,name='qa.launch',**extra):
        return dict(schema_version=1,operation=name,options=dict(project='example',build='build1',profile='stable',**{'expected-owner':'a'*64},**extra),timeout_seconds=90)
    def test_version_and_no_arbitrary_environment_or_path_ids(self):
        q=self.request();o.validate_provider_version(q,beaver.P0_FIX14_VERSION);o.validate_provider_version(q,beaver.P0_FIX15_VERSION);o.validate_provider_version(q,beaver.P0_FIX16_VERSION);o.validate_provider_version(q,beaver.P0_FIX17_VERSION)
        with self.assertRaises(ValueError):o.validate_provider_version(q,beaver.P0_FIX12_VERSION)
        for extra in [{'project':'/tmp/App'},{'profile':'../save'},{'env':{}},{'cwd':'/tmp'},{'duration':True}]:
            x=self.request();x['options'].update(extra)
            with self.assertRaises(ValueError):o.validate(x)
    def test_launch_has_no_out_and_default_budget_guard(self):
        q=self.request();argv=o.argv_for(q,'/tmp/receipt');self.assertNotIn('--out',argv)
        with self.assertRaises(ValueError):o.validate(dict(q,timeout_seconds=30))
        q['options']['duration']=20;o.validate(dict(q,timeout_seconds=30))
    def test_collect_requires_run_and_controlled_output(self):
        q=self.request('qa.collect')
        with self.assertRaises(ValueError):o.validate(q)
        q['options']['run']='run1';argv=o.argv_for(q,'/tmp/receipt');self.assertIn('--out',argv)
