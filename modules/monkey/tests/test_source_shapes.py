import tempfile
import unittest
from pathlib import Path
from monkey.io import write_json,read,load
from monkey.sources.project import catalog,inspect
from monkey.sources.bundle import Bundle
from monkey.sources.compiled import ParseError
from monkey.normalize import normalize
from monkey.targets import unity
from fixtures import fixture


class SourceShapeTests(unittest.TestCase):
    def test_scene_inline_children_null_events_and_bad_graph_isolation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();source=root/'project';(source/'assets').mkdir(parents=True)
            write_json(source/'project.json',dict(id='shapes',version='2.4.15'))
            for name,uid,objects in [
                ('view.fire','00000000-0000-0000-0000-000000000001',[
                    dict(__type__='cc.SceneAsset',scene={'__id__':1}),
                    dict(__type__='cc.Scene',_name='Root',_children=[{'__id__':2}],_components=[]),
                    dict(__type__='cc.Node',_name='View',_parent={'__id__':1},
                         _children=[dict(__type__='cc.Node',_name='Inline',_components=[])],
                         _components=[dict(__type__='cc.Button',node={'__id__':2},clickEvents=[None,{'__id__':0}])])]),
                ('bad.prefab','00000000-0000-0000-0000-000000000002',[
                    dict(__type__='cc.Prefab',data={'__id__':1}),
                    dict(__type__='cc.Node',_name='Bad',_children=[{'__id__':2}],_components=[]),
                    dict(__type__='cc.Node',_name='Broken',_parent=None,_children=[],_components=[])])]:
                write_json(source/'assets'/name,objects);write_json(source/'assets'/(name+'.meta'),dict(uuid=uid))
            c=catalog(source,root/'catalog');inspect(source,[r['index'] for r in c['selection']],root/'inspect')
            ir=normalize(root/'inspect/source-manifest.json',root/'ir')
            self.assertEqual(len(ir['nodes']),3)
            self.assertEqual(sum(n.get('sourceType')=='cc.Scene' for n in ir['nodes']),1)
            child=next(n for n in ir['nodes'] if n['name']=='Inline')
            self.assertEqual(child['parent'],next(n['sourceId'] for n in ir['nodes'] if n['name']=='View'))
            button=next(c for c in ir['components'] if c['type']=='cc.Button')
            self.assertEqual(len(button['events']),2)
            self.assertTrue(all(e['status']=='unresolved_source_event' for e in button['events']))
            self.assertEqual(ir['quarantinedAssets'][0]['reason'],'INVALID_NODE_GRAPH')
            # Independently valid scene can still be planned; no handler is fabricated.
            p=unity.plan(root/'ir/ir.json','shapes',root/'plan');self.assertEqual(len(p['nodes']),3)

    def test_local_resource_bases_and_remote_base_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();p=fixture(root/'bundle');c=load(read(p))
            (p.parent/'import').rename(p.parent/'objects');(p.parent/'native').rename(p.parent/'pixels')
            c.update(importBase='objects',nativeBase='pixels');write_json(p,c)
            b=Bundle(p);self.assertTrue(b.asset(2)['importPath'].startswith('objects/'))
            c['nativeBase']='https://example.invalid/native';write_json(p,c)
            with self.assertRaises(ParseError):Bundle(p)


if __name__=='__main__':unittest.main()
