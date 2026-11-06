import unittest,tempfile
from pathlib import Path
from monkey.io import finish,write_json,load,read
from monkey.identities import assigned,verify
from monkey.sources.compiled import ParseError

class AssignedIdentityTests(unittest.TestCase):
    def test_unity_guid_accepts_lf_and_crlf_but_rejects_duplicate_and_invalid_lines(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();(root/'Assets').mkdir();meta=root/'Assets/Test.png.meta'
            identity='a'*32
            for newline in (b'\n',b'\r\n'):
                with self.subTest(newline=newline):
                    meta.write_bytes(newline.join((b'fileFormatVersion: 2',b'guid: '+identity.encode(),b'')))
                    manifest=assigned(root,dict(targetProfile='unity-6000.6.2f1-ugui',files=[dict(path='Assets/Test.png.meta')]))
                    self.assertEqual(manifest['assignedAssetIdentities'],[dict(path='Assets/Test.png',id=identity)])
                    self.assertEqual(verify(root,manifest),[])
                    for invalid in (b'guid: '+identity.encode()+b' trailing\r\n', (b'guid: '+identity.encode()+b'\r\n')*2):
                        meta.write_bytes(invalid)
                        with self.assertRaises(ParseError):
                            assigned(root,dict(targetProfile='unity-6000.6.2f1-ugui',files=[dict(path='Assets/Test.png.meta')]))
                        self.assertEqual(verify(root,manifest)[0]['code'],'ASSIGNED_NATIVE_IDENTITY_CHANGED')

    def test_importer_expansion_is_allowed_but_a_rehashed_uuid_change_is_not(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();(root/'assets').mkdir();(root/'assets/raw.png').write_bytes(b'opaque-input')
            old='aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb';path=root/'assets/raw.png.meta';write_json(path,dict(uuid=old,importer='image',imported=False,subMetas={}))
            manifest=finish(root,dict(targetProfile='cocos-3.8.8',diagnostics=[]));meta=load(read(path));meta.update(imported=True,subMetas={'frame':dict(uuid=old+'@frame')});write_json(path,meta)
            self.assertEqual(verify(root,manifest),[])
            meta['uuid']='cccccccc-1111-2222-3333-dddddddddddd';write_json(path,meta)
            # A native file hash receipt may legitimately change, but cannot replace the sealed ID.
            errors=verify(root,manifest);self.assertEqual([e['code']for e in errors],['ASSIGNED_NATIVE_IDENTITY_CHANGED'])

if __name__=='__main__':unittest.main()
