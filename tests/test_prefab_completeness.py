import copy
import unittest

from monkey.prefab_completeness import audit


def fixture():
    sid = 'main:prefab'
    objects = [
        {'__type__': 'cc.Prefab', 'data': {'__id__': 1}},
        {'__type__': 'cc.Node', '_name': 'root', '_components': [
            {'__id__': 2}, {'__type__': 'Vendor.Gizmo', 'node': {'__id__': 1}, 'payload': 4},
            None, {'__id__': 99}, {'__id__': 2}, 'bad'], '_children': []},
        {'__type__': 'Vendor.Unknown', 'node': {'__id__': 1}, 'custom': {'x': 2}},
        {'__type__': 'cc.Node', '_name': 'detached', '_components': [], '_children': []},
    ]
    manifest = dict(sourceProfile='cocos-2.4.15-bundle', assets=[dict(sourceId=sid, kind='cc.Prefab',
                   document=dict(root=0, instances=objects))])
    ir = dict(nodes=[dict(sourceId=sid+'#1'), dict(sourceId=sid+'#3')], components=[])
    return manifest, ir


class PrefabCompletenessTests(unittest.TestCase):
    def test_unknown_dropped_component_and_invalid_edges_stay_in_denominator(self):
        manifest, ir = fixture()
        report = audit(manifest, ir, ['main:prefab'])
        self.assertEqual((report['sourceNodes'], report['sourceComponents'], report['unknown']), (2, 2, 2))
        self.assertEqual(report['mapped'], 2)
        self.assertEqual(report['unmapped'], 2)
        codes = {d['code'] for d in report['diagnostics']}
        self.assertTrue({'EMPTY_COMPONENT_REFERENCE', 'DANGLING_COMPONENT_REFERENCE',
                         'DUPLICATE_COMPONENT_REFERENCE', 'INVALID_COMPONENT_REFERENCE'} <= codes)
        self.assertTrue(any(c['sourceId'] == 'main:prefab#2' and c['irMapping'] == 'unmapped'
                            for c in report['components']))
        self.assertTrue(all(f['traceability'] == 'unverified' for c in report['components'] for f in c['fields']))

    def test_integer_id_is_exact_and_selection_diagnostics_are_explicit(self):
        manifest, ir = fixture()
        ir['components'] = [dict(sourceId='main:prefab#2', type='Vendor.Unknown')]
        report = audit(manifest, ir, ['main:prefab', 'main:prefab', 'missing'])
        self.assertEqual(next(c for c in report['components'] if c['sourceId'] == 'main:prefab#2')['irMapping'], 'mapped')
        codes = {d['code'] for d in report['diagnostics']}
        self.assertIn('DUPLICATE_SELECTED_SOURCE_ID', codes)
        self.assertIn('SELECTED_SOURCE_MISSING', codes)

    def test_input_is_unchanged_and_unsupported_profile_rejected(self):
        manifest, ir = fixture()
        before = copy.deepcopy((manifest, ir))
        audit(manifest, ir, ['main:prefab'])
        self.assertEqual((manifest, ir), before)
        rejected = audit(dict(sourceProfile='cocos-3.8.7-bundle', assets=[]), {}, [])
        self.assertEqual(rejected['status'], 'rejected')
        self.assertEqual(rejected['diagnostics'][0]['code'], 'UNSUPPORTED_SOURCE_PROFILE')

    def test_other_assets_ir_is_outside_selected_audit_scope(self):
        manifest, ir = fixture()
        other_id = 'main:other'
        manifest['assets'].append(dict(sourceId=other_id, kind='cc.Prefab', document=dict(root=0, instances=[
            {'__type__': 'cc.Prefab', 'data': {'__id__': 1}},
            {'__type__': 'cc.Node', '_components': [{ '__id__': 2 }], '_children': []},
            {'__type__': 'Custom.Other', 'node': {'__id__': 1}},
        ])))
        ir['nodes'].append(dict(sourceId=other_id+'#1'))
        ir['components'].append(dict(sourceId=other_id+'#2', type='Custom.Other'))
        report = audit(manifest, ir, ['main:prefab'])
        codes = {d['code'] for d in report['diagnostics']}
        self.assertEqual(report['sourceNodes'], 2)
        self.assertFalse({'IR_NODE_WITHOUT_SOURCE', 'IR_COMPONENT_WITHOUT_SOURCE'} & codes)

    def test_empty_or_non_list_selection_and_boolean_id_are_diagnosed(self):
        manifest, ir = fixture()
        empty = audit(manifest, ir, [])
        self.assertIn('EMPTY_SELECTION', {d['code'] for d in empty['diagnostics']})
        invalid = audit(manifest, ir, None)
        self.assertIn('INVALID_SELECTION', {d['code'] for d in invalid['diagnostics']})
        manifest['assets'][0]['document']['instances'][1]['_components'] = [{'__id__': True}]
        report = audit(manifest, ir, ['main:prefab'])
        self.assertIn('INVALID_COMPONENT_REFERENCE', {d['code'] for d in report['diagnostics']})

    def test_component_without_type_is_unknown(self):
        manifest, ir = fixture()
        manifest['assets'][0]['document']['instances'][1]['_components'] = [{'__id__': 4}]
        manifest['assets'][0]['document']['instances'].append({'payload': 'no declared type'})
        report = audit(manifest, ir, ['main:prefab'])
        missing_type = next(c for c in report['components'] if c['sourceId'] == 'main:prefab#4')
        self.assertIsNone(missing_type['sourceType'])
        self.assertFalse(missing_type['known'])
        self.assertEqual(report['unknown'], 1)

    def test_multilevel_integer_child_references_are_one_declaration_each(self):
        sid = 'main:tree'
        manifest = dict(sourceProfile='cocos-2.4.15-bundle', assets=[dict(sourceId=sid, kind='cc.Prefab',
            document=dict(root=0, instances=[
                {'__type__': 'cc.Prefab', 'data': {'__id__': 1}},
                {'__type__': 'cc.Node', '_name': 'root', '_children': [{'__id__': 2}], '_components': []},
                {'__type__': 'cc.Node', '_name': 'middle', '_parent': {'__id__': 1}, '_children': [{'__id__': 3}], '_components': []},
                {'__type__': 'cc.Node', '_name': 'leaf', '_parent': {'__id__': 2}, '_children': [], '_components': []},
            ]))])
        ir = dict(nodes=[dict(sourceId=f'{sid}#{i}') for i in (1, 2, 3)], components=[])
        report = audit(manifest, ir, [sid])
        self.assertEqual(report['sourceNodes'], 3)
        self.assertEqual(report['mapped'], 3)
        self.assertEqual(report['unmapped'], 0)
        self.assertNotIn('DUPLICATE_SOURCE_NODE_IDENTITY', {d['code'] for d in report['diagnostics']})

    def test_duplicate_asset_namespace_is_reported_as_distinct_source_declaration(self):
        manifest, ir = fixture()
        second = copy.deepcopy(manifest['assets'][0])
        second['document']['instances'][1]['_name'] = 'different declaration'
        manifest['assets'].append(second)
        report = audit(manifest, ir, ['main:prefab'])
        self.assertIn('DUPLICATE_SOURCE_ASSET_ID', {d['code'] for d in report['diagnostics']})

    def test_label_sprite_widget_button_fields_are_checked_from_source(self):
        sid = 'main:fields'
        root = {'__type__': 'cc.Node', '_components': [{'__id__': 2}, {'__id__': 3},
                    {'__id__': 4}, {'__id__': 5}], '_children': []}
        label = {'__type__': 'cc.Label', 'node': {'__id__': 1}, '_N$string': '源文案',
                 '_N$file': {'__uuid__': 'font-id'}, '_fontSize': 22, '_lineHeight': 25,
                 '_N$horizontalAlign': 2, '_verticalAlign': 1, '_styleFlags': 7,
                 '_spacingX': 3, '_isSystemFontUsed': False, '_overflow': 1, '_N$overflow': 1,
                 '_enableWrapText': False}
        sprite = {'__type__': 'cc.Sprite', 'node': {'__id__': 1}, '_spriteFrame': {'__uuid__': 'frame-id'},
                  '_type': 2, '_sizeMode': 1, '_isTrimmedMode': False}
        widget = {'__type__': 'cc.Widget', 'node': {'__id__': 1}, '_alignFlags': 9,
                  '_target': {'__id__': 1}, '_left': 1, '_bottom': 2, '_right': 3, '_top': 4,
                  '_isAbsLeft': False, '_isAbsBottom': True, '_isAbsRight': False, '_isAbsTop': True,
                  'alignMode': 2, '_horizontalCenter': 5, '_verticalCenter': 6,
                  '_isAbsHorizontalCenter': False, '_isAbsVerticalCenter': True}
        button = {'__type__': 'cc.Button', 'node': {'__id__': 1}, '_N$target': {'__id__': 1},
                  '_N$transition': 2, 'zoomScale': 1.4, 'duration': .3, 'interactable': False,
                  'clickEvents': [{'target': {'__id__': 1}, '_componentId': 'Game.Click',
                                   'handler': 'OnTap', 'customEventData': 'go'}],
                  '_N$pressedColor': {'r': 1, 'g': 2, 'b': 3, 'a': 4}}
        objects = [{'__type__': 'cc.Prefab'}, root, label, sprite, widget, button,
                   {'__type__': 'cc.SpriteFrame'}]
        manifest = dict(sourceProfile='cocos-2.4.15-bundle', assets=[dict(sourceId=sid, kind='cc.Prefab',
                        document=dict(root=0, instances=objects))])
        common = dict(node=sid+'#1', enabled=True, materials=[])
        ir = dict(nodes=[dict(sourceId=sid+'#1')], components=[
            dict(sourceId=sid+'#2', type='cc.Label', **common, text='源文案', font='main:font-id', fontSize=22,
                 lineHeight=25, horizontalAlign=2, verticalAlign=1, bold=True, italic=True, underline=True,
                 spacing=3, systemFont=False, overflow=1, wrap=False),
            dict(sourceId=sid+'#3', type='cc.Sprite', **common, spriteFrame='main:frame-id', mode=2, sizeMode=1, trim=False),
            dict(sourceId=sid+'#4', type='cc.Widget', **common, flags=9, target=sid+'#1', margins=[1,2,3,4],
                 absolute=[False,True,False,True], alignMode=2, center=[5,6], centerAbsolute=[False,True]),
            dict(sourceId=sid+'#5', type='cc.Button', **common, target=sid+'#1', transition=2, zoomScale=1.4,
                 duration=.3, interactable=False, events=[dict(target=sid+'#1', component='Game.Click',
                 handler='OnTap', customData='go')]),
        ])
        report = audit(manifest, ir, [sid])
        components = {c['sourceId']: c for c in report['components']}
        self.assertTrue(all(c['fieldCheck']['status'] == 'partial' for c in components.values()))
        button_fields = {f['sourceField']: f for f in components[sid+'#5']['fieldTraceability']}
        self.assertEqual(button_fields['_N$pressedColor']['status'], 'unmapped_semantics')
        self.assertEqual(report['semanticAccounting']['mismatch'], 0)

        ir['components'][0]['text'] = 'IR 被改动'
        changed = audit(manifest, ir, [sid])
        label_check = next(c for c in changed['components'] if c['sourceId'] == sid+'#2')['fieldCheck']
        self.assertEqual(next(x for x in label_check['checks'] if x['targetProperty'] == 'text')['status'], 'mismatch')
        self.assertEqual(label_check['status'], 'failed')
        self.assertIn('FIELD_IR_MISMATCH', {d['code'] for d in changed['diagnostics']})

    def test_alias_conflict_and_invalid_reference_fail_field_check(self):
        sid = 'main:bad-fields'
        label = {'__type__': 'cc.Label', 'node': {'__id__': 1}, '_overflow': 1, '_N$overflow': 2}
        sprite = {'__type__': 'cc.Sprite', 'node': {'__id__': 1}, '_spriteFrame': {'__id__': 99}}
        objects = [{'__type__': 'cc.Prefab'}, {'__type__': 'cc.Node', '_components': [{'__id__': 2}, {'__id__': 3}]}, label, sprite]
        manifest = dict(sourceProfile='cocos-2.4.15-bundle', assets=[dict(sourceId=sid, kind='cc.Prefab',
                        document=dict(root=0, instances=objects))])
        ir = dict(nodes=[dict(sourceId=sid+'#1')], components=[dict(sourceId=sid+'#2'), dict(sourceId=sid+'#3')])
        report = audit(manifest, ir, [sid])
        components = {c['sourceId']: c for c in report['components']}
        self.assertEqual(components[sid+'#2']['fieldCheck']['status'], 'failed')
        self.assertEqual(components[sid+'#2']['fieldCheck']['checks'][0]['code'], 'LABEL_OVERFLOW_ALIAS_CONFLICT')
        self.assertEqual(components[sid+'#3']['fieldCheck']['status'], 'failed')
        self.assertIn('FIELD_SOURCE_INVALID', {d['code'] for d in report['diagnostics']})

    def test_scroll_fields_with_ir_properties_are_checked_but_unrepresented_semantics_are_marked(self):
        sid = 'main:scroll'
        scroll = {'__type__': 'cc.ScrollView', 'node': {'__id__': 1}, '_N$content': {'__id__': 3},
                  'horizontal': False, 'vertical': True, 'brake': .7, 'bounceDuration': .4, 'inertia': False}
        objects = [{'__type__': 'cc.Prefab'}, {'__type__': 'cc.Node', '_components': [{'__id__': 2}]},
                   scroll, {'__type__': 'cc.Node'}]
        manifest = dict(sourceProfile='cocos-2.4.15-bundle', assets=[dict(sourceId=sid, kind='cc.Prefab',
                        document=dict(root=0, instances=objects))])
        ir = dict(nodes=[dict(sourceId=sid+'#1'), dict(sourceId=sid+'#3')], components=[
            dict(sourceId=sid+'#2', node=sid+'#1', enabled=True, materials=[], content=sid+'#3',
                 horizontal=False, vertical=True)])
        report = audit(manifest, ir, [sid])
        component = report['components'][0]
        statuses = {f['sourceField']: f['status'] for f in component['fieldTraceability']}
        self.assertEqual(component['fieldCheck']['status'], 'partial')
        self.assertEqual(statuses['brake'], 'unmapped_semantics')
        self.assertEqual(statuses['inertia'], 'unmapped_semantics')

    def test_valid_source_reference_with_wrong_ir_identity_fails(self):
        sid = 'main:reference'
        sprite = {'__type__': 'cc.Sprite', 'node': {'__id__': 1}, '_spriteFrame': {'__uuid__': 'frame'}}
        objects = [{'__type__': 'cc.Prefab'}, {'__type__': 'cc.Node', '_components': [{'__id__': 2}]}, sprite]
        manifest = dict(sourceProfile='cocos-2.4.15-bundle', assets=[dict(sourceId=sid, kind='cc.Prefab',
                        document=dict(root=0, instances=objects))])
        ir = dict(nodes=[dict(sourceId=sid+'#1')], components=[dict(sourceId=sid+'#2', type='cc.Sprite',
                 node=sid+'#1', enabled=True, materials=[], spriteFrame='main:wrong-frame',
                 mode=0, sizeMode=0, trim=True)])
        report = audit(manifest, ir, [sid])
        check = report['components'][0]['fieldCheck']
        frame = next(c for c in check['checks'] if c['targetProperty'] == 'spriteFrame')
        self.assertEqual(frame['status'], 'mismatch')
        self.assertEqual(frame['expected'], 'main:frame')
        self.assertEqual(check['status'], 'failed')

    def test_node_transform_layout_and_order_are_independently_checked(self):
        sid = 'main:nodes'
        root = {'__type__': 'cc.Node', '_name': 'root', '_parent': None, '_children': [{'__id__': 2}],
                '_active': False, '_trs': [2, 3, 4, .1, .2, .3, .9, 1.5, 2, 2.5],
                '_contentSize': {'width': 200, 'height': 100}, '_anchorPoint': {'x': .2, 'y': .8}, '_zIndex': 7}
        child = {'__type__': 'cc.Node', '_name': 'child', '_parent': {'__id__': 1}, '_children': [],
                 '_active': True, '_contentSize': {'width': 20, 'height': 30}, '_anchorPoint': {'x': .5, 'y': .5}}
        objects = [{'__type__': 'cc.Prefab'}, root, child]
        manifest = dict(sourceProfile='cocos-2.4.15-bundle', assets=[dict(sourceId=sid, kind='cc.Prefab',
                        document=dict(root=0, instances=objects))])
        ir = dict(nodes=[dict(sourceId=sid+'#1', name='root', parent=None, children=[sid+'#2'], active=False,
                              position=[2,3,4], rotation=[.1,.2,.3,.9], scale=[1.5,2,2.5], size=[200,100],
                              anchor=[.2,.8]),
                         dict(sourceId=sid+'#2', name='child', parent=sid+'#1', children=[], active=True,
                              size=[20,30], anchor=[.5,.5])], components=[])
        report = audit(manifest, ir, [sid])
        nodes = {n['sourceId']: n for n in report['nodes']}
        self.assertEqual(nodes[sid+'#1']['fieldCheck']['status'], 'partial')  # _zIndex is not represented
        self.assertIn('_zIndex', {f['sourceField'] for f in nodes[sid+'#1']['fieldTraceability']
                                  if f['status'] == 'unmapped_semantics'})
        self.assertEqual(nodes[sid+'#2']['fieldCheck']['status'], 'partial')
        self.assertEqual(set(nodes[sid+'#2']['fieldCheck']['unverifiedProperties']), {'position','rotation','scale'})
        self.assertEqual(report['nodeFieldAccounting']['mismatch'], 0)

        ir['nodes'][0]['position'] = [0, 0, 0]
        ir['nodes'][0].pop('children')
        changed = audit(manifest, ir, [sid])
        root_check = next(n for n in changed['nodes'] if n['sourceId'] == sid+'#1')['fieldCheck']
        self.assertEqual(root_check['status'], 'failed')
        self.assertEqual({x['targetProperty'] for x in root_check['checks'] if x['status'] == 'mismatch'},
                         {'position', 'children'})
        self.assertIn('NODE_IR_MISMATCH', {d['code'] for d in changed['diagnostics']})


if __name__ == '__main__':
    unittest.main()
