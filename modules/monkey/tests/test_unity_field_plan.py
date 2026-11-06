import copy
import json
import tempfile
import unittest
from pathlib import Path
from monkey.io import sha, write_json
from monkey.sources.compiled import ParseError
from monkey.unity_semantics import SemanticError, validate_component, validate_value
from monkey.unity_field_plan import build, plan
from monkey.unity_code_model import field_type


def node(name, typ, children=None):
    result = dict(name=name,type=typ,metaFlag=0,version=1)
    if children is not None:result['children']=children
    return result


def strings():
    return node('Words','vector',[node('Array','Array',[node('size','int'),node('data','string')])])


def fixture():
    source=dict(sha256=sha(b'container'),metadataSha256=sha(b'metadata'),unityVersion='2021.3.30f1')
    ptr=lambda n:dict(m_FileID=0,m_PathID=n)
    schema=node('Base','MonoBehaviour',[node('m_GameObject','PPtr<GameObject>'),node('m_Script','PPtr<MonoScript>'),
                                      node('m_Enabled','UInt8'),strings(),node('Other','PPtr<GameObject>')])
    header=dict(m_GameObject=ptr(3),m_Script=ptr(2))
    obj=dict(file='level0',pathId='-9223372036854775807',rawSha256='a'*64,
             typeIdentity=dict(assembly='Game.dll',type='Game.Label',declarationSha256='b'*64,scriptId='b'*32,typeHash='c'*32),
             schema=schema,data=dict(header,m_Enabled=1,Words=[],Other=ptr(3)),header=header,
             evidence=dict(kind='exact-frozen-bundle',sha256='c'*64))
    candidate=dict(schemaVersion=1,source=source,files=[dict(name='level0',externals=[])],objects=[obj])
    trusted=copy.deepcopy(candidate)
    trusted['objects'].append(dict(file='level0',pathId='3',rawSha256='d'*64))
    targets=[dict(assetGuid='e'*32,assetPath='Assets/Test.unity',assetSha256=sha(b'%YAML 1.1\n--- !u!114 &101\nMonoBehaviour:\n--- !u!1 &102\nGameObject:\n'),
                  localId=str(101+i),type=t,hierarchy=[dict(name='Root',ordinal=0),dict(name='Same/#Name',ordinal=i)])
             for i,t in enumerate(['Game.Label','GameObject'])]
    bindings=dict(schemaVersion=1,source=copy.deepcopy(source),objects=[dict(source={k:o[k] for k in ('file','pathId','rawSha256')},target=t)for o,t in zip(trusted['objects'],targets)])
    inventory=dict(schemaVersion=1,unityVersion='6000.6.2f1',objects=copy.deepcopy(targets))
    return candidate,trusted,bindings,inventory


class SemanticGateTests(unittest.TestCase):
    def test_exact_ids_resolve_duplicate_names_and_nonnull_reference(self):
        result=build(*fixture());self.assertTrue(result['writable'])
        field=result['entries'][0]['fields']['Other']
        self.assertEqual(field['target']['localId'],'102')
        self.assertEqual(result['entries'][0]['target']['hierarchy'][-1]['name'],'Same/#Name')

    def test_full_read_is_not_semantic_success_for_misaligned_script_header(self):
        c,t,b,i=fixture();c['objects'][0]['data']['m_Script']['m_PathID']=2<<32
        result=build(c,t,b,i);self.assertFalse(result['writable']);self.assertNotIn('entries',result)
        self.assertIn('header identity',result['diagnostics'][0]['message'])

    def test_empty_string_array_must_not_become_scalar_string(self):
        c,t,b,i=fixture();c['objects'][0]['schema']['children'][3]['type']='string'
        c['objects'][0]['data']['Words']=''
        self.assertFalse(build(c,t,b,i)['writable'])
        malformed=c['objects'][0]['schema']['children'][3]
        with self.assertRaises(SemanticError):validate_value(malformed,'')
        with self.assertRaises(ParseError):field_type(malformed)
        # Equal wrong assertions cannot bypass validation either.
        t['objects'][0]=copy.deepcopy(c['objects'][0]);self.assertFalse(build(c,t,b,i)['writable'])

    def test_mutation_cases_block_all_entries(self):
        mutations=[lambda c,t,b,i:i.update(unityVersion='2021.3.30f1'),
                   lambda c,t,b,i:c['source'].update(unityVersion='2021.3.31f1'),
                   lambda c,t,b,i:c['source'].update(metadataSha256='f'*64),
                   lambda c,t,b,i:c['objects'][0].update(rawSha256='f'*64),
                   lambda c,t,b,i:c['objects'][0]['typeIdentity'].update(declarationSha256='f'*64),
                   lambda c,t,b,i:c['objects'][0]['schema']['children'][2].update(metaFlag=16384),
                   lambda c,t,b,i:c['objects'][0]['data'].update(Words=''),
                   lambda c,t,b,i:c['objects'][0]['data'].update(m_Enabled=True),
                   lambda c,t,b,i:c['objects'][0]['data'].update(Other=dict(m_FileID=True,m_PathID=3)),
                   lambda c,t,b,i:c['objects'][0]['data'].update(Other=dict(m_FileID=1,m_PathID=3)),
                   lambda c,t,b,i:b['objects'][0]['target'].pop('localId'),
                   lambda c,t,b,i:b['objects'][0]['target']['hierarchy'][1].update(ordinal=9),
                   lambda c,t,b,i:b['objects'].append(copy.deepcopy(b['objects'][0])),
                   lambda c,t,b,i:i['objects'].append(copy.deepcopy(i['objects'][0])),
                   lambda c,t,b,i:t['objects'].pop(0)]
        for change in mutations:
            with self.subTest(change=mutations.index(change)):
                args=fixture();change(*args);result=build(*args)
                self.assertFalse(result['writable']);self.assertNotIn('entries',result)

    def test_equal_pointer_assertions_still_require_real_file_and_target_mapping(self):
        c,t,b,i=fixture();b['objects'].pop()
        result=build(c,t,b,i);self.assertFalse(result['writable'])
        self.assertIn('no exact target mapping',result['diagnostics'][0]['message'])
        c,t,b,i=fixture()
        for d in (c,t):d['objects'][0]['data']['Other']['m_FileID']=1
        result=build(c,t,b,i);self.assertFalse(result['writable'])
        self.assertIn('external file',result['diagnostics'][0]['message'])

    def test_custom_named_array_and_empty_nested_arrays_follow_schema(self):
        shape=node('Calls','PersistentCall',[node('Array','Array',[node('size','int'),node('data','Call',[node('Name','string')])])])
        validate_value(shape,[])
        validate_value(shape,[dict(Name='Go')])
        with self.assertRaises(SemanticError):validate_value(shape,'')
        with self.assertRaises(SemanticError):validate_value(shape,[dict(Other='Go')])

    def test_large_field_integer_is_lossless_and_reference_looking_struct_stays_struct(self):
        c,t,b,i=fixture()
        for d in (c,t):
            o=d['objects'][0]
            o['schema']['children'] += [node('Count','SInt64'),node('Pair','CustomPair',[node('m_FileID','float'),node('m_PathID','SInt64')])]
            o['data'].update(Count=(1<<63)-1,Pair=dict(m_FileID=1.25,m_PathID=9))
        fields=build(c,t,b,i)['entries'][0]['fields']
        self.assertEqual(fields['Count'],{'$type':'integer','decimal':str((1<<63)-1)})
        self.assertEqual(fields['Pair'],dict(m_FileID=1.25,m_PathID=9))

    def test_null_references_and_lossless_signed64_bounds(self):
        c,t,b,i=fixture()
        for d in (c,t):d['objects'][0]['data']['Other']['m_PathID']=0
        self.assertIsNone(build(c,t,b,i)['entries'][0]['fields']['Other'])
        for bad in ('-0',str(1<<63),True):
            c,t,b,i=fixture();c['objects'][0]['pathId']=bad
            self.assertFalse(build(c,t,b,i)['writable'])

    def test_plan_is_atomic_and_pins_actual_source_metadata_and_target_bytes(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp).resolve();game=root/'game';(game/'Assets').mkdir(parents=True)
            (game/'ProjectSettings').mkdir();(game/'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 6000.6.2f1\n')
            args=fixture();c,t,b,i=args
            scene=game/'Assets/Test.unity';scene.write_bytes(b'%YAML 1.1\n--- !u!114 &101\nMonoBehaviour:\n--- !u!1 &102\nGameObject:\n')
            scene.with_suffix('.unity.meta').write_text('fileFormatVersion: 2\nguid: '+'e'*32+'\n')
            paths=[]
            for name,data in zip(('candidate','trusted','bindings','inventory'),args):
                p=root/(name+'.json');write_json(p,data);paths.append(p)
            source=root/'source';source.write_bytes(b'container');metadata=root/'metadata';metadata.write_bytes(b'metadata')
            def run(out):return plan(paths[0],paths[1],sha(paths[1].read_bytes()),paths[2],paths[3],sha(paths[3].read_bytes()),source,metadata,game,root/out)
            self.assertTrue(run('good')['writable']);self.assertTrue((root/'good/field-plan.json').exists())
            c['objects'][0]['data']['Words']='';write_json(paths[0],c)
            self.assertFalse(run('blocked')['writable']);self.assertFalse((root/'blocked/field-plan.json').exists())
            self.assertNotIn('fields',(root/'blocked/validation.json').read_text())
            metadata.write_bytes(b'changed')
            with self.assertRaises(ParseError):run('bad-metadata')
            self.assertFalse((root/'bad-metadata').exists());metadata.write_bytes(b'metadata')
            scene.write_bytes(scene.read_bytes()+b'# changed\n')
            with self.assertRaises(ParseError):run('bad-scene')
            self.assertFalse((root/'bad-scene').exists())


if __name__=='__main__':unittest.main()
