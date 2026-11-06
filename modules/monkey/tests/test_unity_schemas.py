import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from monkey.sources.unity_worker import schema_pool, inspect_bytes
from monkey.unity_schemas import frozen_pool
from monkey.io import write_json
from monkey.sources.compiled import ParseError


def tree(alignment=0):
    child = NS(m_Name='value',m_Type='float',m_Children=[])
    return NS(m_Name='Base',m_Type='MonoBehaviour',m_Children=[child],
              to_dict_list=lambda:[dict(m_Name='Base',m_Type='MonoBehaviour',m_Level=0,m_MetaFlag=alignment),
                                   dict(m_Name='value',m_Type='float',m_Level=1,m_MetaFlag=0)])


def typ(node=None, script=b'a'*16, old=b'b'*16):
    return NS(class_id=114,node=node,script_id=script,old_type_hash=old)


def asset(serialized_type,version='2021.3.30f1',platform=20):
    return NS(name='level0',unity_version=version,target_platform=platform,
              types=[serialized_type],objects={},externals=[],_enable_type_tree=False)


class SchemaBorrowingTests(unittest.TestCase):
    def fixture(self, root):
        source=root/'pool.bundle';source.write_bytes(b'known-bundle')
        row=dict(path=str(source),bytes=source.stat().st_size,sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        target=asset(typ())
        target.objects[1]=NS(type=NS(name='MonoBehaviour'),serialized_type=target.types[0])
        return target,dict(sourceManifestSha256='c'*64,files=[row])

    def test_all_four_identity_axes_required_and_zero_hashes_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target,job=self.fixture(Path(tmp))
            cases=[asset(typ(tree())),asset(typ(tree()),version='2021.3.31f1'),
                   asset(typ(tree()),platform=13),asset(typ(tree(),script=b'x'*16)),
                   asset(typ(tree(),old=b'x'*16)),asset(typ(tree(),script=bytes(16)))]
            for i,source in enumerate(cases):
                with patch.dict('sys.modules',UnityPy=NS(load=lambda raw:NS(assets=[source]))):
                    self.assertEqual(len(schema_pool([target],job)),int(i==0))

    def test_alignment_conflict_rejected_even_when_names_types_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            target,job=self.fixture(Path(tmp))
            with patch.dict('sys.modules',UnityPy=NS(load=lambda raw:NS(assets=[asset(typ(tree(0))),asset(typ(tree(16384)))]))):
                with self.assertRaisesRegex(ValueError,'Ambiguous'):schema_pool([target],job)
            job['files'][0]['sha256']='0'*64
            with patch.dict('sys.modules',UnityPy=NS()):
                with self.assertRaisesRegex(ValueError,'identity'):schema_pool([target],job)

    def test_borrowed_read_stays_strict_and_does_not_turn_trailing_bytes_into_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            target,job=self.fixture(Path(tmp));node=tree()
            obj=target.objects[1]
            class Kind:
                name='MonoBehaviour'
                def __int__(self):return 114
            obj.type=Kind();obj.path_id=-9223372036854775807;obj.byte_size=16;obj.get_raw_data=lambda:b'raw-body'
            calls=[]
            def read(nodes=None,check_read=False):
                calls.append((nodes,check_read))
                raise ValueError('trailing bytes')
            obj.read_typetree=read
            provider=NS(__version__='1.25.3',load=lambda raw:NS(assets=[target] if raw==b'primary' else [asset(typ(node))]))
            with patch.dict('sys.modules',UnityPy=provider):result=inspect_bytes(b'primary',job)
            row=result['objects'][0]
            self.assertEqual(calls,[(node,True)])
            self.assertEqual(row['status'],'unparsed');self.assertEqual(row['references'],[])
            self.assertEqual(result['summary']['borrowedSchemaParsed'],0)
            self.assertEqual(row['schemaProvenance']['sources'][0]['bundleSha256'],job['files'][0]['sha256'])
            self.assertNotIn('embeddedSchemaId',row)
            self.assertFalse(result['sourceCodeExecuted'])

    def test_worker_rejects_full_read_with_shifted_header_and_retains_no_writable_data(self):
        import copy
        with tempfile.TemporaryDirectory() as tmp:
            target,job=self.fixture(Path(tmp))
            children=[NS(m_Name=n,m_Type=t,m_Children=[]) for n,t in [('m_GameObject','PPtr<GameObject>'),('m_Script','PPtr<MonoScript>'),('value','float')]]
            node=tree();node.m_Children=children
            obj=target.objects[1]
            class Kind:
                name='MonoBehaviour'
                def __int__(self):return 114
            obj.type=Kind();obj.path_id=7;obj.byte_size=32;obj.get_raw_data=lambda:b'original bytes'
            values=dict(m_GameObject=dict(m_FileID=0,m_PathID=3),m_Script=dict(m_FileID=0,m_PathID=2),value=1.25)
            obj.read_typetree=lambda **kwargs:copy.deepcopy(values)
            obj.parse_monobehaviour_head=lambda:NS(m_GameObject=NS(m_FileID=0,m_PathID=3),m_Script=NS(m_FileID=0,m_PathID=2))
            provider=NS(__version__='1.25.3',load=lambda raw:NS(assets=[target] if raw==b'primary' else [asset(typ(node))]))
            with patch.dict('sys.modules',UnityPy=provider):
                row=inspect_bytes(b'primary',job)['objects'][0]
                self.assertEqual(row['status'],'parsed');self.assertFalse(row['semanticValidation']['writable'])
                values['m_Script']['m_PathID']=2<<32
                row=inspect_bytes(b'primary',job)['objects'][0]
                self.assertEqual(row['status'],'unparsed');self.assertEqual(row['references'],[])
                self.assertNotIn('data',row);self.assertIn('header identity',row['error']['message'])

    def test_manifest_rejects_duplicates_and_boolean_size_before_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();_,job=self.fixture(root);manifest=root/'pool.json'
            write_json(manifest,dict(schemaVersion=1,files=job['files']))
            self.assertEqual(len(frozen_pool(manifest)['files']),1)
            write_json(manifest,dict(schemaVersion=1,files=job['files']*2))
            with self.assertRaises(ParseError):frozen_pool(manifest)
            job['files'][0]['bytes']=True
            write_json(manifest,dict(schemaVersion=1,files=job['files']))
            with self.assertRaises(ParseError):frozen_pool(manifest)


if __name__=='__main__':unittest.main()
