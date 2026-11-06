import copy
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from monkey.io import finish,sha,write_json
from monkey.resource_probe import PROFILE,prepare,prepare_shader,verify,verify_static_resource_probe
from monkey.sources.compiled import ParseError


class ResourceProbeTests(unittest.TestCase):
    def binding(self):
        spec=dict(sourceId='s',skeletonUuid='skeleton',sourceSkeletonSha256='a'*64,version='3.8.99',
                  pages=[dict(name='page.png',imageUuid='image')])
        proof=dict(**{k:spec[k]for k in ('sourceId','skeletonUuid','sourceSkeletonSha256','version')},
                   savedReferenceVerified=True,nativeStateAdvanced=True,poseChanged=True,animation='idle',bones=3,
                   textures=[dict(name='page.png',imageUuid='image',textureUuid='image@native',nativeUuid='image@native')],
                   trackTimeBefore=0,trackTimeAfter=.125)
        return dict(resourceProbes=dict(profile=PROFILE,spines=[spec])),dict(resourceProbes=dict(profile=PROFILE,spines=[proof]))

    def test_native_time_alone_or_wrong_page_or_source_never_passes(self):
        plan,readback=self.binding();self.assertTrue(verify(plan,readback))
        for field,value in [('poseChanged',False),('savedReferenceVerified',False),('sourceSkeletonSha256','b'*64),('trackTimeAfter',float('nan')),('version','4.2')]:
            bad=copy.deepcopy(readback);bad['resourceProbes']['spines'][0][field]=value
            self.assertFalse(verify(plan,bad),field)
        bad=copy.deepcopy(readback);bad['resourceProbes']['spines'][0]['textures'][0]['nativeUuid']='other@native'
        self.assertFalse(verify(plan,bad))
        bad=copy.deepcopy(readback);bad['resourceProbes']['spines']*=2;self.assertFalse(verify(plan,bad))

    def test_static_resource_proof_allows_no_bone_motion_but_not_identity_gaps(self):
        plan, readback = self.binding()
        readback["creatorVersion"] = "3.8.8"
        readback["manifestSha256"] = "b" * 64
        row = readback["resourceProbes"]["spines"][0]
        row["slots"] = 1
        row["poseChanged"] = False
        row["diagnostics"] = [{"code": "NO_OBSERVED_BONE_MOTION"}]
        execution = {"sourceManifestSha256": "b" * 64, "processStarted": True,
                     "processExited": True, "stopReason": "native_completed", "importPlanSha256": "c" * 64,
                     "nativeProgress": {"planSha256": "c" * 64, "status": "completed", "phase": "complete",
                                        "processed": 1, "total": 1}}
        proof = verify_static_resource_probe(plan, readback, execution,
                                             expected_import_plan_sha256="c" * 64,
                                             expected_candidate_manifest_sha256="b" * 64)
        self.assertEqual(proof["status"], "static_resource_identity_verified")
        self.assertFalse(proof["dynamicAnimationComplete"])
        self.assertEqual(proof["spines"][0]["dynamicPoseStatus"], "partial_no_observed_bone_motion")
        bad = copy.deepcopy(readback)
        bad["resourceProbes"]["spines"][0]["savedReferenceVerified"] = False
        with self.assertRaisesRegex(ValueError, "identity or saved native reference"):
            verify_static_resource_probe(plan, bad, execution,
                                         expected_import_plan_sha256="c" * 64,
                                         expected_candidate_manifest_sha256="b" * 64)
        bad_execution = copy.deepcopy(execution)
        bad_execution["sourceManifestSha256"] = "d" * 64
        with self.assertRaisesRegex(ValueError, "native import did not complete"):
            verify_static_resource_probe(plan, readback, bad_execution,
                                         expected_import_plan_sha256="c" * 64,
                                         expected_candidate_manifest_sha256="b" * 64)

    def candidate(self,root,version='3.8.99'):
        project=root/'source';folder=project/'assets/resources/Spine/Fixture';folder.mkdir(parents=True)
        payloads={'Fixture.json':json.dumps(dict(skeleton=dict(spine=version))).encode(),'Fixture.atlas':b'page.png\nsize: 1,1\nformat: RGBA8888\nfilter: Linear,Linear\nrepeat: none\n','page.png':b'synthetic-image-not-imported'}
        files=[]
        for name,raw in payloads.items():
            path=folder/name;path.write_bytes(raw);uid='skeleton'if name.endswith('json')else 'atlas'if name.endswith('atlas')else 'image'
            write_json(Path(str(path)+'.meta'),dict(uuid=str(uuid.uuid5(uuid.NAMESPACE_URL,uid)),userData=dict(atlasUuid=str(uuid.uuid5(uuid.NAMESPACE_URL,'atlas')))if uid=='skeleton'else {}))
            files.append(dict(path=path.relative_to(project).as_posix(),sha256=sha(raw)))
        write_json(project/'Analysis/Evidence/spine-closures.json',dict(skeletons=[dict(sourceId='s',status='closure_recovered',runtime='creator-builtin-3.8',skeletonVersion=version,
                   skeletonPath='assets/resources/Spine/Fixture/Fixture.json',atlasPath='assets/resources/Spine/Fixture/Fixture.atlas',files=files)]))
        finish(project,dict(schemaVersion=1,targetProfile='cocos-3.8.8',diagnostics=[]))
        return project,sha((project/'manifest.json').read_bytes())

    def test_custom_version_or_tampered_selected_source_stops_before_output(self):
        with tempfile.TemporaryDirectory()as temp:
            r=Path(temp).resolve();project,digest=self.candidate(r,version='3.8-from-4.2')
            with self.assertRaises(ParseError):prepare(project,digest,['s'],r/'custom')
            self.assertFalse((r/'custom').exists())
        with tempfile.TemporaryDirectory()as temp:
            r=Path(temp).resolve();project,digest=self.candidate(r)
            (project/'assets/resources/Spine/Fixture/page.png').write_bytes(b'edited')
            with self.assertRaises(ParseError):prepare(project,digest,['s'],r/'edited')
            self.assertFalse((r/'edited').exists())

    def test_prepared_probe_has_no_source_hierarchy_or_recovered_program(self):
        with tempfile.TemporaryDirectory()as temp:
            r=Path(temp).resolve();project,digest=self.candidate(r);result=prepare(project,digest,['s'],r/'out')
            receipt=json.loads(Path(result['report']).read_bytes());self.assertFalse(receipt['gameplayIncluded'])
            plan=json.loads((Path(result['candidate'])/'extensions/monkey-import/import-plan.json').read_bytes())
            self.assertEqual(plan['nodes'],[]);self.assertEqual(plan['components'],[])
            self.assertEqual(plan['resourceProbes']['spines'][0]['sourceSkeletonSha256'],sha((project/'assets/resources/Spine/Fixture/Fixture.json').read_bytes()))

    def test_unknown_shader_preserves_source_without_an_approximate_adapter(self):
        with tempfile.TemporaryDirectory()as temp:
            r=Path(temp).resolve();project=r/'candidate';effect='assets/resources/Shaders/Fixture/EffectDescription.json'
            write_json(project/effect,dict(__type__='cc.EffectAsset',_name='builtin-2d-sprite',shaders=[]))
            write_json(project/'Analysis/Mappings/resource-catalog.json',dict(shaders=[dict(sourceId='unknown',files=[dict(path=effect,sha256=sha((project/effect).read_bytes()))])]))
            finish(project,dict(schemaVersion=1,targetProfile='cocos-3.8.8',diagnostics=[]));digest=sha((project/'manifest.json').read_bytes())
            with self.assertRaises(ParseError):prepare_shader(project,digest,'unknown',r/'probe')
            self.assertFalse((r/'probe').exists());self.assertEqual(digest,sha((project/'manifest.json').read_bytes()))
