"""Pinned continuation preserves owned inputs and refuses stale identities."""
import contextlib
import copy
import io as streams
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from monkey import io
from monkey.prefab_static_continuation import SCHEMA, prepare
import test_prefab_static_animation_continuation as animation_fixture


class StaticContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name).resolve()
        fixture=animation_fixture.StaticAnimationContinuationTests();fixture.setUp()
        manifest=copy.deepcopy(fixture.source_manifest)
        manifest.update(schemaVersion=1,inputs=[],sourceProfile='cocos-2.4.15-bundle',sourceVersion='2.4.15')
        self.manifest=self.root/'source/source-manifest.json'
        self.manifest.parent.mkdir();io.write_json(self.manifest,manifest)
        self.ir=self.root/'ir/ir.json';self.ir.parent.mkdir()
        ir=copy.deepcopy(fixture.ir)
        ir.update(sourceProfile=manifest['sourceProfile'],sourceManifestPath=str(self.manifest),
                  sourceManifestSha256=self.pin(self.manifest)['sha256'])
        io.write_json(self.ir,ir);io.finish(self.ir.parent,ir)
        self.plan=self.root/'parent/plan.json';self.plan.parent.mkdir()
        plan=copy.deepcopy(fixture.plan)
        plan.update(schemaVersion=1,sourceProfile=manifest['sourceProfile'],sourceManifestPath=str(self.manifest),
                    projectLayout='monkey-project/2.0.0',
                    nodes=[{'sourceId':fixture.node_id,'name':'Neutral','parent':None}],
                    assets=[],diagnostics=[],galleryOnly=False,textures=[],bitmapFonts=[],
                    sourceManifestSha256=self.pin(self.manifest)['sha256'],sourceIrSha256=self.pin(self.ir)['sha256'])
        (self.plan.parent/'unchanged.png').write_bytes(b'frozen decoded texture')
        io.write_json(self.plan,plan);io.finish(self.plan.parent,plan)
        self.request=self.root/'request.json'
        self.spec={'schema':SCHEMA,'schemaVersion':1,'plan':self.pin(self.plan),
                   'planManifest':self.pin(self.plan.parent/'manifest.json'),'ir':self.pin(self.ir),
                   'sourceManifest':self.pin(self.manifest),'families':['materials','animation']}
        self.write_request()

    @staticmethod
    def pin(path):
        return {'path':str(path),'sha256':io.sha(path.read_bytes())}

    def write_request(self):
        io.write_json(self.request,self.spec)
        self.request_sha=io.sha(self.request.read_bytes())

    def run_prepare(self):
        return prepare(self.request,self.request_sha,self.root/'new')

    def test_real_family_dispatch_clones_payload_and_preserves_partial_curves(self):
        before={p:p.read_bytes()for p in (self.plan,self.ir,self.manifest,self.plan.parent/'unchanged.png')}
        result=self.run_prepare()
        continued=io.stage_document(Path(result['planPath']))
        self.assertEqual(continued['animations'],io.stage_document(self.plan)['animations'])
        self.assertTrue(continued['staticAnimationBindingsEnabled'])
        self.assertNotIn('staticCompletion',continued)
        self.assertFalse(continued['animations'][0]['convertible'])
        self.assertEqual(continued['staticContinuation']['parentPlanSha256'],self.pin(self.plan)['sha256'])
        self.assertEqual((Path(result['planPath']).parent/'unchanged.png').read_bytes(),b'frozen decoded texture')
        self.assertEqual(result['familyResults']['animation']['componentCount'],1)
        self.assertLess(len(json.dumps(result['familyResults'])),1200)
        self.assertEqual(result['native'],'not_run')
        for path,raw in before.items():self.assertEqual(path.read_bytes(),raw)

    def test_stale_request_and_input_pins_refuse_before_output(self):
        with self.assertRaisesRegex(ValueError,'STATIC_CONTINUATION_REQUEST_HASH'):
            prepare(self.request,'0'*64,self.root/'new')
        self.ir.write_bytes(self.ir.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'STATIC_CONTINUATION_INPUT_CHANGED'):self.run_prepare()
        self.assertFalse((self.root/'new').exists())

    def test_changed_owned_payload_is_rejected(self):
        (self.plan.parent/'unchanged.png').write_bytes(b'edited')
        with self.assertRaises(ValueError):self.run_prepare()

    def test_source_identity_mismatch_is_rejected(self):
        plan=io.stage_document(self.plan);plan['sourceIrSha256']='0'*64
        io.write_json(self.plan,plan);io.finish(self.plan.parent,plan)
        self.spec['plan']=self.pin(self.plan)
        self.spec['planManifest']=self.pin(self.plan.parent/'manifest.json');self.write_request()
        with self.assertRaisesRegex(ValueError,'STATIC_CONTINUATION_SOURCE_MISMATCH'):self.run_prepare()

    def test_output_create_only_and_overlap(self):
        self.run_prepare()
        with self.assertRaisesRegex(ValueError,'OUTPUT_EXISTS'):self.run_prepare()
        with self.assertRaisesRegex(ValueError,'OUTPUT_OVERLAP'):
            prepare(self.request,self.request_sha,self.plan.parent/'nested')

    def test_midflight_input_change_is_detected(self):
        from monkey.prefab_static_animation_continuation import prepare as real
        def mutate(*args,**kwargs):
            result=real(*args,**kwargs)
            self.manifest.write_bytes(self.manifest.read_bytes()+b' ')
            return result
        with patch('monkey.prefab_static_animation_continuation.prepare',side_effect=mutate):
            with self.assertRaisesRegex(ValueError,'STATIC_CONTINUATION_INPUT_CHANGED'):self.run_prepare()
        self.assertFalse((self.root/'new/manifest.json').exists())

    def test_runtime_requires_explicit_absolute_root(self):
        self.spec['families']=['spine']
        sdk=self.root/'sdk.json';io.write_json(sdk,{})
        self.spec['spineRuntime']={'manifest':self.pin(sdk),'assetsRoot':None};self.write_request()
        with self.assertRaisesRegex(ValueError,'STATIC_CONTINUATION_RUNTIME_INVALID'):self.run_prepare()

    def test_layout_dispatch_requires_pinned_engine_inputs_even_without_matching_components(self):
        self.spec['families']=['layout'];self.write_request()
        with self.assertRaisesRegex(ValueError,'ENGINE_EVIDENCE_INVALID'):self.run_prepare()
        engine=self.root/'engine/source.js';engine.parent.mkdir();engine.write_bytes(b'bounded evidence fixture')
        self.spec['sourceEngineEvidence']={'sourceVersion':'2.4.15','files':[
            dict(logicalPath='components/engine.js',**self.pin(engine))]}
        self.write_request();before=self.plan.read_bytes()
        result=self.run_prepare()
        self.assertEqual(result['familyResults']['layout']['selectedComponents'],0)
        self.assertEqual(self.plan.read_bytes(),before)

    def test_changed_engine_or_unsafe_identity_is_refused_before_output(self):
        self.spec['families']=['layout']
        engine=self.root/'engine/source.js';engine.parent.mkdir();engine.write_bytes(b'original')
        row=dict(logicalPath='../engine.js',**self.pin(engine))
        self.spec['sourceEngineEvidence']={'sourceVersion':'2.4.15','files':[row]};self.write_request()
        with self.assertRaisesRegex(ValueError,'ENGINE_EVIDENCE_INVALID'):self.run_prepare()
        row['logicalPath']='engine.js';self.write_request();engine.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'INPUT_CHANGED'):self.run_prepare()
        self.assertFalse((self.root/'new').exists())

    def test_rendering_requires_explicit_spine_family_and_pinned_runtime(self):
        for value in ('true', 1, None, True):
            self.spec['spineRendering']=value;self.write_request()
            with self.assertRaisesRegex(ValueError,'STATIC_CONTINUATION_RENDERING_INVALID'):self.run_prepare()
        self.spec['families']=['spine'];self.spec['spineRendering']=True;self.write_request()
        with self.assertRaisesRegex(ValueError,'STATIC_CONTINUATION_RENDERING_INVALID'):self.run_prepare()

    def test_owned_manifest_change_cannot_redefine_frozen_payloads(self):
        (self.plan.parent/'unchanged.png').write_bytes(b'edited')
        manifest=io.stage_manifest(self.plan.parent)
        for row in manifest['files']:
            if row['path']=='unchanged.png':
                row.update(sha256=io.sha(b'edited'),bytes=len(b'edited'))
        io.write_json(self.plan.parent/'manifest.json',manifest)
        with self.assertRaisesRegex(ValueError,'STATIC_CONTINUATION_INPUT_CHANGED'):self.run_prepare()
        self.assertFalse((self.root/'new').exists())

    def test_all_families_allow_a_source_without_spine_without_sdk(self):
        self.spec['families']=['materials','animation','spine'];self.write_request()
        result=self.run_prepare()
        from monkey.targets.unity import export
        export(Path(result['planPath']),self.root/'export')
        self.assertEqual(result['preparationStatus'],'prepared')
        self.assertTrue((Path(result['planPath']).parent/'unchanged.png').is_file())

    def test_full_shared_facade_exports_spine_and_retained_material_once(self):
        from test_prefab_static_spine_continuation import _minimal_full_fixture
        from monkey.targets.unity import export
        from monkey.layout import standard
        fixture=self.root/'spine-fixture';fixture.mkdir()
        plan,ir,manifest,source,_,material_id=_minimal_full_fixture(fixture)
        manifest['sourceProfile']='cocos-2.4.15-bundle';io.write_json(source,manifest)
        manifest_sha=self.pin(source)['sha256']
        ir.update(sourceProfile=manifest['sourceProfile'],sourceManifestSha256=manifest_sha)
        self.ir=self.root/'spine-ir/ir.json';self.ir.parent.mkdir()
        io.write_json(self.ir,ir);io.finish(self.ir.parent,ir)
        plan.update(schemaVersion=1,targetProfile='unity-6000.6.2f1-ugui',
                    sourceProfile=manifest['sourceProfile'],sourceManifestSha256=manifest_sha,
                    sourceIrSha256=self.pin(self.ir)['sha256'],copies=[],animations=[],assets=[],
                    textures=[],bitmapFonts=[],diagnostics=[],galleryOnly=False,
                    nodes=[{'sourceId':c['node'],'name':'Neutral'+str(i),'parent':None}
                           for i,c in enumerate(plan['components'])])
        self.plan=self.root/'spine-plan/plan.json';self.plan.parent.mkdir()
        (self.plan.parent/'unchanged.bin').write_bytes(b'frozen older payload')
        io.write_json(self.plan,plan);io.finish(self.plan.parent,plan)
        self.spec.update(plan=self.pin(self.plan),planManifest=self.pin(self.plan.parent/'manifest.json'),
                         ir=self.pin(self.ir),sourceManifest=self.pin(source),families=['materials','animation','spine'])
        self.write_request();result=self.run_prepare()
        continued=io.stage_document(Path(result['planPath']))
        self.assertEqual(continued['staticSpineContinuation']['summary']['sourceSpineComponentCount'],2)
        self.assertTrue((Path(result['planPath']).parent/'unchanged.bin').is_file())
        self.assertEqual(continued['components'],plan['components'])
        export(Path(result['planPath']),self.root/'export')
        instruction=io.load((self.root/'export'/standard.unity('importPlan')).read_bytes())
        self.assertTrue(instruction['staticSpineContinuationJson'])
        retained=instruction['staticRetainedAssets']
        self.assertEqual([a['sourceId']for a in retained['assets']],[material_id])
        for row in retained['payloads']:
            if row['target'].startswith('Assets/Game/Content/'):
                self.assertEqual(io.sha((self.root/'export'/row['target']).read_bytes()),row['sha256'])

    def test_public_cli_prepares_new_plan(self):
        from monkey.cli import main
        output=streams.StringIO()
        with contextlib.redirect_stdout(output):
            code=main(['continue-static-prefabs','--request',str(self.request),
                       '--expected-request',self.request_sha,'--out',str(self.root/'new')])
        self.assertEqual(code,0)
        self.assertEqual(json.loads(output.getvalue())['preparationStatus'],'prepared')

    def test_export_keeps_family_enable_and_owned_source_evidence(self):
        from monkey.targets.unity import export
        from monkey.layout import standard
        result=self.run_prepare()
        export(Path(result['planPath']),self.root/'export')
        instruction=io.load((self.root/'export'/standard.unity('importPlan')).read_bytes())
        self.assertTrue(instruction['staticAnimationBindingsEnabled'])
        self.assertFalse(instruction['staticCompletionEnabled'])
        evidence=instruction['staticAnimationEvidence'][0]
        self.assertEqual(io.sha((self.root/'export'/evidence['path']).read_bytes()),evidence['sha256'])


if __name__=='__main__':unittest.main()
