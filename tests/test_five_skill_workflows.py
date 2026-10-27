import unittest
from pathlib import Path
from grea.common import package_root
from grea.application import dispatch


class FiveSkillWorkflowTests(unittest.TestCase):
    ROUTES = {
        'research': ('grea-research', 'research'),
        'assess': ('grea-research', 'research'),
        'evidence': ('grea-recover', 'recover'),
        'recover': ('grea-recover', 'recover'),
        'port': ('grea-recover', 'recover'),
        'fix': ('grea-develop', 'develop'),
        'refactor': ('grea-develop', 'develop'),
        'performance': ('grea-develop', 'develop'),
        'reskin': ('grea-develop', 'develop'),
        'evolve': ('grea-develop', 'develop'),
        'feature': ('grea-develop', 'develop'),
        'tuning': ('grea-develop', 'develop'),
        'prototype': ('grea-develop', 'develop'),
        'operate': ('grea-develop', 'develop'),
        'deliver': ('grea-release', 'release'),
        'maintain': ('grea', 'orchestration'),
    }

    def plan(self, mode, **kwargs):
        response = dispatch('plan_workflow', dict(mode=mode, **kwargs))
        self.assertEqual(response['status'], 'ok', response)
        return response['result']

    def test_all_existing_modes_gain_additive_skill_route(self):
        for mode, (skill, stage) in self.ROUTES.items():
            with self.subTest(mode=mode):
                result = self.plan(mode)
                self.assertEqual(result['primary_skill'], skill)
                self.assertEqual(result['stage'], stage)
                self.assertEqual(result['entrypoint'], skill + '/SKILL.md')
                self.assertTrue((package_root() / 'plugin/skills' / result['entrypoint']).is_file())
                for step in result['steps']:
                    self.assertTrue(Path(step['reference']).is_file(), step)
                for field in ('mode', 'title', 'steps', 'executed', 'task'):
                    self.assertIn(field, result)

    def test_recovery_business_continuation_routes_to_develop(self):
        for mode in ('recover', 'port'):
            with self.subTest(mode=mode):
                result = self.plan(mode, source_engine='cocos')
                route = result['initial_project_pipeline']['business_continuation_route']
                self.assertEqual(route, {
                    'primary_skill': 'grea-develop',
                    'stage': 'develop',
                    'entrypoint': 'grea-develop/SKILL.md',
                })
                self.assertIn('business_continuation', result['initial_project_pipeline']['stages'])

    def test_delivery_keeps_release_route_for_non_unity_targets_and_go_backend(self):
        cases = (
            {'target_engine': 'cocos'},
            {'target_engine': 'none', 'backend': 'go'},
            {'target_engine': 'cocos', 'backend': 'go'},
        )
        for kwargs in cases:
            with self.subTest(**kwargs):
                result = self.plan('deliver', **kwargs)
                self.assertEqual(result['primary_skill'], 'grea-release')
                self.assertEqual(result['stage'], 'release')
                self.assertIn('platform', result['required_dimensions'])
                self.assertNotIn('initial_project_pipeline', result)
                names = {step['reference'].rsplit('/', 1)[-1] for step in result['steps']}
                self.assertNotIn('Cocos工程与迁移.md', names)
                self.assertNotIn('Go六服与事务.md', names)
                tools = {tool for step in result['steps'] for tool in step['tool_ids']}
                self.assertTrue(tools.isdisjoint({'cocos_project', 'cocos_convert', 'server_go_project'}))

    def test_evidence_only_never_enters_implementation_for_other_targets(self):
        for target in ('unity', 'cocos', 'none'):
            with self.subTest(target=target):
                result = self.plan('evidence', target_engine=target, backend='go', source_format='xapk')
                self.assertEqual(result['primary_skill'], 'grea-recover')
                self.assertNotIn('initial_project_pipeline', result)
                self.assertTrue(all(s['phase'] == 'source_evidence' for s in result['steps']))
                self.assertIn('unpack_xapk', result['steps'][0]['tool_ids'])
                self.assertTrue(all(not s['executed'] for s in result['steps']))


if __name__ == '__main__':
    unittest.main()
