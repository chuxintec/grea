import unittest
from monkey.project_model import import_plan_model,replace_slots,asset_path
from monkey.targets import unity
from monkey.sources.compiled import ParseError


class TypedProjectPathTests(unittest.TestCase):
    def test_only_proven_path_slots_change_and_identity_text_keys_do_not(self):
        old='Assets/Generated/Art/name.png';new='Assets/Game/Content/Images/name.png'
        doc={'assets':[{'id':'source:1','kind':'sprite','path':old,'nativeId':'stable','name':old,'logicalKey':old,'text':'load '+old}],
             'nodes':[{'name':old,'text':old}],'sourcePrefabs':[{'sourceId':'source:p','path':'Assets/Generated/Views/Main.prefab'}]}
        model=import_plan_model(doc,unity.PROFILE);changed=replace_slots(doc,model['pathSlots'],{old:new})
        self.assertEqual(changed['assets'][0]['path'],new)
        for field in ['name','logicalKey','text']:self.assertEqual(changed['assets'][0][field],doc['assets'][0][field])
        self.assertEqual(changed['nodes'],doc['nodes']);self.assertEqual(changed['assets'][0]['nativeId'],'stable')
        self.assertEqual(model['assets'][1]['identityState'],'native_assignment_pending')
        self.assertEqual(doc['assets'][0]['path'],old)

    def test_stale_pointer_and_unsafe_paths_fail_without_partial_rewrite(self):
        with self.assertRaises(ParseError):replace_slots({'path':'changed'},[{'pointer':['path'],'path':'old'}],{'old':'new'})
        for bad in ['../Assets/a','Assets/../a','Assets//a','Assets/a\\b','Assets/C:/a','/Assets/a']:
            with self.assertRaises(ParseError):asset_path(bad,unity.PROFILE)


if __name__=='__main__':unittest.main()
