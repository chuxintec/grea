import unittest
from monkey.sources.cocos38_graphs import graph
from monkey.sources.compiled import ParseError


def asset(objects):return dict(sourceId='main:original',document=dict(root=0,instances=objects))
def ref(index):return {'__id__':index}
def value(kind,*values):return {'__value_type__':kind,'values':list(values)}


class Creator38GraphTests(unittest.TestCase):
    def test_distinct_node_ui_renderer_and_opacity_values_are_projected(self):
        a=asset([{'__type__':'cc.Prefab','data':ref(1)},{'__type__':'cc.Node','_name':'actual','_lpos':value(1,17,-22,0),'_lscale':value(1,2,3,1),'_components':[
            {'__type__':'cc.UITransform','node':ref(1),'_anchorPoint':value(0,.25,.75)},
            {'__type__':'cc.UIOpacity','node':ref(1),'_opacity':123},
            {'__type__':'cc.Sprite','node':ref(1),'_color':value(4,0xff342211),'_spriteFrame':{'__uuid__':'original-frame'}}]}])
        nodes,components,gaps=graph(a);n=nodes[0];c=components[0]
        self.assertEqual(n['size'],[100,100]);self.assertEqual(n['anchor'],[.25,.75]);self.assertEqual(n['position'],[17,-22,0]);self.assertEqual(n['scale'],[2,3,1]);self.assertEqual(n['color'],[17,34,52,255]);self.assertEqual(n['opacity'],123)
        self.assertEqual(n['sourceLayer'],1<<30);self.assertEqual(c['sizeMode'],1);self.assertEqual(n['components'],[c['sourceId']]);self.assertEqual(len(n['sourceGeometryComponents']),2)

    def test_omitted_label_defaults_use_v387_not_v24_and_outline_is_named(self):
        a=asset([{'__type__':'cc.Node','_components':[{'__type__':'cc.UITransform','node':ref(0)},{'__type__':'cc.Label','node':ref(0),'_enableOutline':True}]}])
        nodes,components,gaps=graph(a);label,outline=components
        self.assertEqual(label['text'],'label');self.assertEqual(label['horizontalAlign'],1);self.assertEqual(label['verticalAlign'],1);self.assertEqual(outline['width'],2);self.assertEqual(outline['outlineColor'],[0,0,0,255])
        self.assertEqual(nodes[0]['rotation'],[0,0,0,1]);self.assertEqual(nodes[0]['name'],'New Node')

    def test_nested_prefab_instances_and_ambiguous_ui_do_not_emit_guessed_geometry(self):
        for obj in [dict(__type__='cc.Node',_prefab=dict(__type__='cc.PrefabInfo',instance=ref(8))),dict(__type__='cc.Node',_components=[dict(__type__='cc.UITransform',node=ref(0)),dict(__type__='cc.UITransform',node=ref(0))])]:
            with self.assertRaises(ParseError):graph(asset([obj]))
        for raw in (value(3,10,20,0),{'unrecognized':99}):
            with self.assertRaisesRegex(ParseError,'VALUE_TYPE'):graph(asset([dict(__type__='cc.Node',_lpos=raw)]))
        with self.assertRaisesRegex(ParseError,'UI_TRANSFORM_DISABLED'):graph(asset([dict(__type__='cc.Node',_components=[dict(__type__='cc.UITransform',node=ref(0),_enabled=False)])]))

    def test_wrong_owner_is_rejected_and_widget_uses_native_semantic_fields(self):
        with self.assertRaisesRegex(ParseError,'COMPONENT_OWNER'):
            graph(asset([dict(__type__='cc.Node',_components=[dict(__type__='cc.Sprite',node=ref(9))])]))
        nodes,components,gaps=graph(asset([dict(__type__='cc.Node',_components=[dict(__type__='cc.Widget',node=ref(0),_alignFlags=45)])]))
        self.assertEqual(components[0]['flags'],45);self.assertEqual(components[0]['alignMode'],1)
        self.assertEqual(components[0]['center'],[0,0]);self.assertFalse(gaps)

    def test_asset_root_closure_keeps_detached_records_in_evidence_only(self):
        import copy
        data=asset([dict(__type__='cc.Prefab',data=ref(1)),
            dict(__type__='cc.Node',_children=[ref(2)]),dict(__type__='cc.Node',_parent=ref(1)),
            dict(__type__='cc.Node',_name='Detached',_parent=ref(1))])
        before=copy.deepcopy(data);nodes,components,gaps=graph(data)
        self.assertEqual([n['sourceId'].rsplit('#',1)[1]for n in nodes],['1','2'])
        self.assertTrue(any('Detached serialized node'in g['message']for g in gaps));self.assertEqual(data,before)


if __name__=='__main__':unittest.main()
