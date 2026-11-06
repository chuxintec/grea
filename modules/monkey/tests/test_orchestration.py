import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from fixtures import fixture
from monkey import orchestration
from monkey.cli import main
from monkey.package import convert_package
from monkey.sources.compiled import ParseError
from monkey.sources.containers import fingerprint


class OrchestrationTests(unittest.TestCase):
    def setup_package(self, root):
        source = fixture(root / 'source').parent
        editors = []
        for name in ('Unity', 'CocosCreator'):
            p = root / name
            p.write_text('#!/bin/sh\nexit 99\n')
            p.chmod(0o700)
            editors.append(p)
        settings = orchestration.options(root/'candidate', 'both', None, *editors, 600, [source])
        converted = convert_package(source, 'both', root/'candidate')
        return source, editors, settings, converted

    def test_sequential_stages_have_fresh_independent_deadlines_and_preserve_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            _, _, settings, converted = self.setup_package(root)
            before = [fingerprint(root/'candidate'/p['path']/'manifest.json') for p in converted['projects']]
            clock = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
            calls = []
            def execute(candidate, output, editor, identity, budget, deadline, end, enabled):
                calls.append((candidate.name, identity, budget, deadline, end, enabled))
                clock[0] += timedelta(seconds=15)
                return dict(processExited=True, nativeProgress=dict(status='completed_partial'),
                            verification=dict(editor='partial', diagnostics=0), status='partial')
            with patch.object(orchestration, 'now', side_effect=lambda:clock[0]), patch.object(orchestration, 'native_import', side_effect=execute):
                result = orchestration.run(converted, settings)
            self.assertEqual(result['status'], 'completed_native_stages')
            self.assertEqual([c[0] for c in calls], ['UnityProject', 'CocosProject'])
            self.assertEqual([c[1] for c in calls], before)
            self.assertTrue(all(c[2]==600 and c[5] is True for c in calls))
            self.assertEqual(calls[0][3], '2026-01-01T00:28:00Z')
            self.assertEqual(calls[1][4], '2026-01-01T00:30:15Z')
            self.assertEqual(before, [fingerprint(root/'candidate'/p['path']/'manifest.json') for p in converted['projects']])
            self.assertEqual(result['business'], 'not_run')

    def test_unreleased_child_or_readback_difference_stops_next_editor(self):
        for native_result in [dict(processExited=False, requiresAttention=True),
                              dict(processExited=True, nativeProgress=dict(status='completed'), verification=dict(editor='fail',diagnostics=1))]:
            with self.subTest(result=native_result), tempfile.TemporaryDirectory() as temp:
                _, _, settings, converted = self.setup_package(Path(temp).resolve())
                with patch.object(orchestration, 'native_import', return_value=native_result) as launch:
                    result = orchestration.run(converted, settings)
                self.assertEqual(launch.call_count, 1)
                self.assertEqual(result['status'], 'stopped')
                self.assertEqual(json.loads(Path(result['report']).read_text())['status'], 'stopped')

    def test_manifest_drift_and_output_overlap_fail_before_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source, editors, settings, converted = self.setup_package(root)
            with self.assertRaises(ParseError):
                orchestration.options(root/'other', 'both', source/'bad', *editors, 600, [source])
            (root/'candidate/UnityProject/manifest.json').write_text('{}')
            with patch.object(orchestration,'native_import',side_effect=AssertionError('must not launch')):
                with self.assertRaises(ParseError):orchestration.run(converted,settings)
            self.assertFalse(settings['output'].exists())

    def test_missing_second_target_entrypoint_blocks_first_editor_too(self):
        from monkey.io import load,read,write_json
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();_,_,settings,converted=self.setup_package(root)
            project=root/'candidate/CocosProject';entry='extensions/monkey-import/execution.js';(project/entry).unlink()
            manifest=load(read(project/'manifest.json'));manifest['files']=[r for r in manifest['files']if r['path']!=entry];write_json(project/'manifest.json',manifest)
            converted['projects'][1]['manifestSha256']=fingerprint(project/'manifest.json')
            with patch.object(orchestration,'native_import',side_effect=AssertionError('must not launch')):
                with self.assertRaisesRegex(ParseError,'ENTRYPOINT_MISSING'):orchestration.run(converted,settings)
            self.assertFalse(settings['output'].exists())

    def test_single_cli_invocation_converts_and_then_dispatches_both_editors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source = fixture(root/'source').parent
            editors=[]
            for name in ('Unity','CocosCreator'):
                p=root/name;p.write_text('not executed');editors.append(str(p))
            stream=io.StringIO()
            result=dict(processExited=True,nativeProgress=dict(status='completed'),verification=dict(editor='pass',diagnostics=0))
            with contextlib.redirect_stdout(stream),patch.object(orchestration,'native_import',return_value=result) as launch:
                exit_code=main(['convert','--source',str(source),'--target','both','--out',str(root/'candidate'),
                                '--native','--unity-editor',editors[0],'--creator-editor',editors[1]])
            output=json.loads(stream.getvalue())
            self.assertEqual(launch.call_count,2)
            self.assertEqual(output['nativeExecution']['status'],'completed_native_stages')
            self.assertEqual(exit_code,1)  # Source/business gaps still require work.

    def test_native_flags_are_explicit_and_cannot_be_used_in_offline_mode(self):
        for flags in [['--unity-editor','/unused/Unity'],['--native','--offline']]:
            with self.subTest(flags=flags), contextlib.redirect_stderr(io.StringIO()):
                with patch('monkey.package.convert_package',side_effect=AssertionError('must not convert')):
                    with self.assertRaises(SystemExit) as error:main(['convert',*flags])
                self.assertEqual(error.exception.code,2)
