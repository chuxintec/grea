import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from grea import cases, registry, runner
from grea.application import dispatch
from grea.common import GreaError
from module_support import with_modules


class ReviewContractTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def test_case_initialization_failure_is_retryable_without_partial_case(self):
        source = self.root/'source';source.write_bytes(b'baseline')
        with patch.object(cases,'write_new',side_effect=OSError('injected')):
            with self.assertRaises(OSError): cases.init_case(self.root,source,'recover')
        self.assertFalse((self.root/'.grea').exists())
        self.assertFalse(list(self.root.glob('.grea-init-*')))
        result = cases.init_case(self.root,source,'recover')
        self.assertTrue((Path(result['case_dir'])/'case.json').is_file())
        with self.assertRaises(GreaError): cases.init_case(self.root,source,'recover')

    def test_system_wrapper_presence_checks_actual_target(self):
        with patch('grea.registry.platform.system',return_value='Darwin'), \
                patch('grea.registry.platform.machine',return_value='arm64'), \
                patch.dict(os.environ,{'GREA_SYSTEM_BIN':str(self.root)}):
            entry = registry.tool('jadx')
            self.assertEqual(registry.presence(entry)['state'],'unavailable')
            exe = self.root/'jadx';exe.write_text('#!/bin/sh\nexit 0\n');exe.chmod(0o755)
            with patch('grea.registry.command',return_value=['/registered/mac-wrapper']),patch('grea.registry.os.access',return_value=True):report=registry.presence(entry)
            self.assertEqual(report['state'],'detected');self.assertEqual(report['executable'],str(exe))

    def test_session_explicit_skill_compatibility(self):
        from grea import __version__
        (self.root/'version.json').write_text(json.dumps({'version':'custom','greaVersion':__version__,'requiredOperations':['session']}))
        self.assertEqual(dispatch('session',{'skill_dir':str(self.root)})['result']['skill']['scope'],'explicit_install')
        (self.root/'version.json').write_text(json.dumps({'greaVersion':'wrong','requiredOperations':['session']}))
        self.assertEqual(dispatch('session',{'skill_dir':str(self.root)})['error']['code'],'SKILL_VERSION_MISMATCH')

    @with_modules

    def test_explicit_cwd_resolves_relative_argv_without_guessing(self):
        (self.root/'a.jsonl').write_text('{"a":1}\n');(self.root/'b.jsonl').write_text('{"a":1}\n')
        result,_,error=runner.execute('compare_traces',['a.jsonl','b.jsonl'],self.root/'run',working_directory=str(self.root))
        self.assertIsNone(error);self.assertEqual(result['working_directory'],str(self.root))
        with self.assertRaises(GreaError): runner.execute('compare_traces',[],self.root/'bad',working_directory='relative')
        self.assertFalse((self.root/'bad').exists())


if __name__=='__main__':unittest.main()
