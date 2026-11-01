import shutil
import struct
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

from beaver.managed_metadata import inspect_managed


def _align4(value): return (value + 3) & ~3


def managed_dll(name="Fixture.One", namespace="Demo", type_name="Widget", nested_type_name=None, type_visibility=1,
                mvid="12345678-1234-5678-90ab-cdef12345678", truncate_guid_heap=False,
                mvid_index=1,module_count=1) -> bytes:
    """Build a small, valid PE/CLI image containing real ECMA metadata tables."""
    strings=bytearray(b"\0")
    def add_string(value):
        idx=len(strings);strings.extend(value.encode("utf-8")+b"\0");return idx
    mod_idx=add_string("Fixture.dll");type_idx=add_string(type_name);ns_idx=add_string(namespace);asm_idx=add_string(name)
    nested_idx=add_string(nested_type_name) if nested_type_name else None
    blob=b"\0"
    # #~: Module(0), TypeDef(2), Assembly(32), one row each.
    type_count=2 if nested_type_name else 1
    valid=(1<<0)|(1<<2)|(1<<32)|((1<<41) if nested_type_name else 0)
    tables=struct.pack("<IBBBBQQ",0,2,0,0,1,valid,0)
    tables+=struct.pack("<III",module_count,type_count,1)
    if nested_type_name: tables+=struct.pack("<I",1)
    for _ in range(module_count): tables+=struct.pack("<HHHHH",0,mod_idx,mvid_index,0,0)
    # TypeDef row: flags, name, namespace, Extends(TypeDefOrRef), FieldList, MethodList.
    tables+=struct.pack("<IHHHHH",type_visibility,type_idx,ns_idx,0,1,1)
    if nested_type_name: tables+=struct.pack("<IHHHHH",2,nested_idx,0,0,1,1)
    # Assembly row: hash algorithm, version, flags, public key, name, culture.
    tables+=struct.pack("<IHHHHIHHH",0x8004,1,0,0,0,0,0,asm_idx,0)
    if nested_type_name: tables+=struct.pack("<HH",2,1)

    version=b"v4.0.30319\0"
    fixed=struct.pack("<IHHII",0x424A5342,1,1,0,len(version))+version
    fixed+=b"\0"*(_align4(len(fixed))-len(fixed))+struct.pack("<HH",0,4)
    names=[b"#~\0",b"#Strings\0",b"#Blob\0",b"#GUID\0"]
    headers_size=sum(8+_align4(len(n)) for n in names)
    data_start=_align4(len(fixed)+headers_size)
    guid=uuid.UUID(mvid).bytes_le
    if truncate_guid_heap: guid=guid[:15]
    contents=[bytes(tables),bytes(strings),blob,guid]
    offsets=[];cursor=data_start
    for content in contents: offsets.append(cursor);cursor+=len(content)
    headers=b"".join(struct.pack("<II",off,len(content))+name+b"\0"*(_align4(len(name))-len(name)) for off,content,name in zip(offsets,contents,names))
    metadata=fixed+headers+b"\0"*(data_start-len(fixed)-len(headers))+b"".join(contents)

    # Minimal PE32 with one section containing an IMAGE_COR20_HEADER and metadata root.
    image=bytearray(0x1200);image[:2]=b"MZ";struct.pack_into("<I",image,0x3c,0x80)
    pe=0x80;image[pe:pe+4]=b"PE\0\0";coff=pe+4
    struct.pack_into("<HHIIIHH",image,coff,0x14c,1,0,0,0,224,0x210e)
    opt=coff+20;struct.pack_into("<H",image,opt,0x10b)
    struct.pack_into("<I",image,opt+32,0x2000);struct.pack_into("<I",image,opt+36,0x200)
    struct.pack_into("<I",image,opt+56,0x4000);struct.pack_into("<I",image,opt+60,0x200)
    struct.pack_into("<I",image,opt+92,16)
    dirs=opt+96;struct.pack_into("<II",image,dirs+14*8,0x2000,72)
    sec=opt+224;image[sec:sec+5]=b".text";struct.pack_into("<IIII",image,sec+8,0x1000,0x2000,0x1000,0x200)
    struct.pack_into("<I",image,0x200,72);struct.pack_into("<HH",image,0x204,2,5)
    struct.pack_into("<II",image,0x208,0x2100,len(metadata));image[0x300:0x300+len(metadata)]=metadata
    return bytes(image)


class ManagedMetadataTests(unittest.TestCase):
    def test_assembly_identity_comes_from_metadata_not_renamed_filename(self):
        with tempfile.TemporaryDirectory() as temp:
            renamed=Path(temp)/"unrelated-name.dll"
            renamed.write_bytes(managed_dll(name="Identity.From.Metadata",namespace="Demo",type_name="Widget"))
            result=inspect_managed(renamed.read_bytes())
        self.assertEqual(result["name"],"Identity.From.Metadata")
        self.assertEqual(result["version"],[1,0,0,0])
        self.assertEqual(result["types"],["Demo.Widget"])
        self.assertEqual(result["publicTypes"],["Demo.Widget"])
        self.assertEqual(result["moduleVersionId"],"12345678-1234-5678-90ab-cdef12345678")
        self.assertIsNone(result["publicKeySha256"])

    def test_distinct_assembly_names_can_report_overlapping_type(self):
        one=inspect_managed(managed_dll("Library.One","Shared","Duplicate"))
        two=inspect_managed(managed_dll("Library.Two","Shared","Duplicate"))
        self.assertNotEqual(one["name"],two["name"])
        self.assertEqual(set(one["types"]) & set(two["types"]),{"Shared.Duplicate"})
        internal=inspect_managed(managed_dll("Library.Internal","Shared","Duplicate",type_visibility=0))
        self.assertEqual(internal["types"],["Shared.Duplicate"])
        self.assertEqual(internal["publicTypes"],[])
        self.assertEqual(set(one["publicTypes"]) & set(internal["publicTypes"]),set())

    def test_nested_typedef_uses_enclosing_type_name(self):
        result=inspect_managed(managed_dll("Nested",nested_type_name="Inner"))
        self.assertEqual(result["types"],["Demo.Widget","Demo.Widget+Inner"])
        self.assertEqual(result["publicTypes"],["Demo.Widget","Demo.Widget+Inner"])

    def test_rejects_native_truncated_and_over_budget_inputs(self):
        with self.assertRaises(ValueError): inspect_managed(b"MZ"+b"\0"*126)
        valid=managed_dll()
        with self.assertRaises(ValueError): inspect_managed(valid[:-40])
        with self.assertRaises(ValueError): inspect_managed(b"\0"*(64*1024*1024+1))

    def test_rejects_truncated_guid_heap(self):
        with self.assertRaises(ValueError): inspect_managed(managed_dll(truncate_guid_heap=True))
        with self.assertRaises(ValueError): inspect_managed(managed_dll(mvid_index=0))
        with self.assertRaises(ValueError): inspect_managed(managed_dll(mvid_index=2))
        with self.assertRaises(ValueError): inspect_managed(managed_dll(module_count=2))

    @unittest.skipUnless(shutil.which("dotnet"),"dotnet SDK unavailable; pure PE fixture tests still cover metadata parsing")
    def test_real_compiled_managed_dll_renamed_identity_and_overlapping_types(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            root=Path(temp)
            nuget=root/"NuGet.Config"
            nuget.write_text('<configuration><packageSources><clear /></packageSources></configuration>',encoding="utf-8")
            for assembly in ("Compiler.One","Compiler.Two"):
                proj=root/assembly;proj.mkdir()
                (proj/(assembly+".csproj")).write_text(f'<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework><AssemblyName>{assembly}</AssemblyName><Version>2.3.4.5</Version></PropertyGroup></Project>',encoding="utf-8")
                visibility="public" if assembly=="Compiler.One" else "internal"
                (proj/"Class1.cs").write_text(f"namespace Same.Namespace; {visibility} class SharedType {{}}",encoding="utf-8")
                subprocess.run(["dotnet","build",str(proj/(assembly+".csproj")),"--configfile",str(nuget),"--nologo","--verbosity","quiet"],check=True,capture_output=True,text=True,timeout=120)
            dll=root/"Compiler.One/bin/Debug/net8.0/Compiler.One.dll"
            renamed=root/"renamed.bin";renamed.write_bytes(dll.read_bytes())
            a=inspect_managed(renamed.read_bytes())
            original=inspect_managed(dll.read_bytes())
            b=inspect_managed((root/"Compiler.Two/bin/Debug/net8.0/Compiler.Two.dll").read_bytes())
            self.assertEqual((a["name"],a["version"]),("Compiler.One",[2,3,4,5]))
            self.assertEqual(a["moduleVersionId"],original["moduleVersionId"])
            self.assertNotEqual(a["moduleVersionId"],b["moduleVersionId"])
        self.assertIn("Same.Namespace.SharedType",a["types"])
        self.assertEqual(set(a["types"]) & set(b["types"]),{"Same.Namespace.SharedType"})
        self.assertIn("Same.Namespace.SharedType",a["publicTypes"])
        self.assertNotIn("Same.Namespace.SharedType",b["publicTypes"])


if __name__=="__main__": unittest.main()
