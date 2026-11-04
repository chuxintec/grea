import re,unittest
from monkey.prefab_static_carriers import _creator_script
class CreatorStaticImportsTests(unittest.TestCase):
    def test_fallback_decorators_are_imported_for_legacy_untyped_snapshots(self):
        fields=[{'fieldName':'snapshot','storageType':'string','kind':'object'},{'fieldName':'textArray','storageType':'string[]','elementKind':'string','kind':'array'},{'fieldName':'flag','storageType':'bool','kind':'bool'}]
        code=_creator_script('Test','Carrier',fields)
        imports=set(re.search(r'import \{ ([^}]+) \}',code).group(1).replace(' ','').split(','))
        decorators=set(re.findall(r'\bCC(?:String|Boolean|Integer|Float)\b',code.split("from 'cc';",1)[1]))
        self.assertTrue(decorators<=imports,decorators-imports)
        self.assertIn('CCString',decorators);self.assertIn('CCBoolean',decorators)
