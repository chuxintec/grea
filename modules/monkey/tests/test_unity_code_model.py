import json,tempfile,unittest
from pathlib import Path
from monkey.io import write_json,sha,read
from monkey.unity_code_model import model,field_type,identifier
from monkey.sources.compiled import ParseError


class UnityCodeSchemaTests(unittest.TestCase):
    def test_original_sprite_pointer_vector_and_uint64_have_explicit_types(self):
        n={'type':'vector','name':'Idle','children':[{'type':'Array','name':'Array','children':[{'type':'int','name':'size'},{'type':'PPtr<$Sprite>','name':'data'}]}]}
        self.assertEqual(field_type(n),'UnityEngine.Sprite[]')
        self.assertEqual(field_type({'type':'UInt64','name':'assetQuantity'}),'ulong')
        self.assertEqual(identifier('class'),'@class')
        self.assertEqual(identifier('FrameSpritePool'),'FrameSpritePool')
        with self.assertRaises(ParseError):field_type({'type':'PPtr<$UnknownClass>','name':'Unknown'})
        with self.assertRaises(ParseError):identifier('Name; execute()')

    def test_schema_producer_generates_named_nonempty_fields_and_retains_missing_logic(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();source=root/'inspection';source.mkdir()
            schema={'children':[{'name':'m_GameObject','type':'PPtr<GameObject>'},{'name':'m_Script','type':'PPtr<MonoScript>'},{'name':'Volume','type':'float'}]}
            obj={'file':'0','pathId':'-9223372036854775807','type':'MonoBehaviour','status':'parsed','embeddedSchemaId':'shape','rawSha256':'a'*64,'references':[], 'data':{'m_Script':{'fileId':'0','pathId':'2'},'m_GameObject':{'fileId':'0','pathId':'3'}}}
            script={'file':'0','pathId':'2','type':'MonoScript','status':'parsed','data':{'m_ClassName':'AudioSettings','m_Namespace':'Game','m_AssemblyName':'GameBase.dll'}}
            data={'source':{'sha256':'b'*64},'objects':[obj,script],'embeddedSchemas':{'shape':schema}}
            write_json(source/'typed-objects.json',data);write_json(source/'inspection.json',{'typedObjectsSha256':sha(read(source/'typed-objects.json'))})
            result=model(source,root/'out');self.assertEqual(result['summary']['fields'],1)
            code=(root/'out/CSharp/GameBase/Game/AudioSettings.cs').read_text();self.assertIn('public float Volume;',code)
            self.assertNotIn('Invoke',code);self.assertEqual(result['summary']['methodsImplemented'],0)
            (source/'typed-objects.json').write_text('{}')
            with self.assertRaises(ParseError):model(source,root/'changed')
            self.assertFalse((root/'changed').exists())

    def test_bulk_alias_requires_identical_script_bytes_and_fields_and_keeps_all_source_ids(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();source=root/'inspection';source.mkdir()
            shape=dict(children=[dict(name='m_GameObject',type='PPtr<GameObject>'),dict(name='gain',type='float')])
            objects=[]
            for file in ['0','1']:
                objects.extend([dict(file=file,pathId='1',type='MonoBehaviour',status='parsed',embeddedSchemaId='shape',rawSha256='a'*64,references=[],data=dict(m_Script=dict(fileId='0',pathId='2'),m_GameObject=dict(fileId='0',pathId='3'))),dict(file=file,pathId='2',type='MonoScript',status='parsed',rawSha256='b'*64,data=dict(m_ClassName='Gain',m_Namespace='Game',m_AssemblyName='Game.dll'))])
            data=dict(source=dict(sha256='c'*64),objects=objects,embeddedSchemas=dict(shape=shape))
            def save():
                write_json(source/'typed-objects.json',data);write_json(source/'inspection.json',dict(typedObjectsSha256=sha(read(source/'typed-objects.json'))))
            save()
            with self.assertRaises(ParseError):model(source,root/'strict')
            result=model(source,root/'bulk',True);self.assertEqual(result['summary']['classes'],1);self.assertEqual(result['summary']['instances'],2)
            body=json.loads((root/'bulk/unity-code-model.json').read_text());self.assertEqual(len(body['classes'][0]['sourceScripts']),2)
            objects[-1]['rawSha256']='d'*64;save()
            with self.assertRaises(ParseError):model(source,root/'different-bytes',True)
            objects[-1]['rawSha256']='b'*64;data['embeddedSchemas']['other']=dict(children=[dict(name='m_GameObject',type='PPtr<GameObject>'),dict(name='gain',type='int')]);objects[-2]['embeddedSchemaId']='other';save()
            with self.assertRaises(ParseError):model(source,root/'different-fields',True)

    def test_borrowed_fields_resolve_exact_external_file_and_do_not_shadow_native_or_invent_asset_base(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();source=root/'inspection';source.mkdir()
            shape=dict(children=[dict(name='m_GameObject',type='PPtr<GameObject>'),dict(name='gain',type='double')])
            obj=dict(file='scene',pathId='-7',type='MonoBehaviour',status='parsed',typeTreeSource='exact-frozen-bundle',borrowedSchemaId='shape',schemaProvenance={'layoutSha256':'c'*64},rawSha256='a'*64,references=[],data=dict(m_Script=dict(fileId='1',pathId='2'),m_GameObject=dict(fileId='0',pathId='3')))
            script=dict(file='scripts',pathId='2',type='MonoScript',status='parsed',data=dict(m_ClassName='Gain',m_Namespace='Game',m_AssemblyName='Game.dll'))
            data=dict(source={'sha256':'b'*64},objects=[obj,script],borrowedSchemas={'shape':shape},files=[dict(id='scene',name='level0',externals=[dict(fileId='1',path='scripts.assets')]),dict(id='scripts',name='scripts.assets',externals=[])])
            def save():
                write_json(source/'typed-objects.json',data);write_json(source/'inspection.json',{'typedObjectsSha256':sha(read(source/'typed-objects.json'))})
            save();result=model(source,root/'known');self.assertEqual(result['summary']['classes'],1)
            report=json.loads((root/'known/unity-code-model.json').read_text());instance=report['classes'][0]['instances'][0]
            self.assertEqual(instance['schemaEvidence']['kind'],'exact-frozen-bundle');self.assertEqual(report['classes'][0]['sourceScript']['file'],'scripts')
            script['data'].update(m_AssemblyName='UnityEngine.UI.dll',m_Namespace='UnityEngine.UI',m_ClassName='Graphic')
            save();result=model(source,root/'builtin');self.assertEqual(result['summary']['classes'],0)
            self.assertEqual(len(json.loads((root/'builtin/unity-code-model.json').read_text())['nativePackageTypes']),1)
            script['data']['m_AssemblyName']='Game.dll';shape['children']=shape['children'][1:]
            save();result=model(source,root/'asset');self.assertEqual(result['summary']['classes'],0)
            self.assertIn('base class',json.loads((root/'asset/unity-code-model.json').read_text())['gaps'][0]['reason'])
            data['files'].append(dict(id='ambiguous',name='scripts.assets',externals=[]));save()
            result=model(source,root/'ambiguous');self.assertEqual(result['summary']['classes'],0)


if __name__=='__main__':unittest.main()
