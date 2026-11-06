import copy
import unittest
from monkey.prefab_static_readback import verify

class StaticReadbackTests(unittest.TestCase):
    def fixture(self):
        f=dict(fieldName='caption',sourceFieldName='caption',kind='string',storageType='string',stringValue='original')
        spec=dict(typeName='Generated.Panel',scriptGuid='script',fields=[f])
        components=[dict(sourceId='bundle:panel#2',staticFieldBinding=spec)]
        b=dict(sourceId='bundle:panel#2',typeName='Generated.Panel',nativeScriptGuid='script',nativeSourceId='bundle:panel#2',nativeIdentityVerified=True,enabled=False,fieldsVerified=True,fields=[dict(f)])
        return components,[dict(binding=b,assetGuid='asset',localFileId=9,references=[])]
    def test_checks_actual_fields_identity_and_disabled_policy(self):
        c,rows=self.fixture()
        self.assertEqual(verify(c,rows,'asset','unity','owner'),[])
        for key,value in [('enabled',True),('nativeIdentityVerified',False),('nativeSourceId','wrong'),('nativeScriptGuid','wrong')]:
            bad=copy.deepcopy(rows);bad[0]['binding'][key]=value
            self.assertTrue(verify(c,bad,'asset','unity','owner'))
        rows[0]['binding']['fields'][0]['stringValue']='changed'
        self.assertTrue(verify(c,rows,'asset','unity','owner'))
    def test_absent_or_duplicate_readback_never_passes(self):
        c,rows=self.fixture()
        self.assertTrue(verify(c,[],'asset','unity','owner'))
        self.assertTrue(verify(c,rows+rows,'asset','unity','owner'))
        self.assertTrue(verify(c,rows,'different','unity','owner'))
        self.assertEqual(verify([],None,None,'unity','owner'),[])

    def test_color_uses_all_four_native_channels(self):
        c, rows = self.fixture()
        spec = c[0]['staticFieldBinding']
        spec['fields'] = [dict(fieldName='tint', sourceFieldName='tint', kind='object', storageType='Color',
                               colorR=12, colorG=34, colorB=56, colorA=78)]
        actual = dict(spec['fields'][0])
        rows[0]['binding']['fields'] = [actual]
        self.assertEqual(verify(c, rows, 'asset', 'unity', 'owner'), [])
        rows[0]['binding']['fields'][0]['colorB'] = 57
        self.assertTrue(verify(c, rows, 'asset', 'unity', 'owner'))

    def test_typed_record_arrays_check_shape_leaf_values_and_references(self):
        c, rows = self.fixture()
        leaf = dict(fieldName='__node', sourceFieldName='node', kind='node_ref', storageType='UnityEngine.Object',
                    referenceKind='node_ref', nullExpected=False, refValue='bundle:panel#4')
        title = dict(fieldName='__title', sourceFieldName='title', kind='string', storageType='string', stringValue='first')
        record = dict(fieldName='records', sourceFieldName='records', kind='array', storageType='PanelRow[]',
                      elementKind='record', recordTypeName='PanelRow', recordValues=[dict(index=0, fields=[title, leaf])])
        c[0]['staticFieldBinding']['fields'] = [record]
        actual_title = dict(title)
        actual_leaf = dict(leaf, referenceVerified=True)
        actual = dict(record, recordValues=[dict(index=0, fields=[actual_title, actual_leaf])])
        rows[0]['binding']['fields'] = [actual]
        rows[0]['references'] = [dict(field='records', fieldPath='records[0].node', sourceId='bundle:panel#4',
                                       recordIndex=0, recordField='node', guid='guid', localFileId=42, persistent=True)]
        self.assertEqual(verify(c, rows, 'asset', 'unity', 'owner'), [])
        rows[0]['binding']['fields'][0]['recordValues'][0]['fields'][0]['stringValue'] = 'changed'
        self.assertTrue(verify(c, rows, 'asset', 'unity', 'owner'))
        rows[0]['binding']['fields'][0]['recordValues'][0]['fields'][0]['stringValue'] = 'first'
        rows[0]['references'][0]['localFileId'] = 0
        self.assertTrue(verify(c, rows, 'asset', 'unity', 'owner'))

    def test_unknown_storage_type_is_gap_not_key_error(self):
        c, rows = self.fixture()
        f = dict(fieldName='future', sourceFieldName='future', kind='opaque', storageType='FutureStorage')
        c[0]['staticFieldBinding']['fields'] = [f]
        rows[0]['binding']['fields'] = [dict(f)]
        result = verify(c, rows, 'asset', 'unity', 'owner')
        self.assertTrue(result)
        self.assertIn('Unknown static field storage type', result[0]['message'])

    def test_collects_failures_from_each_carrier(self):
        components, rows = self.fixture()
        second_spec = copy.deepcopy(components[0]['staticFieldBinding'])
        components.append(dict(sourceId='bundle:panel#3', staticFieldBinding=second_spec))
        components[1]['staticFieldBinding']['fields'] = [dict(
            fieldName='reference', sourceFieldName='reference', kind='object',
            storageType='UnityEngine.Object', refValue='bundle:panel#4')]
        second_spec['fields'] = [dict(components[1]['staticFieldBinding']['fields'][0])]
        rows[0]['binding']['sourceId'] = 'bundle:panel#2'
        rows[0]['binding']['fieldsVerified'] = False
        rows[0]['assetUuid'] = 'asset'
        rows[0]['componentUuid'] = 'component-2'
        rows[0]['binding']['sourceId'] = components[0]['sourceId']
        rows[0]['binding']['fields'] = [dict(
            fieldName='caption', sourceFieldName='caption', kind='string', storageType='string',
            stringValue='changed')]
        second = copy.deepcopy(rows[0])
        second['binding']['sourceId'] = components[1]['sourceId']
        second['binding']['fields'] = [dict(components[1]['staticFieldBinding']['fields'][0], referenceVerified=False)]
        second['binding']['fieldsVerified'] = False
        second['componentUuid'] = 'component-3'
        result = verify(components, [rows[0], second], 'asset', 'creator', 'owner')
        messages = [d['message'] for d in result]
        self.assertTrue(any('bundle:panel#2/caption' in message for message in messages), messages)
        self.assertTrue(any('bundle:panel#3/reference' in message for message in messages), messages)
        self.assertTrue(any('bundle:panel#2' in message for message in messages), messages)
        self.assertTrue(any('bundle:panel#3' in message for message in messages), messages)

    def test_collects_multiple_typed_record_leaf_failures(self):
        c, rows = self.fixture()
        leaves = [
            dict(fieldName='__first', sourceFieldName='first', kind='string', storageType='string', stringValue='a'),
            dict(fieldName='__second', sourceFieldName='second', kind='string', storageType='string', stringValue='b'),
        ]
        record = dict(fieldName='records', sourceFieldName='records', kind='array', storageType='Row[]',
                      elementKind='record', recordTypeName='Row',
                      recordValues=[dict(index=0, fields=leaves)])
        c[0]['staticFieldBinding']['fields'] = [record]
        actual = copy.deepcopy(record)
        actual['recordValues'][0]['fields'][0]['stringValue'] = 'wrong-a'
        actual['recordValues'][0]['fields'][1]['stringValue'] = 'wrong-b'
        rows[0]['binding']['fields'] = [actual]
        result = verify(c, rows, 'asset', 'unity', 'owner')
        record_errors = [d['message'] for d in result if 'records' in d['message']]
        self.assertTrue(any('row 0/first' in message for message in record_errors), record_errors)
        self.assertTrue(any('row 0/second' in message for message in record_errors), record_errors)

if __name__=='__main__':unittest.main()
