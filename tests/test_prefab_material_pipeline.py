import copy
import tempfile
import unittest
from pathlib import Path
from monkey.prefab_material_pipeline import emit, supported_component, verify
from monkey.sources.compiled import ParseError
from monkey.io import sha


class MaterialPipelineTests(unittest.TestCase):
    def fixture(self):
        props=dict(brightness=1.25,saturation=.6,constrast=1.4,gray=.35,silhouette=[.2,.4,.6,.8])
        spec=dict(materialSourceId='source:material',materialGuid='material',shaderGuid='shader',
                  properties=props,sourceComponentIds=['sprite'],creator=dict(materialUuid='material',effectUuid='effect'))
        row=dict(sourceId='source:material',materialGuid='material',shaderGuid='shader',localFileId=2100000,
                 persistent=True,propertiesVerified=True,**props)
        row['silhouette']=dict(zip('rgba',props['silhouette']))
        return spec,row

    def test_exact_native_parameters_and_identities_are_required(self):
        spec,row=self.fixture();self.assertEqual(verify(spec,row,'unity'),[])
        for key,value in [('materialGuid','other'),('shaderGuid','other'),('localFileId',0),('propertiesVerified',False),('gray',float('nan')),('brightness',1)]:
            changed=copy.deepcopy(row);changed[key]=value
            self.assertTrue(verify(spec,changed,'unity'),key)
        creator=dict(sourceId='source:material',materialUuid='material',effectUuid='effect',metaUuid='material',
                     metaUuidVerified=True,propertiesVerified=True,technique=0,properties=spec['properties'])
        self.assertEqual(verify(spec,creator,'creator'),[])
        creator['properties']=dict(spec['properties'],saturation=True)
        self.assertTrue(verify(spec,creator,'creator'))

    def test_component_mapping_does_not_clear_other_materials(self):
        spec,_=self.fixture();profile=dict(spec=spec)
        component=dict(sourceId='sprite',type='cc.Sprite',materials=['alias'])
        self.assertTrue(supported_component(component,profile,lambda x:'source:material'))
        component['materials'].append('second')
        self.assertFalse(supported_component(component,profile,lambda x:'source:material'))
        component.update(sourceId='unselected',materials=['source:material'])
        self.assertFalse(supported_component(component,profile,lambda x:x))

    def test_emit_refuses_changed_owned_file_and_existing_destination(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();source=root/'plan';source.mkdir();out=root/'candidate';out.mkdir()
            (source/'shader').write_bytes(b'original')
            binding=dict(spec={},payloads=[dict(source='shader',target='Assets/Game/Content/Shaders/Shared/Test.shader',sha256=sha(b'original'))])
            emit(binding,source,out)
            with self.assertRaises(ParseError):emit(binding,source,out)
            (source/'shader').write_bytes(b'changed')
            with self.assertRaises(ParseError):emit(binding,source,root/'other')
