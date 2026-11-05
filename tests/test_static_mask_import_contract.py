"""Typed saved-instruction admission is distinct from original-byte export proof."""
import copy
import unittest

import test_prefab_static_mask_export_contract as export_fixture
from src.monkey.prefab_static_mask_continuation import StaticMaskContinuationError, validate_import_contract


class StaticMaskImportContractTests(unittest.TestCase):
    def fixture(self):
        case = export_fixture.StaticMaskExportContractTests()
        plan, _ = case.fixture()
        self.addCleanup(case.doCleanups)
        plan.pop('sourceManifestPath')
        plan['staticMasksPresent'] = True
        plan['staticSortQueue'] = None
        components = {row['sourceId']: row for row in plan['components']}
        for index, row in enumerate(plan['staticMasks']['masks']):
            row['nativeId'] = 'unit-mask-' + str(index)
            row['sourceQueueDisposition'] = ('outside-static-sort-queue-scope' if row['sourceActive'] and row['enabled']
                else 'outside-active-render-flow-inactive-ancestor' if not row['sourceActive']
                else 'outside-active-render-flow-disabled-mask')
            components[row['sourceId']].update({key: row[key] for key in ('nativeId', 'enabled', 'maskType', 'inverted')})
            if row['maskType'] == 2:
                row.update(unityMaskShaderPath='Assets/UnitMask.shader', unityMaskShaderSha256='1'*64,
                           unityMaskMaterialGuid='2'*32, unityMaskMaterialPath='Assets/UnitMask.mat')
        return plan

    def test_no_queue_no_source_path_admits_only_a_typed_declaration(self):
        result = validate_import_contract(self.fixture())
        self.assertEqual(result['status'], 'saved-instruction-declaration')
        self.assertEqual(result['sourceMaskCount'], 6)
        self.assertIs(result['sourceBytesRevalidated'], False)
        self.assertIs(result['nativeClippingValidated'], False)

    def test_corrupt_component_queue_material_and_default_declarations_are_refused(self):
        base = self.fixture()
        for mutation in ('denominator', 'native-id', 'node', 'enabled-type', 'mask-type', 'threshold',
                         'raw-fields', 'raw-json', 'material-reference', 'resolver', 'default-scope',
                         'source-pin', 'source-engine', 'marker', 'queue-event', 'duplicate-node'):
            plan = copy.deepcopy(base)
            row = plan['staticMasks']['masks'][0]
            if mutation == 'denominator': plan['staticMasks']['masks'].pop()
            elif mutation == 'native-id': row['nativeId'] = 'wrong'
            elif mutation == 'node': row['node'] = 'wrong'
            elif mutation == 'enabled-type': row['enabled'] = int(row['enabled'])
            elif mutation == 'mask-type': row['maskType'] = str(row['maskType'])
            elif mutation == 'threshold': row['alphaThreshold'] = float('nan')
            elif mutation == 'raw-fields': row['sourceFields']['__type__'] = 'cc.Sprite'
            elif mutation == 'raw-json': row['sourceFieldsJson'] = '{}'
            elif mutation == 'material-reference': row['sourceMaterialId'] = 'internal:invented'
            elif mutation == 'resolver': row['sourceMaterialResolverPath'] = 'invented'
            elif mutation == 'default-scope': plan['staticMasks']['sourceDefaults'][0]['sourceIds'].pop()
            elif mutation == 'source-pin': plan['staticMasks']['sourceManifestSha256'] = '0'*64
            elif mutation == 'source-engine': plan['staticMasks']['sourceEngine']['sha256'] = '0'*64
            elif mutation == 'marker': plan['staticMasksPresent'] = False
            elif mutation == 'queue-event': plan['staticSortQueue'] = [{'masks': [{'sourceId': row['sourceId']}]}]
            elif mutation == 'duplicate-node': plan['nodes'].append(copy.deepcopy(plan['nodes'][0]))
            with self.subTest(mutation=mutation), self.assertRaises(StaticMaskContinuationError):
                validate_import_contract(plan)
