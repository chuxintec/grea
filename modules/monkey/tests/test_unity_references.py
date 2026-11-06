import unittest
from monkey.unity_references import resolve
from monkey.sources.compiled import ParseError


class UnityReferenceTests(unittest.TestCase):
    def index(self):
        a={'key':'a:CAB-a','name':'CAB-a','externals':[{'fileId':'1','path':'archive:/CAB-b/CAB-b'}],'objects':[{'pathId':'1','type':'GameObject'}]}
        b={'key':'b:CAB-b','name':'CAB-b','externals':[],'objects':[{'pathId':'-9223372036854775807','type':'Sprite'}]}
        return {'containers':[{'status':'indexed','files':[a,b]}]}
    def test_exact_external_table_and_signed64_keep_metadata_separate_from_native(self):
        r=resolve(self.index(),'a:CAB-a','1','-9223372036854775807');self.assertEqual(r['status'],'metadata-resolved');self.assertEqual(r['type'],'Sprite');self.assertEqual(r['nativeReference'],'not_verified')
        self.assertEqual(resolve(self.index(),'a:CAB-a','0','0'),{'status':'null'})
        self.assertEqual(resolve(self.index(),'a:CAB-a','2','1')['reason'],'external-fileId-out-of-range')
        with self.assertRaises(ParseError):resolve(self.index(),'a:CAB-a','1',9223372036854775807)
    def test_missing_or_ambiguous_cab_never_falls_back_to_first_match(self):
        index=self.index();index['containers'][0]['files'].append(dict(index['containers'][0]['files'][1],key='c:CAB-b'))
        self.assertEqual(resolve(index,'a:CAB-a','1','-9223372036854775807')['reason'],'external-file-ambiguous')
        index=self.index();index['containers'][0]['files'][0]['externals'][0]['path']='archive:/other/CAB-b'
        self.assertEqual(resolve(index,'a:CAB-a','1','-9223372036854775807')['reason'],'archive-path-contract-unknown')


if __name__=='__main__':unittest.main()
