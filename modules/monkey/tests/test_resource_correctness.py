from types import SimpleNamespace
import unittest
from pathlib import PurePosixPath
from monkey.layout import LayoutPlanner
from monkey.sources.unity_worker import component_prefix
from monkey.creator_geometry import tiled_vertices,renderer_budget,verify_tiled_readback


class ResourceCorrectnessTests(unittest.TestCase):
    def test_unknown_component_retains_only_exact_native_prefix_refs(self):
        head=SimpleNamespace(m_GameObject=SimpleNamespace(m_FileID=0,m_PathID=9223372036854775807),
                             m_Script=SimpleNamespace(m_FileID=2,m_PathID=-9223372036854775808))
        obj=SimpleNamespace(parse_monobehaviour_head=lambda:head)
        prefix,refs=component_prefix(obj)
        self.assertEqual(prefix['body'],'unparsed')
        self.assertEqual(refs,[dict(location='$/m_GameObject',fileId='0',pathId='9223372036854775807'),
                               dict(location='$/m_Script',fileId='2',pathId='-9223372036854775808')])
        head.m_Script.m_PathID=True
        with self.assertRaises(ValueError):component_prefix(obj)

    def test_derived_clip_names_keep_short_paths_and_budget_full_long_filename(self):
        naming=LayoutPlanner('unity')
        for sid,name in [('short','StartButton'),('long','测试按钮'*35),('similar','测试按钮'*34+'尾')]:
            owner=naming.path(sid,'controller','.controller',metadata=dict(logicalPath='UI/'+name))
            paths=[]
            for state in ('normal','pressed'):
                target=naming.derived_path(sid+'@'+state,owner,'_'+state,'.anim');paths.append(target)
                self.assertLessEqual(len(PurePosixPath(target).name.encode()),64)
                self.assertEqual(target,naming.derived_path(sid+'@'+state,owner,'_'+state,'.anim'))
                if sid=='short':self.assertEqual(target,owner[:-len('.controller')]+'_'+state+'.anim')
            self.assertNotEqual(*paths)
        targets=[r['target'].casefold() for r in naming.records];self.assertEqual(len(targets),len(set(targets)))

    def test_native_tiled_budget_uses_border_repeat_geometry_and_uint16_bound(self):
        self.assertEqual(tiled_vertices([690,1180],[32,32],[8,8,8,8]),13500)
        self.assertEqual(tiled_vertices([0,0],[2,2],[0,0,0,0]),0)
        nodes=[dict(sourceId='node',size=[690,1180])]
        assets=[dict(sourceId='frame',size=[32,32],originalSize=[32,32],border=[8,8,8,8])]
        c=dict(sourceId='sprite',node='node',type='cc.Sprite',mode=2,convertible=True,spriteFrame='frame',nativeSizeMode=0)
        budget,gaps=renderer_budget(nodes,[c],assets)
        self.assertFalse(gaps);self.assertGreater(budget['macroConfig']['BATCHER2D_MEM_INCREMENT'],144)
        self.assertGreaterEqual(budget['vertexCapacity'],13500);self.assertLess(budget['vertexCapacity'],65536)
        # RAW sizing uses the actual frame original size, not the earlier authored node size.
        c['nativeSizeMode']=2;budget,gaps=renderer_budget(nodes,[c],assets)
        self.assertEqual(budget['macroConfig']['BATCHER2D_MEM_INCREMENT'],144)
        c['nativeSizeMode']=0;nodes[0]['size']=[1e9,1e9];budget,gaps=renderer_budget(nodes,[c],assets)
        self.assertFalse(c['convertible']);self.assertEqual(len(gaps),1)
        self.assertEqual(budget['maxTiledVertices'],0)

    def test_invalid_tiled_insets_do_not_become_guessed_geometry(self):
        for size,rect,border in [([1,1],[2,2],[2,0,2,0]),([1,float('inf')],[2,2],[0,0,0,0])]:
            with self.assertRaises(ValueError):tiled_vertices(size,rect,border)

    def test_tiled_readback_rejects_invisible_geometry_missing_allocation_and_wrong_frame(self):
        import copy
        c=dict(sourceId='sprite',node='node',type='cc.Sprite',mode=2,convertible=True,spriteFrame='frame',nativeSizeMode=0)
        frames=[dict(sourceId='frame',size=[2,2],border=[0,0,0,0])]
        budget,_=renderer_budget([dict(sourceId='node',size=[4,2])],[c],frames)
        plan=dict(rendererBudget=budget,components=[c],assets=frames)
        rb=dict(nodes=[dict(sourceId='node',size=[4,2])],assets=[dict(sourceId='frame',spriteFrameUuid='native-frame')],
                tiledRenderer=dict(profile=budget['profile'],macroKiB=144,sprites=[dict(sourceId='sprite',vertexCount=8,indexCount=12,allocated=True,spriteFrameUuid='native-frame')]))
        self.assertTrue(verify_tiled_readback(plan,rb))
        for field,value in [('vertexCount',0),('vertexCount',True),('indexCount',6),('allocated',False),('spriteFrameUuid','other')]:
            wrong=copy.deepcopy(rb);wrong['tiledRenderer']['sprites'][0][field]=value
            self.assertFalse(verify_tiled_readback(plan,wrong),field)
        wrong=copy.deepcopy(rb);wrong['tiledRenderer']['sprites']*=2
        self.assertFalse(verify_tiled_readback(plan,wrong))
        # Genuine zero-size source geometry is allowed, unlike a missing positive mesh.
        rb['nodes'][0]['size']=[0,0];rb['tiledRenderer']['sprites'][0].update(vertexCount=0,indexCount=0)
        self.assertTrue(verify_tiled_readback(plan,rb))

    def test_tight_mesh_retains_concave_topology_and_exact_uv_not_a_rectangular_hull(self):
        import base64,copy,struct
        from monkey.io import sha
        from monkey.unity_sprite import tight_geometry
        vertices=[(-1.,-1.,0.),(1.,-1.,0.),(0.,0.,0.),(-1.,1.,0.)]
        raw=b''.join(struct.pack('<fff',*v) for v in vertices)+bytes(32)
        indices=list(struct.pack('<6H',0,1,2,0,2,3))
        data=dict(m_RD=dict(m_VertexData=dict(m_VertexCount=4,m_Channels=[dict(stream=0,offset=0,format=0,dimension=3),
                *[dict(dimension=0) for _ in range(3)],dict(stream=1,offset=0,format=0,dimension=2)],
                m_DataSize={'$type':'bytes','base64':base64.b64encode(raw).decode(),'bytes':len(raw),'sha256':sha(raw)}),m_IndexBuffer=indices,
                m_SubMeshes=[dict(firstByte=0,indexCount=6,topology=0,baseVertex=0,firstVertex=0,vertexCount=4)]))
        atlas=dict(uvTransform=dict(x=2,y=4,z=2,w=4))
        result=tight_geometry(data,atlas,8,8)
        self.assertEqual(result['meshVertices'][2],dict(x=0,y=0));self.assertEqual(result['triangleIndices'],[0,1,2,0,2,3])
        self.assertEqual(result['meshUv'][0],dict(x=.25,y=.25))
        flipped=tight_geometry(data,dict(atlas,settingsRaw=73,textureRect=dict(x=2,y=1,width=4,height=5)),8,8)
        self.assertEqual(flipped['meshVertices'],result['meshVertices'])
        self.assertEqual(flipped['triangleIndices'],result['triangleIndices'])
        self.assertEqual(flipped['meshUv'],[dict(x=.25,y=.625),dict(x=.75,y=.625),dict(x=.5,y=.375),dict(x=.25,y=.125)])
        from monkey.unity_sprite import atlas_settings
        self.assertEqual(atlas_settings(73)['packingRotation'],'FlipVertical')
        rect=dict(x=2,y=1,width=4,height=5)
        horizontal=tight_geometry(data,dict(atlas,settingsRaw=69,textureRect=rect),8,8)
        half_turn=tight_geometry(data,dict(atlas,settingsRaw=77,textureRect=rect),8,8)
        self.assertEqual(horizontal['meshUv'],[dict(x=.75,y=.25),dict(x=.25,y=.25),dict(x=.5,y=.5),dict(x=.75,y=.75)])
        self.assertEqual(half_turn['meshUv'],[dict(x=.75,y=.625),dict(x=.25,y=.625),dict(x=.5,y=.375),dict(x=.75,y=.125)])
        for geometry in [horizontal,half_turn]:
            self.assertEqual(geometry['meshVertices'],result['meshVertices'])
            self.assertEqual(geometry['triangleIndices'],result['triangleIndices'])
        self.assertEqual(atlas_settings(69)['packingRotation'],'FlipHorizontal')
        self.assertEqual(atlas_settings(77)['packingRotation'],'Rotate180')
        for raw in (True,64,71,75,79,81,125,129,-1,73.0):
            with self.subTest(settings=raw),self.assertRaises(ValueError):atlas_settings(raw)
        with self.assertRaises(ValueError):tight_geometry(data,dict(atlas,settingsRaw=67),8,8)

        for key,value in [('m_IndexBuffer',list(struct.pack('<6H',0,1,8,0,2,3))),('m_SubMeshes',[dict(firstByte=2)])]:
            wrong=copy.deepcopy(data);wrong['m_RD'][key]=value
            with self.assertRaises(ValueError):tight_geometry(wrong,atlas,8,8)
        wrong=copy.deepcopy(data);wrong['m_RD']['m_VertexData']['m_Channels'][0]['format']=1
        with self.assertRaises(ValueError):tight_geometry(wrong,atlas,8,8)
        with self.assertRaises(ValueError):tight_geometry(data,dict(uvTransform=dict(x=1e308,y=1e308,z=2,w=4)),8,8)
