import json
import tempfile
import unittest
from pathlib import Path
from monkey.io import write_json
from monkey.sources.project import inspect, catalog
from monkey.normalize import normalize
from fixtures import PREFAB

class SourceValueObjectsTests(unittest.TestCase):
    def test_click_event_and_nested_record_are_preserved_without_fake_components(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); source=root/'source'; (source/'assets').mkdir(parents=True)
            write_json(source/'project.json',dict(version='2.4.15',id='neutral-values'))
            write_json(source/'assets/panel.prefab.meta',dict(uuid=PREFAB,importer='prefab'))
            event=dict(__type__='cc.ClickEvent',target={'__id__':1},handler='onSelect',customEventData='test')
            record=dict(__type__='NeutralOption',text='choice',target={'__id__':1})
            write_json(source/'assets/panel.prefab',[
                {'__type__':'cc.Prefab','data':{'__id__':1}},
                dict(__type__='cc.Node',_name='Panel',_parent=None,_children=[],_components=[{'__id__':2}],_contentSize={'width':100,'height':50},_anchorPoint={'x':.5,'y':.5},_trs={'__type__':'TypedArray','ctor':'Float64Array','array':[0,0,0,0,0,0,1,1,1,1]}),
                dict(__type__='cc.Button',node={'__id__':1},clickEvents=[{'__id__':3}],_interactable=True),event,record])
            rows=catalog(source,root/'catalog')['selection'];index=next(x['index']for x in rows if x['key']==PREFAB)
            inspect(source,[index],root/'inspect');normalize(root/'inspect/source-manifest.json',root/'ir')
            ir=json.loads((root/'ir/ir.json').read_text())
            self.assertEqual([c['type'] for c in ir['components']],['cc.Button'])
            self.assertEqual([v['sourceData'] for v in ir['sourceValueObjects']],[event,record])
            self.assertEqual(len(ir['nodes']),1)
            self.assertEqual(ir['quarantinedAssets'],[])

if __name__=='__main__':unittest.main()
