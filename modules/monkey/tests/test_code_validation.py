import unittest
from monkey.code_validation import numeric


class ScriptBindingTests(unittest.TestCase):
    def test_creator_class_name_alone_cannot_substitute_for_assigned_script_identity(self):
        spec=dict(sourceId='source#1',convertible=True,codeClassName='Meter',sourceScriptIdentity='original-registration',
            codeScriptUuid='00000000-0000-0000-0000-000000000001')
        row=dict(sourceId='source#1',className='Meter',sourceScriptIdentity='original-registration',
            classId='00000'+'A'*17+'B',componentUuid='local-component',nodeUuid='local-node',uninitialized=True)
        self.assertEqual(numeric([spec],[row],'cocos','own-fixture'),[])
        wrong=dict(row,classId='Meter')
        self.assertTrue(numeric([spec],[wrong],'cocos','own-fixture'))


if __name__=='__main__':unittest.main()
