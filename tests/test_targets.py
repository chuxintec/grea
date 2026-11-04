import tempfile
import unittest
from pathlib import Path
from monkey.io import read, load, write_json
from monkey.sources.bundle import inspect
from monkey.sources.compiled import ParseError
from monkey.normalize import normalize, open_texture
from monkey.targets.unity import plan, export, verify, handoff
from fixtures import fixture, FRAME, PREFAB, normal


class TargetTests(unittest.TestCase):
    def test_native_candidate_determinism_conflicts_and_missing_editor(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();config=fixture(root/'source')
            inspect(config,[0],root/'inspect');normalize(root/'inspect/source-manifest.json',root/'ir')
            plan(root/'ir/ir.json','project-a',root/'plan')
            a=export(root/'plan/plan.json',root/'unity');b=export(root/'plan/plan.json',root/'repeat')
            instruction=load(read(root/'unity/Assets/Game/Editor/Conversion/import-plan.json'))
            self.assertIsNone(instruction['toggleBinding'])
            self.assertIs(instruction['toggleBindingPresent'],False)
            self.assertEqual(a['files'],b['files'])
            self.assertTrue(any(f['path']=='Packages/manifest.json' for f in a['files']))
            result=verify(root/'unity',root/'verified');self.assertEqual(result['staticValidation'],'pass')
            result=verify(root/'unity',root/'editor','editor')
            self.assertEqual(result['editorValidation'],'not_run');self.assertTrue(any(d['code']=='EDITOR_NOT_RUN' for d in result['diagnostics']))
            source=root/'unity/Packages/manifest.json';source.write_text('{}')
            result=verify(root/'unity',root/'conflict')
            self.assertEqual(result['staticValidation'],'conflict')
            self.assertTrue(any(d['location']=='Packages/manifest.json' for d in result['diagnostics']))
            with self.assertRaises(ParseError):export(root/'plan/plan.json',root/'unity')
            handoff(root/'unity',root/'handoff');self.assertTrue((root/'handoff/HANDOFF.md').is_file())

    def test_explicit_cross_bundle_redirect_and_inline_unknowns(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();config=fixture(root/'source');c=load(read(config))
            dep=root/'dependency';dep.mkdir()
            write_json(dep/'config.json',dict(name='alias',uuids=[FRAME],deps=['synthetic'],redirect=[0,0],
                                             paths={},types=[],versions={},packs={}))
            m=inspect(dep/'config.json',[0],root/'inspect',[config])
            self.assertEqual(m['diagnostics'],[])
            ir=normalize(root/'inspect/source-manifest.json',root/'ir')
            self.assertEqual(len(ir['spriteFrames']),1)
            self.assertEqual(ir['aliases']['alias:'+FRAME],'synthetic:'+FRAME)
            # Inlined unsupported components preserve precise ordinal source locations.
            path=root/'source/import/00'/(PREFAB+'.a.json');doc=load(read(path))
            # Field order from fixture: node _components sits at class property index 4.
            node_values=doc[5][1];keys=doc[3][1][1];slot=keys.index('_components')+1
            node_values[slot].append({'__type__':'Example.Business','node':{'__id__':1},'rule':42})
            write_json(path,doc)
            inspect(config,[2],root/'second-inspect')
            ir=normalize(root/'second-inspect/source-manifest.json',root/'second-ir')
            component=next(c for c in ir['components'] if c['type']=='Example.Business')
            self.assertTrue(component['sourceId'].endswith('#1/components/2'))
            self.assertTrue(any(d['sourceId']==component['sourceId'] for d in ir['diagnostics']))

    def test_astc_explicit_provider_header_and_channel_order(self):
        raw=bytes.fromhex('13aba15c040401040000040000010000fcfdffffffffffffffff00000000ffff')
        try:
            image=open_texture(raw,'.astc')
        except ParseError as error:
            if error.code=='DEPENDENCY_MISSING':self.skipTest('Optional pinned ASTC provider not installed')
            raise
        with image:
            self.assertEqual(image.size,(4,4));self.assertEqual(image.getpixel((3,3)),(255,0,0,255))
        for invalid in (raw[:-1],b'bad',raw[:4]+b'\x00'+raw[5:]):
            with self.assertRaises(ParseError):open_texture(invalid,'.astc')

    def test_plan_refuses_tampered_assets_or_instruction(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();config=fixture(root/'source')
            inspect(config,[0],root/'inspect');normalize(root/'inspect/source-manifest.json',root/'ir')
            plan(root/'ir/ir.json','project-a',root/'plan')
            p=root/'plan/plan.json';d=load(read(p));d['namespace']='edited';write_json(p,d)
            with self.assertRaises(ParseError) as caught:export(p,root/'bad')
            self.assertEqual(caught.exception.code,'PLAN_CHANGED');self.assertFalse((root/'bad').exists())
            image=next((root/'ir/assets').glob('*.png'));image.write_bytes(b'edited')
            with self.assertRaises(ParseError):plan(root/'ir/ir.json','project-a',root/'bad-plan')

if __name__=='__main__':unittest.main()
