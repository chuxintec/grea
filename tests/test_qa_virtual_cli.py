import contextlib
import io
import json
import unittest
from unittest.mock import patch
from pathlib import Path
from beaver import cli,qa_runtime,qa_virtual_pointer
from beaver.errors import BeaverError
from beaver.io import write_json
from beaver.output_limits import digest_file
import test_qa_runtime as qa_fixtures

class VirtualQaIntegrationTests(unittest.TestCase):
 def test_batchmode_is_limited_to_a_typed_virtual_config(self):
  fixture=qa_fixtures.QaRuntimePrepareTests();fixture.setUp();self.addCleanup(fixture.tearDown)
  p,_=fixture.make_spec();x=json.loads(p.read_text());x['arguments']=['-batchmode'];write_json(p,x)
  with self.assertRaises(BeaverError) as caught:qa_runtime._load_spec(p,digest_file(p))
  self.assertEqual(caught.exception.code,'QA_ARGUMENTS')
  x['environmentBindings']['BEAVER_VIRTUAL_POINTER_CONFIG']={'kind':'config','id':'private-settings'};write_json(p,x)
  qa_runtime._load_spec(p,digest_file(p))
  x['environmentBindings']['BEAVER_NATIVE_JOB']={'kind':'config','id':'private-settings'};write_json(p,x)
  with self.assertRaises(BeaverError) as caught:qa_runtime._load_spec(p,digest_file(p))
  self.assertEqual(caught.exception.code,'QA_ENV_NAME')
 def test_virtual_operation_never_calls_native_and_keeps_verdicts_separate(self):
  args=['qa','virtual-input','--session','/session','--expected-session','a'*64,'--spec','/spec','--expected-spec','b'*64,'--out','/fresh']
  stream=io.StringIO()
  with patch.object(qa_virtual_pointer,'input_event',return_value={'status':'consumed','receipts':[{'sequence':1,'inputEventsQueued':3}]}),patch('beaver.qa_binding._native',side_effect=AssertionError('native fallback forbidden')),contextlib.redirect_stdout(stream):
   code=cli.main(args)
  result=json.loads(stream.getvalue());self.assertEqual(code,0);self.assertEqual(result['data']['inputMode'],'virtual-pointer');self.assertEqual(result['verification']['native'],'not_run');self.assertEqual(result['verification']['virtualInput'],'application-device-consumed');self.assertEqual(result['verification']['business'],'not_run')
 def test_unsupported_virtual_route_is_not_reported_success(self):
  args=['qa','virtual-input','--session','/session','--expected-session','a'*64,'--spec','/spec','--expected-spec','b'*64,'--out','/fresh']
  stream=io.StringIO()
  with patch.object(qa_virtual_pointer,'input_event',return_value={'status':'not_supported'}),contextlib.redirect_stdout(stream):code=cli.main(args)
  result=json.loads(stream.getvalue());self.assertEqual(code,3);self.assertEqual(result['status'],'blocked');self.assertEqual(result['verification']['virtualInput'],'not_verified')
