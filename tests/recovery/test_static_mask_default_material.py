"""Modeled default-material resolution; real engine/file pins are replayed privately."""
import copy
import hashlib
import json
import unittest
import pytest
from pathlib import Path
from unittest.mock import patch

from grea.recovery import prefab_static_mask_continuation as continuation
from grea.recovery.prefab_static_mask_sort import StaticMaskSortError
from . import test_prefab_static_mask_continuation as mask_fixture


class DefaultMaskMaterialTests(unittest.TestCase):
    def fixture(self):
        plan, manifest, _, temp = mask_fixture.StaticMaskContinuationTests.fixture(self)
        for asset in manifest['assets']:
            if asset['kind'] == 'cc.Material':
                asset['sourceId'] = 'internal:' + asset['sourceId'].partition(':')[2]
                asset['bundle'] = 'internal'
            if asset['kind'] == 'cc.Prefab':
                for raw in asset['document']['instances']:
                    if isinstance(raw, dict) and raw.get('__type__') == 'cc.Mask':
                        raw.pop('_materials')
        for queue in plan['staticSortQueue']:
            for event in queue['masks']:
                event['sourceFieldsJson'] = json.dumps(event['sourceFields'], ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        self.reseal(plan, manifest)
        # Controlled source-engine pin for this unit model, never a native or
        # actual Cocos engine proof. Production pins remain constant.
        engine = Path(temp.name) / 'engine-model.js'
        engine.write_bytes(b'unit-model-default-mask-material')
        engine_sha = hashlib.sha256(engine.read_bytes()).hexdigest()
        patched = patch.object(continuation, 'SOURCE_ENGINE_SHA256', engine_sha)
        patched.start(); self.addCleanup(patched.stop)
        evidence = {'sourceVersion': '2.4.15', 'files': [{'logicalPath': continuation.SOURCE_ENGINE_PATH,
            'path': str(engine), 'sha256': engine_sha, 'originUrl': continuation.SOURCE_ENGINE_URL}]}
        return plan, manifest, evidence

    @staticmethod
    def reseal(plan, manifest):
        raw = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        Path(plan['sourceManifestPath']).write_bytes(raw)
        plan['sourceManifestSha256'] = hashlib.sha256(raw).hexdigest()

    def test_omitted_material_requires_engine_bytes_and_resolves_exact_frozen_builtin(self):
        plan, manifest, evidence = self.fixture()
        with self.assertRaisesRegex(StaticMaskSortError, 'verified source engine'):
            continuation.build_contract(plan, manifest)
        contract = continuation.build_contract(plan, manifest, source_engine_evidence=evidence)
        self.assertEqual(len(contract['masks']), len(plan['components']))
        for row in contract['masks']:
            self.assertEqual(row['sourceMaterialResolution'], 'engine-default-builtin')
            self.assertTrue(row['sourceMaterialId'].startswith('internal:'))
            self.assertNotIn('_materials', row['sourceFields'])
            self.assertEqual(row['sourceMaterialResolverSha256'], evidence['files'][0]['sha256'])
        plan['staticMasks'] = contract
        continuation.validate_export_contract(plan)
        plan['staticMasks']['masks'][0]['sourceMaterialId'] = 'internal:wrong'
        with self.assertRaisesRegex(continuation.StaticMaskContinuationError, 'SOURCE_MATERIAL_PROOF'):
            continuation.validate_export_contract(plan)

    def test_removing_resolver_or_inventing_serialized_uuid_cannot_skip_original_source(self):
        plan, manifest, evidence = self.fixture()
        contract = continuation.build_contract(plan, manifest, source_engine_evidence=evidence)
        for variant in ('remove-resolver', 'invent-material-reference', 'wrong-origin'):
            candidate = copy.deepcopy(plan); candidate['staticMasks'] = copy.deepcopy(contract)
            row = candidate['staticMasks']['masks'][0]
            if variant == 'wrong-origin':
                row['sourceOriginId'] = 'not-the-source#1'
            else:
                for key in ('sourceMaterialResolution', 'sourceMaterialResolverPath', 'sourceMaterialResolverSha256'):
                    row.pop(key)
                row['sourceMaterialId'] = 'internal:invented'; row['resolvedSourceMaterialId'] = 'internal:invented'
                if variant == 'invent-material-reference':
                    row['sourceFields']['_materials'] = [{'__uuid__': 'invented'}]
                    row['sourceFieldsJson'] = json.dumps(row['sourceFields'], ensure_ascii=False, sort_keys=True, separators=(',', ':'))
            with self.assertRaisesRegex(continuation.StaticMaskContinuationError, 'SOURCE_MATERIAL_PROOF'):
                continuation.validate_export_contract(candidate)

    def test_wrong_engine_bytes_or_ambiguous_builtin_cannot_grant_default(self):
        plan, manifest, evidence = self.fixture()
        Path(evidence['files'][0]['path']).write_bytes(b'tampered')
        with self.assertRaisesRegex(continuation.StaticMaskContinuationError, 'engine source bytes'):
            continuation.build_contract(plan, manifest, source_engine_evidence=evidence)
        plan, manifest, evidence = self.fixture()
        material = next(a for a in manifest['assets'] if a['kind'] == 'cc.Material')
        extra = copy.deepcopy(material); extra['sourceId'] = 'internal:another-builtin'
        manifest['assets'].append(extra); self.reseal(plan, manifest)
        with self.assertRaisesRegex(StaticMaskSortError, 'absent or ambiguous'):
            continuation.build_contract(plan, manifest, source_engine_evidence=evidence)

    def test_explicit_missing_uuid_is_never_replaced_by_engine_builtin(self):
        plan, manifest, evidence = self.fixture()
        for asset in manifest['assets']:
            if asset['kind'] == 'cc.Prefab':
                for row in asset['document']['instances']:
                    if isinstance(row, dict) and row.get('__type__') == 'cc.Mask':
                        row['_materials'] = [{'__uuid__': 'not-present'}]
        self.reseal(plan, manifest)
        with self.assertRaisesRegex(StaticMaskSortError, 'absent or ambiguous'):
            continuation.build_contract(plan, manifest, source_engine_evidence=evidence)


def test_inline_prefab_mask_source_paths_preserve_raw_fields_and_refuse_alias_indexes():
    from grea.recovery.prefab_static_mask_sort import _raw_component
    raw={'__type__':'cc.Mask','_type':0}
    child_raw={'__type__':'cc.Mask','_type':2,'_spriteFrame':{'__uuid__':'actual-frame'}}
    manifest={'assets':[{'sourceId':'fixture:a','kind':'cc.Prefab','document':{'instances':[
        {'__type__':'cc.Prefab','data':{'__type__':'cc.Node','_components':[raw],
            '_children':[{'__type__':'cc.Node','_components':[child_raw]}]}}]}}]}
    before=copy.deepcopy(manifest)
    assert _raw_component(manifest,'fixture:a#0/data/components/0')==raw
    assert _raw_component(manifest,'fixture:a#0/data/_children/0/components/0')==child_raw
    assert manifest==before
    for suffix in ('-1/components/0','0/data/components/-1','0/datax/components/0'):
        with pytest.raises(StaticMaskSortError):
            _raw_component(manifest,'fixture:a#'+suffix)
