"""Package main-flow behavior, source ownership and full-candidate consumer boundaries."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fixtures import fixture
from monkey.code_graph import facts
from monkey.io import read,load,write_json,sha
from monkey.package import convert_package
from monkey.package_modules import assemble,settings
from monkey.candidate_snapshot import snapshot,verify
from monkey.sources.compiled import ParseError
from monkey.cli import main

RAW=b'var Rules=(function(){function C(){} C.Double=function(x){return x*2;};return C;})();'


def inputs(root):
    config=fixture(root/'source');source=config.parent/'rules.js';source.write_bytes(RAW)
    graph=facts(source);cls=graph['classes'][0];method=graph['methods'][0]
    path=root/'types.json';write_json(path,dict(schemaVersion=1,sourceSha256=sha(RAW),namespace='Game.Domain.Recovered',records=[],modules=[dict(id='Rules',targetClass='Rules',classId=cls['id'],classSha256=cls['sourceSha256'],fields={},methods=[dict(id=method['id'],sha256=method['sourceSha256'],name='Double',parameters=['Number'],returns='Number')])]))
    return config.parent,source,path


class PackageModulesTests(unittest.TestCase):
    def test_public_convert_outputs_code_resources_plans_and_one_consumable_manifest(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as temp:
            root=Path(temp);source,js,contract=inputs(root)
            with contextlib.redirect_stdout(io.StringIO()):
                result=main(['convert','--source',str(source),'--target','unity6','--code-source',str(js),'--module-contract',str(contract),'--out',str(root/'out'),'--offline'])
            self.assertEqual(result,1)
            project=root/'out/UnityProject';report=load(read(root/'out/conversion-result.json'))
            self.assertTrue(report['completed']);m=load(read(project/'manifest.json'))
            self.assertEqual(m['scopeMode'],'whole-input');self.assertEqual(m['codeModules']['implementedMethods'],1)
            cs=project/'Assets/Game/Domain/Recovered/Rules.cs';self.assertIn('return (x * 2d);',cs.read_text())
            self.assertTrue((project/'Assets/Game/Editor/Conversion/import-plan.json').exists())
            self.assertTrue(any(p.suffix=='.png'for p in (project/'Assets/Game/Content').rglob('*')))
            package=load(read(project/'Analysis/Code/package-modules.json'))
            self.assertTrue(package['sourceMembers']);self.assertIn('component-code-bindings.json',package['sourceResourceMappings'])
            self.assertEqual(package['sourceComponentBinding'].split(';')[0],'not_automatically_recovered')
            _,_,files,_=snapshot(project);verify(project,files)
            self.assertTrue(all(row['owner']=='generated'for row in files.values()))
            self.assertIn('RECOVERED-MODULES', (project/'Docs/START-HERE.md').read_text())

    def test_public_frozen_route_reuses_resource_bytes_and_keeps_base_immutable(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as temp:
            root=Path(temp);source,js,contract=inputs(root)
            convert_package(source,'unity6',root/'base',offline=True)
            base=root/'base/UnityProject';raw=read(base/'manifest.json');before=load(raw)
            with contextlib.redirect_stdout(io.StringIO()):
                code=main(['convert','--reuse-candidate',str(base),'--expected-candidate',sha(raw),'--target','unity6','--code-source',str(js),'--module-contract',str(contract),'--out',str(root/'out')])
            self.assertEqual(code,1);self.assertEqual(read(base/'manifest.json'),raw)
            project=root/'out/UnityProject';m=load(read(project/'manifest.json'))
            self.assertEqual(m['resourceBase']['mode'],'exact_frozen_resources_no_redecode')
            draft_paths=set(before['codeDrafts']['files'])
            for row in before['files']:
                if row['path']=='Docs/START-HERE.md' or row['path'] in draft_paths:continue
                self.assertEqual(read(project/row['path']),read(base/row['path']))
            # Recomposition can add original-source aliases in generated draft
            # provenance; the actual C# and resource bytes remain fixed.
            for rel in draft_paths:
                if rel.endswith('.cs'):self.assertEqual(read(project/rel),read(base/rel))
            _,_,files,_=snapshot(project);verify(project,files)

    def test_default_convert_needs_no_type_contract_and_preserves_actual_draft_logic(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as temp:
            root=Path(temp);source,_,_=inputs(root)
            convert_package(source,'unity6',root/'out',offline=True)
            project=root/'out/UnityProject';m=load(read(project/'manifest.json'))
            self.assertNotIn('codeModules',m)
            self.assertGreater(m['codeDrafts']['sourceFiles'],0)
            scripts=list((project/'SourceRecovery/CSharp').rglob('*.cs'))
            self.assertTrue(any('x * 2' in p.read_text() for p in scripts))
            package=load(read(project/m['codeDrafts']['report']))
            self.assertFalse(package['sourceExecuted'])
            _,_,files,_=snapshot(project);verify(project,files)

    def test_same_source_stage_reuses_without_parser_and_refuses_tampered_drafts(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as temp:
            root=Path(temp);source,_,_=inputs(root)
            convert_package(source,'unity6',root/'base',offline=True)
            base=root/'base/UnityProject';raw=read(base/'manifest.json');m=load(raw)
            with patch('monkey.code_drafts.prepare',side_effect=AssertionError('warm stage must not parse or render')):
                result=assemble(base,sha(raw),root/'warm',settings(None))
            self.assertTrue(result['completed'])
            summary=load(read(root/'warm/UnityProject/Analysis/Code/package-csharp-drafts.json'))
            self.assertTrue(all(r['stageReuse']['parserExecuted'] is False for r in summary['sources']))
            script=next((base/'SourceRecovery/CSharp').rglob('*.cs'));script.write_text('// human edit')
            with self.assertRaisesRegex(ParseError,'CANDIDATE_DRIFT'):
                assemble(base,sha(raw),root/'dirty-draft',settings(None))
            self.assertEqual(script.read_text(),'// human edit')

    def test_unrelated_source_wrong_pin_dirty_resource_and_script_collision_fail_closed(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as temp:
            root=Path(temp);source,js,contract=inputs(root)
            convert_package(source,'unity6',root/'base',offline=True)
            base=root/'base/UnityProject';raw=read(base/'manifest.json');pin=sha(raw);spec=settings(js,contract)
            with self.assertRaisesRegex(ParseError,'BASE_CHANGED'):assemble(base,'0'*64,root/'bad-pin',spec)
            self.assertFalse((root/'bad-pin').exists())
            unrelated=root/'other.js';unrelated.write_bytes(RAW+b' ')
            with self.assertRaisesRegex(ParseError,'SOURCE_NOT_OWNED'):assemble(base,pin,root/'foreign',settings(unrelated,contract))
            self.assertFalse((root/'foreign').exists())
            m=load(raw);asset=next(row for row in m['files']if row['path'].endswith('.png'));p=base/asset['path'];original=read(p);p.write_bytes(original+b'x')
            with self.assertRaisesRegex(ParseError,'CANDIDATE_DRIFT'):assemble(base,pin,root/'dirty',spec)
            self.assertEqual(read(p),original+b'x');p.write_bytes(original)
            collision=base/'Assets/Game/Domain/Recovered/Rules.cs';collision.parent.mkdir(parents=True);collision.write_text('// human code')
            m['files'].append(dict(path=collision.relative_to(base).as_posix(),bytes=collision.stat().st_size,sha256=sha(read(collision)),owner='manual'));write_json(base/'manifest.json',m)
            with self.assertRaisesRegex(ParseError,'COLLISION'):assemble(base,sha(read(base/'manifest.json')),root/'collision',spec)
            self.assertEqual(collision.read_text(),'// human code');self.assertFalse((root/'collision/UnityProject/manifest.json').exists())


if __name__=='__main__':unittest.main()

class NativeResourceFreezeTests(unittest.TestCase):
    def test_freeze_includes_proven_native_additions_retains_settings_and_rejects_unlisted_code(self):
        from monkey.package_modules import freeze_native_resources
        with tempfile.TemporaryDirectory(dir='/private/tmp') as temp:
            root=Path(temp);source,_,_=inputs(root);convert_package(source,'unity6',root/'base',offline=True)
            base=root/'base/UnityProject';pin=sha(read(base/'manifest.json'))
            added=base/'Assets/Game/Content/Prefabs/Test/Native.prefab';added.parent.mkdir(parents=True,exist_ok=True);added.write_bytes(b'fixture saved identity only; no Unity proof claimed')
            (base/'ProjectSettings/EditorSettings.asset').write_bytes(b'fixture editor state')
            (base/'ProjectSettings/ProjectVersion.txt').write_bytes(b'm_EditorVersion: 6000.6.2f1\nm_EditorVersionWithRevision: fixture\n')
            rb=base/'Analysis/Readback/editor-readback.json';rb.parent.mkdir(parents=True,exist_ok=True)
            write_json(rb,dict(importPlanSha256=sha(read(base/'Assets/Game/Editor/Conversion/import-plan.json')),sourceManifestSha256=load(read(base/'Assets/Game/Editor/Conversion/import-plan.json')).get('sourceManifestSha256'),status='imported',unityVersion='6000.6.2f1',missingScripts=0,editableRoundtrip=True,sceneReopened=True,nativeScope='source-node-subset',sourceGraphVerification='saved-source-node-subset',nativeFiles=[dict(path=added.relative_to(base).as_posix(),sha256=sha(read(added)))]))
            result=freeze_native_resources(base,pin,sha(read(rb)),root/'frozen')
            self.assertEqual(result['nativeFiles'],1);self.assertEqual(read(root/'frozen'/added.relative_to(base)),read(added))
            _,m,files,_=snapshot(root/'frozen');verify(root/'frozen',files)
            self.assertEqual(files['ProjectSettings/EditorSettings.asset']['owner'],'retained')
            self.assertEqual(m['resourceFreeze']['counts']['native'],1)
            self.assertEqual(m['resourceFreeze']['sourceAcceptance'],'not_granted')
            self.assertEqual(result['workflowStatus'],'partial')
            self.assertTrue(result['validationGaps'])
            self.assertTrue((root/'frozen/Analysis/Code/resource-source-verification.json').is_file())
            extra=base/'Assets/unknown.cs';extra.write_text('// unsupported source')
            with self.assertRaisesRegex(ParseError,'UNOWNED'):freeze_native_resources(base,pin,sha(read(rb)),root/'unknown')
            self.assertEqual(extra.read_text(),'// unsupported source')
