import contextlib
import io
import json
import os
import shutil
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from PIL import Image
from monkey.cli import main
from monkey.io import read,load,sha
from monkey.sources.containers import entries
from monkey.inputs import input_set
from unittest.mock import patch
from monkey.sources.compiled import ParseError
from monkey.package import convert_package
from monkey.sources.code import modules


SCRIPT = b'''window.__require=(function(r,m,e){})({Wallet:[function(require,module,exports){
cc._RF.push(module,"00000000-0000-0000-0000-000000000010","Wallet");
exports.spend=function(amount){throw new Error("not connected");};
events.on("changed", function(){}); cc.resources.load("coin/icon");
cc._RF.pop();
},{"./Data":"Data"}]},{},[]);'''


def files():
    stream=io.BytesIO();Image.new('RGBA',(3,4),(80,120,10,255)).save(stream,format='PNG')
    image=stream.getvalue()
    config=dict(name='main',engineVersion='2.4.15',uuids=['00000000-0000-0000-0000-000000000002'],
                paths={'0':['coin/icon',0]},types=['cc.Texture2D'],packs={})
    return {'assets/config.json':json.dumps(config).encode(),'assets/game.js':SCRIPT,
            'assets/native/00/00000000-0000-0000-0000-000000000002.a.png':image,
            'assets/duplicate.png':image,'assets/unknown.bin':b'unknown\x00data'}


def wxpackage(items):
    index_size=4+sum(4+len(name.encode())+8 for name in items)
    offset=14+index_size;index=struct.pack('>I',len(items));payload=b''
    for name,data in items.items():
        encoded=name.encode();index+=struct.pack('>I',len(encoded))+encoded+struct.pack('>II',offset,len(data))
        offset+=len(data);payload+=data
    return b'\xbe'+b'\x00'*4+struct.pack('>II',index_size,len(payload))+b'\xed'+index+payload


class PackageTests(unittest.TestCase):
    def test_raw_homophone_evidence_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();source=root/'source';source.mkdir()
            (source/'工.bin').write_bytes(b'first');(source/'公.bin').write_bytes(b'second')
            (source/'project.json').write_text(json.dumps(dict(id='test',version='2.4.15')))
            convert_package(source,'unity',root/'out',offline=True)
            project=root/'out/UnityProject'
            ledger=[r for r in load(read(project/'Analysis/Ledger/resource-ledger.json'))['files'] if r['path'].endswith('.bin')]
            self.assertEqual(len({r['target'].casefold() for r in ledger}),2)
            for row in ledger:
                self.assertEqual(sha((project/row['target']).read_bytes()),row['sha256'])

    def test_explicit_combined_budget_keeps_default_and_single_file_guards(self):
        from monkey.sources import containers
        with patch.object(containers,'MAX_TOTAL',5):
            default=containers.Names();default.add('first',3)
            with self.assertRaisesRegex(ParseError,'ARCHIVE_BUDGET'):default.add('second',3)
            expanded=containers.Names(8);expanded.add('first',3);expanded.add('second',3)
            with self.assertRaisesRegex(ParseError,'ARCHIVE_BUDGET'):expanded.add('third',3)
            with patch.object(containers,'MAX_FILE',2):
                with self.assertRaisesRegex(ParseError,'ARCHIVE_BUDGET'):containers.Names(8).add('large',3)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();source=root/'source';source.mkdir();path=root/'inputs.json'
            data=dict(schemaVersion=1,sourceProfile='cocos-2.1.2-resource',inputs=[dict(id='source',path=str(source))])
            for limits in (dict(maxInputBytes=True),dict(maxInputBytes=0),dict(maxInputBytes=8*1024**3+1),dict(maxInputBytes='2147483648'),dict(other=1)):
                path.write_text(json.dumps(dict(data,limits=limits)))
                with self.assertRaisesRegex(ParseError,'INPUT_SET_LIMITS'):input_set(path)
            path.write_text(json.dumps(dict(data,limits=dict(maxInputBytes=2*1024**3))))
            self.assertEqual(input_set(path)['maxInputBytes'],2*1024**3)

    def test_editable_project_default_accounts_unknown_code_and_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();source=root/'project';source.mkdir()
            (source/'project.json').write_text(json.dumps(dict(id='test',version='2.4.15')))
            (source/'View.ts').write_text('export class View {}')
            stdout=io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result=main(['convert','--source',str(source),'--target','cocos','--out',str(root/'out')])
            self.assertEqual(result,1)
            ledger=load(read(root/'out/CocosProject/Analysis/Ledger/resource-ledger.json'))
            self.assertEqual(ledger['coverage']['inputFiles'],2)
            code=load(read(root/'out/CocosProject/Analysis/Code/code-index.json'))['modules'][0]
            self.assertEqual(code['reason']['code'],'SOURCE_CODE_FORMAT_PENDING')
            self.assertTrue((root/'out/CocosProject'/code['sourceEvidence']).exists())

    def test_rf_regions_are_candidates_with_preserved_unmatched_evidence(self):
        raw=b'''define("a",function(require,module,exports){
          cc._RF.push(module,"first","\xe6\xa8\xa1\xe5\x9d\x97");exports.value=1;cc._RF.pop();
          cc._RF.push(module,"second","Unclosed");exports.missing=2;
        });'''
        found,error=modules(raw)
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]['confidence'],'rf_region_syntax_candidate')
        self.assertEqual(found[0]['name'],'模块')
        self.assertEqual(error['code'],'MODULE_RECOVERY_PARTIAL')
        self.assertEqual(error['issues'][0]['code'],'UNMATCHED_RF_PUSH')
        bounds=found[0]['source_bytes']
        self.assertEqual(sha(raw[bounds['start']:bounds['end']]),found[0]['sha256'])

    def test_wxapkg_both_targets_complete_accounting_and_ast_drafts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();source=root/'game.wxapkg';source.write_bytes(wxpackage(files()))
            before=source.read_bytes();stdout=io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code=main(['convert','--source',str(source),'--target','both','--out',str(root/'out')])
            summary=json.loads(stdout.getvalue());self.assertEqual(code,1)
            self.assertEqual(summary['status'],'needs_action');self.assertEqual(summary['inputFiles'],5)
            for project in (root/'out/UnityProject',root/'out/CocosProject'):
                ledger=load(read(project/'Analysis/Ledger/resource-ledger.json'))
                self.assertEqual(ledger['coverage']['inputBytes'],ledger['coverage']['accountedBytes'])
                self.assertEqual(ledger['coverage']['accountedFiles'],5)
                self.assertEqual(ledger['coverage']['dispositions']['deduplicated'],1)
                for row in ledger['files']:
                    self.assertEqual(sha(read(project/row['target'])),row['sha256'])
                asset=load(read(project/'Analysis/Mappings/cocos-assets.json'))['assets'][0]
                self.assertEqual(asset['logicalKey'][0],'coin/icon');self.assertTrue(asset['targets'][0]['id'])
                mod=load(read(project/'Analysis/Code/code-index.json'))['modules'][0]
                self.assertEqual(mod['name'],'Wallet');self.assertIn('spend',mod['syntax']['exports'])
                self.assertIn('changed',mod['syntax']['events']);self.assertIn('coin/icon',mod['syntax']['dynamicKeys'])
                self.assertFalse(mod['compiled']);self.assertFalse(mod['behavior_verified'])
                self.assertTrue((project/mod['draft']).is_file());self.assertTrue((project/'AGENTS.md').is_file())
                self.assertNotIn(str(root),read(project/'Docs/START-HERE.md').decode())
                # All source JS and drafts stay outside engine script compilation roots.
                compiled_root=project/('Assets' if project.name=='UnityProject' else 'assets')
                self.assertFalse(list(compiled_root.rglob('*.js')))
                for script in [*compiled_root.rglob('*.cs'),*compiled_root.rglob('*.ts')]:
                    self.assertNotIn('SourceRecovery',script.parts)
                    self.assertNotIn('Wallet',script.name)
                moved=root/('standalone-'+project.name)
                shutil.copytree(project,moved)
                for row in load(read(moved/'manifest.json'))['files']:
                    self.assertEqual(sha(read(moved/row['path'])),row['sha256'])
                self.assertTrue((moved/'Docs/PROJECT-STRUCTURE.md').exists())
                dynamic=load(read(moved/'Analysis/Mappings/dynamic-keys.json'))['keys'][0]
                self.assertEqual(dynamic['status'],'source_files_mapped')
                self.assertEqual(dynamic['runtimeBinding'],'not_verified')
            self.assertEqual(before,source.read_bytes())

    def test_apk_read_only_unknown_retained_and_non_cocos_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();source=root/'game.apk'
            with zipfile.ZipFile(source,'w') as z:
                for name,data in files().items(): z.writestr(name,data)
                z.writestr('classes.dex',b'dex\n035\x00')
            result=convert_package(source,'unity6',root/'out')
            self.assertEqual(result['projects'][0]['coverage']['dispositions']['filtered'],1)
            bad=root/'other.apk'
            with zipfile.ZipFile(bad,'w') as z: z.writestr('classes.dex',b'dex\n035\x00')
            with self.assertRaises(ParseError): convert_package(bad,'cocos38',root/'bad')
            receipt=load(read(root/'bad/conversion-result.json'))
            self.assertEqual(receipt['error']['code'],'NON_COCOS_INPUT')

    def test_archive_traversal_alias_collision_overlap_and_zip_link_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve()
            for i,items in enumerate(({'../escape':b'x'},{'//escape':b'x'},{'A':b'x','a':b'y'},{'a':b'x','a/b':b'y'})):
                source=root/f'{i}.wxapkg';source.write_bytes(wxpackage(items))
                with self.assertRaises(ParseError): list(entries(source))
            source=root/'overlap.wxapkg';blob=bytearray(wxpackage({'a':b'x','b':b'y'}))
            # Second entry's offset points to first entry's byte.
            offset_at=18+(4+1+8)+4+1;first_offset=struct.unpack_from('>I',blob,23)[0]
            struct.pack_into('>I',blob,offset_at,first_offset);source.write_bytes(blob)
            with self.assertRaises(ParseError): list(entries(source))
            source=root/'link.apk'
            with zipfile.ZipFile(source,'w') as z:
                row=zipfile.ZipInfo('link');row.create_system=3;row.external_attr=(0o120777<<16);z.writestr(row,'/tmp/target')
            with self.assertRaises(ParseError): list(entries(source))
            self.assertFalse((root.parent/'escape').exists())

    def test_directory_symlinks_and_conflicting_bundle_identity_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();source=root/'input';source.mkdir()
            for name,data in files().items():
                p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            (source/'link').symlink_to(source/'assets/game.js')
            with self.assertRaises(ParseError): convert_package(source,'both',root/'links')
            (source/'link').unlink()
            conflict=json.loads(files()['assets/config.json']);conflict['engineVersion']='3.8.8'
            (source/'other.json').write_text(json.dumps(conflict))
            with self.assertRaises(ParseError): convert_package(source,'unity',root/'conflict')


if __name__=='__main__':unittest.main()
