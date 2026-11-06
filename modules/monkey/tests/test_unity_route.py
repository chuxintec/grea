import contextlib,io,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
from monkey.cli import main
from monkey.providers.assetripper import Form


class UnityRouteTests(unittest.TestCase):
    def test_non_cocos_targets_and_unsupported_native_options_reject_before_output(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();source=root/'game.ab';source.write_bytes(b'UnityFS\0dummy')
            for args in [ ['--target','both'], ['--target','unity6','--provider-python','missing','--asset-ripper','missing','--native'] ]:
                with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit)as e:
                    main(['convert','--source',str(source),'--out',str(root/'out'),*args])
                self.assertEqual(e.exception.code,2);self.assertFalse((root/'out').exists())

    def test_webdata_routes_to_unity_without_executing_container(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();source=root/'game.data';source.write_bytes(b'UnityWebData1.0\0explicit')
            result=dict(status='partial',completed=False,resultKind='candidate',projects=[],diagnostics=[],format=dict(profile='none',applied=False))
            with patch('monkey.recover_unity.convert',return_value=result) as convert,contextlib.redirect_stdout(io.StringIO()):
                main(['convert','--source',str(source),'--target','unity6','--out',str(root/'out'),'--provider-python','provider','--asset-ripper','ripper'])
            convert.assert_called_once()
            self.assertFalse((root/'out').exists())

    def test_public_unity_grea_alias_no_longer_requires_native_and_routes_unchanged(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();source=root/'game.ab';source.write_bytes(b'UnityFS\0dummy')
            providers=root/'providers';providers.mkdir();provider=providers/'provider';provider.write_text('provider')
            editor=root/'Unity';editor.write_text('not executed')
            result=dict(status='partial',completed=False,resultKind='candidate',projects=[],diagnostics=[],format=dict(profile='none',applied=False))
            argv=['convert','--source',str(source),'--target','unity6','--out',str(root/'out'),'--provider-python',str(provider),'--asset-ripper',str(provider),'--format','grea']
            # --format grea is a deprecated alias: conversion already writes monkey-project/1, so no --native is required.
            with patch('monkey.recover_unity.convert',return_value=result) as converted,contextlib.redirect_stdout(io.StringIO()):main(argv)
            self.assertTrue(converted.called)
            with patch('monkey.recover_unity.convert',return_value=result),patch('monkey.unity_native.finish_conversion',return_value=result)as finish,contextlib.redirect_stdout(io.StringIO()):
                status=main([*argv,'--native','--unity-editor',str(editor)])
            self.assertEqual(status,1);self.assertEqual(finish.call_args.args[2],'grea')

    def test_cli_passes_explicit_parse_limits(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();source=root/'source';source.write_bytes(b'UnityFS\0test')
            result=dict(status='partial',completed=True,resultKind='candidate',sourceFamily='unity',projects=[],diagnostics=[],format={})
            argv=['convert','--source',str(source),'--target','unity6','--provider-python','/known/python','--asset-ripper','/known/provider','--out',str(root/'out'),
                  '--unity-object-value-limit','100000','--unity-container-value-limit','6000000']
            with patch('monkey.recover_unity.convert',return_value=result) as converted,contextlib.redirect_stdout(io.StringIO()):main(argv)
            self.assertEqual(converted.call_args.kwargs['parse_limits'],dict(objectValues=100000,containerValues=6000000))

    def test_similar_or_truncated_signatures_do_not_classify(self):
        from monkey.sources.unity_serialized import container_kind
        for header in (b'UnityWebData1.0',b'UnityWebData1.1\0',b'UnityWebData',b'prefixUnityFS\0'):
            self.assertIsNone(container_kind(header))

    def test_invalid_etc1_blocks_before_provider_without_explicit_quarantine(self):
        from monkey.recover_unity import convert
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();source=root/'source.data';source.write_bytes(b'UnityWebData1.0\0test')
            providers=root/'providers';providers.mkdir();provider=providers/'provider';provider.write_bytes(b'not executable')
            inspection=dict(status='partial',sourceUnchanged=True,processExited=True,summary={'unparsed':1,'invalidInlineTextures':2})
            with patch('monkey.recover_unity.inspect_unity',return_value=inspection),patch('monkey.recover_unity.export_unity') as export:
                result=convert(source,root/'out',provider,provider)
            export.assert_not_called();self.assertFalse(result['completed'])
            self.assertEqual(result['status'],'blocked')
            self.assertEqual(result['diagnostics'][0]['disposition'],'blocked')
            self.assertFalse((root/'out/ProviderExport').exists())

    def test_evidence_only_provider_does_not_promote_empty_unity_candidate(self):
        from monkey.recover_unity import convert
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();source=root/'source.ab';source.write_bytes(b'UnityFS\0test')
            providers=root/'providers';providers.mkdir();provider=providers/'provider';provider.write_bytes(b'not executable')
            inspection=dict(status='partial',sourceUnchanged=True,processExited=True,summary={'unparsed':2})
            result=dict(status='exported_evidence_only',nativeAssetFiles=0,unreadableObjectFiles=3,sourceUnchanged=True,processExited=True)
            with patch('monkey.recover_unity.inspect_unity',return_value=inspection),patch('monkey.recover_unity.code_model',return_value={}),patch('monkey.recover_unity.export_unity',return_value=result):
                report=convert(source,root/'out',provider,provider)
            self.assertFalse(report['completed']);self.assertEqual(report['projects'],[])
            self.assertEqual(report['diagnostics'][0]['code'],'UNITY_PROVIDER_EVIDENCE_ONLY')
            self.assertFalse((root/'out/UnityProject').exists())

    def test_public_settings_form_distinguishes_disabled_and_disk_save_flags(self):
        p=Form();p.feed('<input name="TargetVersion" value="6000.6.2f1"><input type="checkbox" name="Premium" checked disabled><input type="checkbox" name="SaveSettingsToDisk"><select name="ScriptContentLevel"><option value="Level2">x</option><option value="Level0" selected>y</option></select>')
        self.assertEqual(p.values,{'TargetVersion':'6000.6.2f1','ScriptContentLevel':'Level0'})


if __name__=='__main__':unittest.main()
