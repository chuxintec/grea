import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from grea.recovery.io import encoded, sha, write_json
from grea.recovery.sources.compiled import ParseError
from grea.recovery.unity_prefab_texture_material_assets import plan_texture_material_rebuild


class TextureMaterialPlannerTests(unittest.TestCase):
    def fixture(self, root, main_index=0, source_file_id='2', edge_file_id='2', target_name='effect', shader_class_id=48):
        candidate = root / 'candidate'; (candidate / 'Analysis/Evidence').mkdir(parents=True)
        (candidate / 'Analysis/Mappings').mkdir(parents=True)
        material_rel = 'Assets/Materials/effect.mat'
        mat_path = candidate / material_rel; mat_path.parent.mkdir(parents=True)
        meta_path = Path(str(mat_path) + '.meta')
        source_guid = '1' * 32; shader_guid = '2' * 32
        mat_yaml = (f'''%YAML 1.1\n--- !u!21 &2100000\nMaterial:\n  m_Name: {target_name}\n  m_Shader: {{fileID: 4800000, guid: {shader_guid}, type: 2}}\n  m_SavedProperties:\n    m_TexEnvs:\n      _MainTex:\n        m_Texture: {{fileID: 2800000, guid: 0000000deadbeef15deadf00d0000000, type: 2}}\n        m_Scale: {{x: 1, y: 1}}\n        m_Offset: {{x: 0, y: 0}}\n''').encode()
        meta = f'fileFormatVersion: 2\nguid: {source_guid}\n'.encode()
        mat_path.write_bytes(mat_yaml); meta_path.write_bytes(meta)
        shader_path = candidate / 'Assets/Shaders/exact.asset'; shader_path.parent.mkdir(parents=True)
        shader_path.write_bytes(f'%YAML 1.1\n--- !u!{shader_class_id} &4800000\nShader: {{}}\n'.encode())
        Path(str(shader_path)+'.meta').write_text(f'fileFormatVersion: 2\nguid: {shader_guid}\n')
        bundle = root / 'source.bundle'; bundle.write_bytes(b'original immutable source bundle')
        container = sha(bundle.read_bytes())
        sid_tex, sid_mat, sid_shader = 'source-texture', 'source-material', 'source-shader'
        texture_data = dict(m_Name='selected', m_Width=2, m_Height=2, m_ColorSpace=1, m_MipCount=1,
                            m_TextureSettings=dict(m_FilterMode=1, m_Aniso=1, m_MipBias=0.0, m_WrapU=0, m_WrapV=0, m_WrapW=0))
        material_data = dict(m_Name='effect', m_Shader={'$type':'UnityPPtr','fileId':'1','pathId':'9'},
            m_SavedProperties=dict(m_Colors=[['_TintColor',dict(r=.5,g=.5,b=.5,a=.5)]],
              m_Floats=[['_AlphaOpen',0.0],['_AlphaStrength',1.0]],m_Ints=[],
              m_TexEnvs=[['_MainTex',dict(m_Texture={'$type':'UnityPPtr','fileId':source_file_id,'pathId':'7'},m_Scale=dict(x=1.0,y=1.0),m_Offset=dict(x=0.0,y=0.0))]]))
        if main_index:
            material_data['m_SavedProperties']['m_TexEnvs'].insert(0,['OtherTex',dict(m_Texture={'$type':'UnityPPtr','fileId':'1','pathId':'8'},m_Scale=dict(x=1.0,y=1.0),m_Offset=dict(x=0.0,y=0.0))])
        ident = lambda path: dict(containerSha256=container, serializedFile='CAB-test', serializedFileSha256='a'*64, pathId=str(path))
        objects = [dict(sourceObjectId=sid_tex,type='Texture2D',identity=ident(7),rawSha256='b'*64,data=texture_data),
                   dict(sourceObjectId=sid_mat,type='Material',identity=ident(8),rawSha256='c'*64,data=material_data),
                   dict(sourceObjectId=sid_shader,type='Shader',identity=ident(9),rawSha256='d'*64,data=dict(m_Name='original'))]
        graph = dict(contract='monkey-unity-prefab-source-graph/1',sourceUnityVersions=['2021.3.30f1'],reachableObjects=objects,
             referenceEdges=[dict(sourceObjectId=sid_mat,location=f'$/m_SavedProperties/m_TexEnvs/{main_index}/1/m_Texture',status='resolved',fileId=edge_file_id,pathId='7',targetSourceObjectId=sid_tex),
                             dict(sourceObjectId=sid_mat,location='$/m_Shader',status='resolved',fileId='1',pathId='9',targetSourceObjectId=sid_shader)])
        inputs = [dict(sourceSha256=container,sourcePath=str(bundle))]
        relocation = dict(layout='monkey-project/2.0.0',moves=[dict(target=material_rel,kind='material',guid=source_guid,source='Assets/source/effect.mat')])
        for rel, value in [('Analysis/Evidence/source-graph.json',graph),('Analysis/Evidence/source-inputs.json',inputs),('Analysis/Mappings/unity-relocation.json',relocation)]:
            write_json(candidate / rel,value)
        files=[]
        for p in sorted(candidate.rglob('*')):
            if p.is_file():
                rel=p.relative_to(candidate).as_posix(); raw=p.read_bytes(); files.append(dict(path=rel,sha256=sha(raw),bytes=len(raw)))
        manifest=dict(contract='monkey-unity-prefab-recovery/1',targetProfile='unity-6000.6.2f1-ugui',files=files)
        write_json(candidate/'manifest.json',manifest)
        # 2x2 bottom-up source RGBA; export PNG is vertically flipped by the exporter.
        rgba=bytes([1,2,3,4, 5,6,7,8, 9,10,11,12, 13,14,15,16])
        png_path=root/'selected.png'; Image.frombytes('RGBA',(2,2),rgba).transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(png_path)
        png=png_path.read_bytes()
        pixel=dict(contract='unity-selected-texture-export/1',status='partial',scope='selected-texture-pngs',nativeImport='not_run',
            exportComplete=True,sourceAndDerivativeUnchanged=True,sourceContainerStatus='partial',wholeContainerComplete=False,unselectedObjectsUnchanged=True,
            inputPins=dict(source=container),files=[dict(path='selected.png',sha256=sha(png),bytes=len(png),width=2,height=2)],
            textures=[dict(source=dict(file='CAB-test',pathId='7',sourceName='selected',sourceRawSha256='b'*64),
              hydration=dict(logicalPath='Assets/Textures/selected.astc',cacheSha256='e'*64,rgbaRawSha256=sha(rgba)),
              target=dict(path='selected.png',sha256=sha(png),bytes=len(png),width=2,height=2,nativeGuid='not-assigned',nativeImport='not_run'))])
        pixel_path=root/'pixels.json'; write_json(pixel_path,pixel)
        return candidate,pixel_path,sid_tex,sid_mat,material_rel

    def invoke(self, fixture, out, **override):
        candidate,pixels,tid,mid,rel=fixture
        graph= json.loads((candidate/'Analysis/Evidence/source-graph.json').read_text())
        args=dict(candidate_root=candidate,expected_manifest_sha256=sha((candidate/'manifest.json').read_bytes()),
                  selected_pixel_manifest=pixels,selected_pixel_manifest_sha256=sha(pixels.read_bytes()),
                  source_texture_ids=[tid],source_material_ids=[mid],provider_assets={mid:{'assetPath':rel}},output_path=out)
        args.update(override)
        return plan_texture_material_rebuild(**args)

    def test_pins_exact_material_texture_edge_and_allows_partial_unselected_pool(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as d:
            root=Path(d); fixture=self.fixture(root)
            result=self.invoke(fixture,root/'plan.json')
            asset=result['assets'][0]
            self.assertEqual(result['status'],'planned-not-applied')
            self.assertEqual(result['selectedPixelManifestStatus'],'partial')
            self.assertFalse(result['selectedPixelWholeContainerComplete'])
            self.assertEqual(asset['sourceTextureId'],'source-texture')
            self.assertEqual(asset['sourceMaterialData']['m_SavedProperties']['m_Floats'][1],['_AlphaStrength',1.0])
            self.assertTrue(Path(asset['texture']['rgbaAbsolutePath']).is_file())

    def test_rejects_texture_tuple_that_does_not_match_selected_manifest(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as d:
            root=Path(d); fixture=self.fixture(root); candidate,pixels,tid,mid,rel=fixture
            doc=json.loads(pixels.read_text()); doc['textures'][0]['source']['pathId']='999'; write_json(pixels,doc)
            with self.assertRaises(ParseError) as caught:
                self.invoke(fixture,root/'bad-plan.json')
            self.assertEqual(caught.exception.code,'TEXTURE_MATERIAL_PIXEL_CROSSWALK')

    def test_rejects_ambiguous_material_texture_edge(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as d:
            root=Path(d); fixture=self.fixture(root); candidate,pixels,tid,mid,rel=fixture
            p=candidate/'Analysis/Evidence/source-graph.json'; graph=json.loads(p.read_text())
            graph['referenceEdges'].append(dict(sourceObjectId=mid,location='$/m_SavedProperties/m_TexEnvs/0/1/m_Texture',status='resolved',fileId='2',pathId='7',targetSourceObjectId=tid))
            write_json(p,graph)
            manifest=json.loads((candidate/'manifest.json').read_text())
            for row in manifest['files']:
                if row['path']==p.relative_to(candidate).as_posix(): row.update(sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
            write_json(candidate/'manifest.json',manifest)
            with self.assertRaises(ParseError) as caught:
                self.invoke(fixture,root/'bad-plan.json')
            self.assertEqual(caught.exception.code,'TEXTURE_MATERIAL_SOURCE_EDGE')


    def test_uses_typed_maintex_index_and_file_id_not_fixed_location(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as d:
            root=Path(d); fixture=self.fixture(root,main_index=1,source_file_id='7',edge_file_id='7')
            result=self.invoke(fixture,root/'plan.json')
            ref=result['assets'][0]['sourceMainTextureReference']
            self.assertEqual(ref['location'],'$/m_SavedProperties/m_TexEnvs/1/1/m_Texture')
            self.assertEqual(ref['fileId'],'7')

    def test_rejects_graph_file_id_different_from_typed_maintex_ptr(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as d:
            root=Path(d); fixture=self.fixture(root,main_index=1,source_file_id='7',edge_file_id='2')
            with self.assertRaises(ParseError) as caught: self.invoke(fixture,root/'bad-plan.json')
            self.assertEqual(caught.exception.code,'TEXTURE_MATERIAL_MAIN_TEX')

    def test_rejects_graph_edge_at_wrong_maintex_array_index(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as d:
            root=Path(d); fixture=self.fixture(root,main_index=1,source_file_id='7',edge_file_id='7')
            candidate=fixture[0]; graph_path=candidate/'Analysis/Evidence/source-graph.json'; graph=json.loads(graph_path.read_text())
            graph['referenceEdges'][0]['location']='$/m_SavedProperties/m_TexEnvs/0/1/m_Texture'; write_json(graph_path,graph)
            manifest=json.loads((candidate/'manifest.json').read_text())
            for row in manifest['files']:
                if row['path']=='Analysis/Evidence/source-graph.json': row.update(sha256=sha(graph_path.read_bytes()),bytes=graph_path.stat().st_size)
            write_json(candidate/'manifest.json',manifest)
            with self.assertRaises(ParseError) as caught: self.invoke(fixture,root/'bad-plan.json')
            self.assertEqual(caught.exception.code,'TEXTURE_MATERIAL_SOURCE_EDGE')

    def test_rejects_shader_closure_wrong_native_type_proof(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as d:
            root=Path(d); fixture=self.fixture(root,shader_class_id=21)
            with self.assertRaises(ParseError) as caught: self.invoke(fixture,root/'bad-plan.json')
            self.assertEqual(caught.exception.code,'TEXTURE_MATERIAL_SHADER_CLOSURE')

    def test_rejects_provider_material_name_mismatch(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as d:
            root=Path(d); fixture=self.fixture(root,target_name='wrongName')
            candidate=fixture[0]; asset=candidate/'Assets/Materials/effect.mat'; manifest=json.loads((candidate/'manifest.json').read_text())
            for row in manifest['files']:
                if row['path']=='Assets/Materials/effect.mat': row.update(sha256=sha(asset.read_bytes()),bytes=asset.stat().st_size)
            write_json(candidate/'manifest.json',manifest)
            with self.assertRaises(ParseError) as caught: self.invoke(fixture,root/'bad-plan.json')
            self.assertEqual(caught.exception.code,'TEXTURE_MATERIAL_TARGET_NAME')


if __name__ == '__main__': unittest.main()
