import contextlib
import io
import json
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from monkey import acquisition,unity_acquisition
from monkey.cli import main
from monkey.io import write_json,sha
from monkey.sources.compiled import ParseError
from monkey.unity_native import owned
from test_unity_native import fixture


def astc():return bytes.fromhex('13aba15c')+bytes([8,8,1])+bytes([8,0,0,8,0,0,1,0,0])+bytes(16)


class UnityAcquisitionTests(unittest.TestCase):
    def acquire(self,root,entries,offline=True):
        source=root/'source.ab';source.write_bytes(b'UnityFS\0original')
        cache=root/'cache';cache.mkdir()
        rows=[]
        for path,raw in entries:
            p=cache/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
            rows.append(dict(path=path,url='https://cdn.example/'+path,bytes=len(raw),sha256=sha(raw)))
        manifest=root/'remote.json';write_json(manifest,rows)
        settings=unity_acquisition.prepare(source,root/'acquired',manifest,cache,900,[source,root/'out'])
        with patch.object(acquisition,'build_opener',side_effect=AssertionError('offline must not fetch')):
            acquired=acquisition.acquire(settings,offline)
        return acquired

    def test_mixed_remote_inputs_are_classified_and_unknown_code_stays_outside_assets(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();logical='Assets/Textures/astc/8/atlas.hash.txt'
            acquired=self.acquire(root,[(logical,astc()),('Assets/ab/exact.ab',b'UnityFS\0dependency'),('unrecognized.js',b'throw new Error("never execute")')])
            inputs=unity_acquisition.merge(acquired)
            self.assertEqual(len(inputs['dependencies']),1)
            self.assertEqual(json.loads(inputs['texture_cache'].read_text())['files'][0]['logicalPath'],logical)
            receipt=json.loads(acquired['receipt'].read_text());self.assertEqual(receipt['sourceSelectionKind'],'unity-container');self.assertNotIn('sourceInputSetSha256',receipt)
            out=root/'out';out.mkdir();project=fixture(out/'UnityProject')
            conversion=dict(completed=True,projects=[dict(path='UnityProject')],diagnostics=[]);write_json(out/'conversion-result.json',conversion)
            unity_acquisition.attach(conversion,out,acquired)
            self.assertEqual((project/'SourceRecovery/Acquired/unrecognized.js').read_bytes(),b'throw new Error("never execute")')
            self.assertFalse(list((project/'Assets').rglob('*.js')));self.assertEqual(conversion['acquisition']['localVerifiedFiles'],3);owned(project)
            self.assertEqual(conversion['diagnostics'][0]['code'],'UNITY_ACQUIRED_EVIDENCE_ONLY')

    def test_changed_acquired_bytes_leave_owned_candidate_intact(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();acquired=self.acquire(root,[('one.bin',b'one'),('two.bin',b'two')]);unity_acquisition.merge(acquired)
            out=root/'out';out.mkdir();project=fixture(out/'UnityProject');identity=owned(project)[0]
            conversion=dict(completed=True,projects=[dict(path='UnityProject')],diagnostics=[]);write_json(out/'conversion-result.json',conversion)
            (acquired['filesRoot']/'two.bin').write_bytes(b'changed')
            with self.assertRaisesRegex(ParseError,'SOURCE_CHANGED'):unity_acquisition.attach(conversion,out,acquired)
            self.assertEqual(owned(project)[0],identity);self.assertFalse((project/'SourceRecovery/Acquired').exists())

    def test_same_logical_path_with_different_bytes_is_not_overridden(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();logical='Assets/Textures/astc/8/atlas.hash.txt';acquired=self.acquire(root,[(logical,astc())])
            original=root/'original.txt';original.write_bytes(b'different')
            manifest=root/'textures.json';write_json(manifest,dict(schemaVersion=1,files=[dict(logicalPath=logical,path=str(original),bytes=9,sha256=sha(b'different'))]))
            with self.assertRaisesRegex(ParseError,'COLLISION'):unity_acquisition.merge(acquired,manifest)
            self.assertEqual(original.read_bytes(),b'different')

    def test_invalid_remote_texture_is_not_treated_as_a_bundle_or_filled(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();acquired=self.acquire(root,[('Assets/Textures/astc/8/a.txt',b'UnityFS\0not ASTC')])
            with self.assertRaisesRegex(ParseError,'TEXTURE_INVALID'):unity_acquisition.merge(acquired)

    def test_remote_bundle_joins_frozen_pool_and_unreachable_selection_is_deferred_to_exact_resolver(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();acquired=self.acquire(root,[('Assets/ab/exact.ab',b'UnityFS\0remote')])
            original=root/'old.ab';original.write_bytes(b'UnityFS\0old')
            manifest=root/'pool.json';write_json(manifest,dict(schemaVersion=1,files=[dict(path=str(original),bytes=original.stat().st_size,sha256=sha(original.read_bytes()))]))
            inputs=unity_acquisition.merge(acquired,dependency_manifest=manifest)
            rows=json.loads(inputs['dependency_manifest'].read_text())['files'];self.assertEqual(len(rows),2);self.assertEqual(inputs['dependencies'],[])
            self.assertEqual(rows[0]['path'],str(original))

    def test_public_command_materializes_inputs_before_conversion_and_freezes_acquisition(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();source=root/'source.ab';source.write_bytes(b'UnityFS\0source');cache=root/'cache';cache.mkdir();logical='Assets/Textures/astc/8/a.txt';p=cache/logical;p.parent.mkdir(parents=True);p.write_bytes(astc())
            remote=root/'remote.json';write_json(remote,[dict(path=logical,url='https://cdn.example/'+logical,sha256=sha(astc()),bytes=len(astc()))])
            providers=root/'providers';providers.mkdir();provider=providers/'python';provider.write_text('not executed')
            def convert(source,out,*args,**kwargs):
                self.assertTrue(Path(kwargs['texture_cache']).is_file());self.assertEqual(kwargs['dependencies'],[])
                out=Path(out);out.mkdir();fixture(out/'UnityProject')
                result=dict(status='partial',completed=True,resultKind='candidate',sourceFamily='unity',projects=[dict(path='UnityProject')],diagnostics=[],format=dict(profile='none',applied=False))
                write_json(out/'conversion-result.json',result);return result
            stream=io.StringIO()
            with contextlib.redirect_stdout(stream),patch('monkey.recover_unity.convert',side_effect=convert),patch.object(acquisition,'build_opener',side_effect=AssertionError('no GET')):
                status=main(['convert','--source',str(source),'--target','unity6','--out',str(root/'out'),'--provider-python',str(provider),'--asset-ripper',str(provider),
                    '--remote-manifest',str(remote),'--remote-cache-root',str(cache),'--offline'])
            self.assertEqual(status,1);result=json.loads(stream.getvalue());self.assertEqual(result['remoteAcquisition']['localVerifiedFiles'],1)
            owned(root/'out/UnityProject')


if __name__=='__main__':unittest.main()
