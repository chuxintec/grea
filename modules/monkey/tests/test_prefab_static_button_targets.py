import copy
import unittest
from monkey.prefab_static_button_targets import apply


class StaticButtonTargetTests(unittest.TestCase):
    def fixture(self):
        return dict(components=[dict(sourceId='b#button', node='b#owner', target='b#target',
                                     type='cc.Button', transition=1, convertible=True,
                                     staticButtonBinding=dict(renderReady=True, sourceFields={'target': 'authored'})),
                                dict(sourceId='b#sprite', node='b#target', type='cc.Sprite',
                                     convertible=False)], diagnostics=[])

    def test_missing_native_renderer_is_explicit_handoff_without_source_rewrite(self):
        plan = self.fixture()
        original = copy.deepcopy(plan['components'])
        rows = apply(plan)
        self.assertEqual(rows[0]['targetRendererSourceIds'], ['b#sprite'])
        self.assertFalse(plan['components'][0]['convertible'])
        self.assertEqual(plan['components'][0]['target'], original[0]['target'])
        self.assertEqual(plan['components'][0]['staticButtonBinding'], original[0]['staticButtonBinding'])
        self.assertEqual(plan['components'][1], original[1])
        self.assertEqual(len(plan['components']), 2)
        self.assertEqual(plan['diagnostics'][0]['code'], 'BUTTON_TARGET_RENDERER_HANDOFF')
        self.assertEqual(apply(plan), [])

    def test_ready_renderer_grouping_target_and_noncolor_transitions_are_preserved(self):
        for change in ('ready', 'grouping', 'scale', 'none'):
            with self.subTest(change=change):
                plan = self.fixture()
                if change == 'ready': plan['components'][1]['convertible'] = True
                if change == 'grouping': plan['components'].pop()
                if change == 'scale': plan['components'][0]['transition'] = 3
                if change == 'none': plan['components'][0]['transition'] = 0
                before = copy.deepcopy(plan)
                self.assertEqual(apply(plan), [])
                self.assertEqual(plan, before)
