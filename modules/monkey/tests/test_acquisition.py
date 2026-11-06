import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

from fixtures import fixture
from monkey import acquisition,orchestration
from monkey.cli import main
from monkey.inputs import input_set
from monkey.io import write_json,sha
from monkey.sources.containers import fingerprint
from monkey.sources.compiled import ParseError
from monkey.targets import cocos,unity


class Response(io.BytesIO):
    status=200


class AcquisitionTests(unittest.TestCase):
    def test_transient_retry_is_bounded_and_404_is_not_retried(self):
        from collections import Counter
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();_,selection=self.setup_source(root);manifest=root/'downloads.json';counts=Counter()
            write_json(manifest,[dict(url='https://cdn.example/'+p,path=p)for p in ['flaky','missing','overloaded']])
            class Opener:
                def open(self,request,timeout):
                    name=request.full_url.rsplit('/',1)[-1];counts[name]+=1
                    if name=='missing' or name=='overloaded' or counts[name]<2:raise HTTPError(request.full_url,404 if name=='missing' else 503,'transient',{},None)
                    return Response(b'original')
            with patch.object(acquisition,'build_opener',return_value=Opener()),patch.object(acquisition.time,'sleep'):
                result=acquisition.acquire(acquisition.prepare(manifest,root/'out',selection))
            self.assertEqual(dict(counts),dict(flaky=2,missing=1,overloaded=3))
            self.assertEqual(result['summary']['availableFiles'],1)
            rows={r['path']:r for r in json.loads(result['receipt'].read_text())['files']}
            self.assertEqual(rows['overloaded']['attempts'],3);self.assertEqual(rows['missing']['httpStatus'],404)

    def test_resume_revalidates_exact_old_payload_and_fetches_only_missing_in_fresh_layer(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();_,selection=self.setup_source(root);manifest=root/'downloads.json'
            write_json(manifest,[dict(url='https://cdn.example/'+p,path=p,sha256=sha(p.encode()))for p in ['one','two']])
            class First:
                def open(self,request,timeout):
                    name=request.full_url.rsplit('/',1)[-1]
                    if name=='two':raise HTTPError(request.full_url,404,'missing',{},None)
                    return Response(name.encode())
            with patch.object(acquisition,'build_opener',return_value=First()):
                initial=acquisition.acquire(acquisition.prepare(manifest,root/'first',selection))
            before=initial['receipt'].read_bytes();requested=[]
            class Next:
                def open(self,request,timeout):requested.append(request.full_url);return Response(b'two')
            with patch.object(acquisition,'build_opener',return_value=Next()):
                result=acquisition.acquire(acquisition.prepare(manifest,root/'second',selection,resume_from=root/'first'))
            self.assertEqual(requested,['https://cdn.example/two']);self.assertEqual(result['summary']['reusedVerifiedFiles'],1)
            self.assertTrue(result['summary']['allDeclaredAvailable']);self.assertEqual(before,initial['receipt'].read_bytes())
            (root/'first/files/one').write_bytes(b'changed')
            with self.assertRaisesRegex(ParseError,'REMOTE_RESUME_CHANGED'):
                acquisition.prepare(manifest,root/'third',selection,resume_from=root/'first')
            self.assertFalse((root/'third').exists())

    def setup_source(self,root):
        source=fixture(root/'source').parent
        path=root/'inputs.json'
        write_json(path,dict(schemaVersion=1,sourceProfile='cocos-2.4.15-bundle',inputs=[dict(id='source',path=str(source))]))
        return source,input_set(path)

    def test_pinned_cache_already_in_inputs_is_read_only_and_not_duplicated(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();source,selection=self.setup_source(root);raw=b'cached original';(source/'cached.bin').write_bytes(raw)
            manifest=root/'downloads.json';write_json(manifest,[dict(url='https://cdn.example/cached.bin?token=private-value',path='cached.bin',sha256=sha(raw),bytes=len(raw))])
            settings=acquisition.prepare(manifest,root/'acquired',selection,source)
            with patch.object(acquisition,'build_opener',side_effect=AssertionError('must reuse local hash')):
                result=acquisition.acquire(settings)
            self.assertEqual(result['inputSet'],selection['path']);self.assertEqual(result['summary']['localVerifiedFiles'],1)
            self.assertFalse(list((root/'acquired/files').rglob('*')))
            self.assertEqual((source/'cached.bin').read_bytes(),raw)
            self.assertNotIn('private-value',result['receipt'].read_text())

    def test_download_missing_and_identity_mismatch_keep_separate_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();_,selection=self.setup_source(root);manifest=root/'downloads.json'
            write_json(manifest,dict(schemaVersion=1,files=[dict(url='https://cdn.example/'+p,path=p,sha256=h) for p,h in [('good.bin',sha(b'good')),('bad.bin',sha(b'expected')),('missing.bin',None)]]))
            class Opener:
                def open(self,request,timeout):
                    name=request.full_url.rsplit('/',1)[-1]
                    if name=='missing.bin':raise HTTPError(request.full_url,404,'missing',{},None)
                    return Response(b'good' if name=='good.bin' else b'wrong')
            with patch.object(acquisition,'build_opener',return_value=Opener()):
                result=acquisition.acquire(acquisition.prepare(manifest,root/'acquired',selection))
            receipt=json.loads(result['receipt'].read_text());statuses={r['path']:r['status'] for r in receipt['files']}
            self.assertEqual(statuses,{'good.bin':'downloaded','bad.bin':'identity_mismatch','missing.bin':'unavailable'})
            self.assertEqual((root/'acquired/files/good.bin').read_bytes(),b'good')
            self.assertFalse((root/'acquired/files/bad.bin').exists())
            self.assertEqual(len(list((root/'acquired/Quarantine').iterdir())),1)
            self.assertEqual(len(input_set(result['inputSet'])['inputs']),2)
            self.assertEqual(receipt['summary']['missingFiles'],2)

    def test_offline_rejects_stale_cache_without_network(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();source,selection=self.setup_source(root);(source/'x.bin').write_bytes(b'stale')
            manifest=root/'downloads.json';write_json(manifest,[dict(url='https://cdn.example/x.bin',path='x.bin',sha256=sha(b'expected'))])
            with patch.object(acquisition,'build_opener',side_effect=AssertionError('offline cannot request')):
                result=acquisition.acquire(acquisition.prepare(manifest,root/'acquired',selection,source),offline=True)
            self.assertEqual(result['summary']['availableFiles'],0);self.assertEqual((source/'x.bin').read_bytes(),b'stale')

    def test_paths_credentials_and_existing_workspaces_are_rejected_before_fetch(self):
        for entries in [[dict(path='../escape',url='https://cdn.example/file')],
                        [dict(path='file',url='https://user:password@cdn.example/file')],
                        [dict(path='A',url='https://cdn.example/a'),dict(path='a',url='https://cdn.example/b')],
                        [dict(path='file',url='https://cdn.example/a'),dict(path='file/child',url='https://cdn.example/b')]]:
            with self.subTest(entries=entries),tempfile.TemporaryDirectory() as temp:
                root=Path(temp).resolve();_,selection=self.setup_source(root);manifest=root/'downloads.json';write_json(manifest,entries)
                with self.assertRaises((ParseError,ValueError)):acquisition.prepare(manifest,root/'acquired',selection)
                self.assertFalse((root/'acquired').exists())

    def test_total_budget_failure_does_not_publish_partial_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();_,selection=self.setup_source(root);manifest=root/'downloads.json';write_json(manifest,[dict(path='x.bin',url='https://cdn.example/x')])
            class Opener:
                def open(self,*args,**kwargs):return Response(b'1234')
            with patch.object(acquisition,'build_opener',return_value=Opener()),patch.object(acquisition,'MAX_TOTAL',3):
                result=acquisition.acquire(acquisition.prepare(manifest,root/'acquired',selection))
            self.assertFalse((root/'acquired/files/x.bin').exists())
            row=json.loads(result['receipt'].read_text())['files'][0];self.assertEqual(row['errorCode'],'REMOTE_TOTAL_BYTE_BUDGET')

    def test_acquired_input_set_preserves_explicit_combined_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();_,selected=self.setup_source(root)
            data=json.loads(selected['path'].read_text());data['limits']=dict(maxInputBytes=2*1024**3)
            selected['path'].write_text(json.dumps(data));selection=input_set(selected['path'])
            manifest=root/'downloads.json';write_json(manifest,[dict(path='new.bin',url='https://cdn.example/new')])
            class Opener:
                def open(self,*args,**kwargs):return Response(b'new original')
            with patch.object(acquisition,'build_opener',return_value=Opener()):
                result=acquisition.acquire(acquisition.prepare(manifest,root/'acquired',selection))
            self.assertEqual(input_set(result['inputSet'])['maxInputBytes'],2*1024**3)

    def test_one_command_acquires_then_freezes_candidate_and_dispatches_native(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();source,selection=self.setup_source(root);raw=b'new remote payload';manifest=root/'downloads.json'
            write_json(manifest,[dict(path='remote/new.bin',url='https://cdn.example/new',sha256=sha(raw),bytes=len(raw))])
            editors=[]
            for name in ('Unity','CocosCreator'):
                p=root/name;p.write_text('never executed');editors.append(str(p))
            class Opener:
                def open(self,*args,**kwargs):return Response(raw)
            seen=[]
            def native(candidate,output,editor,identity,*args):
                self.assertEqual(fingerprint(candidate/'manifest.json'),identity)
                self.assertEqual(json.loads((candidate/'Analysis/Ledger/acquisition.json').read_text())['summary']['downloadedFiles'],1)
                seen.append(candidate)
                return dict(processExited=True,nativeProgress=dict(status='completed'),verification=dict(editor='pass',diagnostics=0))
            stream=io.StringIO()
            original_write_text=Path.write_text
            def portable_write_text(path,data,*args,**kwargs):
                encoding=kwargs.get('encoding',args[0] if args else None)
                if not data.isascii():self.assertEqual(encoding,'utf-8','Unicode output must not depend on the host locale')
                return original_write_text(path,data,*args,**kwargs)
            with contextlib.redirect_stdout(stream),patch.object(Path,'write_text',portable_write_text),patch.object(acquisition,'build_opener',return_value=Opener()),patch.object(orchestration,'native_import',side_effect=native):
                code=main(['convert','--input-set',str(selection['path']),'--remote-manifest',str(manifest),'--target','both','--out',str(root/'candidate'),
                           '--native','--unity-editor',editors[0],'--creator-editor',editors[1]])
            result=json.loads(stream.getvalue());self.assertEqual(code,1);self.assertEqual(len(seen),2)
            self.assertEqual(result['remoteAcquisition']['downloadedFiles'],1)
            self.assertEqual(result['nativeExecution']['status'],'completed_native_stages')
            self.assertEqual(unity.verify(root/'candidate/UnityProject',root/'unity-check')['staticValidation'],'pass')
            self.assertEqual(cocos.verify(root/'candidate/CocosProject',root/'cocos-check')['staticValidation'],'pass')

    def test_attachment_accepts_large_generated_manifest_but_still_checks_owned_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project=root/'candidate/UnityProject';(project/'Analysis').mkdir(parents=True)
            asset=project/'asset.bin';asset.write_bytes(b'owned content')
            manifest=project/'manifest.json'
            write_json(manifest,dict(files=[dict(path='asset.bin',sha256=fingerprint(asset),bytes=asset.stat().st_size,owner='generated')],
                                     diagnostics=[dict(message='x'*(33*1024*1024))]))
            receipt=root/'acquisition.json';write_json(receipt,dict(summary=dict(availableFiles=1)))
            conversion=dict(completed=True,projects=[dict(path='UnityProject',manifestSha256=fingerprint(manifest))])
            write_json(root/'candidate/conversion-result.json',conversion)
            acquired=dict(receipt=receipt,summary=dict(availableFiles=1))
            asset.write_bytes(b'tampered')
            with self.assertRaises(ParseError):acquisition.attach(conversion,root/'candidate',acquired)
            self.assertFalse((project/'Analysis/Ledger/acquisition.json').exists())
            asset.write_bytes(b'owned content')
            acquisition.attach(conversion,root/'candidate',acquired)
            self.assertEqual(conversion['projects'][0]['manifestSha256'],fingerprint(manifest))
            self.assertEqual(json.loads((project/'Analysis/Ledger/acquisition.json').read_text())['summary']['availableFiles'],1)
