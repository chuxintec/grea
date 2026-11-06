import tempfile
import unittest
from pathlib import Path
from monkey.assets.bitmap import normalize_font,single_line
from monkey.sources.compiled import ParseError
from monkey.normalize import component_ir,node_ir,normalize
from monkey.sources.bundle import inspect
from monkey.targets.unity import plan,export,verify
from monkey.io import load,read,write_json,sha
from fixtures import fixture,FRAME,FONT,custom


class BitmapAndUiTests(unittest.TestCase):
    def font(self):
        return normalize_font(dict(fontSize=20,_fntConfig=dict(fontSize=20,commonHeight=25,
            fontDefDictionary={'65':dict(rect=dict(x=1,y=2,width=5,height=7),xOffset=-1,yOffset=3,xAdvance=4),
                               '60000':dict(rect=dict(x=6,y=2,width=5,height=7),xOffset=0,yOffset=-2,xAdvance=5)},
            kerningDict={str(((60000<<16)|65)-(1<<32)):-2})), 'font','atlas',[16,16])

    def test_colored_glyph_metric_origin_and_signed_kerning(self):
        f=self.font();self.assertEqual(f['glyphs'][0]['rect'],[1,7,5,7])
        self.assertEqual(f['glyphs'][0]['metrics'],[5,7,-1,17,4])
        self.assertEqual(f['kernings'],[dict(first=60000,second=65,advance=-2)])
        self.assertEqual(f['descent'],0);self.assertTrue(f['colored'])
        probe=single_line(f,chr(60000)+'A',10)
        self.assertEqual(probe['boxes'][1]['x'],0)
        self.assertEqual(probe['advance'],2.5)
        self.assertGreater(probe['inkRight'],probe['advance']-1)
        with self.assertRaises(ParseError):single_line(f,'missing',20)
        bad=dict(fontSize=20,_fntConfig=dict(fontSize=20,commonHeight=25,fontDefDictionary={
            '65':dict(rect=dict(x=15,y=2,width=5,height=7),xOffset=0,yOffset=0,xAdvance=4)}))
        with self.assertRaises(ParseError):normalize_font(bad,'bad','atlas',[16,16])

    def test_native_padded_quad_retains_exact_ink_and_rejects_invalid_proof(self):
        from monkey.targets.common import native_ink_box
        # A half-size 5x7 source glyph with one atlas pixel of TMP padding.
        ink=native_ink_box(dict(unicode=65,left=-1,top=9,width=3.5,height=4.5,quadPadding=.5))
        self.assertEqual(ink,dict(unicode=65,left=-.5,top=8.5,width=2.5,height=3.5))
        with self.assertRaises(ParseError):native_ink_box(dict(unicode=65,left=0,top=0,width=1,height=1,quadPadding=2))
        with self.assertRaises(ParseError):native_ink_box(dict(unicode=65,left=0,top=0,width=1,height=1,quadPadding=float('nan')))

    def test_observed_ui_fields_and_default_identity(self):
        namespace='b:prefab'
        label,gaps=component_ir(namespace,2,dict(__type__='cc.Label',node={'__id__':1},_N='{ignored}',
            **{'_N$horizontalAlign':2,'_N$verticalAlign':1,'_fontSize':36,'_styleFlags':1}))
        self.assertEqual((label['horizontalAlign'],label['verticalAlign']),(2,1));self.assertTrue(label['bold'])
        node,gaps=node_ir(namespace,1,dict(__type__='cc.Node',_name='identity'))
        self.assertEqual(node['position'],[0,0,0]);self.assertEqual(gaps,[])
        widget,gaps=component_ir(namespace,3,dict(__type__='cc.Widget',node={'__id__':1},_alignFlags=45))
        self.assertEqual(widget['margins'],[0]*4);self.assertEqual(gaps,[])
        mask,gaps=component_ir(namespace,4,dict(__type__='cc.Mask',node={'__id__':1},**{'_N$alphaThreshold':0}))
        self.assertEqual(mask['maskType'],0);self.assertEqual(gaps,[])

    def test_font_native_directory_evidence_binding_and_grouped_handoff(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();config=fixture(root/'source')
            # Synthetic binary is a path-resolution fixture, not a valid font claim.
            directory=root/'source/native/00'/(FONT+'.f');directory.mkdir(parents=True)
            (directory/'example.ttf').write_bytes(b'not-a-real-font')
            imported=root/'source/import/00'/(FONT+'.a.json')
            write_json(imported,custom('cc.TTFFont',{}))
            # Use normal compiled property fields so _native is a native asset property.
            from fixtures import normal
            write_json(imported,normal([dict(__type__='cc.TTFFont',_native='example.ttf')]))
            c=load(read(config));c['versions']['native'] += [3,'f'];write_json(config,c)
            evidence=root/'evidence.txt';evidence.write_text('explicit font-selection source evidence')
            inspect(config,[2],root/'inspect',evidence_sources=[evidence])
            manifest=load(read(root/'inspect/source-manifest.json'))
            self.assertTrue(next(a for a in manifest['assets'] if a['key']==FONT)['native'].endswith('/example.ttf'))
            normalize(root/'inspect/source-manifest.json',root/'ir')
            ir=load(read(root/'ir/ir.json'));label=next(c for c in ir['components'] if c['type']=='cc.Label')
            # Existing explicit fonts cannot be overwritten by a declared system-font policy.
            bind=dict(sourceManifestSha256=sha(read(root/'inspect/source-manifest.json')),evidenceSha256=sha(read(evidence)),
                      offset=0,bytes=8,labelFonts=[dict(component=label['sourceId'],font=label['font'])])
            write_json(root/'binding.json',bind)
            with self.assertRaises(ParseError) as caught:plan(root/'ir/ir.json','test',root/'bad',root/'binding.json')
            self.assertEqual(caught.exception.code,'BINDING_REPLACES_EXPLICIT_FONT')
            plan(root/'ir/ir.json','test',root/'plan');export(root/'plan/plan.json',root/'unity')
            tasks=load(read(root/'unity/Analysis/Tasks/handoff.json'))['tasks']
            self.assertTrue(all('rootCause' in t and 'module' in t for t in tasks))

    def test_source_backed_font_binding_and_stage_integrity(self):
        from test_ttf import sfnt
        import struct
        from fixtures import PREFAB
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();config=fixture(root/'source')
            directory=root/'source/native/00'/(FONT+'.f');directory.mkdir(parents=True)
            # Only a cmap preflight fixture; this does not claim rasterizer acceptance.
            sub=struct.pack('>16H',4,32,0,4,4,1,0,65,65535,0,65,65535,65472,1,0,0)
            (directory/'example.ttf').write_bytes(sfnt(sub))
            from fixtures import normal
            write_json(root/'source/import/00'/(FONT+'.a.json'),normal([dict(__type__='cc.TTFFont',_native='example.ttf')]))
            c=load(read(config));c['versions']['native'] += [3,'f'];write_json(config,c)
            prefab_path=root/'source/import/00'/(PREFAB+'.a.json');doc=load(read(prefab_path))
            label_keys=doc[3][3][1]
            doc[5][3][label_keys.index('_N$file')+1]=None
            doc[5][3][label_keys.index('_string')+1]='A';write_json(prefab_path,doc)
            evidence=root/'evidence.txt';evidence.write_text('explicit font binding proof')
            inspect(config,[2,3],root/'inspect',evidence_sources=[evidence])
            normalize(root/'inspect/source-manifest.json',root/'ir')
            ir=load(read(root/'ir/ir.json'));label=next(c for c in ir['components'] if c['type']=='cc.Label')
            bind=dict(sourceManifestSha256=sha(read(root/'inspect/source-manifest.json')),evidenceSha256=sha(read(evidence)),
                      offset=0,bytes=8,labelFonts=[dict(component=label['sourceId'],font='synthetic:'+FONT,syntheticBold=False)])
            write_json(root/'binding.json',bind)
            result=plan(root/'ir/ir.json','test',root/'plan',root/'binding.json')
            self.assertTrue(next(c for c in result['components'] if c['type']=='cc.Label')['convertible'])
            export(root/'plan/plan.json',root/'unity');self.assertTrue((root/'unity/Analysis/Mappings/font-bindings.json').is_file())
            # Synthetic readback input must never turn a wrong-font claim into Editor pass.
            write_json(root/'unity/Analysis/Readback/editor-readback.json',dict(status='imported',unityVersion='6000.6.2f1',missingScripts=0,
                diagnostics=[],nativeFiles=[],sprites=[],nodes=[],
                fonts=[dict(id='synthetic:'+FONT,guid='original-font')],
                labels=[dict(sourceId=label['sourceId'],text='A',fontGuid='substituted-font',fontSize=40,allCharactersPresent=True)]))
            verified=verify(root/'unity',root/'readback-contract','editor')
            self.assertEqual(verified['editorValidation'],'fail')
            self.assertTrue(any(d['code']=='LABEL_FONT_READBACK_MISMATCH' for d in verified['diagnostics']))
            write_json(root/'ir/ir.json',dict(ir,sourceProfile='edited'))
            with self.assertRaises(ParseError) as caught:plan(root/'ir/ir.json','test',root/'bad')
            self.assertEqual(caught.exception.code,'STAGE_DOCUMENT_CHANGED')
            source=root/'inspect/source-manifest.json';m=load(read(source));m['diagnostics']=[];m['selection']=[0];write_json(source,m)
            with self.assertRaises(ParseError) as caught:normalize(source,root/'bad-normalize')
            self.assertEqual(caught.exception.code,'STAGE_DOCUMENT_CHANGED')

if __name__=='__main__':unittest.main()
