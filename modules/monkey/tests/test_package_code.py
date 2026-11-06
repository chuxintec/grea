import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from fixtures import fixture, normal, FRAME, PREFAB, FONT
from monkey.io import write_json,load,read,sha
from monkey.sources.code import modules
from monkey.sources.compiled import ParseError
from monkey.package import convert_package, resume_package
from monkey.package_code import declaration,prepare
from monkey.cli import main

RF='rf-numeric-meter'
SCRIPT=('cc._RF.push({},"'+RF+'","Meter");(function(Base){function M(){};return inherit(M,Base),'
        'M.prototype.set=function(v){this.value=v;},M.prototype.get=function(){return this.value;},'
        'M.prototype.delay=async function(v){this.value=v;},M;})(cc.Label);cc._RF.pop();').encode()


def numeric_fixture(root, extra=None):
    config=fixture(root/'source')
    prefab=[{'__type__':'cc.Prefab','data':{'__id__':1}},
            dict(__type__='cc.Node',_name='Meter',_parent=None,_children=[],_active=True,_components=[{'__id__':2}],
                 _contentSize={'width':210,'height':180},_anchorPoint={'x':.5,'y':.5},_trs=[0,0,0,0,0,0,1,1,1,1]),
            dict(__type__=RF,node={'__id__':1},_string='A',_fontSize=20,_lineHeight=20,**{'_N$file':{'__uuid__':FONT}})]
    if extra:prefab[-1].update(extra)
    write_json(config.parent/'import'/PREFAB[:2]/(PREFAB+'.a.json'),normal(prefab))
    font=dict(name='OriginalFont',fontSize=20,spriteFrame={'__uuid__':FRAME},_fntConfig=dict(fontSize=20,commonHeight=20,
        fontDefDictionary={'65':dict(rect=dict(x=0,y=0,width=2,height=1),xOffset=0,yOffset=0,xAdvance=2)},kerningDict={}))
    write_json(config.parent/'import'/FONT[:2]/(FONT+'.a.json'),normal([dict(__type__='cc.BitmapFont',**font)]))
    (config.parent/'game.js').write_bytes(SCRIPT)
    found,error=modules(SCRIPT);assert len(found)==1
    contract=root/'numeric.json'
    write_json(contract,dict(schemaVersion=1,kind='numeric-call-subdomain-v1',moduleName='Meter',registrationId=RF,moduleSha256=found[0]['sha256'],numericField='value'))
    return config.parent,contract


class PackageCodeTests(unittest.TestCase):
    def test_js_public_export_keeps_esm_boundary_and_formats_actual_script(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp).resolve();source,contract=numeric_fixture(root)
            with contextlib.redirect_stdout(io.StringIO()):
                main(['convert','--source',str(source),'--target','cocos38','--numeric-code-contract',str(contract),'--cocos-code-language','js','--format','grea','--out',str(root/'out')])
            project=root/'out/CocosProject';manifest=load(read(project/'manifest.json'))
            self.assertEqual(manifest['codeEmission']['language'],'js')
            self.assertEqual(manifest['codeEmission']['scriptPath'],'assets/Game/Presentation/UI/Meter.js')
            self.assertEqual(load(read(project/'assets/package.json')),{'type':'module'})
            meta=load(read(project/'assets/Game/Presentation/UI/Meter.js.meta'))
            self.assertEqual((meta['importer'],meta['ver']),('javascript','4.0.24'))
            self.assertEqual(meta['uuid'],manifest['codeEmission']['scriptUuid'])

    def test_one_public_command_discovers_emits_binds_and_formats_both_targets(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp).resolve();source,contract=numeric_fixture(root)
            with contextlib.redirect_stdout(io.StringIO()):
                result=main(['convert','--source',str(source),'--target','both','--numeric-code-contract',str(contract),'--format','grea','--out',str(root/'out')])
            self.assertEqual(result,1)
            report=load(read(root/'out/conversion-result.json'));self.assertTrue(report['completed'])
            self.assertEqual((report['codeEmission']['implementedMethods'],report['codeEmission']['pendingMethods']),(2,1))
            for target,plan_rel,code_rel in [('UnityProject','Assets/Game/Editor/Conversion/import-plan.json','Assets/Game/Presentation/UI/Meter.cs'),('CocosProject','extensions/monkey-import/import-plan.json','assets/Game/Presentation/UI/Meter.ts')]:
                project=root/'out'/target;plan=load(read(project/plan_rel));manifest=load(read(project/'manifest.json'))
                bound=[c for c in plan['components']if c.get('codeClassName')]
                self.assertEqual(len(bound),1);self.assertTrue(bound[0]['convertible'])
                self.assertEqual(bound[0]['sourceScriptIdentity'],RF);self.assertEqual(bound[0]['numericMethods'],dict(setter='set',getter='get'))
                self.assertEqual(manifest['codeEmission']['scriptPath'],code_rel)
                self.assertTrue((project/code_rel).is_file());self.assertTrue((project/(code_rel+'.meta')).is_file())
                self.assertIn('this.value = v;',read(project/code_rel).decode())
                self.assertNotIn('delay(',read(project/code_rel).decode())
                self.assertEqual(manifest['validation']['editor'],'not_run')
                for row in manifest['files']:self.assertEqual(sha(read(project/row['path'])),row['sha256'])
            # Refuse a future resume before archiving or changing either candidate.
            before=read(root/'out/UnityProject/manifest.json')
            with self.assertRaisesRegex(ParseError,'FRESH_ONLY'):resume_package(root/'out',root/'unused.json')
            self.assertEqual(read(root/'out/UnityProject/manifest.json'),before)

    def test_changed_source_duplicate_registration_and_js_binding_fail_closed(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp).resolve();source,contract=numeric_fixture(root);spec=declaration(contract)
            found,_=modules(SCRIPT);found[0]['sourceId']='original-module'
            with self.assertRaisesRegex(ParseError,'MODULE'):prepare(found*2,spec,'test',root/'duplicates')
            self.assertFalse((root/'duplicates').exists())
            spec['data']['moduleSha256']='0'*64
            with self.assertRaisesRegex(ParseError,'SOURCE_CHANGED'):prepare(found,spec,'test',root/'changed')
            self.assertFalse((root/'changed').exists())
            self.assertEqual(declaration(contract,'js')['language'],'js')
            with self.assertRaises(ParseError):declaration(contract,'lua')
            self.assertEqual(read(source/'game.js'),SCRIPT)

    def test_unknown_serialized_business_field_stops_declared_binding_not_baseline_success(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp).resolve();source,contract=numeric_fixture(root,dict(unmodeledBusiness=42))
            with self.assertRaises(ParseError):convert_package(source,'both',root/'out',code_contract=contract)
            result=load(read(root/'out/conversion-result.json'));self.assertFalse(result['completed']);self.assertEqual(result['workflowStatus'],'failed')
            self.assertEqual(result['structuredRecovery']['reason'],'CODE_LABEL_CUSTOM_FIELDS')


if __name__=='__main__':unittest.main()
