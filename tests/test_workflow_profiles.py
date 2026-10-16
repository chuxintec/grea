import unittest
from grea.application import dispatch


class WorkflowProfiles(unittest.TestCase):
    def plan(self, mode, engine, **kwargs):
        response = dispatch('plan_workflow', dict(mode=mode, source_engine=engine, **kwargs))
        self.assertEqual(response['status'], 'ok', response)
        return response['result']

    def test_non_unity_sources_never_use_assetripper(self):
        for engine in ('cocos', 'laya', 'other'):
            plan = self.plan('recover', engine)
            tools = {tool for step in plan['steps'] for tool in step['tool_ids']}
            self.assertNotIn('assetripper', tools)
            self.assertIn('native', plan['required_dimensions'])
        self.assertIn('assetripper', {t for s in self.plan('recover', 'unity')['steps'] for t in s['tool_ids']})

    def test_unknown_and_read_only_intents_do_not_plan_implementation(self):
        for mode in ('assess', 'evidence'):
            plan = self.plan(mode, 'cocos', source_format='wxapkg', engine_version='3.4.1')
            self.assertEqual(plan['required_dimensions'], ['identity'])
            self.assertFalse(any(step['phase'] == 'implementation' for step in plan['steps']))
        plan = self.plan('recover', 'unknown')
        self.assertEqual(plan['required_dimensions'], ['identity'])
        self.assertEqual(plan['next_decision'], 'identify_source_engine')

    def test_source_container_and_target_audit_are_distinct(self):
        plan = self.plan('recover', 'cocos', source_format='wxapkg', engine_version='2.4.15', target_platform='Windows')
        self.assertNotIn('unpack_xapk', {t for s in plan['steps'] for t in s['tool_ids']})
        self.assertEqual(plan['task']['target_platform'], 'Windows')
        self.assertIn('native', self.plan('refactor', 'laya')['required_dimensions'])
        self.assertEqual(self.plan('fix', 'unity')['required_dimensions'], ['rules', 'runtime'])


if __name__ == '__main__': unittest.main()
