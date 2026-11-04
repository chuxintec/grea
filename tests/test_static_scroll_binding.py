import copy,tempfile,unittest
from pathlib import Path
from fixtures import fixture
from monkey.sources.bundle import inspect
from monkey.normalize import normalize
from monkey.targets import unity,cocos
from monkey import io

class StaticScrollBindingTests(unittest.TestCase):
    def test_native_axes_and_content_are_retained_without_claiming_physics(self):
        for missing in (False,True):
            with self.subTest(missing=missing),tempfile.TemporaryDirectory() as temp:
                r=Path(temp).resolve();config=fixture(r/'source')
                inspect(config,[2],r/'inspect');normalize(r/'inspect/source-manifest.json',r/'ir')
                p=r/'ir/ir.json';d=io.stage_document(p);root=d['nodes'][0];content=copy.deepcopy(root)
                content.update(sourceId=root['sourceId']+'/content',name='Content',parent=root['sourceId'],children=[],components=[])
                root['children'].append(content['sourceId']);d['nodes'].append(content)
                sid=root['sourceId']+'/scroll';root.setdefault('components',[]).append(sid)
                d['components'].append(dict(sourceId=sid,node=root['sourceId'],type='cc.ScrollView',enabled=True,materials=[],horizontal=True,vertical=True,content='absent'if missing else content['sourceId']))
                io.write_json(p,d);io.finish(p.parent,d)
                for name,target in [('unity',unity),('creator',cocos)]:
                    planned=target.plan(p,'neutral',r/name)
                    c=next(x for x in planned['components']if x['sourceId']==sid)
                    self.assertEqual(c['convertible'],not missing)
                    self.assertTrue(c['horizontal']);self.assertTrue(c['vertical'])
                    self.assertFalse(c['dynamicScrollingVerified'])
                    self.assertEqual(c['content'],'absent'if missing else content['sourceId'])
                    self.assertTrue(any(x['code']=='SCROLL_PHYSICS_NOT_VERIFIED'for x in planned['diagnostics']))
