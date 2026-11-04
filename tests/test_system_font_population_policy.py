import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from monkey.prefab_system_fonts import prepare, prepare_static_coretext_sdf_plan


def fixture():
    label_id='synthetic-label'
    ir={'sourceProfile':'cocos-2.4.15-bundle','sourceManifestSha256':'a'*64,'components':[
        {'sourceId':label_id,'type':'cc.Label','systemFont':True,'font':None,'text':'A中',
         'fontFamily':'Arial','fontFamilyEvidence':'synthetic','fontSize':24}]}
    rows=[];evidence=[];files=[]
    for char,family,fallback in [('A','Arial',False),('中','Example Sans',True)]:
        url='/synthetic/'+family+'.ttc';postscript=family.replace(' ','')+'-Regular'
        rows.append(dict(character=char,scalarValue=ord(char),codepoint=f'U+{ord(char):04X}',
                         fallback=fallback,family=family,styleName='Regular',postScriptName=postscript,
                         systemFontFileUrl=url,variationAxes={},requiredForVisualText=True,glyphCovered=True))
        evidence.append(dict(family=family,styleName='Regular',postScriptName=postscript,
                             systemFontFileUrl=url,exactPostScriptFaceCount=1,exactPostScriptFaces=[{'index':0}]))
        files.append(dict(path=url,status='inspected',fileSha256='f'*64,fileSizeBytes=100))
    receipt=dict(schema='monkey-macos-system-font-resolution/1',status='resolved',targetOS='macOS',
        targetOSVersion='synthetic',visualEquivalent=False,
        sourceDefaultEvidence=dict(sourceProfile=ir['sourceProfile'],sourceVersion='2.4.15',
            sourceFontFamilyDefault='Arial',sourceSystemFontDefault=True,sourceOSIdentityVerified=False),
        sourceSample=dict(sourceProfile=ir['sourceProfile'],sourceVersion='2.4.15',sourceManifestSha256='a'*64,
            normalizedSystemFontLabelCount=1,frozenInputs=dict(ir=dict(path='/synthetic/ir.json',sha256='b'*64),
            sourceManifest=dict(path='/synthetic/source.json',sha256='a'*64)),
            sourceFamilyBindings=[dict(sourceLabelId=label_id,requestedFamily='Arial',familyBindingSource='synthetic')]),
        labels=[dict(targetLabelId=label_id,text='A中',pointSize=24,requestedFamily='Arial',
            resolvedPrimaryFamily='Arial',resolvedPrimaryStyleName='Regular',resolvedPrimaryPostScriptName='Arial-Regular',
            resolvedPrimarySystemFontFileUrl='/synthetic/Arial.ttc',resolvedPrimaryVariationAxes={},unicodeScalars=rows)],
        coreTextToPhysicalFaceEvidence=evidence,resolvedFontFiles=files)
    return ir,receipt


class SystemFontPopulationPolicyTests(unittest.TestCase):
    def test_exact_physical_fallback_can_be_explicitly_static_without_font_substitution(self):
        ir,receipt=fixture()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory).resolve()/'resolution.json'
            def run():
                raw=json.dumps(receipt).encode();path.write_bytes(raw);pin=hashlib.sha256(raw).hexdigest()
                return prepare(ir,'b'*64,path,pin),pin
            default,_=run()
            self.assertEqual(default.status,'prepared',default.record)
            self.assertTrue(all(f['populationMode']=='DynamicOS' for f in default.record['systemFonts']['fonts']))
            receipt['unityPopulationPolicy']='coretext-static-fallbacks-v1'
            forced,pin=run()
            self.assertEqual(forced.status,'prepared',forced.record)
            fonts=forced.record['systemFonts']['fonts']
            primary=next(f for f in fonts if f['role']=='primary')
            fallback=next(f for f in fonts if f['role']=='fallback')
            self.assertEqual(primary['populationMode'],'DynamicOS')
            self.assertEqual(fallback['populationMode'],'StaticSDFRequired')
            self.assertEqual(fallback['familyName'],'Example Sans')
            self.assertEqual(fallback['targetPostScriptName'],'ExampleSans-Regular')
            self.assertEqual(fallback['targetSystemFontFileSha256'],'f'*64)
            self.assertEqual(fallback['matchingPhysicalFaces'],[{'index':0}])
            plan=prepare_static_coretext_sdf_plan(ir,'b'*64,path,pin)
            self.assertEqual(plan.status,'prepared',plan.record)
            self.assertEqual(plan.record['systemFonts'][0]['assetId'],fallback['assetId'])
            self.assertEqual(plan.record['systemFonts'][0]['requiredUnicode'],[ord('中')])

    def test_unknown_population_policy_is_rejected(self):
        ir,receipt=fixture();receipt['unityPopulationPolicy']='guess-another-font'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory).resolve()/'resolution.json';raw=json.dumps(receipt).encode();path.write_bytes(raw)
            result=prepare(ir,'b'*64,path,hashlib.sha256(raw).hexdigest())
            self.assertEqual(result.status,'needs_action')
