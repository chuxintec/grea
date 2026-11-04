import tempfile
import unittest
from pathlib import Path
from monkey.io import sha
from monkey.prefab_target_behaviors import binding, prepare, emit, verify_bindings
from monkey.sources.compiled import ParseError


class TargetBehaviorTests(unittest.TestCase):
    def test_persistent_readback_rejects_missing_duplicate_and_changed_fields(self):
        from copy import deepcopy
        import struct
        spec={'typeName':'Example','scriptGuid':'script','fields':[{'name':'delay','type':'float','numberValue':0.3}]}
        components=[{'sourceId':'first','convertible':True,'enabled':False,'behaviorBinding':spec},
                    {'sourceId':'second','convertible':True,'enabled':False,'behaviorBinding':spec}]
        rows=[dict(sourceId=c['sourceId'],typeName='Example',scriptGuid='script',assetGuid='prefab',
                   localFileId=i+1,fieldsVerified=True,enabled=False,
                   fields=[dict(name='delay',type='float',numberValue=struct.unpack('f',struct.pack('f',0.3))[0])])
              for i,c in enumerate(components)]
        self.assertEqual(verify_bindings(components,rows,'prefab','unity','owner'),[])
        self.assertTrue(verify_bindings(components,rows[:1],'prefab','unity','owner'))
        bad=deepcopy(rows);bad[1]['localFileId']=bad[0]['localFileId']
        self.assertTrue(verify_bindings(components,bad,'prefab','unity','owner'))
        bad=deepcopy(rows);bad[0]['fields'][0]['numberValue']=0.4
        self.assertTrue(verify_bindings(components,bad,'prefab','unity','owner'))
        creator=deepcopy(rows)
        for i,row in enumerate(creator):
            row['localFileId']='component-'+str(i);row['fields'][0]['numberValue']=0.3
        self.assertEqual(verify_bindings(components,creator,'prefab','creator','owner'),[])
        creator[0]['fields'][0]['numberValue']=True
        self.assertTrue(verify_bindings(components,creator,'prefab','creator','owner'))

    def component(self):
        return {'sourceId':'source#2','nativeBehavior':{'targets':{'unity':{
            'status':'lowered_with_gaps','requiredProviders':[],
            'component':'Example','scriptPath':'Assets/Game/Scripts/Presentation/Recovered/Example.cs',
            'scriptSha256':'a'*64,'nativeType':'Monkey.Recovered.Behaviors.Example',
            'fields':[{'name':'delay','type':'float','value':0.5,'valueValidated':True}],
            'unsupportedBehaviors':['runtime-unverified']}}}}

    def test_partial_semantics_are_not_promoted_and_missing_providers_block(self):
        component=self.component();result=binding(component,'unity','sample')
        self.assertFalse(result['runtimeComplete'])
        self.assertEqual(result['gaps'],['runtime-unverified'])
        component['nativeBehavior']['targets']['unity']['requiredProviders']=['unbound']
        self.assertIsNone(binding(component,'unity','sample'))

    def test_field_and_destination_rejection(self):
        component=self.component();component['nativeBehavior']['targets']['unity']['fields'][0]['value']=float('nan')
        with self.assertRaises(ParseError):binding(component,'unity','sample')
        component=self.component();component['nativeBehavior']['targets']['unity']['scriptPath']='Assets/Other/Example.cs'
        with self.assertRaises(ParseError):binding(component,'unity','sample')

    def test_generated_bytes_and_script_identity_survive_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();source=root/'ir';source.mkdir();plan=root/'plan';plan.mkdir();output=root/'output';output.mkdir()
            raw=b'// neutral generated test source\n';(source/'Example.cs').write_bytes(raw)
            ir={'emittedBehaviorScripts':[{'target':'unity','targetPath':'Assets/Game/Scripts/Presentation/Recovered/Example.cs','artifactPath':'Example.cs','sha256':sha(raw)}]}
            scripts=prepare(ir,source,'unity','sample',plan)
            emit({'behaviorScripts':scripts},plan,'unity',output)
            dest=output/scripts[0]['target'];self.assertEqual(dest.read_bytes(),raw)
            self.assertIn(scripts[0]['identity'],Path(str(dest)+'.meta').read_text())
            (plan/scripts[0]['source']).write_bytes(b'changed')
            with self.assertRaises(ParseError):emit({'behaviorScripts':scripts},plan,'unity',root/'second')
