import copy
import unittest
from monkey.normalize import component_ir, expand_nodes, node_ir, quarantine_graphs
from monkey.sources.compiled import ParseError


class PrefabGraphSourceEdgeTests(unittest.TestCase):
    def test_empty_family_preserves_component_without_inventing_a_font(self):
        empty, gaps = component_ir('b:p', 2, {'__type__': 'cc.Label', '_N$fontFamily': ''},
                                   source_profile='cocos-2.4.15-bundle')
        self.assertEqual((empty['fontFamily'], empty['sourceFontFamily']), ('Arial', ''))
        self.assertEqual(empty['fontFamilyEvidence'], 'creator-empty-system-family-Arial')
        for family in ('   ',):
            source = dict(__type__='cc.Label', node={'__id__':1}, _N_string='text', _N_fontFamily=family)
            source['_N$fontFamily']=source.pop('_N_fontFamily')
            source['_N$string']=source.pop('_N_string')
            original = copy.deepcopy(source)
            label, gaps = component_ir('b:p', 2, source, source_profile='cocos-2.4.15-bundle')
            self.assertEqual(label['text'], 'text')
            self.assertEqual(label['fontFamily'], family)
            self.assertEqual(label['fontFamilyEvidence'], 'serialized-empty-unresolved')
            self.assertFalse(label['supported'])
            self.assertTrue(any('font unresolved' in gap for gap in gaps))
            from monkey.prefab_static_presentation import _font_mapping
            # Later completion must not promote a preserved unknown family
            # using an unrelated/default target font declaration.
            promoted = dict(label, font='target-font', nativeEffectiveFontBinding={'proved': True})
            self.assertEqual(_font_mapping(promoted, {}),
                             (None, 'source_explicit_empty_font_family_unresolved'))
            self.assertEqual(source, original)
        with self.assertRaises(ParseError):
            component_ir('b:p', 2, {'__type__':'cc.Label', '_N$fontFamily':42})
        with self.assertRaises(ParseError):
            component_ir('b:p', 2, {'__type__':'cc.Label', '_N$fontFamily':'', 'fontFamily':'Arial'})

    def test_inline_prefab_data_and_children_keep_source_paths_and_input_bytes(self):
        source = [{'__type__':'cc.Prefab', 'data':{'__type__':'cc.Node', '_name':'root',
                   '_children':[{'__type__':'cc.Node', '_name':'child'}]}}]
        original = copy.deepcopy(source)
        expanded = list(expand_nodes(source, 'b:p'))
        self.assertEqual([x[0] for x in expanded], [0, '0/data', '0/data/_children/0'])
        ir = dict(nodes=[node_ir('b:p', index, obj)[0] for index, obj in expanded if obj['__type__']=='cc.Node'],
                  components=[], prefabInstances=[], diagnostics=[])
        self.assertEqual(quarantine_graphs(ir), {})
        self.assertEqual(ir['nodes'][1]['parent'], 'b:p#0/data')
        from monkey.prefab_static_fields import extract_static_fields
        from monkey.prefab_completeness import audit
        manifest = dict(sourceProfile='cocos-2.4.15-bundle', assets=[dict(
            sourceId='b:p', kind='cc.Prefab', document=dict(instances=source, root=0))])
        self.assertEqual(extract_static_fields(manifest, ir)['components'], [])
        report = audit(manifest, ir, ['b:p'])
        self.assertEqual({row['sourceId'] for row in report['nodes']},
                         {'b:p#0/data', 'b:p#0/data/_children/0'})
        self.assertFalse(any(row['code'] == 'IR_NODE_WITHOUT_SOURCE' for row in report['diagnostics']))
        self.assertEqual(source, original)
