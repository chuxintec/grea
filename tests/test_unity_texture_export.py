import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PIL import Image

import test_unity_texture_selection as fixtures
Env,encode,decode,digest=fixtures.Env,fixtures.encode,fixtures.decode,fixtures.digest
from monkey.sources.unity_worker import export_selected_textures
from monkey.unity_texture_export import export


class TextureExportTests(unittest.TestCase):
    def fixture(self,root):
        helper=fixtures.TextureSelectionTests();rows,job,source=helper.setup_job(root)
        for row in rows:
            if row['type']=='Texture2D':row['data']['m_TextureDimension']=2
        source.write_bytes(encode(rows));job['sourceSha256']=digest(source.read_bytes());job['selection'][0]['rawSha256']=digest(encode(rows[0]['data']))
        cache=Path(job['cache'][0]['path']);payload=bytearray(cache.read_bytes());payload[136:144]=struct.pack('<HHI',0x001f,0x07e0,0);cache.write_bytes(payload);job['cache'][0]['sha256']=digest(payload)
        helper.run_job(root,rows,job)
        selector=root/'selection.json';selector.write_text(json.dumps(dict(schemaVersion=1,sourceSha256=job['sourceSha256'],objects=job['selection'])))
        paths=dict(source=str(source),derivative=str(root/'hydrated.bundle'),hydrationReport=str(root/'hydration.json'),selectionManifest=str(selector));proof=json.loads(Path(paths['hydrationReport']).read_text())
        export_job=dict(paths=paths,pins={k:digest(Path(v).read_bytes())for k,v in paths.items()},selection=job['selection'],proof=proof)
        return rows,export_job
    def worker(self,root,job):
        job_path=root/'export-job.json';job_path.write_text(json.dumps(job));output=root/'pixel-readback.json'
        with patch.dict('sys.modules',{'UnityPy':SimpleNamespace(__version__='1.25.3',load=lambda raw:Env(decode(raw)))}):export_selected_textures(job_path,output)
        return json.loads(output.read_text())
    def repin_derivative(self,job):
        job['proof']['derivedBundleSha256']=job['pins']['derivative'];path=Path(job['paths']['hydrationReport']);path.write_text(json.dumps(job['proof']));job['pins']['hydrationReport']=digest(path.read_bytes())
    def test_selected_pixels_export_without_parsing_unreadable_neighbor(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();rows,job=self.fixture(root);result=self.worker(root,job)
            self.assertEqual(result['status'],'selected-pixels-verified');self.assertTrue(result['unselectedObjectsUnchanged']);self.assertEqual(len(result['textures']),1)
            row=result['textures'][0];raw=(root/row['payloadPath']).read_bytes();self.assertEqual(raw[:4],bytes([0,0,255,255]));self.assertEqual(raw[-4:],bytes([255,0,0,255]));self.assertEqual(digest(raw),job['proof']['resolved'][0]['rgbaRawSha256'])
    def test_unselected_object_drift_is_rejected_even_with_a_new_derivative_pin(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();rows,job=self.fixture(root);path=Path(job['paths']['derivative']);data=decode(path.read_bytes());data[1]['data']['changed']=True;path.write_bytes(encode(data));job['pins']['derivative']=digest(path.read_bytes())
            self.repin_derivative(job)
            with self.assertRaisesRegex(ValueError,'unselected object'):self.worker(root,job)
    def test_selected_pixel_drift_is_rejected(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();rows,job=self.fixture(root);path=Path(job['paths']['derivative']);data=decode(path.read_bytes());data[0]['data']['image data']=bytes([0])*len(data[0]['data']['image data']);path.write_bytes(encode(data));job['pins']['derivative']=digest(path.read_bytes())
            self.repin_derivative(job)
            with self.assertRaisesRegex(ValueError,'pixels differ'):self.worker(root,job)
    def test_deferred_objects_cannot_be_omitted_from_a_repinned_report(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();rows,job=self.fixture(root);job['proof']['deferred']=[];self.repin_derivative(job)
            with self.assertRaisesRegex(ValueError,'Deferred texture inventory'):self.worker(root,job)
    def test_changed_report_or_selector_is_rejected(self):
        for field in ['hydrationReport','selectionManifest']:
            with self.subTest(field=field),tempfile.TemporaryDirectory()as t:
                root=Path(t).resolve();rows,job=self.fixture(root);Path(job['paths'][field]).write_text('{}')
                with self.assertRaisesRegex(ValueError,'input identity changed'):self.worker(root,job)
    def test_parent_exports_locked_png_with_explicit_unity_orientation_and_partial_status(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();rows,job=self.fixture(root);before={k:Path(v).read_bytes()for k,v in job['paths'].items()};outer=self
            class Child:
                pid=12345
                def __init__(self,args,**kwargs):
                    payload=json.loads(Path(args[-2]).read_text());outer.worker(Path(args[-1]).parent,payload)
                def wait(self,timeout):return 0
                def poll(self):return 0
            with patch('monkey.unity_texture_export.subprocess.Popen',Child):
                r=export(job['paths']['source'],job['paths']['derivative'],job['paths']['hydrationReport'],job['pins']['hydrationReport'],job['paths']['selectionManifest'],sys.executable,root/'Export')
            self.assertEqual(r['status'],'partial');self.assertTrue(r['exportComplete']);self.assertFalse(r['wholeContainerComplete'])
            manifest=json.loads(Path(r['manifest']).read_text());png=Path(r['candidate'])/manifest['files'][0]['path']
            with Image.open(png)as image:
                self.assertEqual(image.getpixel((0,511)),(0,0,255,255));self.assertEqual(image.getpixel((0,0)),(255,0,0,255))
            self.assertEqual(digest(png.read_bytes()),manifest['files'][0]['sha256']);self.assertEqual(manifest['textures'][0]['target']['nativeImport'],'not_run');self.assertFalse(list(Path(r['candidate']).rglob('*.meta')))
            self.assertTrue(all(Path(job['paths'][k]).read_bytes()==value for k,value in before.items()))
    def test_parent_rejects_uncommitted_or_unpinned_hydration_before_launch(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();rows,job=self.fixture(root);args=[job['paths']['source'],job['paths']['derivative'],job['paths']['hydrationReport'],'0'*64,job['paths']['selectionManifest'],sys.executable,root/'NoExport']
            with patch('monkey.unity_texture_export.subprocess.Popen')as child,self.assertRaisesRegex(ValueError,'Frozen hydration report'):export(*args)
            child.assert_not_called();self.assertFalse((root/'NoExport').exists())
            path=Path(job['paths']['hydrationReport']);data=json.loads(path.read_text());data['serializationCommitted']=False;path.write_text(json.dumps(data));args[3]=digest(path.read_bytes())
            with patch('monkey.unity_texture_export.subprocess.Popen')as child,self.assertRaisesRegex(ValueError,'Committed exact selected'):export(*args)
            child.assert_not_called()


if __name__=='__main__':unittest.main()
