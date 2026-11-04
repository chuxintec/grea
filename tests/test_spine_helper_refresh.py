import tempfile
import unittest
from pathlib import Path
from monkey import io
from monkey.prefab_spine_native_stage import CONTRACT, _HELPERS, refresh_unity_stage_helpers, SpineNativeStageError

class SpineHelperRefreshTests(unittest.TestCase):
    def fixture(self, root):
        root.mkdir(); copies=[]
        for index, (_, target) in enumerate(_HELPERS):
            raw=f'// previous helper {index}\n'.encode(); relative=f'payloads/helper{index}.cs';p=root/relative;p.parent.mkdir(exist_ok=True);p.write_bytes(raw)
            copies.append(dict(source=relative,target=target,role='unity-native-spine-helper',sha256=io.sha(raw),bytes=len(raw)))
        raw=b'neutral frozen source';p=root/'payloads/source.bin';p.write_bytes(raw)
        copies.append(dict(source='payloads/source.bin',target='Assets/Game/Content/source.bin',role='source-spine-closure',sha256=io.sha(raw),bytes=len(raw)))
        plan=dict(schemaVersion=1,targetProfile='unity-6000.6.2f1-ugui',namespace='neutral',sourceManifestSha256='a'*64,sourceIrSha256='b'*64)
        plan['spineNativeStage']=dict(contract=CONTRACT,target='unity',sourceManifestSha256=plan['sourceManifestSha256'],sourceIrSha256=plan['sourceIrSha256'],copies=copies)
        io.write_json(root/'plan.json',plan);io.finish(root,plan);return root/'plan.json'

    def test_refresh_only_owned_helper_bytes_in_new_manifest_bound_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();source=self.fixture(root/'old');old=source.read_bytes();result=refresh_unity_stage_helpers(source,root/'new');new=io.stage_document(root/'new/plan.json')
            self.assertEqual(source.read_bytes(),old);self.assertEqual(new['sourceManifestSha256'],'a'*64)
            oldrows=io.stage_document(source)['spineNativeStage']['copies'];newrows=new['spineNativeStage']['copies']
            self.assertEqual(newrows[-1],oldrows[-1]);self.assertEqual((root/'new/payloads/source.bin').read_bytes(),b'neutral frozen source')
            for row, (relative,target) in zip(newrows,_HELPERS):
                expected=(Path(__file__).parents[1]/'src/monkey'/relative).read_bytes()
                self.assertEqual(row['target'],target);self.assertEqual(row['sha256'],io.sha(expected));self.assertEqual((root/'new'/row['source']).read_bytes(),expected)
            self.assertFalse(new['nativeHelperRefresh']['sourceAssetsChanged']);self.assertEqual(len(result['nativeHelperRefresh']['helpers']),len(_HELPERS))

    def test_corrupt_frozen_payload_rejected_before_output_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();source=self.fixture(root/'old');(root/'old/payloads/source.bin').write_bytes(b'changed')
            with self.assertRaisesRegex(SpineNativeStageError,'payload changed'):refresh_unity_stage_helpers(source,root/'new')
            self.assertFalse((root/'new').exists())
