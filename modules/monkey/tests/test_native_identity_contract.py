import unittest
from monkey.cocos_native_contract import prefab_object_ids
from monkey.sources.compiled import ParseError


class NativeIdentityTests(unittest.TestCase):
    def body(self):
        return b'''--- !u!1 &100
GameObject:
  m_Name: Same
--- !u!224 &200
RectTransform:
  m_GameObject: {fileID: 100}
  m_Children:
  - {fileID: 201}
  - {fileID: 202}
  m_Father: {fileID: 0}
--- !u!1 &101
GameObject:
  m_Name: Same
--- !u!224 &201
RectTransform:
  m_GameObject: {fileID: 101}
  m_Children: []
  m_Father: {fileID: 200}
--- !u!1 &102
GameObject:
  m_Name: Same
--- !u!224 &202
RectTransform:
  m_GameObject: {fileID: 102}
  m_Children: []
  m_Father: {fileID: 200}
'''
    def args(self):return dict(sourceId='source',root='root',nodes=['root','left','right'],nodeCount=3),dict(root=dict(children=['left','right']),left=dict(children=[]),right=dict(children=[]))
    def test_actual_prefab_fileids_use_exact_child_ordinals_not_names(self):
        spec,nodes=self.args();result=prefab_object_ids(self.body(),spec,nodes)
        self.assertEqual([(r['sourceId'],r['gameObjectFileId'],r['transformFileId'])for r in result],[('root','100','200'),('left','101','201'),('right','102','202')])
    def test_duplicate_or_wrong_parent_identity_is_refused(self):
        spec,nodes=self.args()
        for body in [self.body()+b'--- !u!1 &101\nGameObject:\n',self.body().replace(b'm_Father: {fileID: 200}',b'm_Father: {fileID: 999}',1)]:
            with self.assertRaises(ParseError):prefab_object_ids(body,spec,nodes)
    def test_source_children_disposition_must_match_native_shape(self):
        spec,nodes=self.args();nodes['root']['children']=['left']
        with self.assertRaises(ParseError):prefab_object_ids(self.body(),spec,nodes)


if __name__=='__main__':unittest.main()
