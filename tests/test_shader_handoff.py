import json
from pathlib import Path
import tempfile
import unittest
from monkey.io import write_json,sha
from monkey.shader_handoff import classify_project


class ShaderHandoffTests(unittest.TestCase):
    def fixture(self,root):
        project=root/'Project';project.mkdir();files=[]
        values={
          'Assets/Game/Content/Shaders/Recovered.asset':b'%YAML 1.1\n--- !u!48 &4800000\nShader:\n  platforms: 0500000009000000\n  compressedBlob: abcd\n',
          'Assets/Game/Content/Shaders/Source.shader':b'Shader "Fixture" { SubShader { Pass { HLSLPROGRAM\nfloat4 f(){return 0;}\nENDHLSL } } }',
          'Assets/Game/Content/Data/Collection.asset':b'%YAML 1.1\n--- !u!200 &20000000\nShaderVariantCollection:\n  m_Shaders: []\n',
          'Assets/Game/Content/Other/Unknown.asset':b'%YAML 1.1\n--- !u!114 &11400000\nMonoBehaviour:\n',
          'Assets/Game/Content/Shaders/Opaque.bin':b'unknown contents',
          'Assets/Game/Content/Shaders/Auxiliary.mat':b'%YAML 1.1\n--- !u!21 &2100000\nMaterial:\n',
          'SourceRecovery/Original/source.shader':b'SubProgram "gles" { }'}
        for i,(path,data)in enumerate(values.items()):
            p=project/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);files.append(dict(path=path,bytes=len(data),sha256=sha(data)))
            meta=p.with_name(p.name+'.meta');meta.write_text('fileFormatVersion: 2\nguid: '+str(i+1)*32+'\n');raw=meta.read_bytes();files.append(dict(path=path+'.meta',bytes=len(raw),sha256=sha(raw)))
        owner=project/'recovery-manifest.json';write_json(owner,dict(files=files));asset=files[0]
        mapping=project/'source-map.json';write_json(mapping,dict(sourceToTarget=[dict(source=dict(containerSha256='a'*64,file='CAB-neutral',fileId='0',pathId='-7',logicalPath='original.shader'),target=dict(path=asset['path'],bytes=asset['bytes'],sha256=asset['sha256'],guid='1'*32))]))
        return project,owner,mapping
    def run_case(self,root,project,owner,mapping):
        return classify_project(project,owner,sha(owner.read_bytes()),root/'Report',mapping,sha(mapping.read_bytes()))
    def test_content_scope_mappings_and_declared_identity_do_not_assert_native_success(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();project,owner,mapping=self.fixture(root);before={p:p.read_bytes()for p in project.rglob('*')if p.is_file()};r=self.run_case(root,project,owner,mapping)
            handoff=json.loads((root/'Report/handoff.json').read_text());self.assertEqual(set(handoff),{'schema','items'});self.assertEqual(r['counts'],{'platform-compiled':1,'source-text':1,'unsupported':1,'unknown':1})
            self.assertEqual(len(handoff['items']),4);self.assertEqual(r['scope']['otherSerializedTypesExcluded'],1);compiled=next(x for x in handoff['items']if x['classification']=='platform-compiled');self.assertEqual(compiled['target'],dict(guid='1'*32,localFileID=4800000));self.assertEqual(compiled['source']['targetIdentityEvidence'],'serialized-declaration-only');self.assertIsNone(compiled['source']['entries'][0]['rawSha256'])
            source=next(x for x in handoff['items']if x['classification']=='source-text');self.assertIsNone(source['target']);self.assertEqual(source['runtimeDisposition'],'source-review');self.assertTrue(all(x['nativeCompilation']=='not_run'for x in handoff['items']));self.assertTrue(all(p.read_bytes()==raw for p,raw in before.items()))
    def test_new_default_inventory_holds_shader_evidence_without_moving_assets(self):
        from monkey.unity_handoff import inventory
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();project,owner,_=self.fixture(root);(project/'Docs').mkdir();before={p:p.read_bytes()for p in project.glob('Assets/**/*')if p.is_file()}
            inventory(project,[],dict(status='exported'));report=json.loads((project/'Analysis/Tasks/full-resource-handoff.json').read_text());self.assertEqual(report['shaderPolicy']['defaultRuntimeAdoption'],'hold-all-unverified-shaders')
            binary=next(r for r in report['nativeFiles']if r['path'].endswith('Recovered.asset'));self.assertEqual(binary['shaderEvidence']['classification'],'platform-compiled');self.assertEqual(binary['shaderEvidence']['runtimeDisposition'],'evidence-only');self.assertEqual(binary['shaderEvidence']['nativeCompilation'],'not_run');self.assertTrue(all(p.read_bytes()==raw for p,raw in before.items()))

    def test_tampered_asset_and_frozen_owner_are_rejected(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();project,owner,mapping=self.fixture(root);(project/'Assets/Game/Content/Shaders/Recovered.asset').write_text('changed')
            with self.assertRaisesRegex(ValueError,'Candidate asset differs'):self.run_case(root,project,owner,mapping)
            self.assertFalse((root/'Report').exists())
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();project,owner,mapping=self.fixture(root)
            with self.assertRaisesRegex(ValueError,'manifest SHA differs'):classify_project(project,owner,'0'*64,root/'Report')
    def test_mapping_disagreement_and_aliases_are_explicit_not_first_match(self):
        for ambiguous in [False,True]:
            with self.subTest(ambiguous=ambiguous),tempfile.TemporaryDirectory()as t:
                root=Path(t).resolve();project,owner,mapping=self.fixture(root);d=json.loads(mapping.read_text())
                if ambiguous:
                    other=json.loads(json.dumps(d['sourceToTarget'][0]));other['source']['pathId']='-8';d['sourceToTarget'].append(other)
                else:d['sourceToTarget'][0]['target']['sha256']='0'*64
                write_json(mapping,d);self.run_case(root,project,owner,mapping);r=json.loads((root/'Report/handoff.json').read_text());x=next(x for x in r['items']if x['classification']=='platform-compiled');self.assertEqual(x['source']['mappingStatus'],'ambiguous'if ambiguous else'inconsistent')
    def test_metadata_drift_and_unowned_metadata_are_not_fabricated_identities(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();project,owner,mapping=self.fixture(root);(project/'Assets/Game/Content/Shaders/Recovered.asset.meta').write_text('changed')
            with self.assertRaisesRegex(ValueError,'Candidate asset differs'):self.run_case(root,project,owner,mapping)
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();project,owner,mapping=self.fixture(root);d=json.loads(owner.read_text());d['files']=[x for x in d['files']if x['path']!='Assets/Game/Content/Shaders/Recovered.asset.meta'];write_json(owner,d);self.run_case(root,project,owner,mapping);r=json.loads((root/'Report/handoff.json').read_text());x=next(x for x in r['items']if x['classification']=='platform-compiled');self.assertIsNone(x['target']);self.assertIn('metadata-not-owned',x['source']['diagnostics'])
    def test_source_text_cannot_forge_localid_with_a_non_yaml_line(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();project,owner,mapping=self.fixture(root);file=project/'Assets/Game/Content/Shaders/Source.shader';file.write_bytes(file.read_bytes()+b'\n--- !u!48 &4800000\n');d=json.loads(owner.read_text())
            for row in d['files']:
                if row['path']==file.relative_to(project).as_posix():row.update(bytes=file.stat().st_size,sha256=sha(file.read_bytes()))
            write_json(owner,d);self.run_case(root,project,owner,mapping);x=next(x for x in json.loads((root/'Report/handoff.json').read_text())['items']if x['path'].endswith('Source.shader'));self.assertIsNone(x['target'])


if __name__=='__main__':unittest.main()
