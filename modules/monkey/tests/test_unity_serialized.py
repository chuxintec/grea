import unittest
from monkey.sources.unity_worker import portable, identifier, texture_payload, astc_header


class UnityIdentityTests(unittest.TestCase):
    def test_negative_path_id_survives_json_and_distinguishes_files(self):
        import json
        path_id = -9223372036854775807
        refs=[]
        data=portable({'first':{'m_FileID':0,'m_PathID':path_id},
                       'other':{'m_FileID':2,'m_PathID':path_id},
                       'unsignedData':18446744073709551615},refs)
        # A JavaScript consumer receives no unsafe number, including ordinary large values.
        restored=json.loads(json.dumps(data))
        self.assertEqual(restored['first']['pathId'],str(path_id))
        self.assertEqual(restored['first']['fileId'],'0')
        self.assertEqual(restored['other']['fileId'],'2')
        self.assertEqual(restored['unsignedData']['decimal'],'18446744073709551615')
        self.assertEqual([r['location'] for r in refs],['$/first','$/other'])
        for bad in [1<<63,-(1<<63)-1,True,1.0,'1']:
            with self.assertRaises(ValueError):identifier(bad)

    def test_binary_text_and_nonfinite_are_losslessly_explicit(self):
        import base64,json
        raw=b'\xff\xfe\x00a';data=portable({'text':raw.decode('utf-8',errors='surrogateescape'),'unknown':float('inf')},[])
        json.dumps(data,ensure_ascii=False,allow_nan=False).encode('utf-8')
        self.assertEqual(base64.b64decode(data['text']['base64']),raw)
        self.assertEqual(data['unknown'],{'$type':'nonfinite','value':'inf'})

    def test_external_texture_key_is_reported_as_unresolved_not_pixels(self):
        key=b'Atlas%20Page.0123abcd'
        row=texture_payload({'image data':bytes([len(key)])+key})
        self.assertEqual(row['kind'],'external-key-token-candidate')
        self.assertEqual(row['resourceResolution'],'required')
        extended=key+b'_5###';extended=texture_payload({'image data':bytes([len(extended)])+extended})
        self.assertEqual(extended['key'],key.decode());self.assertEqual(extended['blockSizeHint'],5)
        self.assertFalse(row['nativePixelsVerified'])
        self.assertEqual(texture_payload({'image data':b'wrong'+key})['kind'],'inline-payload')

    def test_etc1_missing_block_is_not_treated_as_native_pixels(self):
        base={'image data':b'\0','m_Width':1,'m_Height':1,'m_TextureFormat':34,'m_StreamData':{'path':'','size':0}}
        self.assertEqual(texture_payload(base)['kind'],'invalid-inline-etc1')
        self.assertEqual(texture_payload(base)['minimumBaseLevelBytes'],8)
        self.assertEqual(texture_payload(dict(base,**{'image data':bytes(8)}))['kind'],'inline-payload')
        self.assertEqual(texture_payload(dict(base,m_StreamData={'path':'exact.resS','size':8}))['kind'],'inline-payload')
        self.assertEqual(texture_payload(dict(base,m_TextureFormat=999))['kind'],'inline-payload')

    def test_astc_header_checks_exact_payload_dimensions_and_wire_block_hint(self):
        header=b'\x13\xab\xa1\x5c'+bytes([5,5,1])+(10).to_bytes(3,'little')+(15).to_bytes(3,'little')+(1).to_bytes(3,'little')
        raw=header+bytes(2*3*16)
        self.assertEqual(astc_header(raw,10,15,5)['payloadBytes'],96)
        for data,w,h,hint in [(raw+b'X',10,15,5),(raw,11,15,5),(raw,10,15,8)]:
            with self.assertRaises(ValueError):astc_header(data,w,h,hint)

    def test_oversized_object_is_local_gap_and_later_small_objects_still_parse(self):
        from types import SimpleNamespace as NS
        from unittest.mock import patch
        from monkey.sources.unity_worker import inspect_bytes
        class Kind:
            name='ComputeShader'
            def __int__(self):return 72
        def obj(i,values):
            return NS(type=Kind(),path_id=i,byte_size=1,serialized_type=None,
                get_raw_data=lambda:b'x',read_typetree=lambda **kwargs:values)
        objects={1:obj(1,list(range(20))),2:obj(2,[1]),3:obj(3,list(range(8))),4:obj(4,[2])}
        asset=NS(name='known',unity_version='2022.3.61t9',target_platform=20,objects=objects,externals=[],_enable_type_tree=False)
        provider=NS(__version__='1.25.3',load=lambda raw:NS(assets=[asset]))
        with patch.dict('sys.modules',UnityPy=provider),patch('monkey.sources.unity_worker.MAX_VALUES',10),patch('monkey.sources.unity_worker.MAX_TYPED_VALUES',5):
            result=inspect_bytes(b'own fixture')
        self.assertEqual([r['status']for r in result['objects']],['unparsed','parsed','unparsed','parsed'])
        self.assertTrue(all(r['rawSha256']for r in result['objects']))
        self.assertEqual(result['objects'][1]['data'],[1])
        self.assertEqual(result['objects'][3]['data'],[2])

    def test_partial_pptr_is_preserved_as_data_instead_of_guessed_reference(self):
        refs=[];data=portable({'m_FileID':2,'m_PathID':7,'differentSchema':True},refs)
        self.assertEqual(data['differentSchema'],True);self.assertEqual(refs,[])
        with self.assertRaises(ValueError):portable([[[None]]],[],depth=96)


if __name__=='__main__':unittest.main()
