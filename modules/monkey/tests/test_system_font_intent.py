import tempfile
import unittest
from pathlib import Path
from fixtures import fixture, normal, PREFAB
from monkey.io import write_json
from monkey.sources.bundle import inspect
from monkey.sources.compiled import ParseError
from monkey.normalize import component_ir, normalize
from monkey.targets import cocos


class SystemFontIntentTests(unittest.TestCase):
    def test_family_aliases_are_preserved_and_conflicts_rejected(self):
        item, _ = component_ir('source', 2, {'__type__': 'cc.Label', 'fontFamily': 'Example Family'})
        self.assertEqual(item['fontFamily'], 'Example Family')
        self.assertEqual(item['fontFamilyEvidence'], 'serialized')
        with self.assertRaises(ParseError):
            component_ir('source', 2, {'__type__': 'cc.Label', 'fontFamily': 'A', '_N$fontFamily': 'B'})

    def test_creator_keeps_source_system_font_instead_of_requiring_a_packed_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            config = fixture(root / 'source')
            write_json(config.parent / 'import' / PREFAB[:2] / (PREFAB + '.a.json'), normal([
                {'__type__': 'cc.Prefab', 'data': {'__id__': 1}},
                {'__type__': 'cc.Node', '_name': 'Text', '_children': [], '_components': [{'__id__': 2}],
                 '_contentSize': {'width': 200, 'height': 100}},
                {'__type__': 'cc.Label', 'node': {'__id__': 1}, '_string': '中文', '_isSystemFontUsed': True},
            ]))
            inspect(config, [2], root / 'inspect')
            normalize(root / 'inspect/source-manifest.json', root / 'ir')
            result = cocos.plan(root / 'ir/ir.json', 'system-font', root / 'plan')
            label = result['components'][0]
            self.assertTrue(label['convertible'])
            self.assertTrue(label['nativeSystemFont'])
            self.assertEqual(label['fontFamily'], 'Arial')
            self.assertIsNone(label['font'])
            self.assertTrue(any(d['code'] == 'SYSTEM_FONT_PLATFORM_UNVERIFIED' for d in result['diagnostics']))
