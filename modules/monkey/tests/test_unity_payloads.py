import io,json,struct,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from monkey.io import sha
from monkey.unity_payloads import (PayloadWriter,read_streamed,validate_payloads,copy_payloads,iter_references,iter_payload,CHUNK_ELEMENTS)
from monkey.unity_parse_limits import parse_limits
from monkey.sources.unity_worker import portable


class Reader:
    def __init__(self,raw,endian='<'):self.stream=io.BytesIO(raw);self.endian=endian
    @property
    def Position(self):return self.stream.tell()
    @Position.setter
    def Position(self,value):self.stream.seek(value)
    def read_bytes(self,n):return self.stream.read(n)
    def read_int(self):return struct.unpack(self.endian+'i',self.read_bytes(4))[0]
    def align_stream(self):self.Position=(self.Position+3)//4*4


def fixture(root,endian='<',source='a'*64):
    raw=b''.join(struct.pack(endian+'iq',(-2 if i%2 else 4),(-2**63 if i%2 else 2**63-1))for i in range(CHUNK_ELEMENTS+1))
    writer=PayloadWriter(root,source);value=writer.write_array(Reader(raw),CHUNK_ELEMENTS+1,12,endian,'0--9-m_PreloadTable','unity-pptr-i32-i64');descriptor=value.descriptor
    body=dict(source=dict(sha256=source),payloadFiles=writer.files,objects=[dict(status='parsed',data=dict(m_PreloadTable=portable(value,[])),payloads=[dict(location='$/m_PreloadTable',**descriptor)])])
    return raw,body


class UnityPayloadTests(unittest.TestCase):
    def test_pptr_chunks_preserve_signed_ids_order_endian_and_copy_closure(self):
        for endian in ['<','>']:
            with self.subTest(endian=endian),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp).resolve();raw,body=fixture(root,endian);block=body['objects'][0]['payloads'][0]
                self.assertEqual(len(validate_payloads(root,body)),2)
                self.assertEqual(b''.join(iter_payload(root,block)),raw)
                refs=list(iter_references(root,block));self.assertEqual(refs[0]['pathId'],str(2**63-1));self.assertEqual(refs[1]['pathId'],str(-2**63));self.assertEqual(refs[1]['fileId'],'-2');self.assertEqual(refs[-1]['location'],'$/m_PreloadTable/8192')
                dest=root/'copy';dest.mkdir();copy_payloads(root,dest,body);validate_payloads(dest,body)
                self.assertLess(len(json.dumps(body)),5000) # Thousands of references stay out of the document.

    def test_payload_mutation_truncation_and_extra_file_are_rejected(self):
        for mutation in ['hash','missing','extra','descriptor','order']:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp).resolve();raw,body=fixture(root);path=root/body['payloadFiles'][0]['path']
                if mutation=='hash':path.write_bytes(b'x'*path.stat().st_size)
                elif mutation=='missing':path.unlink()
                elif mutation=='extra':(path.parent/'extra.bin').write_bytes(b'x')
                elif mutation=='descriptor':body['objects'][0]['data']['m_PreloadTable']={'$type':'discarded'}
                else:
                    block=body['objects'][0]['payloads'][0];block['chunks']=list(reversed(block['chunks']));body['objects'][0]['data']['m_PreloadTable']={k:v for k,v in block.items()if k!='location'}
                with self.assertRaises((ValueError,OSError)):validate_payloads(root,body)

    def test_font_reads_bounded_chunks_and_rejects_wrong_length_or_layout(self):
        def node(name,typ,size,children=(),flags=0):return types.SimpleNamespace(m_Name=name,m_Type=typ,m_ByteSize=size,m_Children=list(children),m_MetaFlag=flags)
        field=node('m_FontData','vector',-1,[node('Array','Array',-1,[node('size','int',4),node('data','char',1)],0x4000)],0x4000)
        shape=node('Base','Font',-1,[field]);raw=bytes(range(256))*33;encoded=struct.pack('<i',len(raw))+raw
        obj=types.SimpleNamespace(type=types.SimpleNamespace(name='Font'),path_id=9,reader=Reader(b''),assets_file=None,_get_typetree_node=lambda:shape,get_raw_data=lambda:encoded)
        helper=types.ModuleType('UnityPy.helpers.TypeTreeHelper');helper.TypeTreeConfig=lambda *a:None;helper.metaflag_is_aligned=lambda v:bool(v&0x4000);helper.read_value=lambda *a:(_ for _ in ()).throw(AssertionError('large array must not use expanding provider reader'))
        streams=types.ModuleType('UnityPy.streams');streams.EndianBinaryReader=Reader
        with tempfile.TemporaryDirectory() as tmp,patch.dict('sys.modules',{'UnityPy.helpers.TypeTreeHelper':helper,'UnityPy.streams':streams}):
            root=Path(tmp).resolve();writer=PayloadWriter(root,'b'*64);typed,blocks=read_streamed(obj,writer,'0');self.assertEqual(b''.join(iter_payload(root,blocks[0])),raw);self.assertEqual(portable(typed,[],max_values=2)['m_FontData']['bytes'],len(raw))
            obj.get_raw_data=lambda:struct.pack('<i',len(raw)+1)+raw
            with self.assertRaisesRegex(ValueError,'object boundary'):read_streamed(obj,PayloadWriter(root/'bad','b'*64),'0')
            field.m_Children[0].m_Children[1].m_Type='UInt16'
            self.assertIsNone(read_streamed(obj,writer,'0'))

    def test_reuse_binds_limits_and_copies_payloads(self):
        from monkey.unity_batch import reuse_inspections
        from monkey.unity_parse_limits import reader_fingerprint
        from monkey.io import write_json
        from monkey.sources.compiled import ParseError
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();source=root/'input.bundle';source.write_bytes(b'frozen bytes');h=sha(source.read_bytes())
            previous=root/'previous';stage=previous/'SourceInspection';stage.mkdir(parents=True);_,body=fixture(stage,source=h)
            limits=parse_limits();body['parseLimits']=limits;write_json(stage/'typed-objects.json',body)
            row=dict(path=str(source),bytes=source.stat().st_size,sha256=h)
            receipt=dict(status='inspected',sourceUnchanged=True,source=dict(sha256=h),typedObjectsSha256=sha((stage/'typed-objects.json').read_bytes()),parseLimits=limits)
            write_json(stage/'inspection.json',receipt)
            write_json(previous/'BatchInspection/job.json',dict(files=[dict(row,inspection=str(stage))],schemaPool=None,parseLimits=limits,readerContractSha256=reader_fingerprint()))
            write_json(previous/'BatchInspection/execution.json',dict(status='inspected',workerSha256=reader_fingerprint(),schemaBundlesRead=0))
            out=root/'reused';out.mkdir()
            with self.assertRaisesRegex(ParseError,'REUSE_LIMITS'):reuse_inspections([row],previous,out,None,dict(containerValues=4000000))
            self.assertEqual(list(out.iterdir()),[])
            reuse_inspections([row],previous,out,None)
            validate_payloads(out/'SourceInspection',body)

    def test_explicit_limits_are_bounded_and_not_time_limits(self):
        self.assertEqual(parse_limits(),dict(objectValues=250000,containerValues=8000000))
        self.assertEqual(parse_limits(dict(containerValues=4000000))['containerValues'],4000000)
        for value in [dict(objectValues=True),dict(containerValues=16000001),dict(objectValues=0),dict(seconds=120)]:
            with self.assertRaises(ValueError):parse_limits(value)
