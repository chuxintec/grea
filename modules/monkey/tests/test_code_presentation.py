import unittest
from monkey.code_presentation import label_components
from monkey.normalize import component_ir
from monkey.sources.compiled import ParseError

class CodePresentationTests(unittest.TestCase):
    def test_label_alias_is_preserved_and_custom_business_fields_cannot_disappear(self):
        contract=dict(className='Meter',presentation=dict(kind='label-adapter',sourceClassScope=dict(baseArgument='cc.Label'),sourceRegistration=dict(identity='rf-meter',name='Meter')),pendingMethods=[{}])
        value={'__type__':'rf-meter','node':{'__id__':1},'_string':'42','_N$overflow':2,'_N$file':{'__uuid__':'font'},'_isSystemFontUsed':False}
        result=label_components({'instances':[value]},'bundle:prefab',contract)
        self.assertEqual(result[0]['sourceId'],'bundle:prefab#0');self.assertEqual(result[0]['overflow'],2)
        self.assertEqual((result[0]['sourceScriptIdentity'],result[0]['text'],result[0]['pendingMethods']),('rf-meter','42',1))
        with self.assertRaises(ParseError)as e:label_components({'instances':[dict(value,value=0)]},'bundle:prefab',contract)
        self.assertEqual(e.exception.code,'CODE_LABEL_CUSTOM_FIELDS')
        with self.assertRaises(ParseError):label_components({'instances':[dict(value,__type__='other-rf')]},'bundle:prefab',contract)

    def test_conflicting_serialized_overflow_aliases_do_not_silently_select_a_mode(self):
        with self.assertRaises(ParseError)as e:component_ir('bundle:prefab',0,{'__type__':'cc.Label','_overflow':0,'_N$overflow':2})
        self.assertEqual(e.exception.code,'LABEL_OVERFLOW_ALIAS_CONFLICT')

if __name__=='__main__':unittest.main()
