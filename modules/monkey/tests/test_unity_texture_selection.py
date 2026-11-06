import base64
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from monkey.sources.unity_worker import hydrate_manifest
from monkey.unity_texture_selection import matching_cache,validate_selection


def digest(raw):return hashlib.sha256(raw).hexdigest()
def encode(data):return json.dumps(data,sort_keys=True,default=lambda b:{'$bytes':base64.b64encode(b).decode()}).encode()
def decode(raw):return json.loads(raw,object_hook=lambda d:base64.b64decode(d['$bytes'])if set(d)=={'$bytes'}else d)
def texture(name='rect.1234abcd',width=256,height=512):
    token=(name+'_5###').encode()
    return dict(m_Width=width,m_Height=height,m_MipCount=1,m_ImageCount=1,m_TextureFormat=34,**{'image data':bytes([len(token)])+token})
def dds():
    header=bytearray(124);struct.pack_into('<7I',header,0,124,0x81007,512,256,256*512,0,1)
    struct.pack_into('<2I',header,72,32,4);header[80:84]=b'DXT5';struct.pack_into('<I',header,104,0x1000)
    block=bytes([255,0])+bytes(6)+struct.pack('<HHI',0xf800,0x07e0,0)
    return b'DDS '+header+block*(256//4)*(512//4)


class Obj:
    def __init__(self,row):self.row=copy.deepcopy(row);self.path_id=row['id'];self.type=SimpleNamespace(name=row['type'])
    def get_raw_data(self):return encode(self.row['data'])
    def read_typetree(self,check_read):
        if self.row.get('unreadable'):raise AssertionError('Unselected object must not be parsed')
        return copy.deepcopy(self.row['data'])
    def save_typetree(self,data):self.row['data']=copy.deepcopy(data)


class Env:
    def __init__(self,rows,tamper=False):
        self.assets=[SimpleNamespace(name='CAB-fixture',unity_version='2021.3.30f1',objects={r['id']:Obj(r)for r in rows})];self.file=self;self.tamper=tamper
    def save(self,packer):
        rows=[copy.deepcopy(o.row)for o in self.assets[0].objects.values()]
        if self.tamper:rows[-1]['data']['tampered']=True
        return encode(rows)


class TextureSelectionTests(unittest.TestCase):
    def setup_job(self,root,two=True):
        rows=[dict(id=1,type='Texture2D',data=texture()),dict(id=3,type='Sprite',data={'name':'untouched'})]
        if two:rows.insert(1,dict(id=2,type='Texture2D',data=texture('other.abcdef12'),unreadable=True))
        source=root/'source.bundle';source.write_bytes(encode(rows));cache=root/'cache.bin';cache.write_bytes(dds());logical='Assets/Textures/dds/256/rect.1234abcd.txt'
        job=dict(source=str(source),sourceSha256=digest(source.read_bytes()),cache=[dict(path=str(cache),logicalPath=logical,bytes=cache.stat().st_size,sha256=digest(cache.read_bytes()))],selection=[dict(file='CAB-fixture',pathId='1',rawSha256=digest(encode(rows[0]['data'])),logicalPath=logical)])
        return rows,job,source
    def run_job(self,root,rows,job,tamper=False):
        path=root/'job.json';path.write_text(json.dumps(job));output=root/'hydration.json'
        def load(raw):return Env(decode(raw),tamper=tamper if raw==encode(rows)else False)
        module=SimpleNamespace(__version__='1.25.3',load=load)
        with patch.dict('sys.modules',{'UnityPy':module}):hydrate_manifest(path,output)
        return json.loads(output.read_text())
    def test_selected_non_square_texture_uses_literal_bucket_and_preserves_unreadable_neighbor(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);rows,job,source=self.setup_job(root);before=source.read_bytes();r=self.run_job(root,rows,job)
            self.assertEqual(r['status'],'partial');self.assertTrue(r['selectionComplete']);self.assertFalse(r['wholeContainerComplete']);self.assertTrue(r['serializationCommitted']);self.assertEqual(len(r['deferred']),1)
            after=decode((root/'hydrated.bundle').read_bytes());self.assertEqual(after[1:],rows[1:]);self.assertEqual(source.read_bytes(),before)
            self.assertEqual(after[0]['data']['image data'],bytes([255,0,0,255])*(256*512));self.assertEqual(r['resolved'][0]['logicalPath'],'Assets/Textures/dds/256/rect.1234abcd.txt')
    def test_default_container_mode_also_matches_unique_frozen_literal_path(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);rows,job,_=self.setup_job(root,two=False);job.pop('selection');r=self.run_job(root,rows,job)
            self.assertEqual(r['status'],'hydrated');self.assertTrue(r['wholeContainerComplete']);self.assertEqual(r['modifiedTextures'],1)
    def test_full_container_missing_neighbor_stays_blocked_without_derivative(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);rows,job,_=self.setup_job(root);rows[1].pop('unreadable');Path(job['source']).write_bytes(encode(rows));job['sourceSha256']=digest(encode(rows));job.pop('selection');r=self.run_job(root,rows,job)
            self.assertEqual(r['status'],'blocked');self.assertEqual(r['missing'][0]['pathId'],'2');self.assertFalse((root/'hydrated.bundle').exists());self.assertFalse(r['serializationCommitted'])
    def test_unknown_wrong_type_and_stale_selected_identity_never_decode(self):
        for change in [dict(pathId='999'),dict(pathId='3'),dict(rawSha256='0'*64)]:
            with self.subTest(change=change),tempfile.TemporaryDirectory()as t:
                root=Path(t);rows,job,_=self.setup_job(root);job['selection'][0].update(change)
                with patch('monkey.sources.unity_worker.decode_cached_texture')as decoder:r=self.run_job(root,rows,job);decoder.assert_not_called()
                self.assertEqual(r['status'],'needs_action');self.assertFalse(r['selectionComplete']);self.assertFalse((root/'hydrated.bundle').exists())
    def test_missing_or_mismatched_explicit_path_does_not_fall_back(self):
        for path in ['Assets/Textures/dds/512/rect.1234abcd.txt','Assets/Textures/dds/256/different.1234abcd.txt']:
            with self.subTest(path=path),tempfile.TemporaryDirectory()as t:
                root=Path(t);rows,job,_=self.setup_job(root);job['selection'][0]['logicalPath']=path;r=self.run_job(root,rows,job)
                self.assertEqual(r['status'],'needs_action');self.assertFalse((root/'hydrated.bundle').exists())
    def test_selected_set_is_atomic_when_a_second_selected_cache_is_missing(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);rows,job,_=self.setup_job(root);rows[1].pop('unreadable');Path(job['source']).write_bytes(encode(rows));job['sourceSha256']=digest(encode(rows))
            job['selection'].append(dict(file='CAB-fixture',pathId='2',rawSha256=digest(encode(rows[1]['data'])),logicalPath='Assets/Textures/dds/256/other.abcdef12.txt'))
            r=self.run_job(root,rows,job);self.assertEqual(r['status'],'needs_action');self.assertEqual(len(r['resolved']),1);self.assertEqual(len(r['missing']),1);self.assertFalse(r['serializationCommitted']);self.assertFalse(r['selectionComplete']);self.assertFalse((root/'hydrated.bundle').exists())
    def test_ambiguous_default_binding_rejects_but_explicit_binding_is_unambiguous(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);rows,job,_=self.setup_job(root,two=False);job['cache'].append(dict(job['cache'][0],logicalPath='Assets/Textures/dds/512/rect.1234abcd.txt'));selected=copy.deepcopy(job);job.pop('selection');r=self.run_job(root,rows,job)
            self.assertEqual(r['status'],'needs_action');self.assertEqual(r['diagnostics'][0]['code'],'UNITY_TEXTURE_CACHE_AMBIGUOUS');self.assertFalse((root/'hydrated.bundle').exists())
            r=self.run_job(root,rows,selected);self.assertEqual(r['status'],'hydrated')
    def test_changed_cache_and_unselected_serialization_drift_are_not_committed(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);rows,job,_=self.setup_job(root);job['cache'][0]['sha256']='0'*64;r=self.run_job(root,rows,job)
            self.assertEqual(r['diagnostics'][0]['code'],'UNITY_TEXTURE_CACHE_IDENTITY');self.assertFalse((root/'hydrated.bundle').exists())
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);rows,job,_=self.setup_job(root)
            with self.assertRaisesRegex(ValueError,'Unselected or non-texture'):self.run_job(root,rows,job,tamper=True)
            self.assertFalse((root/'hydrated.bundle').exists())
    def test_selection_manifest_pins_source_and_canonical_object_ids(self):
        valid=dict(schemaVersion=1,sourceSha256='a'*64,objects=[dict(file='CAB-x',pathId='-9223372036854775808',rawSha256='b'*64,logicalPath='Assets/Textures/astc/256/rect.1234abcd.txt')])
        self.assertEqual(len(validate_selection(valid,'a'*64)),1)
        for path_id in ['01','-0','9223372036854775808',1,True]:
            bad=copy.deepcopy(valid);bad['objects'][0]['pathId']=path_id
            with self.subTest(pathId=path_id),self.assertRaises(ValueError):validate_selection(bad,'a'*64)
        with self.assertRaises(ValueError):validate_selection(valid,'c'*64)
        bad=copy.deepcopy(valid);bad['objects']*=2
        with self.assertRaises(ValueError):validate_selection(bad,'a'*64)
    def test_literal_astc_matching_preserves_escaped_key_and_opaque_bucket(self):
        path='Assets/Textures/astc/256/rect%20name.1234abcd.txt';pool={path:{'sha256':'a'*64}}
        self.assertEqual(matching_cache(pool,'rect%20name.1234abcd')[0][1],path)
        self.assertEqual(matching_cache(pool,'rect name.1234abcd'),[])


if __name__=='__main__':unittest.main()
