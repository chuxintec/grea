import hashlib,json,tempfile,unittest
from pathlib import Path
from grea.tools.research_report import normalize,report
class Research(unittest.TestCase):
 def test_count_direction_stage_unknown_and_source_integrity(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);f=p/'source.txt';f.write_text('owned example')
   v=dict(schema_version=1,game='Example',sources=[dict(id='s',path='source.txt',sha256=hashlib.sha256(f.read_bytes()).hexdigest())],items=[dict(id='p',kind='prefab',stage='parsed',source_id='s')]*2,protocols=[dict(name='Start',direction=d,kind=k,source_id='s') for d,k in [('client_to_server','rpc'),('client_to_server','rpc'),('server_to_client','rpc'),('client_to_server','field')]])
   i=p/'input.json';i.write_text(json.dumps(v));r=normalize(i)
   self.assertEqual(r['metrics']['prefab']['parsed'],1);self.assertIsNone(r['metrics']['prefab']['runtime']);self.assertIsNone(r['metrics']['level']['unique_observed']);self.assertEqual(r['protocols']['client_to_server']['rpc'],1);self.assertEqual(r['protocols']['server_to_client']['rpc'],1)
   report(i,p/'new');self.assertTrue((p/'new/report.md').is_file())
   with self.assertRaises(ValueError):report(i,p/'new')
   f.write_text('changed')
   with self.assertRaises(ValueError):normalize(i)
