import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
from monkey.sources.egret_binary import Reader,inflate,resource_manifest,plist_pack,bin_json
from monkey.sources.compiled import ParseError
from monkey.io import sha,load,read


def uint(value):
    out=bytearray()
    while value>127:out.append((value&127)|128);value>>=7
    out.append(value);return bytes(out)


def text(value):
    data=value.encode();return uint(len(data))+data


def manifest(rows):
    # One original prefix; image and bin entries share the table ordering.
    kinds=sorted({r[0]for r in rows});body=b'\x00\x01'+text('assets/')+uint(len(kinds))
    body+=b''.join(uint(k)+uint(sum(r[0]==k for r in rows))for k in kinds)
    for kind in kinds:
        for k,name,url,size in rows:
            if k==kind:body+=text(name)+b'\0'+text(url)+uint(size)
    return zlib.compress(body+b'\0')


def plist():
    # Signed first-byte encoding -3 (0x43), +2 (0x02).
    body=b'\1'+text('trimmed')+b'\1\2\6\4\1\x43\2\x0a\x08'
    return zlib.compress(text('sheet')+uint(len(body))+body)


class EgretBinaryTests(unittest.TestCase):
    def test_source_variable_integer_sign_magnitude_and_exact_budget(self):
        self.assertEqual(Reader(b'\x81\1').number(),129)
        self.assertEqual(Reader(b'\xc1\1').number(True),-65)
        self.assertEqual(Reader(b'\x3f').number(True),63)
        for data in [b'\x80',b'\xff'*9]:
            with self.assertRaises(ParseError):Reader(data).number()

    def test_resource_names_groups_and_prefixes_preserve_missing_keys(self):
        raw=manifest([(0,'sheet_png','page.hash.png',13),(6,'plist_pack_bin','plist.hash.bin',17)])
        d=resource_manifest(raw);self.assertEqual([(r['name'],r['url'])for r in d['resources']],[('sheet_png','assets/page.hash.png'),('plist_pack_bin','assets/plist.hash.bin')]);self.assertFalse(d['sourceExecuted'])
        with self.assertRaisesRegex(ParseError,'SUFFIX'):resource_manifest(zlib.compress(zlib.decompress(raw)+b'\0'))
        with self.assertRaisesRegex(ParseError,'PREFIX'):resource_manifest(zlib.compress(b'\0\0\1\0\1'+text('image')+b'\0'+text('image.png')+b'\0\0'))

    def test_plist_trimmed_geometry_and_record_end_are_explicit(self):
        d=plist_pack(plist());sheet=d['sheets'][0];self.assertEqual(sheet['name'],'sheet_json');self.assertEqual(sheet['textureName'],'sheet_png');f=sheet['frames'][0]
        self.assertEqual(f['rect'],[1,2,6,4]);self.assertEqual(f['trimOrigin'],[-3,2]);self.assertEqual(f['originalSize'],[10,8]);self.assertFalse(f['rotated'])
        raw=zlib.decompress(plist())
        with self.assertRaises(ParseError):plist_pack(zlib.compress(raw[:-1]))

    def test_json_version_string_indices_nested_types_and_signed_zero(self):
        # VERSION=2, strings root/value, object {root: [true, false, null, -0, value]}.
        raw=zlib.compress(b'\0\2\2'+text('root')+text('value')+b'\x15\1\0\x10\5\x18\x19\0\2\0\x0c\1')
        d=bin_json(raw);self.assertEqual(d['value']['root'][:3],[True,False,None]);self.assertEqual(d['value']['root'][4],'value')
        import math
        self.assertEqual(math.copysign(1,d['value']['root'][3]),-1)
        with self.assertRaisesRegex(ParseError,'STRING'):bin_json(zlib.compress(b'\0\2\0\x0c\0'))
        with self.assertRaisesRegex(ParseError,'VERSION'):bin_json(zlib.compress(b'\0\3\0\0'))
        with self.assertRaisesRegex(ParseError,'TAG'):bin_json(zlib.compress(b'\0\2\0\xff'))

    def test_inflate_rejects_suffix_truncation_and_expansion_budget(self):
        for raw in [zlib.compress(b'data')+b'extra',zlib.compress(b'data')[:-1]]:
            with self.assertRaises(ParseError):inflate(raw)
        with patch('monkey.sources.egret_binary.MAX_BYTES',8):
            with self.assertRaisesRegex(ParseError,'BUDGET'):inflate(zlib.compress(b'x'*9))

    def test_logical_path_closure_never_matches_a_basename(self):
        from monkey.egret_recovery import inspect
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();snapshot=root/'input';snapshot.mkdir();data={
                'main/resource/default.res_hash.bin':manifest([(0,'sheet_png','page.hash.png',3),(6,'plist_pack_bin','plist.hash.bin',len(plist()))]),
                'cfg/resource/assets/plist.hash.bin':plist(),'wrong/another/page.hash.png':b'bad'}
            for path,raw in data.items():
                p=snapshot/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
            rows=[dict(path=k,bytes=len(v),sha256=sha(v))for k,v in data.items()]
            with patch('monkey.egret_recovery.source_facts',return_value=dict(profile='fixture',sourceExecuted=False)):
                result=inspect(snapshot,rows,root/'out')
            self.assertEqual(result['summary']['parsedSourceFrames'],1);self.assertEqual(result['summary']['sheetsWithLocalTexture'],0);self.assertEqual(result['sheets'][0]['status'],'missing_texture')
            self.assertEqual(result['summary']['providedResourceDeclarations'],1)

    def test_public_conversion_keeps_decoded_source_data_outside_compilation(self):
        from monkey.resource_package import convert
        from PIL import Image
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();source=root/'source';(source/'resource/assets').mkdir(parents=True)
            (source/'resource/default.res_hash.bin').write_bytes(manifest([(0,'sheet_png','missing.hash.png',12),(6,'plist_pack_bin','plist.hash.bin',len(plist()))]))
            (source/'resource/assets/plist.hash.bin').write_bytes(plist());Image.new('RGBA',(3,2),(17,29,41,255)).save(source/'preview.png')
            with patch('monkey.egret_recovery.source_facts',return_value=dict(profile='fixture',sourceExecuted=False)):
                result=convert(source,'unity6',root/'out',family='egret',source_profile='egret-custom-resource-plist-v1',format_profile='grea')
            self.assertTrue(result['completed']);self.assertEqual(result['sourceData']['parsedSourceFrames'],1);self.assertEqual(result['sourceSpriteFrames'],0)
            project=root/'out/UnityProject';self.assertTrue((project/'Analysis/Evidence/Egret/recovery.json').exists());self.assertEqual(result['format']['status'],'retired')
            self.assertTrue(load(read(project/'Analysis/Tasks/agent-work.json'))['tasks']);self.assertFalse(list((project/'Assets').rglob('*.bin')))

    def test_unknown_source_callbacks_cannot_select_reviewed_profile(self):
        from monkey.egret_recovery import source_facts
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();p=root/'source/game.js';p.parent.mkdir();raw=b'throw Error("not executed")';p.write_bytes(raw)
            with self.assertRaisesRegex(ParseError,'PROFILE_UNVERIFIED'):source_facts(root,[dict(path='source/game.js',bytes=len(raw),sha256=sha(raw))])

    def test_binjson_helper_must_share_the_reader_lexical_scope(self):
        from monkey.egret_recovery import source_facts
        helper='function Be(e,t){return 0}'
        reader='function(e,t){return Be(e,t)}'
        for mutate in [False,True]:
            with self.subTest(mutate=mutate),tempfile.TemporaryDirectory()as temp:
                root=Path(temp).resolve();p=root/'source/game.js';p.parent.mkdir()
                raw=('function outer(){'+helper+';var Ue={};Ue.readFullJson='+reader+';'+('Be=changed;'if mutate else'')+'}').encode();p.write_bytes(raw)
                with patch('monkey.egret_recovery.PINS',{'binJsonVarInt':sha(helper.encode()),'readFullJson':sha(reader.encode())}):
                    if mutate:
                        with self.assertRaisesRegex(ParseError,'SOURCE_PARSE'):source_facts(root,[dict(path='source/game.js',bytes=len(raw),sha256=sha(raw))])
                    else:
                        proof=source_facts(root,[dict(path='source/game.js',bytes=len(raw),sha256=sha(raw))]);self.assertTrue(proof['lexicalVarIntBindings']);self.assertFalse(proof['sourceExecuted'])

    def test_source_top_left_trim_pixels_and_invalid_trim_are_distinct(self):
        from monkey.egret_recovery import materialize_frames
        from PIL import Image
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();(root/'assets').mkdir();atlas=Image.new('RGBA',(8,6))
            for y in range(6):
                for x in range(8):atlas.putpixel((x,y),(x*25,y*35,73,255))
            frame=dict(name='frame',rect=[1,2,3,2],trimOrigin=[2,1],originalSize=[7,5],sourceBytes=dict(start=0,end=12))
            sheet=dict(name='sheet_json',status='provided_texture',localTextures=['input/page.png'],sourceManifest='input/resource/res.bin',sourcePack='input/plist.bin',sourcePackSha256='a'*64,frames=[frame])
            ir=dict(spriteFrames=[],sourceNames={},diagnostics=[]);result=materialize_frames(dict(sheets=[sheet]),[('input/page.png','b'*64,atlas)],root,ir,'fixture')
            self.assertEqual(result['sourceSpriteFrames'],1);f=ir['spriteFrames'][0];self.assertEqual(f['offset'],[0,.5]);self.assertEqual(f['trimOrigin'],[2,1])
            full=Image.open(root/f['originalImage']);self.assertEqual(full.getpixel((2,1)),atlas.getpixel((1,2)));self.assertEqual(full.getpixel((4,2)),atlas.getpixel((3,3)));self.assertEqual(full.getpixel((0,0))[3],0)
            frame['trimOrigin']=[-1,1];ir=dict(spriteFrames=[],sourceNames={},diagnostics=[])
            result=materialize_frames(dict(sheets=[sheet]),[('input/page.png','b'*64,atlas)],root,ir,'bad');self.assertEqual(result['sourceSpriteFrames'],0);self.assertEqual(ir['diagnostics'][0]['code'],'TRIM_BOUNDS')

    def test_cli_remote_cache_closes_exact_declared_page_without_network(self):
        from monkey.cli import main
        from monkey.io import write_json
        from PIL import Image
        from io import BytesIO,StringIO
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();source=root/'source';(source/'resource/assets').mkdir(parents=True)
            image=BytesIO();Image.new('RGBA',(8,8),(17,29,41,255)).save(image,format='PNG');raw=image.getvalue()
            (source/'resource/default.res_hash.bin').write_bytes(manifest([(0,'sheet_png','page.hash.png',len(raw)),(6,'plist_pack_bin','plist.hash.bin',len(plist()))]));(source/'resource/assets/plist.hash.bin').write_bytes(plist())
            cache=root/'cache';(cache/'resource/assets').mkdir(parents=True);(cache/'resource/assets/page.hash.png').write_bytes(raw)
            inputs=root/'inputs.json';write_json(inputs,dict(schemaVersion=1,sourceProfile='egret-custom-resource-plist-v1',inputs=[dict(id='source',path=str(source))]))
            remote=root/'remote.json';write_json(remote,dict(schemaVersion=1,files=[dict(path='resource/assets/page.hash.png',url='https://example.invalid/resource/assets/page.hash.png',sha256=sha(raw),bytes=len(raw))]))
            with patch('monkey.egret_recovery.source_facts',return_value=dict(profile='fixture',sourceExecuted=False)),redirect_stdout(StringIO()):
                exit_code=main(['convert','--input-set',str(inputs),'--target','unity6','--out',str(root/'out'),'--remote-manifest',str(remote),'--remote-cache-root',str(cache),'--format','grea','--offline'])
            self.assertEqual(exit_code,1);result=load(read(root/'out/conversion-result.json'));self.assertEqual(result['acquisition']['localVerifiedFiles'],1);self.assertEqual(result['acquisition']['downloadedFiles'],0)
            self.assertEqual(result['sourceData']['sheetsWithLocalTexture'],1);self.assertTrue((root/'out/UnityProject/Analysis/Ledger/acquisition.json').exists())


class EuiClassRecordTests(unittest.TestCase):
    def test_metadata_and_unclassified_roots_are_not_counted_as_skin_classes(self):
        import copy
        from monkey.egret_recovery import skin_records
        table={'$skins':{'Button':'ButtonSkin'},'$styles':{},'ButtonSkin':{'$sC':'$eSk','$path':'skins/ButtonSkin.exml'},'unknown':[]}
        original=copy.deepcopy(table);classes,metadata,unknown=skin_records(table,'supplied.bin')
        self.assertEqual([r['name']for r in classes],['ButtonSkin']);self.assertEqual(len(metadata),2);self.assertEqual(len(unknown),1)
        self.assertEqual(classes[0]['baseClass'],'$eSk');self.assertEqual(table,original)


if __name__=='__main__':unittest.main()
