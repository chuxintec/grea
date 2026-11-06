import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from monkey.prefab_static_layout_continuation import prepare,StaticLayoutContinuationError
from test_prefab_static_layout_completion import _plan_and_manifest


class LayoutContinuationTests(unittest.TestCase):
    def fixture(self):
        plan,manifest=_plan_and_manifest()
        plan['components']=plan['components'][:2]
        manifest['sourceVersion']='2.4.15'
        return plan,dict(components=copy.deepcopy(plan['components'])),manifest

    def test_source_identity_and_engine_evidence_are_required(self):
        plan,ir,manifest=self.fixture()
        with tempfile.TemporaryDirectory()as stage:
            with self.assertRaisesRegex(StaticLayoutContinuationError,'ENGINE_VERSION_UNPROVEN'):
                prepare(plan,ir,manifest,Path(stage).resolve())
            ir['components'].pop()
            with self.assertRaisesRegex(StaticLayoutContinuationError,'PLAN_IR_IDENTITY_MISMATCH'):
                prepare(plan,ir,manifest,Path(stage).resolve())

    def test_preserves_two_ordered_slots_without_modifying_source_plan(self):
        plan,ir,manifest=self.fixture();before=copy.deepcopy(plan)
        with tempfile.TemporaryDirectory()as stage,patch('monkey.prefab_static_layout_continuation._engine_evidence',return_value=[]):
            result=prepare(plan,ir,manifest,Path(stage).resolve())
        self.assertEqual(result['summary']['preparedComponents'],2)
        self.assertEqual(plan,before)
        slots=result['plan']['layoutCompletion']['nodes'][0]['layouts']
        self.assertEqual([s['componentOrder']for s in slots],[0,1])
        for c in result['plan']['components']:
            self.assertFalse(c['convertible'])
            self.assertEqual(c['nativeSlotId'],c['sourceId'])

    def test_unknown_ancestor_context_fails_closed(self):
        plan,manifest=_plan_and_manifest();manifest['sourceVersion']='2.4.15'
        plan['components']=plan['components'][-1:]
        ir=dict(components=copy.deepcopy(plan['components']))
        with tempfile.TemporaryDirectory()as stage,patch('monkey.prefab_static_layout_continuation._engine_evidence',return_value=[]):
            result=prepare(plan,ir,manifest,Path(stage).resolve())
        self.assertEqual(result['summary']['preparedComponents'],0)
        self.assertEqual(result['plan']['staticLayoutContinuation']['gaps'][0]['code'],'WIDGET_TARGET_CONTEXT_MISSING')
